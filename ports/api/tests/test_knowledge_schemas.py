"""Unit tests for knowledge_schemas — validate_attrs for all 12 node types."""

from __future__ import annotations

import pytest

from services.knowledge_schemas import (
    validate_attrs,
    NODE_TYPE_REGISTRY,
    NodeRef,
)


# ── Helpers ──

def _ref(**overrides) -> dict:
    base = {"layer": "tactical", "node_type": "entity", "slug": "test"}
    base.update(overrides)
    return base


def _prop(name="field1", type="string", **kw) -> dict:
    return {"name": name, "type": type, **kw}


# ── Strategic layer ──


class TestBoundedContext:
    def test_valid(self):
        result = validate_attrs("strategic", "bounded_context", {
            "responsibility": "管理所得稅申報",
            "adjacent": [_ref(layer="strategic", node_type="bounded_context", slug="revenue")],
            "language_scope": ["tax-info", "due"],
        })
        assert result["responsibility"] == "管理所得稅申報"
        assert len(result["adjacent"]) == 1

    def test_valid_minimal(self):
        result = validate_attrs("strategic", "bounded_context", {
            "responsibility": "管理所得稅申報",
        })
        assert result["adjacent"] == []
        assert result["language_scope"] == []

    def test_invalid_missing_responsibility(self):
        with pytest.raises(Exception):
            validate_attrs("strategic", "bounded_context", {})


class TestContextMap:
    def test_valid(self):
        result = validate_attrs("strategic", "context_map", {
            "contexts": [_ref(layer="strategic", node_type="bounded_context", slug="a")],
            "relationships": [{"from": "a", "to": "b", "type": "ACL"}],
        })
        assert len(result["contexts"]) == 1
        assert len(result["relationships"]) == 1

    def test_invalid_missing_contexts(self):
        with pytest.raises(Exception):
            validate_attrs("strategic", "context_map", {
                "relationships": [],
            })


class TestSubdomain:
    def test_valid(self):
        result = validate_attrs("strategic", "subdomain", {
            "kind": "supporting",
            "rationale": "申報為支援能力",
        })
        assert result["kind"] == "supporting"

    def test_invalid_kind(self):
        with pytest.raises(Exception):
            validate_attrs("strategic", "subdomain", {
                "kind": "unknown",
                "rationale": "test",
            })


# ── Tactical layer ──


class TestAggregate:
    def test_valid(self):
        result = validate_attrs("tactical", "aggregate", {
            "root_entity": _ref(slug="tax-info"),
            "members": [_ref(slug="detail")],
            "invariants": [_ref(layer="rule", node_type="invariant", slug="inv-1")],
        })
        assert result["root_entity"]["slug"] == "tax-info"
        assert len(result["members"]) == 1

    def test_valid_minimal(self):
        result = validate_attrs("tactical", "aggregate", {
            "root_entity": _ref(slug="root"),
        })
        assert result["members"] == []
        assert result["repository"] is None

    def test_invalid_missing_root(self):
        with pytest.raises(Exception):
            validate_attrs("tactical", "aggregate", {})


class TestEntity:
    def test_valid(self):
        result = validate_attrs("tactical", "entity", {
            "properties": [_prop("status", "enum", values=["active", "done"])],
            "aggregate": _ref(node_type="aggregate", slug="tax-info"),
        })
        assert result["identity"] == "id"
        assert result["properties"][0]["values"] == ["active", "done"]

    def test_invalid_missing_properties(self):
        with pytest.raises(Exception):
            validate_attrs("tactical", "entity", {})


class TestValueObject:
    def test_valid(self):
        result = validate_attrs("tactical", "value_object", {
            "properties": [_prop("amount", "decimal")],
        })
        assert result["equality"] == "structural"

    def test_invalid_missing_properties(self):
        with pytest.raises(Exception):
            validate_attrs("tactical", "value_object", {})


class TestDomainService:
    def test_valid(self):
        result = validate_attrs("tactical", "domain_service", {
            "operations": ["calculate_income_method(due) -> IncomeMethod"],
            "depends_on": [_ref(node_type="repository", slug="tax-info-repo")],
        })
        assert len(result["operations"]) == 1

    def test_invalid_missing_operations(self):
        with pytest.raises(Exception):
            validate_attrs("tactical", "domain_service", {})


class TestRepository:
    def test_valid(self):
        result = validate_attrs("tactical", "repository", {
            "aggregate": _ref(node_type="aggregate", slug="tax-info"),
            "queries": ["find_by_period(year, month)"],
        })
        assert result["aggregate"]["slug"] == "tax-info"

    def test_invalid_missing_aggregate(self):
        with pytest.raises(Exception):
            validate_attrs("tactical", "repository", {})


class TestDomainEvent:
    def test_valid(self):
        result = validate_attrs("tactical", "domain_event", {
            "payload": [_prop("task_id", "uuid"), _prop("occurred_at", "datetime")],
            "emitted_by": _ref(node_type="aggregate", slug="tax-info"),
        })
        assert len(result["payload"]) == 2

    def test_valid_minimal(self):
        result = validate_attrs("tactical", "domain_event", {
            "payload": [_prop("id", "uuid")],
        })
        assert result["emitted_by"] is None


# ── Rule layer ──


class TestInvariant:
    def test_valid(self):
        result = validate_attrs("rule", "invariant", {
            "statement": "Due:Payment = 1:1 under success",
            "applies_to": [_ref(slug="due"), _ref(slug="payment")],
            "formal": {"cardinality": "1:1", "condition": "status=success"},
        })
        assert len(result["applies_to"]) == 2
        assert result["formal"]["cardinality"] == "1:1"

    def test_invalid_missing_statement(self):
        with pytest.raises(Exception):
            validate_attrs("rule", "invariant", {
                "applies_to": [_ref(slug="due")],
            })


class TestPolicy:
    def test_valid(self):
        result = validate_attrs("rule", "policy", {
            "trigger": _ref(node_type="domain_event", slug="overdue-detected"),
            "action": "send notification to owner",
            "references": [_ref(slug="task")],
        })
        assert result["action"] == "send notification to owner"

    def test_invalid_missing_trigger(self):
        with pytest.raises(Exception):
            validate_attrs("rule", "policy", {"action": "test"})


class TestBusinessRule:
    def test_valid(self):
        result = validate_attrs("rule", "business_rule", {
            "statement": "所得類別判定按優先序",
            "given": ["source: RoofRentalAccount 或 Due"],
            "when": "匯出時",
            "then": ["priority 1: RoofRentalAccount → lease_income"],
            "references": [_ref(node_type="value_object", slug="income-method")],
            "source": "Knowledge audit 2026-04-08",
        })
        assert len(result["then"]) == 1
        assert result["source"] == "Knowledge audit 2026-04-08"

    def test_valid_minimal(self):
        result = validate_attrs("rule", "business_rule", {
            "statement": "test rule",
            "given": ["condition"],
            "when": "trigger",
            "then": ["result"],
        })
        assert result["references"] == []
        assert result["source"] is None

    def test_invalid_missing_fields(self):
        with pytest.raises(Exception):
            validate_attrs("rule", "business_rule", {"statement": "incomplete"})


# ── Registry-level tests ──


class TestValidateAttrs:
    def test_unknown_layer(self):
        with pytest.raises(ValueError, match="Unknown layer"):
            validate_attrs("unknown", "entity", {})

    def test_unknown_node_type(self):
        with pytest.raises(ValueError, match="Unknown node type"):
            validate_attrs("tactical", "nonexistent", {})

    def test_all_registry_entries_have_tests(self):
        tested = {
            ("strategic", "bounded_context"),
            ("strategic", "context_map"),
            ("strategic", "subdomain"),
            ("tactical", "aggregate"),
            ("tactical", "entity"),
            ("tactical", "value_object"),
            ("tactical", "domain_service"),
            ("tactical", "repository"),
            ("tactical", "domain_event"),
            ("rule", "invariant"),
            ("rule", "policy"),
            ("rule", "business_rule"),
        }
        assert tested == set(NODE_TYPE_REGISTRY.keys())


class TestNodeRef:
    def test_valid(self):
        ref = NodeRef(layer="tactical", node_type="entity", slug="task")
        assert ref.domain is None
        assert ref.slug == "task"

    def test_with_domain(self):
        ref = NodeRef(layer="strategic", node_type="bounded_context",
                      domain="Revenue", slug="revenue")
        assert ref.domain == "Revenue"

    def test_invalid_layer(self):
        with pytest.raises(Exception):
            NodeRef(layer="invalid", node_type="entity", slug="x")
