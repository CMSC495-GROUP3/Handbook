"""Time the What People Ask pipelines against a seeded MongoDB (issue #291).

Seeds ``query_logs`` with one popular question asked across many conversations
over a 90-day window, plus a spread of other questions, then runs the gaps and
FAQ pipelines the way ``GET /api/reports/gaps`` does, with the route's
``maxTimeMS``. It runs both the shipped single-pass ``$addToSet`` pipelines and
the two-pass ``$group`` alternative #291 proposed, which measured slower and was
not adopted, and checks that they agree.

Point it at a throwaway server only. It drops the database it seeds:

    docker run -d --rm --name sourcebook-report-timing -p 27099:27017 mongo:7
    .venv/bin/python -m scripts.loadtest.report_timing --uri mongodb://localhost:27099
    docker stop sourcebook-report-timing

Results and method are in docs/load-testing.md.
"""

from __future__ import annotations

import argparse
import random
import statistics
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.errors import ExecutionTimeout, OperationFailure

from sourcebook.rag.query_log_reports import (
    DEFAULT_MIN_REPEAT,
    DEFAULT_TOP,
    content_gap_pipeline,
    faq_pipeline,
)

BATCH = 10_000
# sourcebook.api.routes.reports.QUERY_TIMEOUT_MS. Importing the route opens the
# app's own Mongo client from MONGODB_URI, which this script must not touch.
QUERY_TIMEOUT_MS = 5000
HOT_HASH = "hot-question"


def _two_pass_group(extra: dict[str, Any]) -> list[dict[str, Any]]:
    """The two-pass count #291 proposed, kept here for comparison only.

    First on (hash, session), then on the hash with ``session_count`` as
    ``{$sum: 1}``, so no stage holds an array of session ids. ``extra`` holds
    per-row ``$sum`` accumulators, summed in both passes.
    """
    return [
        {
            "$group": {
                "_id": {"hash": "$question_hash", "session": "$session_id"},
                "count": {"$sum": 1},
                **extra,
                "sample_raw": {"$first": "$question_raw"},
                "sample_condensed": {"$first": "$question_condensed"},
            }
        },
        {
            "$group": {
                "_id": "$_id.hash",
                "count": {"$sum": "$count"},
                "session_count": {"$sum": 1},
                **{field: {"$sum": f"${field}"} for field in extra},
                "sample_raw": {"$first": "$sample_raw"},
                "sample_condensed": {"$first": "$sample_condensed"},
            }
        },
    ]


def two_pass_pipelines(since: datetime, until: datetime) -> dict[str, list[dict[str, Any]]]:
    window = {"created_at": {"$gte": since, "$lt": until}}
    refused = {"refused_count": {"$sum": {"$cond": [{"$eq": ["$refused", True]}, 1, 0]}}}
    return {
        "gaps": [
            {"$match": {**window, "refused": True}},
            *_two_pass_group({}),
            {"$sort": {"count": -1, "_id": 1}},
            {"$limit": DEFAULT_TOP},
        ],
        "faq": [
            {"$match": window},
            *_two_pass_group(refused),
            {"$match": {"session_count": {"$gte": DEFAULT_MIN_REPEAT}}},
            {"$sort": {"session_count": -1, "count": -1, "_id": 1}},
            {"$limit": DEFAULT_TOP},
        ],
    }


def current_pipelines(since: datetime, until: datetime) -> dict[str, list[dict[str, Any]]]:
    return {
        "gaps": content_gap_pipeline(since, until, DEFAULT_TOP),
        "faq": faq_pipeline(since, until, DEFAULT_TOP, DEFAULT_MIN_REPEAT),
    }


def _row(now: datetime, days: int, rng: random.Random, **fields: Any) -> dict[str, Any]:
    """One row shaped like analytics.log_query writes it, at a random time in the window."""
    created_at = now - timedelta(seconds=rng.uniform(0, days * 86400))
    return {
        "created_at": created_at,
        "question_raw": f"{fields['question_hash']} as asked",
        "question_condensed": f"{fields['question_hash']} condensed",
        "best_score": round(rng.uniform(0.2, 0.9), 4),
        "passage_count": 5,
        "sources": [],
        "cache_hit": None,
        "latency_ms": rng.randint(800, 4000),
        **fields,
    }


def seed(col, args: argparse.Namespace, now: datetime) -> None:
    """Hot question: ``--rows`` asks spread over ``--sessions`` conversations.
    Noise: ``--noise`` asks over ``--noise-questions`` other hashes."""
    rng = random.Random(args.seed)
    col.drop()
    # The same keys db.ensure_indexes builds, minus the TTL, so the monitor
    # cannot delete rows between seeding and timing.
    col.create_index([("created_at", DESCENDING)])
    col.create_index([("refused", ASCENDING), ("created_at", DESCENDING)])
    col.create_index([("question_hash", ASCENDING), ("created_at", DESCENDING)])

    sessions = [str(uuid.UUID(int=rng.getrandbits(128))) for _ in range(args.sessions)]
    batch: list[dict[str, Any]] = []
    for i in range(args.rows + args.noise):
        if i < args.rows:
            # Every conversation asks at least once, the rest repeat at random.
            session = sessions[i] if i < len(sessions) else rng.choice(sessions)
            fields = {"question_hash": HOT_HASH, "refused": rng.random() < args.refused_share}
        else:
            session = str(uuid.UUID(int=rng.getrandbits(128)))
            fields = {
                "question_hash": f"noise-{rng.randrange(args.noise_questions)}",
                "refused": rng.random() < 0.2,
            }
        batch.append(_row(now, args.days, rng, session_id=session, **fields))
        if len(batch) == BATCH:
            col.insert_many(batch, ordered=False)
            batch = []
    if batch:
        col.insert_many(batch, ordered=False)


def time_pipeline(col, pipeline: list[dict[str, Any]], runs: int) -> dict[str, Any]:
    """Wall time per run with the route's maxTimeMS.

    Timeouts (the route's 503) and other server errors (its 500) are counted,
    not timed.
    """
    times: list[float] = []
    timeouts = 0
    errors: list[str] = []
    rows: list[dict[str, Any]] = []
    for _ in range(runs):
        start = time.perf_counter()
        try:
            rows = list(col.aggregate(pipeline, maxTimeMS=QUERY_TIMEOUT_MS))
        except ExecutionTimeout:
            timeouts += 1
            continue
        except OperationFailure as exc:
            errors.append(str((exc.details or {}).get("codeName", exc.code)))
            continue
        times.append((time.perf_counter() - start) * 1000)
    return {"times": times, "timeouts": timeouts, "errors": errors, "rows": rows}


def group_stats(col, pipeline: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Per-$group time and spill figures from explain, without maxTimeMS.

    executionStats verbosity runs the pipeline to completion.
    """
    try:
        plan = col.database.command(
            {
                "explain": {"aggregate": col.name, "pipeline": pipeline, "cursor": {}},
                "verbosity": "executionStats",
            }
        )
    except OperationFailure as exc:
        return [{"error": (exc.details or {}).get("codeName", exc.code)}]
    stats = []
    for stage in plan.get("stages", []):
        if "$group" in stage:
            stats.append(
                {
                    "ms": stage.get("executionTimeMillisEstimate"),
                    "spills": stage.get("spills"),
                    "used_disk": stage.get("usedDisk"),
                }
            )
    return stats


def _key(rows: list[dict[str, Any]]) -> list[tuple]:
    return [(r["_id"], r["count"], r["session_count"], r.get("refused_count")) for r in rows]


def _summary(result: dict[str, Any]) -> str:
    times = result["times"]
    failed = f"{result['timeouts']} timeouts, errors {sorted(set(result['errors'])) or 'none'}"
    if not times:
        return f"no run finished ({failed})"
    return (
        f"median {statistics.median(times):.0f} ms, min {min(times):.0f}, "
        f"max {max(times):.0f} over {len(times)} runs ({failed})"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--uri", default="mongodb://localhost:27099")
    parser.add_argument("--db", default="report_timing")
    parser.add_argument("--rows", type=int, default=500_000, help="asks of the hot question")
    parser.add_argument("--sessions", type=int, default=400_000, help="its conversations")
    parser.add_argument("--noise", type=int, default=100_000, help="asks of other questions")
    parser.add_argument("--noise-questions", type=int, default=5_000)
    parser.add_argument("--refused-share", type=float, default=0.5)
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--seed", type=int, default=291)
    parser.add_argument("--skip-seed", action="store_true", help="reuse the seeded rows")
    args = parser.parse_args(argv)
    if args.sessions > args.rows:
        parser.error("--sessions cannot exceed --rows")

    client = MongoClient(args.uri, serverSelectionTimeoutMS=5000)
    col = client[args.db]["query_logs"]
    now = datetime.now(UTC)
    if not args.skip_seed:
        start = time.perf_counter()
        seed(col, args, now)
        print(
            f"seeded {col.estimated_document_count()} rows in {time.perf_counter() - start:.0f} s"
        )
    print(f"server {client.server_info()['version']}")

    until = datetime.now(UTC)
    since = until - timedelta(days=args.days)
    before, after = current_pipelines(since, until), two_pass_pipelines(since, until)
    for name in ("gaps", "faq"):
        # One untimed pass each to warm the cache, so neither side pays for disk reads.
        time_pipeline(col, before[name], 1)
        time_pipeline(col, after[name], 1)
        old = time_pipeline(col, before[name], args.runs)
        new = time_pipeline(col, after[name], args.runs)
        print(f"{name} before ($addToSet): {_summary(old)}")
        print(f"  $group stats: {group_stats(col, before[name])}")
        print(f"{name} after (two $group): {_summary(new)}")
        print(f"  $group stats: {group_stats(col, after[name])}")
        if old["rows"] and new["rows"]:
            same = _key(old["rows"]) == _key(new["rows"])
            print(f"  same ranked counts: {same}; top row {_key(new['rows'])[:1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
