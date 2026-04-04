"""Report endpoints."""

from __future__ import annotations

import json
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from db import get_cursor

router = APIRouter()

DEFAULT_ORG = "00000000-0000-0000-0000-000000000001"


class ReportCreate(BaseModel):
    project: str
    type: str       # weekly, monthly, domain-health, causation
    period: Optional[str] = None   # 2026-W14, 2026-03
    data: dict


# ── Endpoints ──


@router.get("")
def list_reports(
    org_id: UUID = Query(default=DEFAULT_ORG),
    project: Optional[str] = None,
    type: Optional[str] = None,
    limit: int = Query(default=20, le=100),
):
    """List reports with optional filters."""
    conditions = ["org_id = %s"]
    params: list = [str(org_id)]

    if project:
        conditions.append("project = %s")
        params.append(project)
    if type:
        conditions.append("type = %s")
        params.append(type)

    where = " AND ".join(conditions)
    params.append(limit)

    with get_cursor() as cur:
        cur.execute(
            f"SELECT * FROM reports WHERE {where} ORDER BY created_at DESC LIMIT %s",
            params,
        )
        return cur.fetchall()


@router.post("", status_code=201)
def create_report(body: ReportCreate, org_id: UUID = Query(default=DEFAULT_ORG)):
    """Create a new report."""
    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO reports (org_id, project, type, period, data)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING *
            """,
            (str(org_id), body.project, body.type, body.period, json.dumps(body.data)),
        )
        return cur.fetchone()


@router.get("/{report_id}")
def get_report(report_id: UUID):
    """Get a single report."""
    with get_cursor() as cur:
        cur.execute("SELECT * FROM reports WHERE id = %s", (str(report_id),))
        report = cur.fetchone()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report
