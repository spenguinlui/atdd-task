"""Domain health endpoints."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from db import get_cursor

router = APIRouter()

import os
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
    conditions = ["org_id = %s"]
    params: list = [str(org_id)]

    if project:
        conditions.append("project = %s")
        params.append(project)
    if status:
        conditions.append("status = %s")
        params.append(status)

    where = " AND ".join(conditions)

    with get_cursor() as cur:
        cur.execute(
            f"SELECT * FROM domains WHERE {where} ORDER BY health_score ASC NULLS LAST",
            params,
        )
        return cur.fetchall()


@router.get("/{domain_id}")
def get_domain(domain_id: UUID):
    """Get a single domain."""
    with get_cursor() as cur:
        cur.execute("SELECT * FROM domains WHERE id = %s", (str(domain_id),))
        domain = cur.fetchone()
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")
    return domain


@router.put("")
def upsert_domain(body: DomainUpsert, org_id: UUID = Query(default=DEFAULT_ORG)):
    """Create or update a domain (by org_id + project + name)."""
    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO domains (org_id, project, name, health_score, status,
                                 fix_rate, coupling_rate, change_frequency,
                                 knowledge_coverage, escape_rate, calculated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
            ON CONFLICT (org_id, project, name) DO UPDATE SET
                health_score = EXCLUDED.health_score,
                status = EXCLUDED.status,
                fix_rate = EXCLUDED.fix_rate,
                coupling_rate = EXCLUDED.coupling_rate,
                change_frequency = EXCLUDED.change_frequency,
                knowledge_coverage = EXCLUDED.knowledge_coverage,
                escape_rate = EXCLUDED.escape_rate,
                calculated_at = now()
            RETURNING *
            """,
            (
                str(org_id), body.project, body.name, body.health_score,
                body.status, body.fix_rate, body.coupling_rate,
                body.change_frequency, body.knowledge_coverage, body.escape_rate,
            ),
        )
        return cur.fetchone()


# ── Couplings ──


@router.get("/couplings/list")
def list_couplings(
    org_id: UUID = Query(default=DEFAULT_ORG),
    project: Optional[str] = None,
):
    """List domain couplings."""
    conditions = ["org_id = %s"]
    params: list = [str(org_id)]

    if project:
        conditions.append("project = %s")
        params.append(project)

    where = " AND ".join(conditions)

    with get_cursor() as cur:
        cur.execute(
            f"SELECT * FROM domain_couplings WHERE {where} ORDER BY co_occurrence_count DESC",
            params,
        )
        return cur.fetchall()


@router.put("/couplings")
def upsert_coupling(body: CouplingUpsert, org_id: UUID = Query(default=DEFAULT_ORG)):
    """Create or update a domain coupling."""
    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO domain_couplings (org_id, project, domain_a, domain_b, co_occurrence_count)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (org_id, project, domain_a, domain_b) DO UPDATE SET
                co_occurrence_count = EXCLUDED.co_occurrence_count,
                updated_at = now()
            RETURNING *
            """,
            (str(org_id), body.project, body.domain_a, body.domain_b, body.co_occurrence_count),
        )
        return cur.fetchone()
