"""Knowledge service — application layer between adapters and DB."""

from __future__ import annotations

import json
import logging
from typing import Optional

from db import get_cursor
from services.knowledge_schemas import validate_attrs
from services.org_routing import merge_lists, merge_paginated
import remote_client

logger = logging.getLogger("knowledge-service")


# ── file_type ↔ layer mapping ──

_FILE_TYPE_TO_LAYER = {
    "strategic": {"layer": "strategic"},
    "tactical": {"layer": "tactical"},
    "business-rules": {"layer": "rule"},
    "domain-map": {"layer": "strategic", "node_type_in": ("bounded_context", "context_map", "subdomain")},
}

_LAYER_TO_FILE_TYPE = {
    "strategic": "strategic",
    "tactical": "tactical",
    "rule": "business-rules",
}


def _node_to_entry_shape(node: dict) -> dict:
    """Convert a knowledge_node row to entry-like shape for backward compat."""
    attrs_str = json.dumps(node.get("attrs", {}), ensure_ascii=False, default=str)
    parts = [f"## {node.get('title', '')}", ""]
    if node.get("summary"):
        parts.append(node["summary"])
        parts.append("")
    parts.append(f"**Type**: {node.get('layer')}/{node.get('node_type')}")
    parts.append(f"**Slug**: {node.get('slug')}")
    parts.append("")
    parts.append(f"### Attributes\n```json\n{attrs_str}\n```")
    if node.get("body_md"):
        parts.append("")
        parts.append(node["body_md"])
    content = "\n".join(parts)

    file_type = _LAYER_TO_FILE_TYPE.get(node.get("layer"), node.get("layer"))
    if node.get("node_type") in ("bounded_context", "context_map", "subdomain"):
        file_type = "domain-map"

    return {
        "id": node["id"],
        "org_id": node.get("org_id"),
        "project": node.get("project"),
        "domain": node.get("domain"),
        "file_type": file_type,
        "section": node.get("title", node.get("slug", "")),
        "content": content,
        "version": node.get("version", 1),
        "updated_by": node.get("updated_by"),
        "created_at": node.get("created_at"),
        "updated_at": node.get("updated_at"),
        "_source": "node",
        "_node_type": node.get("node_type"),
        "_slug": node.get("slug"),
        "_stale": node.get("stale", False),
    }


def _query_nodes_as_entries(
    org_id: str, project: str = "", domain: str = "", file_type: str = "",
) -> list[dict]:
    """Query knowledge_nodes and convert to entry-like shape."""
    mapping = _FILE_TYPE_TO_LAYER.get(file_type) if file_type else None

    conditions = ["org_id = %s"]
    params: list = [org_id]
    if project:
        conditions.append("project = %s")
        params.append(project)
    if domain:
        conditions.append("domain = %s")
        params.append(domain)
    if mapping:
        conditions.append("layer = %s")
        params.append(mapping["layer"])
        if "node_type_in" in mapping:
            placeholders = ", ".join(["%s"] * len(mapping["node_type_in"]))
            conditions.append(f"node_type IN ({placeholders})")
            params.extend(mapping["node_type_in"])

    where = " AND ".join(conditions)

    try:
        with get_cursor() as cur:
            cur.execute(f"""
                SELECT * FROM knowledge_nodes WHERE {where}
                ORDER BY domain, layer, node_type, slug
            """, params)
            return [_node_to_entry_shape(row) for row in cur.fetchall()]
    except Exception as e:
        logger.debug(f"knowledge_nodes query skipped (table may not exist): {e}")
        return []


# ── Knowledge Entries ──


def list_entries(
    org_id: str,
    project: str = "",
    domain: str = "",
    file_type: str = "",
    limit: int = 50,
    offset: int = 0,
) -> dict:
    conditions = ["org_id = %s", "COALESCE(migrated, false) = false"]
    params: list = [org_id]

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

    with get_cursor() as cur:
        cur.execute(f"""
            SELECT *, count(*) OVER() AS total_count
            FROM knowledge_entries WHERE {where}
            ORDER BY updated_at DESC
        """, params)
        rows = cur.fetchall()

    entry_total = rows[0]["total_count"] if rows else 0
    entries = [{k: v for k, v in row.items() if k != "total_count"} for row in rows]

    node_entries = _query_nodes_as_entries(org_id, project, domain, file_type)

    combined = node_entries + entries
    total = len(combined)
    page = combined[offset:offset + limit]

    local = {"items": page, "total": total, "limit": limit, "offset": offset}

    return merge_paginated(local, "/api/v1/knowledge/entries",
                           project=project, domain=domain, file_type=file_type,
                           limit=limit, offset=offset)


def get_entry(entry_id: str) -> Optional[dict]:
    with get_cursor() as cur:
        cur.execute("SELECT * FROM knowledge_entries WHERE id = %s", (entry_id,))
        return cur.fetchone()


def create_entry(org_id: str, project: str, content: str,
                 domain: str = None, file_type: str = None,
                 section: str = None, updated_by: str = None) -> dict:
    with get_cursor() as cur:
        cur.execute("""
            INSERT INTO knowledge_entries (org_id, project, domain, file_type, section, content, updated_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING *
        """, (org_id, project, domain, file_type, section, content, updated_by))
        return cur.fetchone()


def update_entry(entry_id: str, **kwargs) -> Optional[dict]:
    sets = []
    params = []

    for key in ("domain", "file_type", "section", "content", "updated_by"):
        if key in kwargs and kwargs[key] is not None:
            sets.append(f"{key} = %s")
            params.append(kwargs[key])

    if not sets:
        return None

    sets.append("version = version + 1")
    params.append(entry_id)

    with get_cursor() as cur:
        cur.execute(
            f"UPDATE knowledge_entries SET {', '.join(sets)} WHERE id = %s RETURNING *",
            params,
        )
        return cur.fetchone()


def delete_entry(entry_id: str) -> bool:
    with get_cursor() as cur:
        cur.execute("DELETE FROM knowledge_entries WHERE id = %s RETURNING id", (entry_id,))
        return cur.fetchone() is not None


# ── Knowledge Nodes ──


def list_nodes(
    org_id: str,
    project: str = "",
    domain: str = "",
    layer: str = "",
    node_type: str = "",
    stale: Optional[bool] = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    conditions = ["org_id = %s"]
    params: list = [org_id]

    if project:
        conditions.append("project = %s")
        params.append(project)
    if domain:
        conditions.append("domain = %s")
        params.append(domain)
    if layer:
        conditions.append("layer = %s")
        params.append(layer)
    if node_type:
        conditions.append("node_type = %s")
        params.append(node_type)
    if stale is not None:
        conditions.append("stale = %s")
        params.append(stale)

    where = " AND ".join(conditions)
    params.extend([limit, offset])

    with get_cursor() as cur:
        cur.execute(f"""
            SELECT *, count(*) OVER() AS total_count
            FROM knowledge_nodes WHERE {where}
            ORDER BY domain, layer, node_type, slug
            LIMIT %s OFFSET %s
        """, params)
        rows = cur.fetchall()

    total = rows[0]["total_count"] if rows else 0
    items = [{k: v for k, v in row.items() if k != "total_count"} for row in rows]
    return {"items": items, "total": total, "limit": limit, "offset": offset}


def get_node(node_id: str) -> Optional[dict]:
    with get_cursor() as cur:
        cur.execute("SELECT * FROM knowledge_nodes WHERE id = %s", (node_id,))
        return cur.fetchone()


def create_node(
    org_id: str,
    project: str,
    domain: str,
    layer: str,
    node_type: str,
    slug: str,
    title: str,
    summary: str,
    attrs: dict,
    body_md: str = None,
    source_task_id: str = None,
    legacy_entry_id: str = None,
    updated_by: str = None,
) -> dict:
    validated_attrs = validate_attrs(layer, node_type, attrs)

    with get_cursor() as cur:
        cur.execute("""
            INSERT INTO knowledge_nodes
                (org_id, project, domain, layer, node_type, slug,
                 title, summary, attrs, body_md,
                 source_task_id, legacy_entry_id, updated_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
        """, (
            org_id, project, domain, layer, node_type, slug,
            title, summary, json.dumps(validated_attrs, default=str), body_md,
            source_task_id, legacy_entry_id, updated_by,
        ))
        node = cur.fetchone()

        cur.execute("""
            INSERT INTO knowledge_node_revisions
                (node_id, version, attrs, body_md, change_reason,
                 source_task_id, changed_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            node["id"], 1,
            json.dumps(validated_attrs, default=str), body_md,
            "initial creation", source_task_id, updated_by,
        ))

    return node


def update_node(node_id: str, **kwargs) -> Optional[dict]:
    current = get_node(node_id)
    if not current:
        return None

    sets = []
    params = []

    for key in ("domain", "title", "summary", "body_md", "stale", "updated_by",
                "source_task_id"):
        if key in kwargs and kwargs[key] is not None:
            sets.append(f"{key} = %s")
            params.append(kwargs[key])

    if "attrs" in kwargs and kwargs["attrs"] is not None:
        validated = validate_attrs(current["layer"], current["node_type"], kwargs["attrs"])
        sets.append("attrs = %s")
        params.append(json.dumps(validated, default=str))

    if not sets:
        return None

    sets.append("version = version + 1")
    params.append(node_id)

    with get_cursor() as cur:
        cur.execute(
            f"UPDATE knowledge_nodes SET {', '.join(sets)} WHERE id = %s RETURNING *",
            params,
        )
        node = cur.fetchone()

        cur.execute("""
            INSERT INTO knowledge_node_revisions
                (node_id, version, attrs, body_md, change_reason,
                 source_task_id, changed_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            node["id"], node["version"],
            json.dumps(node["attrs"] if isinstance(node["attrs"], dict) else {}, default=str),
            node.get("body_md"),
            kwargs.get("change_reason", "update"),
            kwargs.get("source_task_id"), kwargs.get("updated_by"),
        ))

    return node


def delete_node(node_id: str) -> bool:
    with get_cursor() as cur:
        cur.execute("DELETE FROM knowledge_nodes WHERE id = %s RETURNING id", (node_id,))
        return cur.fetchone() is not None


# ── Knowledge Terms ──


def list_terms(org_id: str, project: str = "", domain: str = "") -> list[dict]:
    conditions = ["org_id = %s"]
    params: list = [org_id]

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
        local = cur.fetchall()

    return merge_lists(local, "/api/v1/knowledge/terms",
                       project=project, domain=domain)


def upsert_term(org_id: str, project: str, english_term: str, chinese_term: str,
                domain: str = None, context: str = None, source: str = None) -> dict:
    with get_cursor() as cur:
        cur.execute("""
            INSERT INTO knowledge_terms (org_id, project, domain, english_term, chinese_term, context, source)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (org_id, project, english_term) DO UPDATE SET
                domain = EXCLUDED.domain,
                chinese_term = EXCLUDED.chinese_term,
                context = EXCLUDED.context,
                source = EXCLUDED.source
            RETURNING *
        """, (org_id, project, domain, english_term, chinese_term, context, source))
        return cur.fetchone()


# ── Dashboard-specific queries (merged local + remote) ──


def get_type_stats(org_id: str, project: str = "", domain: str = "",
                   file_type: str = "") -> list[dict]:
    conditions = ["org_id = %s"]
    params: list = [org_id]
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

    with get_cursor() as cur:
        cur.execute(f"""
            SELECT file_type, count(*) as cnt
            FROM knowledge_entries WHERE {where} AND COALESCE(migrated, false) = false
            GROUP BY file_type ORDER BY cnt DESC
        """, params)
        local_stats = {r["file_type"]: r["cnt"] for r in cur.fetchall()}

    node_entries = _query_nodes_as_entries(org_id, project, domain, file_type)
    for ne in node_entries:
        ft = ne.get("file_type") or "untyped"
        local_stats[ft] = local_stats.get(ft, 0) + 1

    if remote_client.is_configured():
        try:
            result = remote_client.get("/api/v1/knowledge/entries",
                                       project=project, domain=domain,
                                       file_type=file_type, limit=200)
            for item in result.get("items", []):
                ft = item.get("file_type") or "untyped"
                local_stats[ft] = local_stats.get(ft, 0) + 1
        except Exception:
            pass

    return [{"file_type": k, "cnt": v} for k, v in
            sorted(local_stats.items(), key=lambda x: -x[1])]


SHARED_FILE_TYPES = ("domain-map", "business-rules")


def list_entries_grouped_by_project(
    org_id: str, project: str = "", domain: str = "", file_type: str = "",
) -> dict[str, dict]:
    """Return entries nested as {project: {"shared": {file_type: [entries]}, "domains": {domain: [entries]}}}.

    file_type in SHARED_FILE_TYPES (domain-map, business-rules) are project-level shared
    and go into the 'shared' bucket regardless of their domain field. Other types
    (strategic, tactical) are grouped by domain.
    """
    flat = list_entries_grouped(org_id, project, domain, file_type)
    by_project: dict[str, dict] = {}

    for _, entries in flat.items():
        for e in entries:
            proj = (e.get("project") if isinstance(e, dict) else e["project"]) or "(no project)"
            ft = (e.get("file_type") if isinstance(e, dict) else e["file_type"]) or ""
            dom = (e.get("domain") if isinstance(e, dict) else e["domain"]) or "(no domain)"

            bucket = by_project.setdefault(proj, {"shared": {}, "domains": {}})

            if ft in SHARED_FILE_TYPES:
                bucket["shared"].setdefault(ft, []).append(e)
            else:
                bucket["domains"].setdefault(dom, []).append(e)

    return by_project


def list_entries_grouped(org_id: str, project: str = "", domain: str = "",
                         file_type: str = "") -> dict[str, list]:
    conditions = ["org_id = %s", "COALESCE(migrated, false) = false"]
    params: list = [org_id]
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

    with get_cursor() as cur:
        cur.execute(f"""
            SELECT id, project, domain, file_type, section, content, version, updated_at, updated_by
            FROM knowledge_entries WHERE {where}
            ORDER BY domain, file_type, section
        """, params)
        all_entries = list(cur.fetchall())

    all_entries = _query_nodes_as_entries(org_id, project, domain, file_type) + all_entries

    if remote_client.is_configured():
        try:
            result = remote_client.get("/api/v1/knowledge/entries",
                                       project=project, domain=domain,
                                       file_type=file_type, limit=200)
            all_entries.extend(result.get("items", []))
        except Exception:
            pass

    grouped: dict[str, list] = {}
    for e in all_entries:
        key = (e.get("domain") if isinstance(e, dict) else e["domain"]) or "(no domain)"
        grouped.setdefault(key, []).append(e)
    return grouped


def get_migration_stats(org_id: str) -> dict:
    """Get migration progress stats: entries migrated vs total, nodes by type."""
    with get_cursor() as cur:
        cur.execute("""
            SELECT
                count(*) as total_entries,
                count(*) FILTER (WHERE COALESCE(migrated, false) = true) as migrated_entries
            FROM knowledge_entries WHERE org_id = %s
        """, (org_id,))
        entry_stats = cur.fetchone()

        try:
            cur.execute("""
                SELECT layer, node_type, count(*) as cnt
                FROM knowledge_nodes WHERE org_id = %s
                GROUP BY layer, node_type
                ORDER BY layer, node_type
            """, (org_id,))
            node_stats = [dict(r) for r in cur.fetchall()]
        except Exception:
            node_stats = []

        try:
            cur.execute("SELECT count(*) as cnt FROM knowledge_nodes WHERE org_id = %s", (org_id,))
            total_nodes = cur.fetchone()["cnt"]
        except Exception:
            total_nodes = 0

    total = entry_stats["total_entries"] if entry_stats else 0
    migrated = entry_stats["migrated_entries"] if entry_stats else 0

    return {
        "total_entries": total,
        "migrated_entries": migrated,
        "unmigrated_entries": total - migrated,
        "migration_pct": round(migrated / total * 100, 1) if total > 0 else 0,
        "total_nodes": total_nodes,
        "nodes_by_type": node_stats,
    }


def list_all_domains(org_id: str) -> list[str]:
    with get_cursor() as cur:
        cur.execute(
            "SELECT DISTINCT domain FROM knowledge_entries WHERE org_id = %s AND domain IS NOT NULL AND COALESCE(migrated, false) = false ORDER BY domain",
            (org_id,),
        )
        local = [r["domain"] for r in cur.fetchall()]

        try:
            cur.execute(
                "SELECT DISTINCT domain FROM knowledge_nodes WHERE org_id = %s ORDER BY domain",
                (org_id,),
            )
            local = sorted(set(local + [r["domain"] for r in cur.fetchall()]))
        except Exception:
            pass

    if not remote_client.is_configured():
        return local
    try:
        result = remote_client.get("/api/v1/knowledge/entries", limit=200)
        remote = [e["domain"] for e in result.get("items", []) if e.get("domain")]
        return sorted(set(local + remote))
    except Exception:
        return local
