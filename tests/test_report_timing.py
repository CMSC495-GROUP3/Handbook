"""The report timing script must not drop a real query log (#296 review)."""

import pytest

from scripts.loadtest import report_timing


@pytest.mark.parametrize("db", ["policy_assistant", "sourcebook", "timing"])
def test_refuses_a_database_without_the_scratch_prefix(db, monkeypatch):
    def no_connection(*_args, **_kwargs):
        raise AssertionError("connected before checking --db")

    monkeypatch.setattr(report_timing, "MongoClient", no_connection)

    with pytest.raises(SystemExit):
        report_timing.main(["--db", db])
