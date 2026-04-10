"""Report service — application layer between adapters and DB."""

from __future__ import annotations

import json
from typing import Optional

from db import get_cursor


def list_reports(org_id: str, project: str = "", type: str = "",
                 limit: int = 20) -> list[dict]:
    conditions = ["org_id = %s"]
    params: list = [org_id]

    if project:
        conditions.append("project = %s")
        params.append(project)
    if type:
        conditions.append("type = %s")
        params.append(type)

    where = " AND ".join(conditions)
    params.append(limit)

    with get_cursor() as cur:
        cur.execute(
            f"SELECT * FROM reports WHERE {where} ORDER BY created_at DESC LIMIT %s",
            params,
        )
        return cur.fetchall()


def create_report(org_id: str, project: str, type: str, data: dict,
                  period: str = None) -> dict:
    with get_cursor() as cur:
        cur.execute("""
            INSERT INTO reports (org_id, project, type, period, data)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING *
        """, (org_id, project, type, period, json.dumps(data)))
        return cur.fetchone()


def get_report(report_id: str) -> Optional[dict]:
    with get_cursor() as cur:
        cur.execute("SELECT * FROM reports WHERE id = %s", (report_id,))
        return cur.fetchone()
