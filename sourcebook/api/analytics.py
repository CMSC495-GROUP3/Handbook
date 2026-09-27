"""Query logging — the substrate for "learn from interaction patterns".

One record per chat request. Nothing here changes an answer; it records what
happened so the system can be improved from evidence rather than from guesses.

Three things it is designed to answer:

1. **What can the assistant not answer?** Refusals grouped by question hash are
   a ranked list of the documents HR should write next. This is the closest
   thing the system has to learning: the corpus improves because the logs said
   where it was thin.
2. **What gets asked repeatedly?** High-count question hashes are the FAQ, and
   the questions worth curating a canonical answer for.
3. **Is the threshold set correctly?** The score distribution of answered versus
   refused questions is exactly what SIMILARITY_THRESHOLD should be tuned
   against, and it cannot be collected any other way.

## Logging never breaks a chat request

Every write is wrapped. An analytics failure must not turn a working answer into
an error, so failures are logged and swallowed. That is a deliberate exception
to the project's usual rule against swallowing errors: the alternative is losing
a user's answer to a bookkeeping problem.
"""

import logging
from datetime import UTC, datetime

from sourcebook.api.db import query_log_daily_col, query_log_sessions_col, query_logs_col
from sourcebook.api.logutil import normalize_log_token
from sourcebook.rag.cache import question_hash
from sourcebook.rag.query_log_rollup import record_ask

logger = logging.getLogger(__name__)

# Questions are stored to build the content-gap and FAQ lists. Truncated because
# the useful signal is in the first line, and the raw text is employee-entered.
MAX_QUESTION_LENGTH = 500


def log_query(
    *,
    session_id: str | None,
    question: str,
    condensed_question: str,
    passages: list[dict],
    refused: bool,
    sources: list[str],
    cache_hit: str | None,
    latency_ms: int,
    raw_best_score: float | None = None,
) -> None:
    """Record one chat request. Never raises.

    `cache_hit` is "answer", "embedding", or None, so the measured hit rate can
    be reported — that number is what makes the cost projection in
    docs/load-testing.md defensible.
    """
    # Sanitised once, up front, so the stored record and the failure log line
    # below carry the same value. A missing session stays None in Mongo.
    safe_session = None if session_id is None else normalize_log_token(session_id)
    created_at = datetime.now(UTC)
    try:
        raw = question[:MAX_QUESTION_LENGTH]
        condensed = condensed_question[:MAX_QUESTION_LENGTH]
        # Groups repeats of the same question regardless of casing/spacing.
        hashed = question_hash(condensed_question)
        scores = [p.get("score", 0.0) for p in passages]
        query_logs_col.insert_one(
            {
                "created_at": created_at,
                "session_id": safe_session,
                "question_raw": raw,
                "question_condensed": condensed,
                "question_hash": hashed,
                "best_score": max(scores) if scores else None,
                # Best score for the question as asked when a follow-up ran a
                # second retrieval, else None. A refused row whose best_score
                # clears the threshold but whose raw_best_score does not was
                # blocked by the gate on the question as asked (issue #189),
                # not by weak retrieval; keep the two apart when tuning.
                "raw_best_score": raw_best_score,
                "mean_score": (sum(scores) / len(scores)) if scores else None,
                "passage_count": len(passages),
                "refused": refused,
                "sources": sources,
                "cache_hit": cache_hit,
                "latency_ms": latency_ms,
                # Counted in the What People Ask rollup below, so the
                # rollup's backfill skips it.
                "rolled_up": True,
            }
        )
    except Exception:
        logger.exception("Failed to write query log for session %s", safe_session or "-")
        return
    # Separate from the row above, so a rollup failure still keeps the row.
    # A failure here leaves this ask out of the report's counts; the offline
    # report, which reads the rows, still has it.
    try:
        record_ask(
            query_log_daily_col,
            query_log_sessions_col,
            created_at=created_at,
            session_id=safe_session,
            question_hash=hashed,
            question_raw=raw,
            question_condensed=condensed,
            refused=refused,
        )
    except Exception:
        logger.exception("Failed to count query for session %s", safe_session or "-")
