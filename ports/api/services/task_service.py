"""Task service — application layer between adapters and DB."""

from __future__ import annotations

import json
import logging
import time
from typing import Optional

from db import get_cursor
from services.org_routing import merge_lists, merge_paginated
import remote_client

logger = logging.getLogger("task-service")


# ── Queries (shared by API router + dashboard views) ──


def list_tasks(
    org_id: str,
    project: str = "",
    type: str = "",
    status: str = "",
    domain: str = "",
    limit: int = 50,
    offset: int = 0,
) -> dict:
    conditions = ["t.org_id = %s"]
    params: list = [org_id]

    if project:
        conditions.append("t.project = %s")
        params.append(project)
    if type:
        conditions.append("t.type = %s")
        params.append(type)
    if status:
        conditions.append("t.status = %s")
        params.append(status)
    if domain:
        conditions.append("t.domain = %s")
        params.append(domain)

    where = " AND ".join(conditions)
    params.extend([limit, offset])

    with get_cursor() as cur:
        cur.execute(f"""
            SELECT t.*, count(*) OVER() AS total_count
            FROM tasks t WHERE {where}
            ORDER BY t.created_at DESC
            LIMIT %s OFFSET %s
        """, params)
        rows = cur.fetchall()

    total = rows[0]["total_count"] if rows else 0
    items = [{k: v for k, v in row.items() if k != "total_count"} for row in rows]
    return {"items": items, "total": total, "limit": limit, "offset": offset}


def get_task(task_id: str) -> Optional[dict]:
    with get_cursor() as cur:
        cur.execute("SELECT * FROM tasks WHERE id = %s", (task_id,))
        task = cur.fetchone()
    if task:
        return task
    # Fallback to remote API
    if remote_client.is_configured():
        try:
            return remote_client.get(f"/api/v1/tasks/{task_id}")
        except Exception:
            logger.warning(f"Failed to fetch remote task {task_id}")
    return None


def create_task(org_id: str, project: str, type: str, **kwargs) -> dict:
    with get_cursor() as cur:
        cur.execute("""
            INSERT INTO tasks (org_id, project, type, domain, related_domains,
                               description, requirement, causation, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
        """, (
            org_id, project, type,
            kwargs.get("domain"),
            kwargs.get("related_domains"),
            kwargs.get("description"),
            kwargs.get("requirement"),
            json.dumps(kwargs["causation"]) if kwargs.get("causation") else None,
            json.dumps(kwargs.get("metadata") or {}),
        ))
        return cur.fetchone()


def update_task(task_id: str, **kwargs) -> Optional[dict]:
    sets = []
    params = []

    field_map = {
        "status": "status = %s",
        "phase": "phase = %s",
        "domain": "domain = %s",
        "related_domains": "related_domains = %s",
        "description": "description = %s",
        "requirement": "requirement = %s",
    }

    for key, sql in field_map.items():
        if key in kwargs and kwargs[key] is not None:
            sets.append(sql)
            params.append(kwargs[key])

    if "causation" in kwargs and kwargs["causation"] is not None:
        sets.append("causation = %s")
        params.append(json.dumps(kwargs["causation"]))
    if "metadata" in kwargs and kwargs["metadata"] is not None:
        sets.append("metadata = metadata || %s")
        params.append(json.dumps(kwargs["metadata"]))

    if not sets:
        return None

    params.append(task_id)

    with get_cursor() as cur:
        cur.execute(
            f"UPDATE tasks SET {', '.join(sets)} WHERE id = %s RETURNING *",
            params,
        )
        return cur.fetchone()


# ── Task History ──


def list_task_history(task_id: str) -> list:
    with get_cursor() as cur:
        cur.execute(
            "SELECT * FROM task_history WHERE task_id = %s ORDER BY timestamp",
            (task_id,),
        )
        local = cur.fetchall()
    if local:
        return local
    # Fallback to remote API
    if remote_client.is_configured():
        try:
            return remote_client.get(f"/api/v1/tasks/{task_id}/history") or []
        except Exception:
            logger.warning(f"Failed to fetch remote history for {task_id}")
    return []


def create_task_history(task_id: str, phase: str = None, status: str = None,
                        agent: str = None, note: str = None) -> dict:
    with get_cursor() as cur:
        cur.execute("""
            INSERT INTO task_history (task_id, phase, status, agent, note)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING *
        """, (task_id, phase, status, agent, note))
        return cur.fetchone()


# ── Task Metrics ──


def create_task_metrics(task_id: str, agent: str, tool_uses: int = None,
                        tokens: int = None, duration: int = None) -> dict:
    with get_cursor() as cur:
        cur.execute("""
            INSERT INTO task_metrics (task_id, agent, tool_uses, tokens, duration)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING *
        """, (task_id, agent, tool_uses, tokens, duration))
        return cur.fetchone()


# ── Dashboard-specific queries (merged local + remote) ──


_projects_cache: dict = {"data": [], "expires": 0}

def list_projects(org_id: str) -> list[str]:
    now = time.time()
    if _projects_cache["data"] and now < _projects_cache["expires"]:
        return _projects_cache["data"]

    with get_cursor() as cur:
        cur.execute(
            "SELECT DISTINCT project FROM tasks WHERE org_id = %s ORDER BY project",
            (org_id,),
        )
        local = [row["project"] for row in cur.fetchall()]

    if not remote_client.is_configured():
        result = local
    else:
        try:
            domains = remote_client.get("/api/v1/domains")
            remote = sorted(set(d["project"] for d in domains if d.get("project")))
            result = sorted(set(local + remote))
        except Exception:
            logger.warning("Failed to fetch remote projects")
            # Use cached data if available, otherwise fall back to local
            result = _projects_cache["data"] or local

    _projects_cache["data"] = result
    _projects_cache["expires"] = now + 300  # 5 minutes
    return result


def list_tasks_for_board(org_id: str, project: str = "", type: str = "",
                         domain: str = "") -> list[dict]:
    conditions = ["org_id = %s"]
    params: list = [org_id]
    if project:
        conditions.append("project = %s")
        params.append(project)
    if type:
        conditions.append("type = %s")
        params.append(type)
    if domain:
        conditions.append("domain = %s")
        params.append(domain)
    conditions.append(
        "(status NOT IN ('completed','verified','aborted','failed')"
        " OR (status IN ('completed','verified') AND updated_at > NOW() - INTERVAL '7 days'))"
    )
    where = " AND ".join(conditions)

    with get_cursor() as cur:
        cur.execute(f"""
            SELECT id, type, status, project, domain, description, created_at, updated_at
            FROM tasks WHERE {where}
            ORDER BY updated_at DESC
        """, params)
        local = cur.fetchall()

    merged = merge_lists(local, "/api/v1/tasks",
                         project=project, type=type, domain=domain, limit=200)
    # Filter merged results client-side (remote API may not support all filters)
    if type:
        merged = [t for t in merged if t.get("type") == type]
    return merged


def list_fix_tasks_with_causation(org_id: str, project: str = "") -> list[dict]:
    conditions = ["org_id = %s", "type = 'fix'", "causation IS NOT NULL"]
    params: list = [org_id]
    if project:
        conditions.append("project = %s")
        params.append(project)
    where = " AND ".join(conditions)

    with get_cursor() as cur:
        cur.execute(f"""
            SELECT id, type, status, project, domain, description, causation, created_at
            FROM tasks WHERE {where}
            ORDER BY created_at DESC
        """, params)
        local = cur.fetchall()

    merged = merge_lists(local, "/api/v1/tasks", project=project, limit=200)
    # Filter remote results for fix + causation
    return [t for t in merged if t.get("type") == "fix" and t.get("causation")]
