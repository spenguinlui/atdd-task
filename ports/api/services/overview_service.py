"""Overview service — dashboard aggregation queries.

Overview aggregations only query local DB (no remote API equivalent).
Remote tasks are visible on the task board but not in overview stats.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from db import get_cursor


def get_type_status_aggregation(org_id: str, start: Optional[datetime] = None,
                                project: str = "") -> list[dict]:
    conditions = ["org_id = %s"]
    params: list = [org_id]
    if start:
        conditions.append("created_at >= %s")
        params.append(start)
    if project:
        conditions.append("project = %s")
        params.append(project)
    where = " AND ".join(conditions)

    with get_cursor() as cur:
        cur.execute(f"""
            SELECT type, status, count(*) as cnt
            FROM tasks WHERE {where}
            GROUP BY type, status
        """, params)
        return cur.fetchall()


def get_weekly_trends(org_id: str, start: Optional[datetime] = None,
                      project: str = "") -> list[dict]:
    conditions = ["org_id = %s"]
    params: list = [org_id]
    if start:
        conditions.append("created_at >= %s")
        params.append(start)
    if project:
        conditions.append("project = %s")
        params.append(project)
    where = " AND ".join(conditions)

    with get_cursor() as cur:
        cur.execute(f"""
            SELECT date_trunc('week', created_at AT TIME ZONE 'Asia/Taipei')::date as week,
                   count(*) as created,
                   count(*) FILTER (WHERE status IN ('completed','verified')) as completed
            FROM tasks WHERE {where}
            GROUP BY week ORDER BY week
        """, params)
        return cur.fetchall()


def get_cost_by_type(org_id: str, start: Optional[datetime] = None,
                     project: str = "") -> list[dict]:
    conditions = ["t.org_id = %s"]
    params: list = [org_id]
    if start:
        conditions.append("m.timestamp >= %s")
        params.append(start)
    if project:
        conditions.append("t.project = %s")
        params.append(project)
    where = " AND ".join(conditions)

    with get_cursor() as cur:
        cur.execute(f"""
            SELECT t.type,
                   coalesce(sum(m.tool_uses), 0) as total_tools,
                   coalesce(sum(m.tokens), 0) as total_tokens,
                   coalesce(avg(m.duration), 0) as avg_duration
            FROM task_metrics m
            JOIN tasks t ON t.id = m.task_id
            WHERE {where}
            GROUP BY t.type
        """, params)
        return cur.fetchall()
