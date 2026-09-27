"""Offline query_logs reports for content gaps, FAQ ranking, and score distributions.

Every chat request writes one ``query_logs`` row (see ``sourcebook.api.analytics``).
This module is the read side of that loop: a bounded, read-only MongoDB aggregation
over a caller-supplied time window. It does not change logging, grounding, or
``SIMILARITY_THRESHOLD``.

Run from the repository root on the EC2 host, where ``.env`` holds
``MONGODB_URI`` and the cluster's IP access list admits the host. Anywhere
else waits out ``--timeout`` and fails. ``--until`` defaults to now:

    python -m sourcebook.rag.query_log_reports --since 2026-08-01

``query_logs`` rows expire after ``QUERY_LOG_TTL_SECONDS`` (90 days), so a
window that ends earlier than that prints an empty report, not an error.

Reports:

1. Top refused ``question_hash`` groups (content-gap ranking)
2. ``question_hash`` groups asked in at least ``--min-repeat`` conversations
   (FAQ candidates)
3. Answered vs refused ``best_score`` counts and fixed histogram bins

``question_hash`` is the grouping key, so rows group by exact wording after
normalization: a rephrased question is its own row. Each group also counts the
distinct ``session_id`` values it was asked in. One employee asking the same
thing five times is five asks but one conversation, and only the second says
how many people share the question. A conversation is not a person, but it is
the closest the log gets. Rows logged without a session count as one. Sample text is taken from already-logged
truncated ``question_raw`` / ``question_condensed`` fields when present; nothing
new is retained or fabricated.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from itertools import pairwise
from typing import Any

from dotenv import load_dotenv
from pymongo.errors import PyMongoError

from sourcebook.rag.mongo import get_client, get_collection

# Operator-facing caps. Aggregation pipelines always $match the time window first,
# then $group / $sort / $limit so the client never loads the full collection.
DEFAULT_TOP = 20
MAX_TOP = 100
DEFAULT_MIN_REPEAT = 2
# pymongo waits 30 s for server selection by default. That is right for the
# API, which fails at startup, but this is the first interactive consumer and a
# wrong URI should fail fast enough to read as a config error.
DEFAULT_TIMEOUT_SECONDS = 10
# Cosine-style scores land in [0, 1]. Mongo ``$bucket`` upper bounds are exclusive,
# so the final edge is slightly above 1.0 so a perfect 1.0 still lands in [0.9, 1.0].
SCORE_BOUNDARIES = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0001]
QUERY_LOGS_COLLECTION = "query_logs"


class ReportInputError(ValueError):
    """Raised when CLI arguments are invalid before any database access."""


def parse_report_instant(value: str) -> datetime:
    """Parse an ISO-8601 date or datetime into an aware UTC ``datetime``.

    Accepts ``YYYY-MM-DD`` (midnight UTC) or a full ISO timestamp. A trailing
    ``Z`` is treated as UTC. Naive datetimes are assumed to be UTC.
    """
    text = value.strip()
    if not text:
        raise ReportInputError("Empty timestamp")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        if len(text) == 10 and text[4] == "-" and text[7] == "-":
            parsed = datetime.strptime(text, "%Y-%m-%d").replace(tzinfo=UTC)
        else:
            parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ReportInputError(
            f"Invalid timestamp {value!r}; use YYYY-MM-DD or ISO-8601 datetime"
        ) from exc
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def validate_window(since: datetime, until: datetime) -> None:
    """Reject inverted or zero-width time windows."""
    if until <= since:
        raise ReportInputError("--until must be strictly after --since")


def validate_top(top: int) -> None:
    """Bound the number of ranked hash groups returned to the operator."""
    if top < 1 or top > MAX_TOP:
        raise ReportInputError(f"--top must be between 1 and {MAX_TOP}")


def validate_min_repeat(min_repeat: int) -> None:
    """FAQ ranking only includes hashes asked in at least this many conversations."""
    if min_repeat < 2:
        raise ReportInputError("--min-repeat must be at least 2")


def validate_timeout(timeout: int) -> None:
    """Server selection needs a positive wait."""
    if timeout < 1:
        raise ReportInputError("--timeout must be at least 1 second")


def _time_match(since: datetime, until: datetime) -> dict[str, Any]:
    """Match documents whose ``created_at`` falls in ``[since, until)``."""
    return {"created_at": {"$gte": since, "$lt": until}}


def _group_fields() -> dict[str, Any]:
    """Accumulators both rankings share: asks, conversations, sample text."""
    return {
        "count": {"$sum": 1},
        "sessions": {"$addToSet": "$session_id"},
        **_sample_fields(),
    }


# Replace the session list with its size; the ids themselves never leave the
# pipeline.
_SESSION_COUNT_STAGES: list[dict[str, Any]] = [
    {"$addFields": {"session_count": {"$size": "$sessions"}}},
    {"$project": {"sessions": 0}},
]


def _sample_fields() -> dict[str, Any]:
    """Project already-truncated sample text fields into group accumulators."""
    return {
        "sample_raw": {"$first": "$question_raw"},
        "sample_condensed": {"$first": "$question_condensed"},
    }


def content_gap_pipeline(since: datetime, until: datetime, top: int) -> list[dict[str, Any]]:
    """Aggregation: refused hashes ranked by count within the time window."""
    return [
        {"$match": {**_time_match(since, until), "refused": True}},
        {"$group": {"_id": "$question_hash", **_group_fields()}},
        *_SESSION_COUNT_STAGES,
        # Sorted on asks, not conversations: every refusal is a gap, even
        # when one person hit it repeatedly.
        {"$sort": {"count": -1, "_id": 1}},
        {"$limit": top},
    ]


def faq_pipeline(
    since: datetime,
    until: datetime,
    top: int,
    min_repeat: int,
) -> list[dict[str, Any]]:
    """Aggregation: hashes asked in at least ``min_repeat`` conversations (FAQ candidates)."""
    return [
        {"$match": _time_match(since, until)},
        {
            "$group": {
                "_id": "$question_hash",
                **_group_fields(),
                "refused_count": {
                    "$sum": {"$cond": [{"$eq": ["$refused", True]}, 1, 0]},
                },
            }
        },
        *_SESSION_COUNT_STAGES,
        {"$match": {"session_count": {"$gte": min_repeat}}},
        {"$sort": {"session_count": -1, "count": -1, "_id": 1}},
        {"$limit": top},
    ]


def score_distribution_pipeline(since: datetime, until: datetime) -> list[dict[str, Any]]:
    """Aggregation: answered vs refused ``best_score`` summaries and histogram bins.

    Scores are never collected client-side. The pipeline facets answered and
    refused rows, computes count/min/max/avg, and buckets numeric scores into
    fixed bins. Null ``best_score`` values are counted separately.
    """
    boundaries = SCORE_BOUNDARIES
    facet_branch = [
        {
            "$group": {
                "_id": None,
                "count": {"$sum": 1},
                "null_scores": {
                    "$sum": {"$cond": [{"$eq": ["$best_score", None]}, 1, 0]},
                },
                "min_score": {"$min": "$best_score"},
                "max_score": {"$max": "$best_score"},
                "avg_score": {"$avg": "$best_score"},
            }
        }
    ]
    bucket_branch = [
        {"$match": {"best_score": {"$ne": None}}},
        {
            "$bucket": {
                "groupBy": "$best_score",
                "boundaries": boundaries,
                "default": "out_of_range",
                "output": {"count": {"$sum": 1}},
            }
        },
    ]
    return [
        {"$match": _time_match(since, until)},
        {
            "$facet": {
                # Rows with no refused field fall out of every branch below,
                # so the report prints this total beside answered and refused.
                "window_summary": [{"$group": {"_id": None, "count": {"$sum": 1}}}],
                "answered_summary": [
                    {"$match": {"refused": False}},
                    *facet_branch,
                ],
                "refused_summary": [
                    {"$match": {"refused": True}},
                    *facet_branch,
                ],
                "answered_bins": [
                    {"$match": {"refused": False}},
                    *bucket_branch,
                ],
                "refused_bins": [
                    {"$match": {"refused": True}},
                    *bucket_branch,
                ],
            }
        },
    ]


def _sample_text(row: Mapping[str, Any]) -> str:
    """Prefer truncated ``question_raw``, then ``question_condensed``."""
    raw = row.get("sample_raw")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    condensed = row.get("sample_condensed")
    if isinstance(condensed, str) and condensed.strip():
        return condensed.strip()
    return "(no sample text logged)"


def _format_hash_rows(rows: Sequence[Mapping[str, Any]], *, include_refused: bool) -> list[str]:
    """Render ranked hash groups as fixed-width operator lines."""
    if not rows:
        return ["  (none)"]
    lines: list[str] = []
    for index, row in enumerate(rows, start=1):
        question_hash = row.get("_id") or "(missing hash)"
        count = int(row.get("count") or 0)
        sample = _sample_text(row)
        suffix = ""
        if "session_count" in row:
            suffix += f"  conversations={int(row['session_count'])}"
        if include_refused and "refused_count" in row:
            suffix += f"  refused={int(row['refused_count'])}"
        lines.append(f"  {index:>3}. count={count:<6}{suffix}  hash={question_hash}")
        lines.append(f"       sample: {sample}")
    return lines


def _one_summary(rows: Sequence[Mapping[str, Any]]) -> Mapping[str, Any]:
    """Return the single ``$group`` summary document, or empty defaults."""
    if not rows:
        return {
            "count": 0,
            "null_scores": 0,
            "min_score": None,
            "max_score": None,
            "avg_score": None,
        }
    return rows[0]


def _format_score(value: Any) -> str:
    if value is None:
        return "n/a"
    try:
        return f"{float(value):.4f}"
    except (TypeError, ValueError):
        return "n/a"


def _bin_label(boundary_id: Any) -> str:
    if boundary_id == "out_of_range":
        return "out_of_range"
    try:
        start = float(boundary_id)
    except (TypeError, ValueError):
        return str(boundary_id)
    for left, right in pairwise(SCORE_BOUNDARIES):
        if abs(left - start) < 1e-12:
            # Present the final bin as inclusive 1.0 even though the Mongo edge is 1.0001.
            if right > 1.0:
                return f"[{left:.1f}, 1.0]"
            return f"[{left:.1f}, {right:.1f})"
    return f"{start:.1f}+"


def _format_bins(bins: Sequence[Mapping[str, Any]]) -> list[str]:
    if not bins:
        return ["  (no numeric best_score values)"]
    # Fill missing bins with zero so the two sides are comparable.
    counts = {row["_id"]: int(row.get("count") or 0) for row in bins}
    lines: list[str] = []
    for left in SCORE_BOUNDARIES[:-1]:
        label = _bin_label(left)
        lines.append(f"  {label:<16} {counts.get(left, 0)}")
    if "out_of_range" in counts:
        lines.append(f"  {'out_of_range':<16} {counts['out_of_range']}")
    return lines


def format_report(
    *,
    since: datetime,
    until: datetime,
    top: int,
    min_repeat: int,
    content_gaps: Sequence[Mapping[str, Any]],
    faq: Sequence[Mapping[str, Any]],
    score_facet: Mapping[str, Any],
) -> str:
    """Render a deterministic, operator-readable report."""
    total = _one_summary(score_facet.get("window_summary") or []).get("count", 0)
    answered = _one_summary(score_facet.get("answered_summary") or [])
    refused = _one_summary(score_facet.get("refused_summary") or [])
    lines = [
        "query_logs report",
        f"window: [{since.isoformat()}, {until.isoformat()})",
        f"top: {top}  min_repeat: {min_repeat}",
        "",
        "1. Content gaps (refused question_hash groups)",
        *_format_hash_rows(content_gaps, include_refused=False),
        "",
        "2. FAQ candidates (question_hash groups asked in at least min_repeat conversations)",
        *_format_hash_rows(faq, include_refused=True),
        "",
        "3. Answered vs refused best_score",
        f"  rows in window: {total}",
        "  answered:",
        f"    count={answered.get('count', 0)}  "
        f"null_scores={answered.get('null_scores', 0)}  "
        f"min={_format_score(answered.get('min_score'))}  "
        f"max={_format_score(answered.get('max_score'))}  "
        f"avg={_format_score(answered.get('avg_score'))}",
        "  refused:",
        f"    count={refused.get('count', 0)}  "
        f"null_scores={refused.get('null_scores', 0)}  "
        f"min={_format_score(refused.get('min_score'))}  "
        f"max={_format_score(refused.get('max_score'))}  "
        f"avg={_format_score(refused.get('avg_score'))}",
        "  answered histogram:",
        *_format_bins(score_facet.get("answered_bins") or []),
        "  refused histogram:",
        *_format_bins(score_facet.get("refused_bins") or []),
        "",
        "Notes:",
        "  - Grouping key is question_hash: exact wording after normalization.",
        "  - conversations counts distinct session_id values; count counts asks.",
        "  - Sample text is from already-logged truncated question_raw /",
        "    question_condensed when present; hashes alone if samples are absent.",
        "  - Aggregations $match the window first, then $group/$sort/$limit;",
        "    score distributions use $facet + $bucket (no full-collection download).",
    ]
    return "\n".join(lines) + "\n"


def run_report(
    *,
    since: datetime,
    until: datetime,
    top: int = DEFAULT_TOP,
    min_repeat: int = DEFAULT_MIN_REPEAT,
) -> str:
    """Execute the three aggregations and return the formatted report text."""
    validate_window(since, until)
    validate_top(top)
    validate_min_repeat(min_repeat)

    col = get_collection(QUERY_LOGS_COLLECTION)
    content_gaps = list(col.aggregate(content_gap_pipeline(since, until, top)))
    faq = list(col.aggregate(faq_pipeline(since, until, top, min_repeat)))
    score_rows = list(col.aggregate(score_distribution_pipeline(since, until)))
    score_facet: Mapping[str, Any] = score_rows[0] if score_rows else {}
    return format_report(
        since=since,
        until=until,
        top=top,
        min_repeat=min_repeat,
        content_gaps=content_gaps,
        faq=faq,
        score_facet=score_facet,
    )


def build_parser() -> argparse.ArgumentParser:
    """Return the CLI parser for the offline report."""
    parser = argparse.ArgumentParser(
        description=(
            "Read-only query_logs report: content gaps, FAQ ranking, "
            "and answered-vs-refused best_score histograms."
        )
    )
    parser.add_argument(
        "--since",
        required=True,
        help="Window start (inclusive). YYYY-MM-DD or ISO-8601 datetime (UTC if naive).",
    )
    parser.add_argument(
        "--until",
        help=(
            "Window end (exclusive). YYYY-MM-DD or ISO-8601 datetime. "
            "Defaults to the current UTC time."
        ),
    )
    parser.add_argument(
        "--top",
        type=int,
        default=DEFAULT_TOP,
        help=f"Max ranked hash groups per list (1-{MAX_TOP}; default {DEFAULT_TOP}).",
    )
    parser.add_argument(
        "--min-repeat",
        type=int,
        default=DEFAULT_MIN_REPEAT,
        dest="min_repeat",
        help=(f"Minimum distinct conversations for FAQ candidates (default {DEFAULT_MIN_REPEAT})."),
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=(
            f"Seconds to wait for the cluster before giving up (default {DEFAULT_TIMEOUT_SECONDS})."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Validate inputs, run the report, and print operator-safe output."""
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        since = parse_report_instant(args.since)
        until = parse_report_instant(args.until) if args.until else datetime.now(UTC)
        validate_window(since, until)
        validate_top(args.top)
        validate_min_repeat(args.min_repeat)
        validate_timeout(args.timeout)
    except ReportInputError as exc:
        print(f"Invalid arguments: {exc}", file=sys.stderr)
        return 2

    load_dotenv()
    try:
        # Creates the shared client, so the timeout is set before any query.
        get_client(server_selection_timeout_ms=args.timeout * 1000)
        report = run_report(
            since=since,
            until=until,
            top=args.top,
            min_repeat=args.min_repeat,
        )
    except (PyMongoError, RuntimeError) as exc:
        # The driver's message can carry the connection string, so only the
        # class name is printed. RuntimeError is the missing-MONGODB_URI case
        # from mongo.get_client. Anything else is a bug here and keeps its
        # traceback.
        print(
            f"Failed to read query_logs ({type(exc).__name__}). "
            "Confirm MONGODB_URI / MONGODB_DB and try again.",
            file=sys.stderr,
        )
        return 1

    sys.stdout.write(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
