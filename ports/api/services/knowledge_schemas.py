"""Node type schema registry for structured knowledge nodes.

Each (layer, node_type) pair maps to a pydantic model that validates attrs.
Adding a new node_type = adding one class + one registry entry.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


# ── Shared building blocks ──


class PropertySpec(BaseModel):
    name: str
    type: str
    nullable: bool = False
    values: Optional[list[str]] = None
    description: Optional[str] = None


class NodeRef(BaseModel):
    layer: Literal["strategic", "tactical", "rule"]
    node_type: str
    domain: Optional[str] = None
    slug: str


# ── Strategic layer ──


class BoundedContextAttrs(BaseModel):
    responsibility: str
    adjacent: list[NodeRef] = []
    language_scope: list[str] = []
    upstream: list[NodeRef] = []
    downstream: list[NodeRef] = []


class ContextMapAttrs(BaseModel):
    contexts: list[NodeRef]
    relationships: list[dict]


class SubdomainAttrs(BaseModel):
    kind: Literal["core", "supporting", "generic"]
    rationale: str


# ── Tactical layer ──


class AggregateAttrs(BaseModel):
    root_entity: NodeRef
    members: list[NodeRef] = []
    invariants: list[NodeRef] = []
    repository: Optional[NodeRef] = None
    emits: list[NodeRef] = []


class EntityAttrs(BaseModel):
    identity: str = "id"
    properties: list[PropertySpec]
    aggregate: Optional[NodeRef] = None
    invariants: list[NodeRef] = []


class ValueObjectAttrs(BaseModel):
    properties: list[PropertySpec]
    equality: Literal["structural"] = "structural"


class DomainServiceAttrs(BaseModel):
    operations: list[str]
    depends_on: list[NodeRef] = []


class RepositoryAttrs(BaseModel):
    aggregate: NodeRef
    queries: list[str] = []


class DomainEventAttrs(BaseModel):
    payload: list[PropertySpec]
    emitted_by: Optional[NodeRef] = None


# ── Rule layer ──


class InvariantAttrs(BaseModel):
    statement: str
    applies_to: list[NodeRef]
    formal: Optional[dict] = None


class PolicyAttrs(BaseModel):
    trigger: NodeRef
    action: str
    references: list[NodeRef] = []


class BusinessRuleAttrs(BaseModel):
    statement: str
    given: list[str]
    when: str
    then: list[str]
    references: list[NodeRef] = []
    source: Optional[str] = None


# ── Registry ──


VALID_LAYERS = {"strategic", "tactical", "rule"}

NODE_TYPE_REGISTRY: dict[tuple[str, str], type[BaseModel]] = {
    ("strategic", "bounded_context"): BoundedContextAttrs,
    ("strategic", "context_map"):     ContextMapAttrs,
    ("strategic", "subdomain"):       SubdomainAttrs,
    ("tactical",  "aggregate"):       AggregateAttrs,
    ("tactical",  "entity"):          EntityAttrs,
    ("tactical",  "value_object"):    ValueObjectAttrs,
    ("tactical",  "domain_service"):  DomainServiceAttrs,
    ("tactical",  "repository"):      RepositoryAttrs,
    ("tactical",  "domain_event"):    DomainEventAttrs,
    ("rule",      "invariant"):       InvariantAttrs,
    ("rule",      "policy"):          PolicyAttrs,
    ("rule",      "business_rule"):   BusinessRuleAttrs,
}


def validate_attrs(layer: str, node_type: str, attrs: dict) -> dict:
    """Validate attrs against the registered schema for (layer, node_type).

    Returns the validated attrs as a dict (with defaults filled in).
    Raises ValueError if layer/node_type is unknown or attrs are invalid.
    """
    if layer not in VALID_LAYERS:
        raise ValueError(f"Unknown layer: {layer}")
    key = (layer, node_type)
    if key not in NODE_TYPE_REGISTRY:
        raise ValueError(
            f"Unknown node type: {layer}/{node_type}. "
            f"Valid types for '{layer}': "
            f"{[k[1] for k in NODE_TYPE_REGISTRY if k[0] == layer]}"
        )
    model = NODE_TYPE_REGISTRY[key](**attrs)
    return model.model_dump()
