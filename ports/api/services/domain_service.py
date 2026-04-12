"""Domain service — application layer between adapters and DB."""

from __future__ import annotations

import logging
from typing import Optional

from db import get_cursor
from services.org_routing import merge_lists
import remote_client

logger = logging.getLogger("domain-service")


# ── Queries (shared by API router + dashboard views) ──


def list_domains(org_id: str, project: str = "", status: str = "") -> list[dict]:
    conditions = ["org_id = %s"]
    params: list = [org_id]

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
        local = cur.fetchall()

    return merge_lists(local, "/api/v1/domains", project=project, status=status)


def get_domain(domain_id: str) -> Optional[dict]:
    with get_cursor() as cur:
        cur.execute("SELECT * FROM domains WHERE id = %s", (domain_id,))
        return cur.fetchone()


def get_domain_by_name(org_id: str, name: str, project: str = "") -> Optional[dict]:
    with get_cursor() as cur:
        if project:
            cur.execute(
                "SELECT * FROM domains WHERE org_id = %s AND project = %s AND name = %s",
                (org_id, project, name),
            )
        else:
            cur.execute(
                "SELECT * FROM domains WHERE org_id = %s AND name = %s LIMIT 1",
                (org_id, name),
            )
        result = cur.fetchone()

    if result:
        return result

    # Try remote
    if not remote_client.is_configured():
        return None
    try:
        domains = remote_client.get("/api/v1/domains", project=project)
        for d in domains:
            if d.get("name") == name:
                return d
    except Exception:
        pass
    return None


def upsert_domain(org_id: str, name: str, project: str, **kwargs) -> dict:
    with get_cursor() as cur:
        cur.execute("""
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
        """, (
            org_id, project, name,
            kwargs.get("health_score"),
            kwargs.get("status"),
            kwargs.get("fix_rate"),
            kwargs.get("coupling_rate"),
            kwargs.get("change_frequency"),
            kwargs.get("knowledge_coverage"),
            kwargs.get("escape_rate"),
        ))
        return cur.fetchone()


# ── Couplings ──


def list_couplings(org_id: str, project: str = "", limit: int = 30) -> list[dict]:
    conditions = ["org_id = %s"]
    params: list = [org_id]
    if project:
        conditions.append("project = %s")
        params.append(project)
    where = " AND ".join(conditions)
    params.append(limit)

    with get_cursor() as cur:
        cur.execute(
            f"SELECT * FROM domain_couplings WHERE {where} ORDER BY co_occurrence_count DESC LIMIT %s",
            params,
        )
        local = cur.fetchall()

    return merge_lists(local, "/api/v1/domains/couplings/list", project=project)


def list_couplings_for_domain(org_id: str, domain_name: str) -> list[dict]:
    with get_cursor() as cur:
        cur.execute("""
            SELECT * FROM domain_couplings
            WHERE org_id = %s AND (domain_a = %s OR domain_b = %s)
            ORDER BY co_occurrence_count DESC
        """, (org_id, domain_name, domain_name))
        local = cur.fetchall()

    if not remote_client.is_configured():
        return local
    try:
        all_remote = remote_client.get("/api/v1/domains/couplings/list")
        remote = [c for c in all_remote
                  if c.get("domain_a") == domain_name or c.get("domain_b") == domain_name]
        return local + remote
    except Exception:
        return local


def upsert_coupling(org_id: str, project: str, domain_a: str, domain_b: str,
                     co_occurrence_count: int) -> dict:
    with get_cursor() as cur:
        cur.execute("""
            INSERT INTO domain_couplings (org_id, project, domain_a, domain_b, co_occurrence_count)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (org_id, project, domain_a, domain_b) DO UPDATE SET
                co_occurrence_count = EXCLUDED.co_occurrence_count,
                updated_at = now()
            RETURNING *
        """, (org_id, project, domain_a, domain_b, co_occurrence_count))
        return cur.fetchone()


# ── Dashboard-specific queries (merged local + remote) ──


def list_sidebar_domains(org_id: str) -> dict[str, list]:
    with get_cursor() as cur:
        cur.execute(
            "SELECT name, project, status, health_score FROM domains WHERE org_id = %s ORDER BY project, name",
            (org_id,),
        )
        local_rows = cur.fetchall()

    if remote_client.is_configured():
        try:
            remote_rows = remote_client.get("/api/v1/domains")
        except Exception:
            remote_rows = []
    else:
        remote_rows = []

    grouped: dict[str, list] = {}
    for r in local_rows + remote_rows:
        grouped.setdefault(r.get("project", ""), []).append(r)
    return grouped


def get_domain_tasks(org_id: str, domain_name: str, limit: int = 20) -> list[dict]:
    with get_cursor() as cur:
        cur.execute("""
            SELECT id, type, status, description, created_at, updated_at
            FROM tasks WHERE org_id = %s AND domain = %s
            ORDER BY created_at DESC LIMIT %s
        """, (org_id, domain_name, limit))
        local = cur.fetchall()

    return merge_lists(local, "/api/v1/tasks", domain=domain_name, limit=limit)


def get_domain_knowledge_stats(org_id: str, domain_name: str) -> dict[str, int]:
    with get_cursor() as cur:
        cur.execute("""
            SELECT file_type, count(*) as cnt
            FROM knowledge_entries
            WHERE org_id = %s AND domain = %s
            GROUP BY file_type
        """, (org_id, domain_name))
        local = {r["file_type"]: r["cnt"] for r in cur.fetchall()}

    if not remote_client.is_configured():
        return local
    try:
        result = remote_client.get("/api/v1/knowledge/entries", domain=domain_name, limit=200)
        for item in result.get("items", []):
            ft = item.get("file_type") or "untyped"
            local[ft] = local.get(ft, 0) + 1
    except Exception:
        pass
    return local


def get_domain_fix_timeline(org_id: str, domain_name: str) -> list[dict]:
    with get_cursor() as cur:
        cur.execute("""
            SELECT date_trunc('week', created_at AT TIME ZONE 'Asia/Taipei')::date as week, count(*) as cnt
            FROM tasks
            WHERE org_id = %s AND domain = %s AND type = 'fix'
            GROUP BY week ORDER BY week
        """, (org_id, domain_name))
        return cur.fetchall()
