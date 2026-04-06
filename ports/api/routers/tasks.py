"""Task CRUD endpoints."""

from __future__ import annotations

from typing import Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from db import get_cursor

router = APIRouter()

import os
DEFAULT_ORG = os.environ.get("ATDD_ORG", "00000000-0000-0000-0000-000000000001")


# ── Request / Response models ──


class TaskCreate(BaseModel):
    project: str
    type: str  # feature, fix, refactor, test, epic
    domain: Optional[str] = None
    related_domains: Optional[List[str]] = None
    description: Optional[str] = None
    requirement: Optional[str] = None
    causation: Optional[Dict] = None
    metadata: Optional[Dict] = None


class TaskUpdate(BaseModel):
    status: Optional[str] = None
    phase: Optional[str] = None
    domain: Optional[str] = None
    related_domains: Optional[List[str]] = None
    description: Optional[str] = None
    requirement: Optional[str] = None
    causation: Optional[Dict] = None
    metadata: Optional[Dict] = None


class TaskHistoryCreate(BaseModel):
    phase: Optional[str] = None
    status: Optional[str] = None
    agent: Optional[str] = None
    note: Optional[str] = None


class TaskMetricsCreate(BaseModel):
    agent: str
    tool_uses: Optional[int] = None
    tokens: Optional[int] = None
    duration: Optional[int] = None


# ── Endpoints ──


@router.get("")
def list_tasks(
    org_id: UUID = Query(default=DEFAULT_ORG),
    project: Optional[str] = None,
    status: Optional[str] = None,
    domain: Optional[str] = None,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
):
    """List tasks with optional filters."""
    conditions = ["t.org_id = %s"]
    params: list = [str(org_id)]

    if project:
        conditions.append("t.project = %s")
        params.append(project)
    if status:
        conditions.append("t.status = %s")
        params.append(status)
    if domain:
        conditions.append("t.domain = %s")
        params.append(domain)

    where = " AND ".join(conditions)
    params.extend([limit, offset])

    with get_cursor() as cur:
        cur.execute(
            f"""
            SELECT t.*, count(*) OVER() AS total_count
            FROM tasks t
            WHERE {where}
            ORDER BY t.created_at DESC
            LIMIT %s OFFSET %s
            """,
            params,
        )
        rows = cur.fetchall()

    total = rows[0]["total_count"] if rows else 0
    # Remove total_count from each row
    items = [{k: v for k, v in row.items() if k != "total_count"} for row in rows]

    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.post("", status_code=201)
def create_task(body: TaskCreate, org_id: UUID = Query(default=DEFAULT_ORG)):
    """Create a new task."""
    import json

    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO tasks (org_id, project, type, domain, related_domains,
                               description, requirement, causation, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                str(org_id),
                body.project,
                body.type,
                body.domain,
                body.related_domains,
                body.description,
                body.requirement,
                json.dumps(body.causation) if body.causation else None,
                json.dumps(body.metadata or {}),
            ),
        )
        task = cur.fetchone()

    return task


@router.get("/{task_id}")
def get_task(task_id: UUID):
    """Get a single task by ID."""
    with get_cursor() as cur:
        cur.execute("SELECT * FROM tasks WHERE id = %s", (str(task_id),))
        task = cur.fetchone()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.patch("/{task_id}")
def update_task(task_id: UUID, body: TaskUpdate):
    """Update a task (partial update)."""
    import json

    sets = []
    params = []

    if body.status is not None:
        sets.append("status = %s")
        params.append(body.status)
    if body.phase is not None:
        sets.append("phase = %s")
        params.append(body.phase)
    if body.domain is not None:
        sets.append("domain = %s")
        params.append(body.domain)
    if body.related_domains is not None:
        sets.append("related_domains = %s")
        params.append(body.related_domains)
    if body.description is not None:
        sets.append("description = %s")
        params.append(body.description)
    if body.requirement is not None:
        sets.append("requirement = %s")
        params.append(body.requirement)
    if body.causation is not None:
        sets.append("causation = %s")
        params.append(json.dumps(body.causation))
    if body.metadata is not None:
        sets.append("metadata = metadata || %s")
        params.append(json.dumps(body.metadata))

    if not sets:
        raise HTTPException(status_code=400, detail="No fields to update")

    params.append(str(task_id))

    with get_cursor() as cur:
        cur.execute(
            f"UPDATE tasks SET {', '.join(sets)} WHERE id = %s RETURNING *",
            params,
        )
        task = cur.fetchone()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


# ── Task History ──


@router.get("/{task_id}/history")
def list_task_history(task_id: UUID):
    """Get history events for a task."""
    with get_cursor() as cur:
        cur.execute(
            "SELECT * FROM task_history WHERE task_id = %s ORDER BY timestamp",
            (str(task_id),),
        )
        return cur.fetchall()


@router.post("/{task_id}/history", status_code=201)
def create_task_history(task_id: UUID, body: TaskHistoryCreate):
    """Add a history event to a task."""
    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO task_history (task_id, phase, status, agent, note)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING *
            """,
            (str(task_id), body.phase, body.status, body.agent, body.note),
        )
        return cur.fetchone()


# ── Task Metrics ──


@router.post("/{task_id}/metrics", status_code=201)
def create_task_metrics(task_id: UUID, body: TaskMetricsCreate):
    """Record agent metrics for a task."""
    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO task_metrics (task_id, agent, tool_uses, tokens, duration)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING *
            """,
            (str(task_id), body.agent, body.tool_uses, body.tokens, body.duration),
        )
        return cur.fetchone()
