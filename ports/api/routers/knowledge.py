"""Knowledge entries and terms endpoints."""

from __future__ import annotations

import json
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from db import get_cursor

router = APIRouter()

import os
DEFAULT_ORG = os.environ.get("ATDD_ORG", "00000000-0000-0000-0000-000000000001")


# ── Request / Response models ──


class EntryCreate(BaseModel):
    project: str
    domain: Optional[str] = None
    file_type: Optional[str] = None  # strategic, tactical, business-rules, domain-map
    section: Optional[str] = None
    content: str
    updated_by: Optional[str] = None


class EntryUpdate(BaseModel):
    domain: Optional[str] = None
    file_type: Optional[str] = None
    section: Optional[str] = None
    content: Optional[str] = None
    updated_by: Optional[str] = None


class TermUpsert(BaseModel):
    project: str
    domain: Optional[str] = None
    english_term: str
    chinese_term: str
    context: Optional[str] = None
    source: Optional[str] = None  # ul.md, slack, code


# ── Knowledge Entries ──


@router.get("/entries")
def list_entries(
    org_id: UUID = Query(default=DEFAULT_ORG),
    project: Optional[str] = None,
    domain: Optional[str] = None,
    file_type: Optional[str] = None,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
):
    """List knowledge entries with optional filters."""
    conditions = ["org_id = %s"]
    params: list = [str(org_id)]

    if project:
        conditions.append("project = %s")
        params.append(project)
    if domain:
        conditions.append("domain = %s")
        params.append(domain)
    if file_type:
        conditions.append("file_type = %s")
        params.append(file_type)

    where = " AND ".join(conditions)
    params.extend([limit, offset])

    with get_cursor() as cur:
        cur.execute(
            f"""
            SELECT *, count(*) OVER() AS total_count
            FROM knowledge_entries
            WHERE {where}
            ORDER BY updated_at DESC
            LIMIT %s OFFSET %s
            """,
            params,
        )
        rows = cur.fetchall()

    total = rows[0]["total_count"] if rows else 0
    items = [{k: v for k, v in row.items() if k != "total_count"} for row in rows]
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/entries/{entry_id}")
def get_entry(entry_id: UUID):
    """Get a single knowledge entry."""
    with get_cursor() as cur:
        cur.execute("SELECT * FROM knowledge_entries WHERE id = %s", (str(entry_id),))
        entry = cur.fetchone()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    return entry


@router.post("/entries", status_code=201)
def create_entry(body: EntryCreate, org_id: UUID = Query(default=DEFAULT_ORG)):
    """Create a knowledge entry."""
    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO knowledge_entries (org_id, project, domain, file_type, section, content, updated_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (str(org_id), body.project, body.domain, body.file_type,
             body.section, body.content, body.updated_by),
        )
        return cur.fetchone()


@router.patch("/entries/{entry_id}")
def update_entry(entry_id: UUID, body: EntryUpdate):
    """Update a knowledge entry (partial update, auto-increments version)."""
    sets = []
    params = []

    if body.domain is not None:
        sets.append("domain = %s")
        params.append(body.domain)
    if body.file_type is not None:
        sets.append("file_type = %s")
        params.append(body.file_type)
    if body.section is not None:
        sets.append("section = %s")
        params.append(body.section)
    if body.content is not None:
        sets.append("content = %s")
        params.append(body.content)
    if body.updated_by is not None:
        sets.append("updated_by = %s")
        params.append(body.updated_by)

    if not sets:
        raise HTTPException(status_code=400, detail="No fields to update")

    # Auto-increment version on update
    sets.append("version = version + 1")
    params.append(str(entry_id))

    with get_cursor() as cur:
        cur.execute(
            f"UPDATE knowledge_entries SET {', '.join(sets)} WHERE id = %s RETURNING *",
            params,
        )
        entry = cur.fetchone()

    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    return entry


@router.delete("/entries/{entry_id}", status_code=204)
def delete_entry(entry_id: UUID):
    """Delete a knowledge entry."""
    with get_cursor() as cur:
        cur.execute("DELETE FROM knowledge_entries WHERE id = %s RETURNING id", (str(entry_id),))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Entry not found")


# ── Knowledge Terms (UL) ──


@router.get("/terms")
def list_terms(
    org_id: UUID = Query(default=DEFAULT_ORG),
    project: Optional[str] = None,
    domain: Optional[str] = None,
):
    """List UL terms."""
    conditions = ["org_id = %s"]
    params: list = [str(org_id)]

    if project:
        conditions.append("project = %s")
        params.append(project)
    if domain:
        conditions.append("domain = %s")
        params.append(domain)

    where = " AND ".join(conditions)

    with get_cursor() as cur:
        cur.execute(
            f"SELECT * FROM knowledge_terms WHERE {where} ORDER BY english_term",
            params,
        )
        return cur.fetchall()


@router.put("/terms")
def upsert_term(body: TermUpsert, org_id: UUID = Query(default=DEFAULT_ORG)):
    """Create or update a UL term (by org_id + project + english_term)."""
    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO knowledge_terms (org_id, project, domain, english_term, chinese_term, context, source)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (org_id, project, english_term) DO UPDATE SET
                domain = EXCLUDED.domain,
                chinese_term = EXCLUDED.chinese_term,
                context = EXCLUDED.context,
                source = EXCLUDED.source
            RETURNING *
            """,
            (str(org_id), body.project, body.domain, body.english_term,
             body.chinese_term, body.context, body.source),
        )
        return cur.fetchone()
