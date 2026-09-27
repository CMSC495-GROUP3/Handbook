"""Per-day question counts for the What People Ask report (issue #291).

``GET /api/reports/gaps`` used to group raw ``query_logs`` rows. That is one
row per chat request, so its cost grows with every ask. At the 7M rows a day
planned in ``sourcebook/rag/config.py``, a 90-day window is about 630M rows,
and neither ``$group`` shape timed in docs/load-testing.md fits inside the
route's ``maxTimeMS``. Shortening the window does not help either: a single
day at that volume is 7M rows.

So the counts are kept as each ask is logged, one document per question and
UTC day in ``query_log_daily``:

- ``count`` and ``refused_count``: asks, and the refused ones.
- ``session_count`` and ``refused_session_count``: conversations whose
  *first* ask of this question (or first refused ask) in the log fell on this
  day. A marker per (question, conversation) in ``query_log_sessions``
  decides which ask is first; its unique ``_id`` means two concurrent asks
  cannot both count. Summing the days in a window then counts each
  conversation at most once.
- ``sessions`` and ``refused_sessions``: those conversations' ids, at most
  ``ROLLUP_SESSION_SAMPLE`` per day. The route unions them across wordings it
  groups by meaning. They never leave the server.

The report reads these instead of the raw log, so its cost grows with the
number of distinct questions per day, not with asks. That only helps if
questions repeat, which is the product's premise (config.py, the answer
cache) but has not been measured at volume.

**What changes in the counts.** A conversation is counted on the day of its
first ask of a question. If that day is before the window and it asks again
inside the window, it is not counted in that window. So a window's
conversation count can be lower than the raw log's, and never higher. Lower
is the safe direction: a manager sees a wording only when enough
conversations asked it (``MANAGER_MIN_CONVERSATIONS``), and an undercount
can only hide a wording, never show one too early. Asks are exact.

Windows are whole UTC days: the report's ``days`` runs from midnight UTC
``days - 1`` days ago up to now.

Recording never raises into the chat request; ``analytics.log_query`` wraps
it. The offline CLI, ``sourcebook.rag.query_log_reports``, still reads the raw
log, which has no timeout and stays exact.

Rows logged before this existed have no rollup. Backfill them once after
deploying, from the repository root on the EC2 host:

    python -m sourcebook.rag.query_log_rollup --backfill

It records every ``query_logs`` row not yet marked ``rolled_up`` and marks
it, oldest first, so it is safe to run again or while the app is logging.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from typing import Any

from dotenv import load_dotenv
from pymongo.errors import DuplicateKeyError, PyMongoError

logger = logging.getLogger(__name__)

DAILY_COLLECTION = "query_log_daily"
SESSIONS_COLLECTION = "query_log_sessions"
# Session ids kept per question and day, for the route's union across
# wordings. The route only reads them for a wording whose window total is at
# or under this, so the union is exact there and the ids it pulls stay under
# 1,000 per wording. The old per-wording cap on the raw log was also 1,000.
ROLLUP_SESSION_SAMPLE = 1000
# query_logs rows handled per backfill batch before the progress line.
BACKFILL_PROGRESS_EVERY = 10_000


def utc_day(instant: datetime) -> datetime:
    """Midnight UTC of the day ``instant`` falls on."""
    instant = instant.astimezone(UTC) if instant.tzinfo else instant.replace(tzinfo=UTC)
    return instant.replace(hour=0, minute=0, second=0, microsecond=0)


def window_start(until: datetime, days: int) -> datetime:
    """Midnight UTC ``days - 1`` days before ``until``: ``days`` whole days, today included."""
    return utc_day(until) - timedelta(days=days - 1)


def _daily_id(day: datetime, question_hash: str | None) -> str:
    return f"{day:%Y-%m-%d}|{question_hash}"


def _marker_id(question_hash: str | None, session_id: str | None, scope: str) -> str:
    # JSON, so a hash or session containing the separator cannot collide and
    # a missing session (None) is its own key, as it was one member of the
    # raw log's $addToSet.
    return json.dumps([question_hash, session_id, scope])


def _first_ask(markers, question_hash, session_id, scope: str, created_at: datetime) -> bool:
    """True when this is the conversation's first ask of the question in the log."""
    try:
        markers.insert_one(
            {"_id": _marker_id(question_hash, session_id, scope), "created_at": created_at}
        )
    except DuplicateKeyError:
        return False
    return True


def record_ask(
    daily,
    markers,
    *,
    created_at: datetime,
    session_id: str | None,
    question_hash: str | None,
    question_raw: str | None,
    question_condensed: str | None,
    refused: bool,
) -> None:
    """Add one ask to its question's day. Raises on a database error; the
    caller decides whether that may fail the request."""
    day = utc_day(created_at)
    new = _first_ask(markers, question_hash, session_id, "all", created_at)
    new_refused = refused and _first_ask(markers, question_hash, session_id, "refused", created_at)
    update: dict[str, Any] = {
        "$inc": {
            "count": 1,
            "refused_count": int(refused),
            "session_count": int(new),
            "refused_session_count": int(new_refused),
        },
        "$setOnInsert": {
            "day": day,
            "question_hash": question_hash,
            "sample_raw": question_raw,
            "sample_condensed": question_condensed,
        },
    }
    push = {}
    if new:
        push["sessions"] = {"$each": [session_id], "$slice": ROLLUP_SESSION_SAMPLE}
    if new_refused:
        push["refused_sessions"] = {"$each": [session_id], "$slice": ROLLUP_SESSION_SAMPLE}
    if push:
        update["$push"] = push
    daily.update_one({"_id": _daily_id(day, question_hash)}, update, upsert=True)


def _day_match(since: datetime, until: datetime) -> dict[str, Any]:
    return {"day": {"$gte": utc_day(since), "$lt": until}}


def ranking_pipeline(
    since: datetime,
    until: datetime,
    limit: int,
    *,
    refused_only: bool,
    min_sessions: int = 1,
) -> list[dict[str, Any]]:
    """Every question in the window with its asks and conversations, ranked
    and capped the way the route's list ranks.

    Refused wordings rank by refused asks, all wordings by conversations, so
    one person repeating a question cannot take a slot from a wording asked
    once each in several conversations. ``min_sessions`` drops wordings asked
    in fewer conversations before the sort and cap, for a manager's view.

    The output matches the old raw-log ``wording_pipeline`` less its session
    ids: ``_id`` (the hash), ``count``, ``refused_count``, ``session_count``,
    ``sample_raw``, ``sample_condensed``. ``session_samples`` fetches the ids.
    """
    match = _day_match(since, until)
    if refused_only:
        match["refused_count"] = {"$gt": 0}
    asks = "$refused_count" if refused_only else "$count"
    conversations = "$refused_session_count" if refused_only else "$session_count"
    order = (
        {"count": -1, "_id": 1} if refused_only else {"session_count": -1, "count": -1, "_id": 1}
    )
    return [
        {"$match": match},
        {
            "$group": {
                "_id": "$question_hash",
                "count": {"$sum": asks},
                "refused_count": {"$sum": "$refused_count"},
                "session_count": {"$sum": conversations},
                "sample_raw": {"$first": "$sample_raw"},
                "sample_condensed": {"$first": "$sample_condensed"},
            }
        },
        *([{"$match": {"session_count": {"$gte": min_sessions}}}] if min_sessions > 1 else []),
        {"$sort": order},
        {"$limit": limit},
    ]


def totals_pipeline(since: datetime, until: datetime) -> list[dict[str, Any]]:
    """Asks and refused asks in the window, summed from the day documents."""
    return [
        {"$match": _day_match(since, until)},
        {
            "$group": {
                "_id": None,
                "total": {"$sum": "$count"},
                "refused": {"$sum": "$refused_count"},
            }
        },
    ]


def session_samples(
    daily,
    since: datetime,
    until: datetime,
    question_hashes: Iterable[str | None],
    *,
    refused_only: bool,
    max_time_ms: int | None = None,
) -> dict[str | None, frozenset[str | None]]:
    """The conversation ids behind each of ``question_hashes`` in the window.

    Pass only hashes whose window ``session_count`` is at most
    ``ROLLUP_SESSION_SAMPLE``: each conversation is stored once per question,
    on its first day, so for those the ids are complete and the read is
    bounded. A hash with no day documents is left out of the result.
    """
    hashes = list(question_hashes)
    if not hashes:
        return {}
    field = "refused_sessions" if refused_only else "sessions"
    query = {**_day_match(since, until), "question_hash": {"$in": hashes}}
    kwargs = {"max_time_ms": max_time_ms} if max_time_ms is not None else {}
    found: dict[str | None, set[str | None]] = {}
    for doc in daily.find(query, {"question_hash": 1, field: 1}, **kwargs):
        found.setdefault(doc.get("question_hash"), set()).update(doc.get(field) or ())
    return {question_hash: frozenset(ids) for question_hash, ids in found.items()}


def backfill(query_logs, daily, markers) -> int:
    """Record every ``query_logs`` row not yet marked ``rolled_up``, oldest
    first, and mark it. Returns how many rows it recorded.

    Oldest first, so a conversation's first ask lands on the right day. Each
    row is marked right after it is recorded, so a rerun after a failure
    picks up where this stopped. Rows the app logs while this runs are
    already marked and skipped.
    """
    done = 0
    cursor = query_logs.find({"rolled_up": {"$exists": False}}).sort("created_at", 1)
    for row in cursor:
        created_at = row.get("created_at")
        if not isinstance(created_at, datetime):
            continue
        record_ask(
            daily,
            markers,
            created_at=created_at,
            session_id=row.get("session_id"),
            question_hash=row.get("question_hash"),
            question_raw=row.get("question_raw"),
            question_condensed=row.get("question_condensed"),
            refused=row.get("refused") is True,
        )
        query_logs.update_one({"_id": row["_id"]}, {"$set": {"rolled_up": True}})
        done += 1
        if done % BACKFILL_PROGRESS_EVERY == 0:
            print(f"recorded {done} rows", file=sys.stderr)
    return done


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Maintain the What People Ask rollup.")
    parser.add_argument(
        "--backfill",
        action="store_true",
        required=True,
        help="Record query_logs rows logged before the rollup existed.",
    )
    parser.parse_args(argv)

    load_dotenv()
    # Imported here so --help works without MONGODB_URI.
    from sourcebook.rag.mongo import get_collection

    try:
        done = backfill(
            get_collection("query_logs"),
            get_collection(DAILY_COLLECTION),
            get_collection(SESSIONS_COLLECTION),
        )
    except (PyMongoError, RuntimeError) as exc:
        # As in query_log_reports: the driver's message can carry the URI.
        print(f"Backfill failed ({type(exc).__name__}); rerun to continue.", file=sys.stderr)
        return 1
    print(f"Backfill recorded {done} rows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
