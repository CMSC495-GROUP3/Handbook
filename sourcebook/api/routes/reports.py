"""Coverage report — the query log's read side, for the What People Ask page.

Every chat request writes a ``query_logs`` row (see ``sourcebook.api.analytics``).
``sourcebook.rag.query_log_reports`` already ranks those rows for an operator at
a terminal on the EC2 host. This route ranks them for the web app, so Human
Resources can see which questions the corpus does not cover without a shell:

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

Only the ``CANDIDATE_LIMIT`` top hash groups per list are grouped, picked the
way each list ranks. A wording outside that cap cannot join a group, which at
pilot volume is every wording there is. Vectors fetched or embedded here are
kept in a bounded per-process memo, so a repeat load costs no provider call.

The window counts back ``days`` from now, at most 90. ``query_logs`` rows
expire after ``QUERY_LOG_TTL_SECONDS``, so a window longer than the TTL is
shortened to it and the response's ``days`` says what was used. The bound on
the parameter stays fixed, so a short TTL cannot turn every request into a 422.

Question text is the logged ``question_condensed`` (the standalone rewrite that
the hash groups on), falling back to the truncated ``question_raw``. No
session id leaves the server; sessions are only counted.
"""

import logging
import threading
from array import array
from collections import OrderedDict
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pymongo.errors import ExecutionTimeout, OperationFailure

from sourcebook.api.db import query_logs_col
from sourcebook.api.limiter import limiter
from sourcebook.api.routes.deps import require_auth
from sourcebook.rag.cache import embedding_cache_key, get_cached_embeddings
from sourcebook.rag.config import (
    CACHE_ENABLED,
    QUERY_LOG_TTL_SECONDS,
    QUESTION_GROUP_THRESHOLD,
)
from sourcebook.rag.llm import get_provider
from sourcebook.rag.query_log_reports import (
    DEFAULT_MIN_REPEAT,
    DEFAULT_TOP,
    MAX_TOP,
    wording_pipeline,
)
from sourcebook.rag.question_groups import (
    QuestionGroup,
    Wording,
    exact_groups,
    group_by_meaning,
)

logger = logging.getLogger(__name__)

router = APIRouter()

DEFAULT_WINDOW_DAYS = 30
MAX_WINDOW_DAYS = 90
# Rows older than the TTL are gone, so no window reaches past it. Never below
# one day, or a TTL under a day would leave an empty window.
TTL_DAYS = max(1, QUERY_LOG_TTL_SECONDS // 86400)
# Per query. At the volume the TTL comment in config.py plans for, a 90-day
# $group is not free, and any signed-in user can ask for one 30 times a minute.
QUERY_TIMEOUT_MS = 5000
# MongoDB's ExceededMemoryLimit. An $addToSet accumulator cannot spill to disk,
# so one question asked in about 1.6M conversations stops the pipeline with it
# (docs/load-testing.md, #291). A shorter window fixes it like a timeout does.
# Code 292 is the same failure when allowDiskUse is false; nothing here sets
# that and the server default is true, so add it if that ever changes.
EXCEEDED_MEMORY_LIMIT = 146
# Hash groups per list that go into grouping. Two lists of 200 is at most 400
# texts in one embed_many call and about 0.7 s of similarity math.
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


def _question(row: dict[str, Any]) -> str | None:
    """The condensed question if one was logged, else the raw one, else None."""
    for field in ("sample_condensed", "sample_raw"):
        value = row.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _wording(row: dict[str, Any]) -> Wording:
    return Wording(
        question_hash=row.get("_id"),
        question=_question(row),
        count=int(row.get("count") or 0),
        refused=int(row.get("refused_count") or 0),
        sessions=frozenset(row.get("sessions") or ()),
        session_count=int(row.get("session_count") or 0),
    )


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
            dict(zip(missing, get_provider().embed_many(missing), strict=True)) if missing else {}
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


@router.get("/reports/gaps", dependencies=[Depends(require_auth)])
@limiter.limit("30/minute")
def coverage_gaps(
    request: Request,
    days: int = Query(DEFAULT_WINDOW_DAYS, ge=1, le=MAX_WINDOW_DAYS),
    top: int = Query(DEFAULT_TOP, ge=1, le=MAX_TOP),
):
    """Refused and repeated questions over the last ``days`` days, grouped by meaning."""
    days = min(days, TTL_DAYS)
    until = datetime.now(UTC)
    since = until - timedelta(days=days)
    window = {"created_at": {"$gte": since, "$lt": until}}

    limit = {"maxTimeMS": QUERY_TIMEOUT_MS}
    try:
        # Listed here, not lazily in the response, so a timeout while the
        # cursor is read is caught below too.
        refused_rows = list(
            query_logs_col.aggregate(
                wording_pipeline(since, until, CANDIDATE_LIMIT, refused_only=True), **limit
            )
        )
        all_rows = list(
            query_logs_col.aggregate(
                wording_pipeline(since, until, CANDIDATE_LIMIT, refused_only=False), **limit
            )
        )
        total = query_logs_col.count_documents(window, **limit)
        refused = query_logs_col.count_documents({**window, "refused": True}, **limit)
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

    refused_wordings = [_wording(row) for row in refused_rows]
    all_wordings = [_wording(row) for row in all_rows]
    texts = sorted({w.question for w in refused_wordings + all_wordings if w.question})
    vectors = _vectors(texts)
    if vectors is None:
        gap_groups, faq_groups = exact_groups(refused_wordings), exact_groups(all_wordings)
    else:
        gap_groups = group_by_meaning(refused_wordings, vectors, QUESTION_GROUP_THRESHOLD)
        faq_groups = group_by_meaning(all_wordings, vectors, QUESTION_GROUP_THRESHOLD)

    repeated = [group for group in faq_groups if group.conversations >= DEFAULT_MIN_REPEAT]
    return {
        "since": since.isoformat(),
        "until": until.isoformat(),
        "days": days,
        "grouping": "exact" if vectors is None else "meaning",
        "total": total,
        "refused": refused,
        "gaps": [_serialize(group) for group in _by_count(gap_groups)[:top]],
        "faq": [
            {**_serialize(group), "refused": group.refused}
            for group in _by_conversations(repeated)[:top]
        ],
    }
