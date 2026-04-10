"""Knowledge entries and terms endpoints."""

from __future__ import annotations

import os
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from services import knowledge_service

router = APIRouter()

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
    return knowledge_service.list_entries(
        str(org_id), project=project or "", domain=domain or "",
        file_type=file_type or "", limit=limit, offset=offset,
    )


@router.get("/entries/{entry_id}")
def get_entry(entry_id: UUID):
    """Get a single knowledge entry."""
    entry = knowledge_service.get_entry(str(entry_id))
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    return entry


@router.post("/entries", status_code=201)
def create_entry(body: EntryCreate, org_id: UUID = Query(default=DEFAULT_ORG)):
    """Create a knowledge entry."""
    return knowledge_service.create_entry(
        str(org_id), body.project, body.content,
        domain=body.domain, file_type=body.file_type,
        section=body.section, updated_by=body.updated_by,
    )


@router.patch("/entries/{entry_id}")
def update_entry(entry_id: UUID, body: EntryUpdate):
    """Update a knowledge entry (partial update, auto-increments version)."""
    entry = knowledge_service.update_entry(
        str(entry_id),
        domain=body.domain, file_type=body.file_type,
        section=body.section, content=body.content,
        updated_by=body.updated_by,
    )
    if entry is None:
        raise HTTPException(status_code=400, detail="No fields to update")
    return entry


@router.delete("/entries/{entry_id}", status_code=204)
def delete_entry(entry_id: UUID):
    """Delete a knowledge entry."""
    if not knowledge_service.delete_entry(str(entry_id)):
        raise HTTPException(status_code=404, detail="Entry not found")


# ── Knowledge Terms (UL) ──


@router.get("/terms")
def list_terms(
    org_id: UUID = Query(default=DEFAULT_ORG),
    project: Optional[str] = None,
    domain: Optional[str] = None,
):
    """List UL terms."""
    return knowledge_service.list_terms(str(org_id), project=project or "", domain=domain or "")


@router.put("/terms")
def upsert_term(body: TermUpsert, org_id: UUID = Query(default=DEFAULT_ORG)):
    """Create or update a UL term (by org_id + project + english_term)."""
    return knowledge_service.upsert_term(
        str(org_id), body.project, body.english_term, body.chinese_term,
        domain=body.domain, context=body.context, source=body.source,
    )
