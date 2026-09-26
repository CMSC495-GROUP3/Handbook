"""Coverage report — the query log's read side, for the What People Ask page.

Every chat request writes a ``query_logs`` row (see ``sourcebook.api.analytics``).
``sourcebook.rag.query_log_reports`` already ranks those rows for an operator at
a terminal on the EC2 host. This route runs the same two ranking pipelines for
the web app, so Human Resources can see which questions the corpus does not
cover without a shell:

- ``gaps``: refused questions grouped by ``question_hash``, most frequent
  first. Each is a candidate for a new or clearer policy.
- ``faq``: questions asked in at least two conversations, answered or not,
  most conversations first, with how many of those asks were refused.

The window counts back ``days`` from now, at most 90. ``query_logs`` rows
expire after ``QUERY_LOG_TTL_SECONDS``, so a window longer than the TTL is
shortened to it and the response's ``days`` says what was used. The bound on
the parameter stays fixed, so a short TTL cannot turn every request into a 422.

Question text is the logged ``question_condensed`` (the standalone rewrite that
the hash groups on), falling back to the truncated ``question_raw``. Nothing
here writes, and no session id leaves the server. Only a session opened with
the HR password may read it (``require_hr``), because the text is what
employees typed.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pymongo.errors import ExecutionTimeout

from sourcebook.api.db import query_logs_col
from sourcebook.api.limiter import limiter
from sourcebook.api.routes.deps import HR_ONLY_RESPONSES, require_hr
from sourcebook.rag.config import QUERY_LOG_TTL_SECONDS
from sourcebook.rag.query_log_reports import (
    DEFAULT_MIN_REPEAT,
    DEFAULT_TOP,
    MAX_TOP,
    content_gap_pipeline,
    faq_pipeline,
)

router = APIRouter()

DEFAULT_WINDOW_DAYS = 30
MAX_WINDOW_DAYS = 90
# Rows older than the TTL are gone, so no window reaches past it. Never below
# one day, or a TTL under a day would leave an empty window.
TTL_DAYS = max(1, QUERY_LOG_TTL_SECONDS // 86400)
# Per query. At the volume the TTL comment in config.py plans for, a 90-day
# $group is not free, and an HR session can ask for one 30 times a minute.
QUERY_TIMEOUT_MS = 5000


def _question(row: dict[str, Any]) -> str | None:
    """The condensed question if one was logged, else the raw one, else None."""
    for field in ("sample_condensed", "sample_raw"):
        value = row.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _group(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "question_hash": row.get("_id"),
        "question": _question(row),
        "count": int(row.get("count") or 0),
        "conversations": int(row.get("session_count") or 0),
    }


@router.get("/reports/gaps", responses=HR_ONLY_RESPONSES, dependencies=[Depends(require_hr)])
@limiter.limit("30/minute")
def coverage_gaps(
    request: Request,
    days: int = Query(DEFAULT_WINDOW_DAYS, ge=1, le=MAX_WINDOW_DAYS),
    top: int = Query(DEFAULT_TOP, ge=1, le=MAX_TOP),
):
    """Refused and repeated questions over the last ``days`` days."""
    days = min(days, TTL_DAYS)
    until = datetime.now(UTC)
    since = until - timedelta(days=days)
    window = {"created_at": {"$gte": since, "$lt": until}}

    limit = {"maxTimeMS": QUERY_TIMEOUT_MS}
    try:
        # Listed here, not lazily in the response, so a timeout while the
        # cursor is read is caught below too.
        gaps = list(query_logs_col.aggregate(content_gap_pipeline(since, until, top), **limit))
        faq = list(
            query_logs_col.aggregate(faq_pipeline(since, until, top, DEFAULT_MIN_REPEAT), **limit)
        )
        total = query_logs_col.count_documents(window, **limit)
        refused = query_logs_col.count_documents({**window, "refused": True}, **limit)
    except ExecutionTimeout:
        raise HTTPException(
            status_code=503,
            detail="This report took too long. Try a shorter window.",
        ) from None
    return {
        "since": since.isoformat(),
        "until": until.isoformat(),
        "days": days,
        "total": total,
        "refused": refused,
        "gaps": [_group(row) for row in gaps],
        "faq": [{**_group(row), "refused": int(row.get("refused_count") or 0)} for row in faq],
    }
