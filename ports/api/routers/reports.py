"""Report endpoints."""

from __future__ import annotations

import os
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from services import report_service

router = APIRouter()

DEFAULT_ORG = os.environ.get("ATDD_ORG", "00000000-0000-0000-0000-000000000001")


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
    return report_service.list_reports(str(org_id), project=project or "", type=type or "", limit=limit)


@router.post("", status_code=201)
def create_report(body: ReportCreate, org_id: UUID = Query(default=DEFAULT_ORG)):
    """Create a new report."""
    return report_service.create_report(
        str(org_id), body.project, body.type, body.data, period=body.period,
    )


@router.get("/{report_id}")
def get_report(report_id: UUID):
    """Get a single report."""
    report = report_service.get_report(str(report_id))
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report
