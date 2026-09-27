"""The What People Ask rollup: per-day counts kept as each ask is logged (#291)."""

import logging
from datetime import UTC, datetime, timedelta, timezone

import pytest
from conftest import FAKE_DB, make_passages
from pymongo.errors import ExecutionTimeout, OperationFailure

from sourcebook.api import analytics
from sourcebook.rag import query_log_rollup
from sourcebook.rag.query_log_rollup import (
    DAILY_COLLECTION,
    SESSIONS_COLLECTION,
    backfill,
    read_report,
    record_ask,
    session_samples,
    utc_day,
    window_start,
)

NOW = datetime(2026, 9, 27, 15, 30, tzinfo=UTC)


def daily():
    return FAKE_DB[DAILY_COLLECTION]


def ask(question_hash: str, session_id: str | None, *, at: datetime = NOW, refused=False):
    record_ask(
        daily(),
        FAKE_DB[SESSIONS_COLLECTION],
        created_at=at,
        session_id=session_id,
        question_hash=question_hash,
        question_raw=f"{question_hash}?",
        question_condensed=f"{question_hash}?",
        refused=refused,
    )


def report(since=NOW - timedelta(days=89), until=NOW, *, min_sessions=2, limit=10):
    return read_report(daily(), since, until, limit=limit, min_sessions=min_sessions)


def ranked(since=NOW - timedelta(days=89), until=NOW, *, refused_only=False, min_sessions=1):
    """(hash, asks, conversations) for one list: the manager's when
    ``min_sessions`` is over 1, as the route picks it."""
    name = ("manager_" if min_sessions > 1 else "") + ("gaps" if refused_only else "faq")
    rows = report(since, until, min_sessions=max(min_sessions, 2))[name]
    return [(row["_id"], row["count"], row["session_count"]) for row in rows]


def test_window_start_is_whole_utc_days_including_today():
    assert window_start(NOW, 1) == datetime(2026, 9, 27, tzinfo=UTC)
    assert window_start(NOW, 7) == datetime(2026, 9, 21, tzinfo=UTC)


def test_utc_day_is_the_utc_date_not_the_local_one():
    # 20:00 on the 27th in New York is 00:00 on the 28th in UTC.
    new_york = timezone(timedelta(hours=-4))
    assert utc_day(datetime(2026, 9, 27, 20, 0, tzinfo=new_york)) == datetime(
        2026, 9, 28, tzinfo=UTC
    )


def test_repeats_in_one_conversation_are_one_conversation():
    for _ in range(3):
        ask("pto", "a")
    ask("pto", "b")

    assert ranked() == [("pto", 4, 2)]


def test_a_conversation_counts_once_across_days_on_its_first_day():
    ask("pto", "a", at=NOW - timedelta(days=3))
    ask("pto", "a", at=NOW)

    [first, second] = sorted(daily().find({}), key=lambda doc: doc["day"])
    assert (first["count"], first["session_count"]) == (1, 1)
    assert (second["count"], second["session_count"]) == (1, 0)
    assert ranked() == [("pto", 2, 1)]


def test_a_window_after_the_first_ask_undercounts_and_never_overcounts():
    """The documented trade: the conversation's later ask is in the window,
    its first is not, so the window counts the ask but not the conversation."""
    ask("pto", "a", at=NOW - timedelta(days=10))
    ask("pto", "a", at=NOW)

    assert ranked(since=window_start(NOW, 7)) == [("pto", 1, 0)]


def test_refused_conversations_are_counted_apart():
    ask("pto", "a", refused=False)
    ask("pto", "a", refused=True)
    ask("pto", "b", refused=True)

    assert ranked(refused_only=True) == [("pto", 2, 2)]
    assert ranked() == [("pto", 3, 2)]


def test_refused_only_leaves_out_questions_never_refused():
    ask("answered", "a")
    ask("gap", "b", refused=True)

    assert [row[0] for row in ranked(refused_only=True)] == ["gap"]


def test_min_sessions_drops_wordings_before_the_cap():
    ask("once", "a")
    ask("twice", "a")
    ask("twice", "b")

    assert ranked(min_sessions=2) == [("twice", 2, 2)]


def test_rows_without_a_session_count_as_one_conversation():
    ask("pto", None)
    ask("pto", None)

    assert ranked() == [("pto", 2, 1)]


def test_totals_sum_the_days():
    ask("pto", "a", at=NOW - timedelta(days=2))
    ask("gap", "b", refused=True)
    result = report()

    assert (result["total"], result["refused"]) == (2, 1)


def test_an_empty_window_has_empty_lists_and_zero_totals():
    ask("pto", "a", at=NOW - timedelta(days=20))

    result = report(since=window_start(NOW, 7))
    assert result == {
        "gaps": [],
        "faq": [],
        "manager_gaps": [],
        "manager_faq": [],
        "total": 0,
        "refused": 0,
    }


def test_lists_rank_and_cap_as_the_route_expects():
    # "busy" is asked most in one conversation; "wide" in the most conversations.
    for _ in range(4):
        ask("busy", "a", refused=True)
    for session in ("a", "b", "c"):
        ask("wide", session, refused=True)
    ask("rare", "z")

    result = report(limit=1)
    assert [row["_id"] for row in result["gaps"]] == ["busy"]
    assert [row["_id"] for row in result["faq"]] == ["wide"]
    assert [row["_id"] for row in result["manager_gaps"]] == ["wide"]


def test_rows_carry_sample_text_from_the_earliest_day_in_the_window():
    record_ask(
        daily(),
        FAKE_DB[SESSIONS_COLLECTION],
        created_at=NOW - timedelta(days=3),
        session_id="a",
        question_hash="pto",
        question_raw="first wording",
        question_condensed="first condensed",
        refused=False,
    )
    ask("pto", "b")

    [row] = report()["faq"]
    assert (row["sample_raw"], row["sample_condensed"]) == ("first wording", "first condensed")


def test_session_ids_are_capped_per_day(monkeypatch):
    monkeypatch.setattr(query_log_rollup, "ROLLUP_SESSION_SAMPLE", 2)
    for session in ("a", "b", "c"):
        ask("pto", session)

    [doc] = daily().find({})
    assert (doc["session_count"], doc["sessions"]) == (3, ["a", "b"])


def test_session_samples_union_the_days_in_the_window():
    ask("pto", "old", at=NOW - timedelta(days=20))
    ask("pto", "a", at=NOW - timedelta(days=2))
    ask("pto", "b", at=NOW, refused=True)

    since = window_start(NOW, 7)
    assert session_samples(daily(), since, NOW, ["pto"], refused_only=False) == {
        "pto": frozenset({"a", "b"})
    }
    assert session_samples(daily(), since, NOW, ["pto"], refused_only=True) == {
        "pto": frozenset({"b"})
    }
    assert session_samples(daily(), since, NOW, [], refused_only=False) == {}


# ── Logging ───────────────────────────────────────────────────────────────────


def _log(**overrides):
    fields = dict(
        session_id="s1",
        question="How much PTO do I get?",
        condensed_question="How much PTO do I get?",
        passages=make_passages(0.80),
        refused=False,
        sources=["PTO Policy"],
        cache_hit=None,
        latency_ms=120,
    )
    fields.update(overrides)
    analytics.log_query(**fields)


def test_log_query_records_the_ask_and_marks_the_row():
    _log()
    _log(refused=True)

    [row, _] = FAKE_DB["query_logs"].find({})
    [doc] = daily().find({})
    assert row["rolled_up"] is True
    assert (doc["count"], doc["refused_count"], doc["session_count"]) == (2, 1, 1)
    assert doc["question_hash"] == row["question_hash"]


def test_a_rollup_failure_keeps_the_row_and_never_raises(monkeypatch, caplog):
    def broken(*_args, **_kwargs):
        raise RuntimeError("rollup down")

    monkeypatch.setattr(analytics, "record_ask", broken)
    with caplog.at_level(logging.ERROR):
        _log()

    assert FAKE_DB["query_logs"].count_documents({}) == 1
    assert "Failed to count query" in caplog.text


def test_a_failed_row_is_not_counted(monkeypatch):
    def broken(*_args, **_kwargs):
        raise RuntimeError("log down")

    monkeypatch.setattr(analytics.query_logs_col, "insert_one", broken)
    _log()

    assert daily().count_documents({}) == 0


# ── Backfill ──────────────────────────────────────────────────────────────────


def _row(session, at, **fields):
    return {
        "created_at": at,
        "session_id": session,
        "question_raw": "pto?",
        "question_condensed": "pto?",
        "question_hash": "pto",
        "refused": False,
        **fields,
    }


def test_backfill_records_old_rows_oldest_first_and_once():
    logs = FAKE_DB["query_logs"]
    # Inserted newest first; the backfill must still count "a" on its first day.
    logs.insert_one(_row("a", NOW))
    logs.insert_one(_row("a", NOW - timedelta(days=5)))
    logs.insert_one(_row("b", NOW, rolled_up=True))

    assert backfill(logs, daily(), FAKE_DB[SESSIONS_COLLECTION]) == 2
    assert backfill(logs, daily(), FAKE_DB[SESSIONS_COLLECTION]) == 0

    days = {doc["day"]: doc["session_count"] for doc in daily().find({})}
    assert days == {utc_day(NOW - timedelta(days=5)): 1, utc_day(NOW): 0}
    assert logs.count_documents({"rolled_up": True}) == 3


def test_backfill_cli_needs_the_flag():
    with pytest.raises(SystemExit):
        query_log_rollup.main([])


# ── Review follow-ups ─────────────────────────────────────────────────────────


def test_a_missing_covering_index_reads_the_day_documents(monkeypatch, caplog):
    """A hint naming a missing index raises BadValue; the report still answers."""
    ask("pto", "a")
    real = daily().aggregate
    calls = []

    def aggregate(pipeline, **kwargs):
        calls.append(kwargs)
        if "hint" in kwargs:
            raise OperationFailure("hint provided does not correspond to an existing index", code=2)
        return real(pipeline, **kwargs)

    monkeypatch.setattr(daily(), "aggregate", aggregate)
    with caplog.at_level(logging.WARNING):
        result = report()

    assert [row["_id"] for row in result["faq"]] == ["pto"]
    assert [("hint" in kwargs) for kwargs in calls] == [True, False]
    assert "Covering index" in caplog.text


def test_other_bad_values_are_not_retried(monkeypatch):
    def aggregate(_pipeline, **_kwargs):
        raise OperationFailure("$match needs an object", code=2)

    monkeypatch.setattr(daily(), "aggregate", aggregate)
    with pytest.raises(OperationFailure):
        report()


def test_sample_lookups_share_one_time_budget(monkeypatch):
    """max_time_ms bounds every lookup together, so the refresh lease can
    budget for them."""
    for name in ("a", "b", "c"):
        ask(name, "s")
    # The deadline is set at 0.0 s; the third lookup starts at 1.2 s, past it.
    clock = iter([0.0, 0.0, 0.6, 1.2])
    monkeypatch.setattr(query_log_rollup.time, "monotonic", lambda: next(clock))

    with pytest.raises(ExecutionTimeout):
        read_report(
            daily(), NOW - timedelta(days=89), NOW, limit=10, min_sessions=2, max_time_ms=1000
        )


def test_a_backfill_interrupted_before_marking_never_counts_a_row_twice(monkeypatch):
    logs = FAKE_DB["query_logs"]
    logs.insert_one(_row("a", NOW))
    real = logs.update_one

    def crash(*_args, **_kwargs):
        raise RuntimeError("killed after counting, before marking")

    monkeypatch.setattr(logs, "update_one", crash)
    with pytest.raises(RuntimeError):
        backfill(logs, daily(), FAKE_DB[SESSIONS_COLLECTION])
    monkeypatch.setattr(logs, "update_one", real)

    assert backfill(logs, daily(), FAKE_DB[SESSIONS_COLLECTION]) == 0
    [doc] = daily().find({})
    assert doc["count"] == 1
    assert logs.count_documents({"rolled_up": True}) == 1
