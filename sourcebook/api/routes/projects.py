"""Project CRUD endpoints. Like conversations, each project belongs to the owner
id of the session that created it, and other sessions get 404."""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from pymongo.client_session import ClientSession

from sourcebook.api.db import conversations_col, projects_col
from sourcebook.api.routes.deps import Principal, require_auth
from sourcebook.rag.mongo import run_transaction

router = APIRouter()

PROJECT_NAME_MAX_LENGTH = 100


def _normalize_project_name(value: str) -> str:
    """Strip and collapse whitespace; reject empty or oversized names."""
    normalized = " ".join(value.split())
    if not normalized:
        raise ValueError("name must not be blank")
    if len(normalized) > PROJECT_NAME_MAX_LENGTH:
        raise ValueError(f"name must be at most {PROJECT_NAME_MAX_LENGTH} characters")
    return normalized


class CreateProjectRequest(BaseModel):
    name: str = Field(max_length=PROJECT_NAME_MAX_LENGTH)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return _normalize_project_name(value)


@router.get("/projects")
def list_projects(principal: Principal = Depends(require_auth)):
    docs = projects_col.find(
        {"owner": principal.owner},
        {"_id": 0, "_assignment_guard": 0, "owner": 0},
    ).sort("created_at", 1)
    return list(docs)


@router.post("/projects")
def create_project(body: CreateProjectRequest, principal: Principal = Depends(require_auth)):
    doc = {
        "project_id": str(uuid.uuid4()),
        "name": body.name,
        "created_at": datetime.now(UTC),
    }
    projects_col.insert_one({**doc, "owner": principal.owner})
    return doc


@router.delete("/projects/{project_id}")
def delete_project(project_id: str, principal: Principal = Depends(require_auth)):
    """Delete a project and release its conversations.

    On a transaction-capable backend, project deletion and conversation
    unassignment commit atomically. FakeMongo keeps the existing sequential
    behavior and does not claim transactional referential integrity.
    """

    mine = {"project_id": project_id, "owner": principal.owner}

    def delete_and_unassign(session: ClientSession | None) -> dict:
        if session is None:
            if projects_col.find_one(mine) is None:
                raise HTTPException(status_code=404, detail="Project not found.")

            conversations_col.update_many(
                mine,
                {"$set": {"project_id": None}},
            )
            result = projects_col.delete_one(mine)
        else:
            result = projects_col.delete_one(
                mine,
                session=session,
            )

            conversations_col.update_many(
                mine,
                {"$set": {"project_id": None}},
                session=session,
            )

        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Project not found.")

        return {"ok": True}

    return run_transaction(delete_and_unassign)
