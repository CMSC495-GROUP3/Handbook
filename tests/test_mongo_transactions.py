import pytest

from sourcebook.rag import mongo


class _RealLikeDatabase:
    def __init__(self, hello: dict):
        self.hello = hello
        self.calls = 0

    def command(self, name: str) -> dict:
        assert name == "hello"
        self.calls += 1
        return self.hello


class _Session:
    def __init__(self):
        self.transaction_calls = 0

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def with_transaction(self, callback):
        self.transaction_calls += 1
        return callback(self)


class _Client:
    def __init__(self, session):
        self.session = session

    def start_session(self):
        return self.session


def test_transactions_supported_is_false_for_stub(monkeypatch):
    monkeypatch.setattr(mongo, "_transaction_support", None)
    monkeypatch.setattr(mongo, "get_db", object)

    assert mongo.transactions_supported() is False


def test_transactions_supported_detects_replica_set_and_caches(monkeypatch):
    db = _RealLikeDatabase(
        {
            "logicalSessionTimeoutMinutes": 30,
            "setName": "replica-set",
        }
    )

    monkeypatch.setattr(mongo, "Database", _RealLikeDatabase)
    monkeypatch.setattr(mongo, "get_db", lambda: db)
    monkeypatch.setattr(mongo, "_transaction_support", None)

    assert mongo.transactions_supported() is True
    assert mongo.transactions_supported() is True
    assert db.calls == 1


def test_transactions_supported_rejects_standalone(monkeypatch):
    db = _RealLikeDatabase({"logicalSessionTimeoutMinutes": 30})

    monkeypatch.setattr(mongo, "Database", _RealLikeDatabase)
    monkeypatch.setattr(mongo, "get_db", lambda: db)
    monkeypatch.setattr(mongo, "_transaction_support", None)

    assert mongo.transactions_supported() is False


def test_run_transaction_stub_does_not_start_session(monkeypatch):
    monkeypatch.setattr(mongo, "transactions_supported", lambda: False)

    def unexpected_client():
        pytest.fail("stub mode must not start a MongoDB session")

    monkeypatch.setattr(mongo, "get_client", unexpected_client)

    seen = []
    result = mongo.run_transaction(lambda session: seen.append(session) or "done")

    assert result == "done"
    assert seen == [None]


def test_run_transaction_uses_real_session(monkeypatch):
    session = _Session()
    client = _Client(session)

    monkeypatch.setattr(mongo, "transactions_supported", lambda: True)
    monkeypatch.setattr(mongo, "get_client", lambda: client)

    seen = []
    result = mongo.run_transaction(lambda active: seen.append(active) or "done")

    assert result == "done"
    assert seen == [session]
    assert session.transaction_calls == 1
