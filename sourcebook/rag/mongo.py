"""Single shared MongoDB client for the whole application.

Both the API (`sourcebook/api/`) and the ingestion scripts (`sourcebook/rag/`) get their
collections from here. Before this module existed there were two independent
`MongoClient` objects per process — one in `api/db.py` and one in
`rag/rag_chain.py` — each with pymongo's default pool of 100 connections.

## Connection arithmetic — redo this before raising WEB_CONCURRENCY

    total connections = uvicorn workers x MONGO_MAX_POOL_SIZE

    4 workers x 20 = 80

MongoDB Atlas caps concurrent connections per cluster, and the free M0 tier caps
it in the low hundreds. Exceeding the cap fails as connection errors under load,
not as a clean error at startup, so the budget is worth keeping honest.

## Deployment constraint: do not use gunicorn --preload

`MongoClient` is not fork-safe. A client created before a process forks shares
socket state with its children, which corrupts connections in ways that surface
as intermittent errors under load rather than as a clean failure.

The client here is created on first use rather than at import, but note that
`api/db.py` binds its collection handles at module level, which triggers
that first use as soon as it is imported. So in practice the client is created
during application import, and the lazy accessor does not by itself make this
safe under a pre-forking server.

What makes it safe is the deployment model: uvicorn's `--workers` spawns fresh
processes that each import the app independently, so every worker builds its own
client after the fork. gunicorn with `--preload` imports the app once in the
master and then forks, which would share one client across workers. Do not use
it. If that ever changes, move the collection handles in `api/db.py` behind
accessor functions so nothing is bound at import.

Constructing a client performs no I/O — pymongo connects on the first real
operation — so import stays fast either way.
"""

import os
from collections.abc import Callable
from threading import Lock
from typing import TypeVar

from pymongo import MongoClient
from pymongo.client_session import ClientSession
from pymongo.collection import Collection
from pymongo.database import Database

from sourcebook.rag.config import MONGO_MAX_POOL_SIZE

_client: MongoClient | None = None
_lock = Lock()

_T = TypeVar("_T")
_transaction_support: bool | None = None


def get_client(*, server_selection_timeout_ms: int | None = None) -> MongoClient:
    """Return the process-wide client, creating it on first use.

    ``server_selection_timeout_ms`` only applies to the call that creates the
    client. The API never passes it and keeps pymongo's 30 s default; the
    query-log report CLI passes a short one so a wrong URI on a laptop fails
    in seconds instead of stalling.
    """
    global _client
    if _client is not None:
        return _client

    # Double-checked under a lock: FastAPI serves sync routes from a thread
    # pool, so two requests can race here on the very first call.
    with _lock:
        if _client is None:
            uri = os.getenv("MONGODB_URI")
            if not uri:
                raise RuntimeError(
                    "MONGODB_URI is not set. Copy .env.example to .env and fill it in."
                )
            options: dict[str, int] = {"maxPoolSize": MONGO_MAX_POOL_SIZE}
            if server_selection_timeout_ms is not None:
                options["serverSelectionTimeoutMS"] = server_selection_timeout_ms
            _client = MongoClient(uri, **options)
    return _client


def get_db() -> Database:
    """Return the configured application database."""
    return get_client()[os.getenv("MONGODB_DB", "policy_assistant")]


def get_collection(name: str) -> Collection:
    """Return one collection by name."""
    return get_db()[name]


def transactions_supported() -> bool:
    """Return whether the configured real MongoDB backend supports transactions.

    Fake/stub databases deliberately return False rather than pretending to
    provide transactional referential integrity.

    Real transactions require logical sessions and either a replica set or a
    mongos-backed sharded deployment.
    """
    global _transaction_support

    db = get_db()

    # The test/load-test harness replaces PyMongo Database with FakeDB.
    if not isinstance(db, Database):
        return False

    if _transaction_support is None:
        hello = db.command("hello")
        has_sessions = hello.get("logicalSessionTimeoutMinutes") is not None
        is_replica_set = bool(hello.get("setName"))
        is_sharded = hello.get("msg") == "isdbgrid"
        _transaction_support = bool(has_sessions and (is_replica_set or is_sharded))

    return _transaction_support


def run_transaction(callback: Callable[[ClientSession | None], _T]) -> _T:
    """Run a callback in a real transaction when the backend supports one.

    The callback receives a real ClientSession on a transaction-capable MongoDB
    backend. FakeMongo and other non-transactional backends receive ``None`` and
    retain their existing sequential semantics.
    """
    if not transactions_supported():
        return callback(None)

    with get_client().start_session() as session:
        return session.with_transaction(callback)


def reset_client() -> None:
    """Close and forget the client. For tests only."""
    global _client, _transaction_support

    with _lock:
        if _client is not None:
            _client.close()
            _client = None
        _transaction_support = None
