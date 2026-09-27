"""scripts/purge_ownerless_conversations.py against the fake Mongo."""

import pytest
from conftest import FAKE_DB, OWNER

from scripts import purge_ownerless_conversations as purge


@pytest.fixture(autouse=True)
def seeded():
    for name in ("conversations", "projects", "escalations"):
        FAKE_DB[name].delete_many({})
    FAKE_DB["conversations"].insert_one({"session_id": "old", "messages": []})
    FAKE_DB["conversations"].insert_one({"session_id": "mine", "owner": OWNER, "messages": []})
    FAKE_DB["projects"].insert_one({"project_id": "old-project"})
    FAKE_DB["projects"].insert_one({"project_id": "my-project", "owner": OWNER})
    FAKE_DB["escalations"].insert_one({"escalation_id": "e1", "session_id": "old"})
    yield
    for name in ("conversations", "projects", "escalations"):
        FAKE_DB[name].delete_many({})


def _ids(collection: str, key: str) -> list[str]:
    return sorted(doc[key] for doc in FAKE_DB[collection].find({}))


def test_without_delete_it_only_counts(capsys):
    purge.main([])

    assert "1 conversations and 1 projects have no owner" in capsys.readouterr().out
    assert _ids("conversations", "session_id") == ["mine", "old"]
    assert _ids("projects", "project_id") == ["my-project", "old-project"]


def test_delete_removes_only_ownerless_records(capsys):
    purge.main(["--delete"])

    assert "Deleted 1 conversations and 1 projects" in capsys.readouterr().out
    assert _ids("conversations", "session_id") == ["mine"]
    assert _ids("projects", "project_id") == ["my-project"]
    # HR Requests reads escalation records, which keep their copied question.
    assert _ids("escalations", "escalation_id") == ["e1"]
