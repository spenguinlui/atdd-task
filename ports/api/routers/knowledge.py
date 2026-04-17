"""Knowledge entries and terms endpoints."""

from __future__ import annotations

import os
import re
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, field_validator

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


TERM_TYPES = {"Entity", "ValueObject", "Aggregate", "Service", "Event", "Concept"}
BUSINESS_RULE_RE = re.compile(r"^(VR|CR|ST|CA|AU|TE|CD)-\d{3}$")
SOURCE_RE = re.compile(
    r"^(ul\.md(→migration)?|domain-name|code(:.+)?|claude:.+|slack(:.+)?|curator|user)$"
)


class TermUpsert(BaseModel):
    project: str
    english_term: str
    chinese_term: str
    type: str = "Concept"
    definition: Optional[str] = None
    domain: Optional[str] = None
    aggregate_root: Optional[str] = None
    related_entities: Optional[List[str]] = None
    business_rules: Optional[List[str]] = None
    examples: Optional[List[str]] = None
    notes: Optional[List[str]] = None
    related_terms: Optional[List[str]] = None
    context: Optional[str] = None  # DEPRECATED; prefer definition/examples/notes
    source: Optional[str] = None  # ul.md, slack, code

    @field_validator("type")
    @classmethod
    def _check_type(cls, v: str) -> str:
        if v not in TERM_TYPES:
            raise ValueError(f"type must be one of {sorted(TERM_TYPES)}, got {v!r}")
        return v

    @field_validator("business_rules")
    @classmethod
    def _check_business_rules(cls, v):
        if v is None:
            return v
        bad = [r for r in v if not BUSINESS_RULE_RE.match(r)]
        if bad:
            raise ValueError(
                f"business_rules must match {{VR|CR|ST|CA|AU|TE|CD}}-NNN, got {bad}"
            )
        return v

    @field_validator("source")
    @classmethod
    def _check_source(cls, v):
        if v is None:
            return v
        if not SOURCE_RE.match(v):
            raise ValueError(
                f"source must match one of ul.md, ul.md→migration, domain-name, "
                f"code[:path], claude:{{ctx}}, slack[:channel], curator, user; got {v!r}"
            )
        return v


class NodeCreate(BaseModel):
    project: str
    domain: str
    layer: str        # strategic, tactical, rule
    node_type: str    # see knowledge_schemas registry
    slug: str
    title: str
    summary: str
    attrs: dict
    body_md: Optional[str] = None
    source_task_id: Optional[str] = None
    legacy_entry_id: Optional[str] = None
    updated_by: Optional[str] = None


class NodeUpdate(BaseModel):
    domain: Optional[str] = None
    title: Optional[str] = None
    summary: Optional[str] = None
    attrs: Optional[dict] = None
    body_md: Optional[str] = None
    stale: Optional[bool] = None
    source_task_id: Optional[str] = None
    updated_by: Optional[str] = None
    change_reason: Optional[str] = None


# ── Migration Stats ──


@router.get("/migration-stats")
def migration_stats(org_id: UUID = Query(default=DEFAULT_ORG)):
    """Get migration progress: entries migrated vs total, nodes by type."""
    return knowledge_service.get_migration_stats(str(org_id))


# ── Knowledge Nodes ──


@router.get("/nodes")
def list_nodes(
    org_id: UUID = Query(default=DEFAULT_ORG),
    project: Optional[str] = None,
    domain: Optional[str] = None,
    layer: Optional[str] = None,
    node_type: Optional[str] = None,
    stale: Optional[bool] = None,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
):
    """List knowledge nodes with optional filters."""
    return knowledge_service.list_nodes(
        str(org_id), project=project or "", domain=domain or "",
        layer=layer or "", node_type=node_type or "",
        stale=stale, limit=limit, offset=offset,
    )


@router.get("/nodes/{node_id}")
def get_node(node_id: UUID):
    """Get a single knowledge node."""
    node = knowledge_service.get_node(str(node_id))
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    return node


@router.post("/nodes", status_code=201)
def create_node(body: NodeCreate, org_id: UUID = Query(default=DEFAULT_ORG)):
    """Create a knowledge node (attrs validated against schema registry)."""
    try:
        return knowledge_service.create_node(
            str(org_id), body.project, body.domain,
            body.layer, body.node_type, body.slug,
            body.title, body.summary, body.attrs,
            body_md=body.body_md, source_task_id=body.source_task_id,
            legacy_entry_id=body.legacy_entry_id, updated_by=body.updated_by,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.patch("/nodes/{node_id}")
def update_node(node_id: UUID, body: NodeUpdate):
    """Update a knowledge node (partial update, auto-increments version, writes revision)."""
    try:
        node = knowledge_service.update_node(
            str(node_id),
            domain=body.domain, title=body.title, summary=body.summary,
            attrs=body.attrs, body_md=body.body_md, stale=body.stale,
            source_task_id=body.source_task_id, updated_by=body.updated_by,
            change_reason=body.change_reason,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if node is None:
        raise HTTPException(status_code=400, detail="No fields to update or node not found")
    return node


@router.delete("/nodes/{node_id}", status_code=204)
def delete_node(node_id: UUID):
    """Delete a knowledge node (cascades to revisions)."""
    if not knowledge_service.delete_node(str(node_id)):
        raise HTTPException(status_code=404, detail="Node not found")


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
        type=body.type,
        definition=body.definition,
        domain=body.domain,
        aggregate_root=body.aggregate_root,
        related_entities=body.related_entities,
        business_rules=body.business_rules,
        examples=body.examples,
        notes=body.notes,
        related_terms=body.related_terms,
        context=body.context,
        source=body.source,
    )


@router.delete("/terms/{term_id}", status_code=204)
def delete_term(term_id: UUID):
    """Delete a UL term by id."""
    if not knowledge_service.delete_term(str(term_id)):
        raise HTTPException(status_code=404, detail="Term not found")
