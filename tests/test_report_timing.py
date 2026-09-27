"""The report timing script must not drop a real query log (#296 review)."""

import pytest

from scripts.loadtest import report_timing, rollup_timing


@pytest.mark.parametrize("db", ["policy_assistant", "sourcebook", "timing"])
def test_refuses_a_database_without_the_scratch_prefix(db, monkeypatch):
    def no_connection(*_args, **_kwargs):
        raise AssertionError("connected before checking --db")

    monkeypatch.setattr(report_timing, "MongoClient", no_connection)

    with pytest.raises(SystemExit):
        report_timing.main(["--db", db])


@pytest.mark.parametrize("db", ["policy_assistant", "sourcebook", "timing"])
def test_the_rollup_timing_refuses_a_database_without_the_scratch_prefix(db, monkeypatch):
    def no_connection(*_args, **_kwargs):
        raise AssertionError("connected before checking --db")

    monkeypatch.setattr(rollup_timing, "MongoClient", no_connection)

    with pytest.raises(SystemExit):
        rollup_timing.main(["--db", db])


def test_the_rollup_timing_seeds_documents_the_route_can_rank(monkeypatch):
    """The seeded shape must be what record_ask writes, or the timing measures
    a different collection. One small day, through the fake."""
    from datetime import UTC, datetime

    from scripts.loadtest.fakemongo import FakeCollection
    from sourcebook.rag.query_log_rollup import read_report, window_start

    col = FakeCollection()
    col.drop = lambda: None
    col.insert_many = lambda docs, ordered=True: FakeCollection.insert_many(col, docs)
    args = rollup_timing.argparse.Namespace(
        seed=1,
        days=2,
        asks_per_day=1000,
        hot_share=0.5,
        questions_per_day=3,
        new_share=0.0,
        refused_share=0.5,
    )
    now = datetime.now(UTC)
    rollup_timing.seed(col, args, now)

    rows = read_report(col, window_start(now, 2), now, limit=10, min_sessions=3)["faq"]
    assert rows[0]["_id"] == rollup_timing.HOT_HASH
    assert rows[0]["count"] == 1000
    assert rows[0]["session_count"] == 800
