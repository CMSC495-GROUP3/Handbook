"""Time the What People Ask report on its rollup at planned volume (issue #291).

The report reads ``query_log_daily`` (``sourcebook.rag.query_log_rollup``), one
document per question and UTC day, not the raw log. This seeds that
collection directly at the shape the planned volume would leave, then runs the
route's reads with its ``maxTimeMS``: both rankings, the session-id read for
each, and the totals.

The planned volume is 7M asks a day (``sourcebook/rag/config.py``). What
matters to the rollup is how many *distinct* questions that is per day,
which has not been measured, so it is a flag. Run it at a few values:

    docker run -d --rm --name sourcebook-report-timing -p 27099:27017 mongo:7
    .venv/bin/python -m scripts.loadtest.rollup_timing --uri mongodb://localhost:27099
    .venv/bin/python -m scripts.loadtest.rollup_timing --uri mongodb://localhost:27099 \\
      --questions-per-day 200000 --skip-seed
    docker stop sourcebook-report-timing

``--skip-seed`` reuses the seeded documents, so change only timing flags with
it. Point it at a throwaway database only: it drops ``query_log_daily`` there,
and refuses a ``--db`` that does not start with ``report_timing``.
"""

from __future__ import annotations

import argparse
import random
import statistics
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from pymongo import ASCENDING, MongoClient
from pymongo.errors import ExecutionTimeout, OperationFailure

from sourcebook.rag.query_log_rollup import (
    DAILY_COLLECTION,
    ROLLUP_SESSION_SAMPLE,
    ranking_pipeline,
    session_samples,
    totals_pipeline,
    window_start,
)

BATCH = 5_000
# sourcebook.api.routes.reports.QUERY_TIMEOUT_MS and CANDIDATE_LIMIT. Importing
# the route opens the app's Mongo client from MONGODB_URI, which this script
# must not touch.
QUERY_TIMEOUT_MS = 5000
CANDIDATE_LIMIT = 200
HOT_HASH = "hot-question"
SCRATCH_DB_PREFIX = "report_timing"


def _ids(rng: random.Random, n: int) -> list[str]:
    return [str(uuid.UUID(int=rng.getrandbits(128))) for _ in range(n)]


def _doc(day: datetime, question_hash: str, asks: int, sessions: int, rng, refused_share):
    """One day of one question, as record_ask would leave it."""
    refused = round(asks * refused_share)
    refused_sessions = round(sessions * refused_share)
    return {
        "_id": f"{day:%Y-%m-%d}|{question_hash}",
        "day": day,
        "question_hash": question_hash,
        "count": asks,
        "refused_count": refused,
        "session_count": sessions,
        "refused_session_count": refused_sessions,
        "sample_raw": f"{question_hash} as asked",
        "sample_condensed": f"{question_hash} condensed",
        "sessions": _ids(rng, min(sessions, ROLLUP_SESSION_SAMPLE)),
        "refused_sessions": _ids(rng, min(refused_sessions, ROLLUP_SESSION_SAMPLE)),
    }


def seed(col, args: argparse.Namespace, now: datetime) -> None:
    """``--days`` days, each with the hot question and ``--questions-per-day``
    others sharing the rest of ``--asks-per-day``."""
    rng = random.Random(args.seed)
    col.drop()
    # The keys db.ensure_indexes builds, minus the TTL.
    col.create_index([("day", ASCENDING)])
    col.create_index([("question_hash", ASCENDING), ("day", ASCENDING)])

    hot_asks = round(args.asks_per_day * args.hot_share)
    other_asks = max(1, (args.asks_per_day - hot_asks) // args.questions_per_day)
    batch: list[dict[str, Any]] = []
    for offset in range(args.days):
        day = window_start(now, 1) - timedelta(days=offset)
        docs = [_doc(day, HOT_HASH, hot_asks, round(hot_asks * 0.8), rng, args.refused_share)]
        for n in range(args.questions_per_day):
            # Most questions come back day after day; a share are new each day.
            name = f"q-{n}" if rng.random() > args.new_share else f"q-{offset}-{n}"
            docs.append(_doc(day, name, other_asks, max(1, round(other_asks * 0.8)), rng, 0.2))
        for doc in docs:
            batch.append(doc)
            if len(batch) == BATCH:
                col.insert_many(batch, ordered=False)
                batch = []
    if batch:
        col.insert_many(batch, ordered=False)


def _timed(fn, runs: int) -> str:
    times: list[float] = []
    failures: list[str] = []
    for _ in range(runs):
        start = time.perf_counter()
        try:
            fn()
        except ExecutionTimeout:
            failures.append("timeout")
            continue
        except OperationFailure as exc:
            failures.append(str((exc.details or {}).get("codeName", exc.code)))
            continue
        times.append((time.perf_counter() - start) * 1000)
    failed = f"failures {sorted(set(failures)) or 'none'} ({len(failures)})"
    if not times:
        return f"no run finished, {failed}"
    return (
        f"median {statistics.median(times):.0f} ms, min {min(times):.0f}, "
        f"max {max(times):.0f} over {len(times)} runs, {failed}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--uri", default="mongodb://localhost:27099")
    parser.add_argument("--db", default="report_timing")
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--asks-per-day", type=int, default=7_000_000)
    parser.add_argument(
        "--questions-per-day", type=int, default=50_000, help="distinct questions a day"
    )
    parser.add_argument("--hot-share", type=float, default=0.01, help="share of asks, hot question")
    parser.add_argument("--new-share", type=float, default=0.2, help="questions new each day")
    parser.add_argument("--refused-share", type=float, default=0.5)
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--seed", type=int, default=291)
    parser.add_argument("--skip-seed", action="store_true", help="reuse the seeded documents")
    args = parser.parse_args(argv)
    # seed() drops the rollup. Only a database named for this script may be
    # dropped, so pointing --uri at the real cluster cannot delete its counts.
    if not args.db.startswith(SCRATCH_DB_PREFIX):
        parser.error(f"--db must start with {SCRATCH_DB_PREFIX!r}; this script drops the rollup")

    client = MongoClient(args.uri, serverSelectionTimeoutMS=5000)
    col = client[args.db][DAILY_COLLECTION]
    now = datetime.now(UTC)
    if not args.skip_seed:
        start = time.perf_counter()
        seed(col, args, now)
        print(
            f"seeded {col.estimated_document_count()} day documents "
            f"in {time.perf_counter() - start:.0f} s"
        )
    print(f"server {client.server_info()['version']}")
    stats = client[args.db].command("collStats", DAILY_COLLECTION)
    print(
        f"collection {stats['size'] / 1e9:.2f} GB, indexes {stats['totalIndexSize'] / 1e9:.2f} GB"
    )

    until = datetime.now(UTC)
    since = window_start(until, args.days)
    limit = {"maxTimeMS": QUERY_TIMEOUT_MS}
    for refused_only in (True, False):
        name = "gaps" if refused_only else "faq"
        pipeline = ranking_pipeline(since, until, CANDIDATE_LIMIT, refused_only=refused_only)
        rows = list(col.aggregate(pipeline, **limit))  # warm-up, and the hashes to read
        small = [r["_id"] for r in rows if r["session_count"] <= ROLLUP_SESSION_SAMPLE]
        print(
            f"{name} ranking: {_timed(lambda p=pipeline: list(col.aggregate(p, **limit)), args.runs)}"
        )
        print(
            f"{name} session ids ({len(small)} wordings): "
            + _timed(
                lambda s=small, r=refused_only: session_samples(
                    col, since, until, s, refused_only=r, max_time_ms=QUERY_TIMEOUT_MS
                ),
                args.runs,
            )
        )
    totals = totals_pipeline(since, until)
    print(f"totals: {_timed(lambda: list(col.aggregate(totals, **limit)), args.runs)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
