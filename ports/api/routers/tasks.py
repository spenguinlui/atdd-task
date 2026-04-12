"""Task CRUD endpoints."""

from __future__ import annotations

import os
from typing import Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from services import task_service

router = APIRouter()

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
    type: Optional[str] = None,
    status: Optional[str] = None,
    domain: Optional[str] = None,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
):
    """List tasks with optional filters."""
    return task_service.list_tasks(
        str(org_id), project=project or "", type=type or "",
        status=status or "", domain=domain or "", limit=limit, offset=offset,
    )


@router.post("", status_code=201)
def create_task(body: TaskCreate, org_id: UUID = Query(default=DEFAULT_ORG)):
    """Create a new task."""
    return task_service.create_task(
        str(org_id), body.project, body.type,
        domain=body.domain, related_domains=body.related_domains,
        description=body.description, requirement=body.requirement,
        causation=body.causation, metadata=body.metadata,
    )


@router.get("/{task_id}")
def get_task(task_id: UUID):
    """Get a single task by ID."""
    task = task_service.get_task(str(task_id))
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.patch("/{task_id}")
def update_task(task_id: UUID, body: TaskUpdate):
    """Update a task (partial update)."""
    task = task_service.update_task(
        str(task_id),
        status=body.status, phase=body.phase, domain=body.domain,
        related_domains=body.related_domains, description=body.description,
        requirement=body.requirement, causation=body.causation, metadata=body.metadata,
    )
    if task is None:
        raise HTTPException(status_code=400, detail="No fields to update")
    return task


# ── Task History ──


@router.get("/{task_id}/history")
def list_task_history(task_id: UUID):
    """Get history events for a task."""
    return task_service.list_task_history(str(task_id))


@router.post("/{task_id}/history", status_code=201)
def create_task_history(task_id: UUID, body: TaskHistoryCreate):
    """Add a history event to a task."""
    return task_service.create_task_history(
        str(task_id), phase=body.phase, status=body.status,
        agent=body.agent, note=body.note,
    )


# ── Task Metrics ──


@router.post("/{task_id}/metrics", status_code=201)
def create_task_metrics(task_id: UUID, body: TaskMetricsCreate):
    """Record agent metrics for a task."""
    return task_service.create_task_metrics(
        str(task_id), body.agent, tool_uses=body.tool_uses,
        tokens=body.tokens, duration=body.duration,
    )
