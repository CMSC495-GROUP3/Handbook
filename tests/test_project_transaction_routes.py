from types import SimpleNamespace

import pytest
from conftest import OWNER
from fastapi import HTTPException

from sourcebook.api.routes import conversations, projects
from sourcebook.api.routes.deps import Principal

PRINCIPAL = Principal(cred="APP_PASSWORD_HASH", owner=OWNER)


def test_create_assignment_uses_same_transaction_session(monkeypatch):
    session = object()
    calls = []

    monkeypatch.setattr(
        conversations,
        "run_transaction",
        lambda callback: callback(session),
    )

    def project_update_one(query, update, *, session=None):
        calls.append(("guard", session))
        assert query == {"project_id": "project-1", "owner": OWNER}
        assert update == {"$inc": {"_assignment_guard": 1}}
        return SimpleNamespace(matched_count=1)

    def conversation_insert_one(doc, *, session=None):
        calls.append(("insert", session))
        return SimpleNamespace(inserted_id="conversation-1")

    monkeypatch.setattr(conversations.projects_col, "update_one", project_update_one)
    monkeypatch.setattr(
        conversations.conversations_col,
        "insert_one",
        conversation_insert_one,
    )

    body = conversations.CreateConversationRequest(
        title="Assigned conversation",
        project_id="project-1",
    )

    created = conversations.create_conversation(body, PRINCIPAL)

    assert created["project_id"] == "project-1"
    assert calls == [
        ("guard", session),
        ("insert", session),
    ]


def test_reassignment_uses_same_transaction_session(monkeypatch):
    session = object()
    calls = []

    monkeypatch.setattr(
        conversations,
        "run_transaction",
        lambda callback: callback(session),
    )

    def project_update_one(query, update, *, session=None):
        calls.append(("guard", session))
        assert query == {"project_id": "project-2", "owner": OWNER}
        assert update == {"$inc": {"_assignment_guard": 1}}
        return SimpleNamespace(matched_count=1)

    def conversation_update_one(query, update, *, session=None):
        calls.append(("update", session))
        assert query == {"session_id": "conversation-1", "owner": OWNER}
        assert update["$set"]["project_id"] == "project-2"
        return SimpleNamespace(matched_count=1)

    monkeypatch.setattr(conversations.projects_col, "update_one", project_update_one)
    monkeypatch.setattr(
        conversations.conversations_col,
        "update_one",
        conversation_update_one,
    )

    body = conversations.UpdateConversationRequest(project_id="project-2")

    result = conversations.update_conversation("conversation-1", body, PRINCIPAL)

    assert result == {"ok": True}
    assert calls == [
        ("guard", session),
        ("update", session),
    ]


def test_transactional_delete_and_unassign_share_session(monkeypatch):
    session = object()
    calls = []

    monkeypatch.setattr(
        projects,
        "run_transaction",
        lambda callback: callback(session),
    )

    def project_delete_one(query, *, session=None):
        calls.append(("delete", session))
        assert query == {"project_id": "project-1", "owner": OWNER}
        return SimpleNamespace(deleted_count=1)

    def conversation_update_many(query, update, *, session=None):
        calls.append(("unassign", session))
        assert query == {"project_id": "project-1", "owner": OWNER}
        assert update == {"$set": {"project_id": None}}
        return SimpleNamespace(modified_count=1)

    monkeypatch.setattr(projects.projects_col, "delete_one", project_delete_one)
    monkeypatch.setattr(
        projects.conversations_col,
        "update_many",
        conversation_update_many,
    )

    result = projects.delete_project("project-1", PRINCIPAL)

    assert result == {"ok": True}
    assert calls == [
        ("delete", session),
        ("unassign", session),
    ]


def test_transactional_assignment_fails_closed_when_project_is_gone(monkeypatch):
    session = object()

    monkeypatch.setattr(
        conversations,
        "run_transaction",
        lambda callback: callback(session),
    )

    monkeypatch.setattr(
        conversations.projects_col,
        "update_one",
        lambda *_args, **_kwargs: SimpleNamespace(matched_count=0),
    )

    def unexpected_insert(*_args, **_kwargs):
        pytest.fail("conversation must not be written after project validation fails")

    monkeypatch.setattr(
        conversations.conversations_col,
        "insert_one",
        unexpected_insert,
    )

    body = conversations.CreateConversationRequest(
        title="Should fail",
        project_id="missing-project",
    )

    with pytest.raises(HTTPException) as exc:
        conversations.create_conversation(body, PRINCIPAL)

    assert exc.value.status_code == 404
    assert exc.value.detail == "Project not found."
