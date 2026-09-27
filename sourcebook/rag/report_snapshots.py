"""Precomputed What People Ask reports, refreshed in the background (issue #291).

``query_log_rollup`` cut the report from one row per ask to one document per
question and day. At 50k distinct questions a day that is still 4.5M
documents in 90 days, and summing them took 6.5 to 7 s even from a covering
index (docs/load-testing.md), over the route's 5 s ``maxTimeMS``. The page
only offers 7, 30, and 90 days, so a background thread computes those three
windows every ``REPORT_REFRESH_SECONDS`` and stores each as one document in
``query_log_report``. The route reads the stored document, which costs one
lookup whatever the volume.

A snapshot is up to one refresh interval old, and ``until`` in the response
says when it was taken. The route computes live instead when a window has no
snapshot, when the stored one is older than ``max_age`` (the thread stopped),
or when a snapshot was taken with a different candidate cap or manager
threshold, which are part of its key. At pilot volume the live path is well
inside the budget; at planned volume it answers 503, as the route always has
when a report is too slow.

Every API worker runs the thread, and a lease document makes sure only one of
them refreshes per interval. Snapshots expire a day after they were taken, so
keys left behind by an old configuration go away on their own.
"""

from __future__ import annotations

import logging
import threading
import uuid
from collections.abc import Callable, Iterable
from datetime import UTC, datetime, timedelta
from typing import Any

from pymongo.errors import DuplicateKeyError

from sourcebook.rag.query_log_rollup import read_report, window_start

logger = logging.getLogger(__name__)

SNAPSHOT_COLLECTION = "query_log_report"
# The windows the page offers (web/src/pages/CoverageGapsPage.tsx).
WINDOWS = (7, 30, 90)
# How long a stored snapshot is kept, whether or not it is still read.
SNAPSHOT_TTL_SECONDS = 86400
LEASE_ID = "refresh-lease"
# This process's name on the lease, so it can renew a lease it still holds.
HOLDER = uuid.uuid4().hex


def _aware(instant: datetime) -> datetime:
    # The app's client is not tz_aware, so stored datetimes come back naive UTC.
    return instant if instant.tzinfo else instant.replace(tzinfo=UTC)


def snapshot_id(days: int, limit: int, min_sessions: int) -> str:
    return f"{days}d|limit={limit}|min={min_sessions}"


def acquire_lease(snapshots, now: datetime, hold: timedelta, holder: str = HOLDER) -> bool:
    """True when ``holder`` may refresh until ``now + hold``.

    The filter matches an expired lease or one ``holder`` already has, so the
    holder can renew a hold longer than its interval. When another worker
    holds a live one, the upsert tries to insert a second document with the
    same ``_id`` and Mongo refuses it.
    """
    try:
        snapshots.update_one(
            {"_id": LEASE_ID, "$or": [{"expires_at": {"$lt": now}}, {"holder": holder}]},
            {"$set": {"expires_at": now + hold, "holder": holder}},
            upsert=True,
        )
    except DuplicateKeyError:
        return False
    return True


def refresh(
    daily,
    snapshots,
    *,
    windows: Iterable[int],
    limit: int,
    min_sessions: int,
    now: datetime,
    max_time_ms: int | None = None,
) -> None:
    """Compute and store a snapshot of each window ending at ``now``."""
    for days in windows:
        since = window_start(now, days)
        report = read_report(
            daily, since, now, limit=limit, min_sessions=min_sessions, max_time_ms=max_time_ms
        )
        snapshots.update_one(
            {"_id": snapshot_id(days, limit, min_sessions)},
            {"$set": {"since": since, "until": now, "computed_at": now, "report": report}},
            upsert=True,
        )


def load(
    snapshots,
    days: int,
    *,
    limit: int,
    min_sessions: int,
    now: datetime,
    max_age: timedelta,
) -> dict[str, Any] | None:
    """The stored snapshot for this window, or None when there is none or it
    is older than ``max_age``. Returns ``since``, ``until``, and ``report``
    (``read_report``'s result)."""
    doc = snapshots.find_one({"_id": snapshot_id(days, limit, min_sessions)})
    if not doc:
        return None
    until = _aware(doc["until"])
    if now - until > max_age:
        return None
    return {"since": _aware(doc["since"]), "until": until, "report": doc["report"]}


def run_every(interval: float, task: Callable[[], None], stop: threading.Event) -> None:
    """Run ``task`` now and then every ``interval`` seconds until ``stop`` is
    set. A failed run is logged, and the next one still happens."""
    while True:
        try:
            task()
        except Exception:
            # Deliberately broad: a refresh failure must not end the thread,
            # or every later load would fall back to computing live.
            logger.exception("What People Ask refresh failed; retrying next interval.")
        if stop.wait(interval):
            return


def start(interval: float, task: Callable[[], None]) -> threading.Event:
    """Start ``run_every`` on a daemon thread. Set the returned event to stop it."""
    stop = threading.Event()
    threading.Thread(
        target=run_every, args=(interval, task, stop), name="report-refresh", daemon=True
    ).start()
    return stop
