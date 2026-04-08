"""Dashboard HTML page routes — server-rendered with Jinja2 + HTMX.

Each deployment (local / server) reads its own DB only.
Cross-environment access is via org switcher URL redirect.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from db import get_cursor, ORG_PERSONAL, ORG_COMPANY

router = APIRouter()

# Which org does THIS deployment serve?
LOCAL_ORG = os.environ.get("ATDD_ORG", ORG_PERSONAL)

# Remote dashboard URL for org switcher (empty = no switcher)
REMOTE_DASHBOARD_URL = os.environ.get("REMOTE_DASHBOARD_URL", "")

# Status → Kanban column mapping
COLUMN_MAP = {
    "requirement": "Requirement",
    "pending_spec": "Spec",
    "specification": "Spec",
    "specifying": "Spec",
    "testing": "Testing",
    "pending_dev": "Dev",
    "development": "Dev",
    "developing": "Dev",
    "pending_review": "Review",
    "review": "Review",
    "reviewing": "Review",
    "gate": "Gate",
    "deployed": "Deployed",
    "completed": "Completed",
    "verified": "Completed",
    "aborted": "Failed",
    "failed": "Failed",
    "escaped": "Escaped",
}

KANBAN_COLUMNS = [
    "Requirement", "Spec", "Testing", "Dev", "Review", "Gate", "Deployed", "Completed",
]

PERIOD_DAYS = {"7d": 7, "30d": 30, "90d": 90, "all": None}


def _json_serial(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, UUID):
        return str(obj)
    raise TypeError(f"Type {type(obj)} not serializable")


def _get_projects() -> list[str]:
    with get_cursor() as cur:
        cur.execute(
            "SELECT DISTINCT project FROM tasks WHERE org_id = %s ORDER BY project",
            (LOCAL_ORG,),
        )
        return [row["project"] for row in cur.fetchall()]


def _period_start(period: str) -> Optional[datetime]:
    days = PERIOD_DAYS.get(period)
    if days is None:
        return None
    return datetime.now(timezone.utc) - timedelta(days=days)


def _base_ctx(request: Request, active_page: str, **extra) -> dict:
    """Common template context shared by all pages."""
    return {
        "request": request,
        "active_page": active_page,
        "remote_dashboard_url": REMOTE_DASHBOARD_URL,
        **extra,
    }


# ── Pages ──


@router.get("/", response_class=HTMLResponse)
def overview(request: Request, period: str = "30d", project: str = ""):
    templates = request.app.state.templates
    is_htmx = request.headers.get("HX-Request") == "true"

    start = _period_start(period)
    projects = _get_projects()

    conditions = ["org_id = %s"]
    params: list = [LOCAL_ORG]
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
        type_status = cur.fetchall()

        cur.execute(f"""
            SELECT date_trunc('week', created_at AT TIME ZONE 'Asia/Taipei')::date as week,
                   count(*) as created,
                   count(*) FILTER (WHERE status IN ('completed','verified')) as completed
            FROM tasks WHERE {where}
            GROUP BY week ORDER BY week
        """, params)
        weekly = cur.fetchall()

        metric_conditions = ["t.org_id = %s"]
        metric_params: list = [LOCAL_ORG]
        if start:
            metric_conditions.append("m.timestamp >= %s")
            metric_params.append(start)
        if project:
            metric_conditions.append("t.project = %s")
            metric_params.append(project)
        metric_where = " AND ".join(metric_conditions)

        cur.execute(f"""
            SELECT t.type,
                   coalesce(sum(m.tool_uses), 0) as total_tools,
                   coalesce(sum(m.tokens), 0) as total_tokens,
                   coalesce(avg(m.duration), 0) as avg_duration
            FROM task_metrics m
            JOIN tasks t ON t.id = m.task_id
            WHERE {metric_where}
            GROUP BY t.type
        """, metric_params)
        cost_by_type = cur.fetchall()

    total_created = sum(r["cnt"] for r in type_status)
    total_completed = sum(r["cnt"] for r in type_status if r["status"] in ("completed", "verified"))
    total_fixes = sum(r["cnt"] for r in type_status if r["type"] == "fix")
    total_features = sum(r["cnt"] for r in type_status if r["type"] == "feature")
    total_escaped = sum(r["cnt"] for r in type_status if r["status"] == "escaped")
    fix_rate = round(total_fixes / total_features * 100, 1) if total_features else 0
    escape_rate = round(total_escaped / total_created * 100, 1) if total_created else 0
    completion_rate = round(total_completed / total_created * 100, 1) if total_created else 0

    trend_labels = [str(r["week"]) for r in weekly]
    trend_created = [r["created"] for r in weekly]
    trend_completed = [r["completed"] for r in weekly]
    cost_labels = [r["type"] for r in cost_by_type]
    cost_tools = [r["total_tools"] for r in cost_by_type]
    cost_tokens = [r["total_tokens"] for r in cost_by_type]

    ctx = _base_ctx(request, "overview",
        period=period, project=project, projects=projects,
        total_created=total_created, total_completed=total_completed,
        fix_rate=fix_rate, escape_rate=escape_rate, completion_rate=completion_rate,
        trend_labels=json.dumps(trend_labels, default=_json_serial),
        trend_created=json.dumps(trend_created),
        trend_completed=json.dumps(trend_completed),
        cost_labels=json.dumps(cost_labels),
        cost_tools=json.dumps(cost_tools),
        cost_tokens=json.dumps(cost_tokens),
    )

    if is_htmx:
        return templates.TemplateResponse("pages/_overview_metrics.html", ctx)
    return templates.TemplateResponse("pages/overview.html", ctx)


@router.get("/domains", response_class=HTMLResponse)
def domain_health(request: Request, project: str = ""):
    templates = request.app.state.templates
    projects = _get_projects()

    conditions = ["org_id = %s"]
    params: list = [LOCAL_ORG]
    if project:
        conditions.append("project = %s")
        params.append(project)
    where = " AND ".join(conditions)

    with get_cursor() as cur:
        cur.execute(f"""
            SELECT * FROM domains WHERE {where}
            ORDER BY project, name
        """, params)
        domains = cur.fetchall()

        cur.execute(f"""
            SELECT * FROM domain_couplings WHERE {where}
            ORDER BY co_occurrence_count DESC LIMIT 30
        """, params)
        couplings = cur.fetchall()

    return templates.TemplateResponse("pages/domain_health.html", _base_ctx(
        request, "domains",
        project=project, projects=projects, domains=domains, couplings=couplings,
    ))


@router.get("/domains/{domain_name:path}", response_class=HTMLResponse)
def domain_detail(request: Request, domain_name: str, project: str = ""):
    templates = request.app.state.templates

    with get_cursor() as cur:
        if project:
            cur.execute(
                "SELECT * FROM domains WHERE org_id = %s AND project = %s AND name = %s",
                (LOCAL_ORG, project, domain_name),
            )
        else:
            cur.execute(
                "SELECT * FROM domains WHERE org_id = %s AND name = %s LIMIT 1",
                (LOCAL_ORG, domain_name),
            )
        domain = cur.fetchone()

        cur.execute("""
            SELECT id, type, status, description, created_at, updated_at
            FROM tasks WHERE org_id = %s AND domain = %s
            ORDER BY created_at DESC LIMIT 20
        """, (LOCAL_ORG, domain_name))
        tasks = cur.fetchall()

        cur.execute("""
            SELECT file_type, count(*) as cnt
            FROM knowledge_entries
            WHERE org_id = %s AND domain = %s
            GROUP BY file_type
        """, (LOCAL_ORG, domain_name))
        knowledge = {r["file_type"]: r["cnt"] for r in cur.fetchall()}

        cur.execute("""
            SELECT * FROM domain_couplings
            WHERE org_id = %s AND (domain_a = %s OR domain_b = %s)
            ORDER BY co_occurrence_count DESC
        """, (LOCAL_ORG, domain_name, domain_name))
        couplings = cur.fetchall()

        cur.execute("""
            SELECT date_trunc('week', created_at AT TIME ZONE 'Asia/Taipei')::date as week, count(*) as cnt
            FROM tasks
            WHERE org_id = %s AND domain = %s AND type = 'fix'
            GROUP BY week ORDER BY week
        """, (LOCAL_ORG, domain_name))
        fix_timeline = cur.fetchall()

    health_dimensions = {}
    if domain:
        health_dimensions = {
            "Fix Rate": float(domain.get("fix_rate") or 0) * 100,
            "Coupling": float(domain.get("coupling_rate") or 0) * 100,
            "Change Freq": float(domain.get("change_frequency") or 0) * 100,
            "Knowledge": float(domain.get("knowledge_coverage") or 0) * 100,
            "Escape Rate": float(domain.get("escape_rate") or 0) * 100,
        }

    return templates.TemplateResponse("pages/domain_detail.html", _base_ctx(
        request, "domains",
        domain_name=domain_name, domain=domain, tasks=tasks,
        knowledge=knowledge, couplings=couplings,
        health_dims_labels=json.dumps(list(health_dimensions.keys())),
        health_dims_values=json.dumps(list(health_dimensions.values())),
        fix_labels=json.dumps([str(r["week"]) for r in fix_timeline], default=_json_serial),
        fix_counts=json.dumps([r["cnt"] for r in fix_timeline]),
        knowledge_labels=json.dumps(list(knowledge.keys())),
        knowledge_values=json.dumps(list(knowledge.values())),
    ))


@router.get("/tasks", response_class=HTMLResponse)
def task_board(request: Request, project: str = "", type: str = "", domain: str = ""):
    templates = request.app.state.templates
    is_htmx = request.headers.get("HX-Request") == "true"
    projects = _get_projects()

    conditions = ["org_id = %s"]
    params: list = [LOCAL_ORG]
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
        all_tasks = cur.fetchall()

    board: dict[str, list] = {col: [] for col in KANBAN_COLUMNS}
    for t in all_tasks:
        col = COLUMN_MAP.get(t["status"], "Requirement")
        if col in board:
            board[col].append(t)

    ctx = _base_ctx(request, "tasks",
        project=project, type=type, domain=domain,
        projects=projects, board=board, columns=KANBAN_COLUMNS,
    )

    if is_htmx:
        return templates.TemplateResponse("pages/_task_board_inner.html", ctx)
    return templates.TemplateResponse("pages/task_board.html", ctx)


@router.get("/tasks/{task_id}/detail", response_class=HTMLResponse)
def task_detail(request: Request, task_id: str):
    templates = request.app.state.templates

    with get_cursor() as cur:
        cur.execute("SELECT * FROM tasks WHERE id = %s", (task_id,))
        task = cur.fetchone()
        cur.execute(
            "SELECT * FROM task_history WHERE task_id = %s ORDER BY timestamp",
            (task_id,),
        )
        history = cur.fetchall()

    return templates.TemplateResponse("partials/_task_modal.html", {
        "request": request,
        "task": task,
        "history": history,
    })


@router.get("/causation", response_class=HTMLResponse)
def causation_explorer(request: Request, project: str = ""):
    templates = request.app.state.templates
    projects = _get_projects()

    conditions = ["org_id = %s", "type = 'fix'", "causation IS NOT NULL"]
    params: list = [LOCAL_ORG]
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
        fix_tasks = cur.fetchall()

    chains: list[dict] = []
    for t in fix_tasks:
        c = t.get("causation") or {}
        caused_by = c.get("causedBy")
        if isinstance(caused_by, dict):
            parent_id = caused_by.get("taskId")
            parent_desc = caused_by.get("description", "")
        elif isinstance(caused_by, str):
            parent_id = caused_by
            parent_desc = ""
        else:
            parent_id = None
            parent_desc = ""
        chains.append({
            "id": str(t["id"]),
            "description": t["description"],
            "type": t["type"],
            "status": t["status"],
            "project": t["project"],
            "domain": t["domain"],
            "root_cause_type": c.get("rootCauseType", "unknown"),
            "discovered_in": c.get("discoveredIn", "unknown"),
            "parent_id": parent_id,
            "parent_desc": parent_desc,
            "created_at": t["created_at"],
        })

    return templates.TemplateResponse("pages/causation.html", _base_ctx(
        request, "causation",
        project=project, projects=projects, chains=chains,
    ))
