"""Coverage report — the query log's read side, for the What People Ask page.

Every chat request writes a ``query_logs`` row (see ``sourcebook.api.analytics``).
``sourcebook.rag.query_log_reports`` already ranks those rows for an operator at
a terminal on the EC2 host. This route ranks them for the web app, so managers
can see what their people keep asking and fold it into training and
orientation, and Human Resources can see which questions the corpus does not
cover, without a shell:

- ``gaps``: refused questions, most asked first. Each is a candidate for a new
  or clearer policy.
- ``faq``: questions asked in at least two conversations, answered or not,
  most conversations first, with how many of those asks were refused.

Both lists group by meaning, not exact wording (issue #287). The log's
``question_hash`` groups identical text; ``sourcebook.rag.question_groups``
then merges hash groups whose question embeddings are within
``QUESTION_GROUP_THRESHOLD`` cosine. Most vectors are already in
``embedding_cache``, because retrieval embedded the same condensed text. The
rest are embedded in one ``embed_many`` call and not stored, so this route
never writes. If that call fails, the lists fall back to exact wording and
``grouping`` in the response says ``"exact"``: a busy provider must not take
the report down.

Cosine cannot tell a paraphrase from a near neighbour, so pairs between
``QUESTION_JUDGE_FLOOR`` and the threshold go to the utility model in one call
per load (issue #293, ``sourcebook.rag.question_judge``). At most
``QUESTION_JUDGE_MAX_PAIRS`` new pairs go per call, closest first, and each
verdict is memoized per process, so a repeat load judges only pairs it has not
seen. If that call fails or its reply does not parse, those pairs stay apart
and ``grouping`` says ``"cosine"``, as it does when the cap is 0.

Only the ``CANDIDATE_LIMIT`` top hash groups per list are grouped, picked the
way each list ranks. A wording outside that cap cannot join a group, which at
pilot volume is every wording there is. Vectors fetched or embedded here are
kept in a bounded per-process memo, so a repeat load costs no provider call.

The counts come from ``sourcebook.rag.query_log_rollup``, one document per
question and UTC day kept as each ask is logged, not from the raw rows. At
the volume config.py plans for, the raw log is too big to group inside
``QUERY_TIMEOUT_MS`` for any window, and so is a 90-day window of the rollup
(#291). So the page's windows are read from snapshots that a background
thread refreshes every ``REPORT_REFRESH_SECONDS``
(``sourcebook.rag.report_snapshots``), and ``until`` in the response is when
the snapshot was taken. Any other window, or one whose snapshot is missing or
stale, is computed live. The window is ``days`` whole UTC
days, today included, at most 90. ``query_logs`` rows
expire after ``QUERY_LOG_TTL_SECONDS``, so a window longer than the TTL is
shortened to it and the response's ``days`` says what was used. The bound on
the parameter stays fixed, so a short TTL cannot turn every request into a 422.

Question text is the logged ``question_condensed`` (the standalone rewrite that
the hash groups on), falling back to the truncated ``question_raw``. No
session id leaves the server; sessions are only counted. Only a session opened
with the manager or HR password may read it (``require_report_reader``),
because the text is what employees typed.

A manager session sees only wordings asked in at least
``MANAGER_MIN_CONVERSATIONS`` conversations. The rest are dropped in the
query, before the ``CANDIDATE_LIMIT`` cap and grouping, so they cannot take
candidate slots, and no text on a manager's page, leader or other wording, was
typed in fewer conversations than that; ``min_conversations`` in the response says the
filter was applied. ``total`` and ``refused`` still count every row, since a
number names nobody. HR sees every wording.
"""

import logging
import threading
from array import array
from collections import OrderedDict
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pymongo.errors import ExecutionTimeout, OperationFailure, PyMongoError

from sourcebook.api.db import query_log_daily_col, query_log_report_col
from sourcebook.api.limiter import limiter
from sourcebook.api.routes.auth import MANAGER_PASSWORD_HASH_VAR
from sourcebook.api.routes.deps import (
    REPORT_READER_RESPONSES,
    require_report_reader,
)
from sourcebook.rag import report_snapshots
from sourcebook.rag.cache import embedding_cache_key, get_cached_embeddings
from sourcebook.rag.config import (
    CACHE_ENABLED,
    MANAGER_MIN_CONVERSATIONS,
    QUERY_LOG_TTL_SECONDS,
    QUESTION_GROUP_THRESHOLD,
    QUESTION_JUDGE_FLOOR,
    QUESTION_JUDGE_MAX_PAIRS,
    REPORT_PROVIDER_TIMEOUT_SECONDS,
    REPORT_REFRESH_SECONDS,
)
from sourcebook.rag.llm import get_provider
from sourcebook.rag.query_log_reports import (
    DEFAULT_MIN_REPEAT,
    DEFAULT_TOP,
    MAX_TOP,
)
from sourcebook.rag.query_log_rollup import (
    ROLLUP_SESSION_SAMPLE,
    read_report,
    session_samples,
    window_start,
)
from sourcebook.rag.question_groups import (
    QuestionGroup,
    Wording,
    candidate_pairs,
    exact_groups,
    group_by_meaning,
)
from sourcebook.rag.question_judge import QUESTION_JUDGE_PROMPT_VERSION, judge_pairs

logger = logging.getLogger(__name__)

router = APIRouter()

DEFAULT_WINDOW_DAYS = 30
MAX_WINDOW_DAYS = 90
# Rows older than the TTL are gone, so no window reaches past it. Never below
# one day, or a TTL under a day would leave an empty window.
TTL_DAYS = max(1, QUERY_LOG_TTL_SECONDS // 86400)
# Per query. The rollup keeps a 90-day $group to one document per question
# and day, but that is still not free, and a manager or HR session can ask
# for one 30 times a minute.
QUERY_TIMEOUT_MS = 5000
# Per query in the background refresh. A 90-day window at 50k questions a day
# took about 7 s locally (docs/load-testing.md); this stops a runaway one.
REFRESH_TIMEOUT_MS = 120_000
# A snapshot older than this means the refresh has stopped, and the route
# computes live rather than show stale counts.
SNAPSHOT_MAX_AGE = timedelta(seconds=3 * REPORT_REFRESH_SECONDS)
# MongoDB's ExceededMemoryLimit. The rollup's $group holds only sums, so it
# can spill to disk and should not hit this; it is kept so a pipeline change
# that brings back an array accumulator answers 503, not 500
# (docs/load-testing.md, #291). Code 292 is the same failure when allowDiskUse
# is false; nothing here sets that and the server default is true.
EXCEEDED_MEMORY_LIMIT = 146
# Hash groups per list that go into grouping. Two lists of 200 is at most 400
# texts in one embed_many call. Listing the judge's candidates checks every pair
# in each list and grouping checks each wording against the leaders, so the
# worst case is about 80,000 dot products, roughly 1.4 s.
CANDIDATE_LIMIT = 200
# Other wordings listed under each group's leader.
MAX_OTHER_WORDINGS = 5
# Vectors this process has already fetched or embedded, keyed like
# embedding_cache so a provider change cannot serve a stale vector. Without it,
# every load re-embeds every text the Mongo cache no longer holds (its TTL is
# 30 days, the report's window up to 90). Vectors are stored as 32-bit arrays,
# 6 KB each at 1,536 dimensions, so the bound is about 31 MB per process.
# CACHE_ENABLED=0 turns it off with the Mongo caches, so a load test run
# without caching sees every load embed.
VECTOR_MEMO_SIZE = 5000
_vector_memo: OrderedDict[str, array] = OrderedDict()
_vector_memo_lock = threading.Lock()
# Utility-model verdicts on wording pairs, keyed by model, prompt version, and
# both texts, so a model or prompt change cannot reuse an old verdict. Logged
# questions run to 500 characters, so an entry is up to about 1 to 2 KB and a
# full memo 20 to 40 MB per worker. Off with CACHE_ENABLED=0 like the vector memo.
VERDICT_MEMO_SIZE = 20000
_verdict_memo: OrderedDict[tuple[str, str, str, str], bool] = OrderedDict()
_verdict_memo_lock = threading.Lock()


def _question(row: dict[str, Any]) -> str | None:
    """The condensed question if one was logged, else the raw one, else None."""
    for field in ("sample_condensed", "sample_raw"):
        value = row.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _wording(row: dict[str, Any], sessions: dict[str | None, frozenset[str | None]]) -> Wording:
    return Wording(
        question_hash=row.get("_id"),
        question=_question(row),
        count=int(row.get("count") or 0),
        refused=int(row.get("refused_count") or 0),
        sessions=sessions.get(row.get("_id"), frozenset()),
        session_count=int(row.get("session_count") or 0),
    )


def _wordings(
    rows: list[dict[str, Any]], since: datetime, until: datetime, *, refused_only: bool
) -> list[Wording]:
    """Wordings with their conversation ids, for the union across a group.

    Ids are read only for wordings at or under ``ROLLUP_SESSION_SAMPLE``
    conversations, where the rollup holds all of them. A bigger wording
    keeps an empty set, and its exact ``session_count`` is the group's floor.
    """
    small = [
        row.get("_id") for row in rows if (row.get("session_count") or 0) <= ROLLUP_SESSION_SAMPLE
    ]
    sessions = session_samples(
        query_log_daily_col,
        since,
        until,
        small,
        refused_only=refused_only,
        max_time_ms=QUERY_TIMEOUT_MS,
    )
    return [_wording(row, sessions) for row in rows]


def _report(days: int, now: datetime) -> tuple[datetime, datetime, dict[str, Any]]:
    """The window's start, end, and ``read_report`` result: the stored
    snapshot when there is a fresh one, else computed live under
    ``QUERY_TIMEOUT_MS``."""
    limits = {"limit": CANDIDATE_LIMIT, "min_sessions": MANAGER_MIN_CONVERSATIONS}
    if REPORT_REFRESH_SECONDS > 0:
        snapshot = report_snapshots.load(
            query_log_report_col, days, now=now, max_age=SNAPSHOT_MAX_AGE, **limits
        )
        if snapshot:
            return snapshot["since"], snapshot["until"], snapshot["report"]
    since = window_start(now, days)
    return (
        since,
        now,
        read_report(query_log_daily_col, since, now, max_time_ms=QUERY_TIMEOUT_MS, **limits),
    )


def refresh_snapshots() -> None:
    """Refresh the page's windows if this worker holds the lease. Runs on
    the background thread that ``start_refresh`` starts."""
    now = datetime.now(UTC)
    windows = sorted({min(days, TTL_DAYS) for days in report_snapshots.WINDOWS})
    # Long enough to cover every window at its timeouts, the aggregation and
    # the sample lookups each (read_report), so a slow refresh cannot outlive
    # the lease and let a second worker start one alongside it.
    hold = timedelta(
        seconds=max(REPORT_REFRESH_SECONDS, len(windows) * 2 * REFRESH_TIMEOUT_MS / 1000)
    )
    if not report_snapshots.acquire_lease(query_log_report_col, now, hold):
        return
    report_snapshots.refresh(
        query_log_daily_col,
        query_log_report_col,
        windows=windows,
        limit=CANDIDATE_LIMIT,
        min_sessions=MANAGER_MIN_CONVERSATIONS,
        now=now,
        max_time_ms=REFRESH_TIMEOUT_MS,
    )


def start_refresh() -> Callable[[], None] | None:
    """Start the background refresh and return the function that stops it, or
    None when ``REPORT_REFRESH_SECONDS`` is 0.

    Stopping releases the lease when no refresh is running, so the API that
    replaces this one on a deploy refreshes at once. Mid-refresh it leaves the
    lease to expire: releasing it then would let another worker start a
    refresh alongside the one still running on this daemon thread.
    """
    if REPORT_REFRESH_SECONDS <= 0:
        return None
    # Held for each refresh, and by stop() while it releases the lease.
    running = threading.Lock()
    stopped = threading.Event()

    def refresh_unless_stopped() -> None:
        with running:
            if not stopped.is_set():
                refresh_snapshots()

    stop_thread = report_snapshots.start(REPORT_REFRESH_SECONDS, refresh_unless_stopped)

    def stop() -> None:
        stopped.set()
        stop_thread.set()
        if not running.acquire(blocking=False):
            return
        try:
            report_snapshots.release_lease(query_log_report_col)
        except PyMongoError:
            # Shutdown goes on; the lease expires on its own, as it did before.
            logger.warning("Could not release the What People Ask refresh lease.", exc_info=True)
        finally:
            running.release()

    return stop


def _remember(vectors: dict[str, list[float]]) -> None:
    if not CACHE_ENABLED:
        return
    with _vector_memo_lock:
        for text, vector in vectors.items():
            key = embedding_cache_key(text)
            _vector_memo[key] = array("f", vector)
            _vector_memo.move_to_end(key)
        while len(_vector_memo) > VECTOR_MEMO_SIZE:
            _vector_memo.popitem(last=False)


def _recall(texts: list[str]) -> dict[str, array]:
    if not CACHE_ENABLED:
        return {}
    with _vector_memo_lock:
        found = {}
        for text in texts:
            key = embedding_cache_key(text)
            if key in _vector_memo:
                _vector_memo.move_to_end(key)
                found[text] = _vector_memo[key]
        return found


def _vectors(texts: list[str]) -> dict[str, Sequence[float]] | None:
    """A vector for every text, or None on any failure.

    In order: this process's memo, then ``embedding_cache``, then one
    ``embed_many`` call for the rest. Nothing is written to Mongo.
    """
    known = _recall(texts)
    try:
        cached = get_cached_embeddings([text for text in texts if text not in known])
        missing = [text for text in texts if text not in known and text not in cached]
        fresh = (
            dict(
                zip(
                    missing,
                    get_provider().embed_many(missing, timeout=REPORT_PROVIDER_TIMEOUT_SECONDS),
                    strict=True,
                )
            )
            if missing
            else {}
        )
    except Exception:
        # Deliberately broad: the provider raises its own busy error, OpenAI's
        # API errors, and httpx transport errors, and the cache read can raise
        # PyMongoError. Any of them means "show exact wording", never a failed
        # report. The memo is outside this block, so a bug in it surfaces
        # instead of hiding behind the fallback.
        logger.warning("Question grouping fell back to exact wording.", exc_info=True)
        return None
    _remember({**cached, **fresh})
    return {**known, **cached, **fresh}


def _verdict_key(pair: tuple[str, str]) -> tuple[str, str, str, str]:
    return (get_provider().utility_fingerprint(), QUESTION_JUDGE_PROMPT_VERSION, *pair)


def _same_pairs(
    candidates: dict[tuple[str, str], float],
) -> tuple[set[tuple[str, str]], bool, int]:
    """The candidate pairs the utility model says are one question, whether
    every pair it was asked about got a verdict, and how many candidates this
    load left without one.

    Memoized verdicts are free. Of the rest, the closest
    ``QUESTION_JUDGE_MAX_PAIRS`` go in one call; pairs past the cap count as
    different on this load and are judged on a later one. The count lets the
    page say so (#300). It is 0 with the memo off, since a later load would
    judge the same pairs again. A failed call merges nothing below the
    threshold, memoized verdicts included.
    """
    known: dict[tuple[str, str], bool] = {}
    if CACHE_ENABLED:
        with _verdict_memo_lock:
            for pair in candidates:
                key = _verdict_key(pair)
                if key in _verdict_memo:
                    _verdict_memo.move_to_end(key)
                    known[pair] = _verdict_memo[key]
    unknown = sorted(
        (pair for pair in candidates if pair not in known),
        key=lambda pair: (-candidates[pair], pair),
    )
    pending = unknown[:QUESTION_JUDGE_MAX_PAIRS]
    same = {pair for pair, verdict in known.items() if verdict}
    if not pending:
        return same, True, 0
    try:
        verdicts = judge_pairs(pending, timeout=REPORT_PROVIDER_TIMEOUT_SECONDS)
    except Exception:
        # Deliberately broad, as in _vectors: any provider or transport error
        # means "group on cosine alone", never a failed report.
        logger.warning("Question judge failed; grouping on cosine alone.", exc_info=True)
        # Drop the memoized merges too, so "cosine" describes what the page
        # shows: nothing below the threshold merges on a failed load.
        return set(), False, len(unknown)
    if verdicts is None:
        logger.warning("Question judge reply did not parse; grouping on cosine alone.")
        return set(), False, len(unknown)
    fresh = dict(zip(pending, verdicts, strict=True))
    if CACHE_ENABLED:
        with _verdict_memo_lock:
            for pair, verdict in fresh.items():
                key = _verdict_key(pair)
                _verdict_memo[key] = verdict
                _verdict_memo.move_to_end(key)
            while len(_verdict_memo) > VERDICT_MEMO_SIZE:
                _verdict_memo.popitem(last=False)
    # With the memo off, a reload sends the same closest pairs again, so the
    # ones past the cap never get judged and the page must not promise it.
    return (
        same | {pair for pair, verdict in fresh.items() if verdict},
        True,
        len(unknown) - len(pending) if CACHE_ENABLED else 0,
    )


def _grouped(
    refused_wordings: list[Wording],
    all_wordings: list[Wording],
    vectors: dict[str, Sequence[float]] | None,
) -> tuple[list[QuestionGroup], list[QuestionGroup], str, int]:
    """Both lists' groups, the ``grouping`` value that describes them, and how
    many candidate pairs went unjudged."""
    if vectors is None:
        return exact_groups(refused_wordings), exact_groups(all_wordings), "exact", 0
    same: set[tuple[str, str]] = set()
    # With the judge off, grouping is cosine alone, and the page says so.
    judged = False
    unjudged = 0
    if QUESTION_JUDGE_MAX_PAIRS > 0:
        candidates = {
            **candidate_pairs(
                refused_wordings, vectors, QUESTION_JUDGE_FLOOR, QUESTION_GROUP_THRESHOLD
            ),
            **candidate_pairs(
                all_wordings, vectors, QUESTION_JUDGE_FLOOR, QUESTION_GROUP_THRESHOLD
            ),
        }
        same, judged, unjudged = _same_pairs(candidates)

    def group(wordings: list[Wording]) -> list[QuestionGroup]:
        return group_by_meaning(
            wordings, vectors, QUESTION_GROUP_THRESHOLD, floor=QUESTION_JUDGE_FLOOR, same=same
        )

    grouping = "meaning" if judged else "cosine"
    return group(refused_wordings), group(all_wordings), grouping, unjudged


def _serialize(group: QuestionGroup) -> dict[str, Any]:
    others = group.members[1:]
    return {
        "question_hash": group.leader.question_hash,
        "question": group.leader.question,
        "count": group.count,
        "conversations": group.conversations,
        "other_wordings": [
            {"question": member.question, "count": member.count}
            for member in others[:MAX_OTHER_WORDINGS]
        ],
        "other_wording_count": len(others),
    }


def _by_count(groups: list[QuestionGroup]) -> list[QuestionGroup]:
    """Gaps rank on asks: every refusal is a gap, even one person's repeats."""
    return sorted(groups, key=lambda g: (-g.count, g.leader.question_hash or ""))


def _by_conversations(groups: list[QuestionGroup]) -> list[QuestionGroup]:
    """Asked most ranks on conversations, the query log report's FAQ order."""
    return sorted(groups, key=lambda g: (-g.conversations, -g.count, g.leader.question_hash or ""))


@router.get("/reports/gaps", responses=REPORT_READER_RESPONSES)
@limiter.limit("30/minute")
def coverage_gaps(
    request: Request,
    days: int = Query(DEFAULT_WINDOW_DAYS, ge=1, le=MAX_WINDOW_DAYS),
    top: int = Query(DEFAULT_TOP, ge=1, le=MAX_TOP),
    cred: str = Depends(require_report_reader),
):
    """Refused and repeated questions over the last ``days`` days, grouped by meaning."""
    days = min(days, TTL_DAYS)
    now = datetime.now(UTC)
    manager = cred == MANAGER_PASSWORD_HASH_VAR
    min_conversations = MANAGER_MIN_CONVERSATIONS if manager else None

    try:
        since, until, report = _report(days, now)
        lists = ("manager_gaps", "manager_faq") if manager else ("gaps", "faq")
        refused_wordings = _wordings(report[lists[0]], since, until, refused_only=True)
        all_wordings = _wordings(report[lists[1]], since, until, refused_only=False)
    except ExecutionTimeout:
        raise HTTPException(
            status_code=503,
            detail="This report took too long. Try a shorter window.",
        ) from None
    except OperationFailure as exc:
        if exc.code != EXCEEDED_MEMORY_LIMIT:
            raise
        raise HTTPException(
            status_code=503,
            detail="This report needs too much memory. Try a shorter window.",
        ) from None

    total = int(report.get("total") or 0)
    refused = int(report.get("refused") or 0)
    texts = sorted({w.question for w in refused_wordings + all_wordings if w.question})
    gap_groups, faq_groups, grouping, unjudged = _grouped(
        refused_wordings, all_wordings, _vectors(texts)
    )

    repeated = [group for group in faq_groups if group.conversations >= DEFAULT_MIN_REPEAT]
    return {
        "since": since.isoformat(),
        "until": until.isoformat(),
        "days": days,
        "grouping": grouping,
        "unjudged": unjudged,
        "min_conversations": min_conversations,
        "total": total,
        "refused": refused,
        "gaps": [_serialize(group) for group in _by_count(gap_groups)[:top]],
        "faq": [
            {**_serialize(group), "refused": group.refused}
            for group in _by_conversations(repeated)[:top]
        ],
    }
