"""Domain health endpoints."""

from __future__ import annotations

import os
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from services import domain_service

router = APIRouter()

DEFAULT_ORG = os.environ.get("ATDD_ORG", "00000000-0000-0000-0000-000000000001")


class DomainUpsert(BaseModel):
    name: str
    project: str
    health_score: Optional[float] = None
    status: Optional[str] = None  # healthy, degraded, critical
    fix_rate: Optional[float] = None
    coupling_rate: Optional[float] = None
    change_frequency: Optional[float] = None
    knowledge_coverage: Optional[float] = None
    escape_rate: Optional[float] = None


class CouplingUpsert(BaseModel):
    project: str
    domain_a: str
    domain_b: str
    co_occurrence_count: int


# ── Endpoints ──


@router.get("")
def list_domains(
    org_id: UUID = Query(default=DEFAULT_ORG),
    project: Optional[str] = None,
    status: Optional[str] = None,
):
    """List domains with optional filters."""
    return domain_service.list_domains(str(org_id), project=project or "", status=status or "")


@router.get("/{domain_id}")
def get_domain(domain_id: UUID):
    """Get a single domain."""
    domain = domain_service.get_domain(str(domain_id))
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")
    return domain


@router.put("")
def upsert_domain(body: DomainUpsert, org_id: UUID = Query(default=DEFAULT_ORG)):
    """Create or update a domain (by org_id + project + name)."""
    return domain_service.upsert_domain(
        str(org_id), body.name, body.project,
        health_score=body.health_score, status=body.status,
        fix_rate=body.fix_rate, coupling_rate=body.coupling_rate,
        change_frequency=body.change_frequency,
        knowledge_coverage=body.knowledge_coverage,
        escape_rate=body.escape_rate,
    )


# ── Couplings ──


@router.get("/couplings/list")
def list_couplings(
    org_id: UUID = Query(default=DEFAULT_ORG),
    project: Optional[str] = None,
):
    """List domain couplings."""
    return domain_service.list_couplings(str(org_id), project=project or "")


@router.put("/couplings")
def upsert_coupling(body: CouplingUpsert, org_id: UUID = Query(default=DEFAULT_ORG)):
    """Create or update a domain coupling."""
    return domain_service.upsert_coupling(
        str(org_id), body.project, body.domain_a, body.domain_b,
        body.co_occurrence_count,
    )
