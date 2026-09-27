"""Opt-in regression tests for real MongoDB transaction behavior.

These tests require a transaction-capable MongoDB deployment such as an Atlas
replica set or mongos-backed sharded cluster.

They are skipped unless both environment variables are set:

    MONGODB_TX_TEST_URI
    MONGODB_TX_TEST_DB

Temporary collections with unique names are created and removed for each test.
"""

import os
import threading
import uuid

import pytest
from fastapi import HTTPException
from pymongo import MongoClient

from sourcebook.api.routes import conversations, projects
from sourcebook.rag import mongo


class _GateInsertCollection:
    """Pause the first transactional insert until the test releases it."""

    def __init__(self, collection, started: threading.Event, release: threading.Event):
        self._collection = collection
        self._started = started
        self._release = release
        self._paused = False

    def insert_one(self, document, **kwargs):
        if kwargs.get("session") is not None and not self._paused:
            self._paused = True
            self._started.set()
            if not self._release.wait(timeout=10):
                raise RuntimeError("timed out waiting to release transactional insert")

        return self._collection.insert_one(document, **kwargs)

    def __getattr__(self, name):
        return getattr(self._collection, name)


class _SignalDeleteCollection:
    """Signal immediately before a transactional project delete is attempted."""

    def __init__(self, collection, started: threading.Event):
        self._collection = collection
        self._started = started

    def delete_one(self, query, **kwargs):
        if kwargs.get("session") is not None:
            self._started.set()

        return self._collection.delete_one(query, **kwargs)

    def __getattr__(self, name):
        return getattr(self._collection, name)


class _FailTransactionalUpdateMany:
    """Force delete+unassign to fail after the project delete is staged."""

    def __init__(self, collection):
        self._collection = collection

    def update_many(self, query, update, **kwargs):
        if kwargs.get("session") is not None:
            raise RuntimeError("forced transactional unassign failure")

        return self._collection.update_many(query, update, **kwargs)

    def __getattr__(self, name):
        return getattr(self._collection, name)


@pytest.fixture
def transaction_backend(monkeypatch):
    uri = os.getenv("MONGODB_TX_TEST_URI")
    db_name = os.getenv("MONGODB_TX_TEST_DB")

    if not uri or not db_name:
        pytest.skip(
            "set MONGODB_TX_TEST_URI and MONGODB_TX_TEST_DB to run real MongoDB transaction tests"
        )

    client = MongoClient(uri, serverSelectionTimeoutMS=5000)

    hello = client.admin.command("hello")
    has_sessions = hello.get("logicalSessionTimeoutMinutes") is not None
    is_replica_set = bool(hello.get("setName"))
    is_sharded = hello.get("msg") == "isdbgrid"

    if not (has_sessions and (is_replica_set or is_sharded)):
        client.close()
        pytest.fail("configured MongoDB backend does not support transactions")

    suffix = uuid.uuid4().hex
    db = client[db_name]

    projects_col = db[f"_sourcebook_tx_projects_{suffix}"]
    conversations_col = db[f"_sourcebook_tx_conversations_{suffix}"]

    monkeypatch.setattr(mongo, "transactions_supported", lambda: True)
    monkeypatch.setattr(mongo, "get_client", lambda: client)

    monkeypatch.setattr(conversations, "projects_col", projects_col)
    monkeypatch.setattr(conversations, "conversations_col", conversations_col)
    monkeypatch.setattr(projects, "projects_col", projects_col)
    monkeypatch.setattr(projects, "conversations_col", conversations_col)

    try:
        yield projects_col, conversations_col
    finally:
        projects_col.drop()
        conversations_col.drop()
        client.close()


def test_assign_during_concurrent_delete_leaves_no_orphan(
    transaction_backend,
    monkeypatch,
):
    projects_col, conversations_col = transaction_backend

    project_id = "concurrent-project"
    projects_col.insert_one(
        {
            "project_id": project_id,
            "name": "Concurrent project",
        }
    )

    insert_started = threading.Event()
    release_insert = threading.Event()
    delete_started = threading.Event()

    monkeypatch.setattr(
        conversations,
        "conversations_col",
        _GateInsertCollection(
            conversations_col,
            insert_started,
            release_insert,
        ),
    )
    monkeypatch.setattr(
        projects,
        "projects_col",
        _SignalDeleteCollection(
            projects_col,
            delete_started,
        ),
    )

    results = {}
    errors = {}

    def create_worker():
        try:
            results["create"] = conversations.create_conversation(
                conversations.CreateConversationRequest(
                    title="Concurrent assignment",
                    project_id=project_id,
                )
            )
        except Exception as exc:
            errors["create"] = exc

    def delete_worker():
        try:
            results["delete"] = projects.delete_project(project_id)
        except Exception as exc:
            errors["delete"] = exc

    create_thread = threading.Thread(target=create_worker)
    delete_thread = threading.Thread(target=delete_worker)

    create_thread.start()

    assert insert_started.wait(timeout=10), "assignment transaction did not reach the gated insert"

    delete_thread.start()

    assert delete_started.wait(timeout=10), "delete transaction did not reach the project delete"

    release_insert.set()

    create_thread.join(timeout=15)
    delete_thread.join(timeout=15)

    assert not create_thread.is_alive()
    assert not delete_thread.is_alive()

    assert "delete" not in errors
    assert results.get("delete") == {"ok": True}

    if "create" in errors:
        assert isinstance(errors["create"], HTTPException)
        assert errors["create"].status_code == 404
    else:
        assert results["create"]["project_id"] == project_id

    assert projects_col.find_one({"project_id": project_id}) is None
    assert conversations_col.count_documents({"project_id": project_id}) == 0


def test_delete_and_unassign_roll_back_together_on_failure(
    transaction_backend,
    monkeypatch,
):
    projects_col, conversations_col = transaction_backend

    project_id = "rollback-project"

    projects_col.insert_one(
        {
            "project_id": project_id,
            "name": "Rollback project",
        }
    )
    conversations_col.insert_one(
        {
            "session_id": "rollback-conversation",
            "title": "Rollback conversation",
            "project_id": project_id,
            "messages": [],
        }
    )

    monkeypatch.setattr(
        projects,
        "conversations_col",
        _FailTransactionalUpdateMany(conversations_col),
    )

    with pytest.raises(RuntimeError, match="forced transactional unassign failure"):
        projects.delete_project(project_id)

    assert projects_col.find_one({"project_id": project_id}) is not None

    stored = conversations_col.find_one({"session_id": "rollback-conversation"})
    assert stored is not None
    assert stored["project_id"] == project_id
