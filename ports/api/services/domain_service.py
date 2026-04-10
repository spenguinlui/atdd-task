"""Domain service — application layer between adapters and DB."""

from __future__ import annotations

import logging
from typing import Optional

from db import get_cursor
from services.org_routing import is_remote
import remote_client

logger = logging.getLogger("domain-service")


# ── Queries (shared by API router + dashboard views) ──


def list_domains(org_id: str, project: str = "", status: str = "") -> list[dict]:
    if is_remote(org_id):
        try:
            return remote_client.get(
                "/api/v1/domains", project=project, status=status,
            )
        except Exception:
            logger.warning("Failed to fetch remote domains")
            return []

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
        return cur.fetchall()


def get_domain(domain_id: str) -> Optional[dict]:
    with get_cursor() as cur:
        cur.execute("SELECT * FROM domains WHERE id = %s", (domain_id,))
        return cur.fetchone()


def get_domain_by_name(org_id: str, name: str, project: str = "") -> Optional[dict]:
    if is_remote(org_id):
        try:
            domains = remote_client.get("/api/v1/domains", project=project)
            for d in domains:
                if d.get("name") == name:
                    return d
            return None
        except Exception:
            return None

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
        return cur.fetchone()


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
    if is_remote(org_id):
        try:
            return remote_client.get("/api/v1/domains/couplings/list", project=project)
        except Exception:
            return []

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
        return cur.fetchall()


def list_couplings_for_domain(org_id: str, domain_name: str) -> list[dict]:
    if is_remote(org_id):
        try:
            all_couplings = remote_client.get("/api/v1/domains/couplings/list")
            return [c for c in all_couplings
                    if c.get("domain_a") == domain_name or c.get("domain_b") == domain_name]
        except Exception:
            return []

    with get_cursor() as cur:
        cur.execute("""
            SELECT * FROM domain_couplings
            WHERE org_id = %s AND (domain_a = %s OR domain_b = %s)
            ORDER BY co_occurrence_count DESC
        """, (org_id, domain_name, domain_name))
        return cur.fetchall()


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


# ── Dashboard-specific queries ──


def list_sidebar_domains(org_id: str) -> dict[str, list]:
    if is_remote(org_id):
        try:
            domains = remote_client.get("/api/v1/domains")
            grouped: dict[str, list] = {}
            for d in domains:
                grouped.setdefault(d.get("project", ""), []).append(d)
            return grouped
        except Exception:
            return {}

    with get_cursor() as cur:
        cur.execute(
            "SELECT name, project, status, health_score FROM domains WHERE org_id = %s ORDER BY project, name",
            (org_id,),
        )
        rows = cur.fetchall()
    grouped: dict[str, list] = {}
    for r in rows:
        grouped.setdefault(r["project"], []).append(r)
    return grouped


def get_domain_tasks(org_id: str, domain_name: str, limit: int = 20) -> list[dict]:
    if is_remote(org_id):
        from services.task_service import list_tasks
        result = list_tasks(org_id, domain=domain_name, limit=limit)
        return result.get("items", [])

    with get_cursor() as cur:
        cur.execute("""
            SELECT id, type, status, description, created_at, updated_at
            FROM tasks WHERE org_id = %s AND domain = %s
            ORDER BY created_at DESC LIMIT %s
        """, (org_id, domain_name, limit))
        return cur.fetchall()


def get_domain_knowledge_stats(org_id: str, domain_name: str) -> dict[str, int]:
    if is_remote(org_id):
        try:
            result = remote_client.get("/api/v1/knowledge/entries", domain=domain_name, limit=200)
            stats: dict[str, int] = {}
            for item in result.get("items", []):
                ft = item.get("file_type") or "untyped"
                stats[ft] = stats.get(ft, 0) + 1
            return stats
        except Exception:
            return {}

    with get_cursor() as cur:
        cur.execute("""
            SELECT file_type, count(*) as cnt
            FROM knowledge_entries
            WHERE org_id = %s AND domain = %s
            GROUP BY file_type
        """, (org_id, domain_name))
        return {r["file_type"]: r["cnt"] for r in cur.fetchall()}


def get_domain_fix_timeline(org_id: str, domain_name: str) -> list[dict]:
    if is_remote(org_id):
        # Remote API doesn't have a dedicated fix timeline endpoint
        return []

    with get_cursor() as cur:
        cur.execute("""
            SELECT date_trunc('week', created_at AT TIME ZONE 'Asia/Taipei')::date as week, count(*) as cnt
            FROM tasks
            WHERE org_id = %s AND domain = %s AND type = 'fix'
            GROUP BY week ORDER BY week
        """, (org_id, domain_name))
        return cur.fetchall()
