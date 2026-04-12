"""Knowledge service — application layer between adapters and DB."""

from __future__ import annotations

import logging
from typing import Optional

from db import get_cursor
from services.org_routing import merge_lists, merge_paginated
import remote_client

logger = logging.getLogger("knowledge-service")


# ── Knowledge Entries ──


def list_entries(
    org_id: str,
    project: str = "",
    domain: str = "",
    file_type: str = "",
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
    if file_type:
        conditions.append("file_type = %s")
        params.append(file_type)

    where = " AND ".join(conditions)
    params.extend([limit, offset])

    with get_cursor() as cur:
        cur.execute(f"""
            SELECT *, count(*) OVER() AS total_count
            FROM knowledge_entries WHERE {where}
            ORDER BY updated_at DESC
            LIMIT %s OFFSET %s
        """, params)
        rows = cur.fetchall()

    total = rows[0]["total_count"] if rows else 0
    items = [{k: v for k, v in row.items() if k != "total_count"} for row in rows]
    local = {"items": items, "total": total, "limit": limit, "offset": offset}

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
            FROM knowledge_entries WHERE {where}
            GROUP BY file_type ORDER BY cnt DESC
        """, params)
        local_stats = {r["file_type"]: r["cnt"] for r in cur.fetchall()}

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


def list_entries_grouped(org_id: str, project: str = "", domain: str = "",
                         file_type: str = "") -> dict[str, list]:
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
            SELECT id, project, domain, file_type, section, content, version, updated_at, updated_by
            FROM knowledge_entries WHERE {where}
            ORDER BY domain, file_type, section
        """, params)
        all_entries = list(cur.fetchall())

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


def list_all_domains(org_id: str) -> list[str]:
    with get_cursor() as cur:
        cur.execute(
            "SELECT DISTINCT domain FROM knowledge_entries WHERE org_id = %s AND domain IS NOT NULL ORDER BY domain",
            (org_id,),
        )
        local = [r["domain"] for r in cur.fetchall()]

    if not remote_client.is_configured():
        return local
    try:
        result = remote_client.get("/api/v1/knowledge/entries", limit=200)
        remote = [e["domain"] for e in result.get("items", []) if e.get("domain")]
        return sorted(set(local + remote))
    except Exception:
        return local
