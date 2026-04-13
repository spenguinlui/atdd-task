"""Dashboard HTML page routes — server-rendered with Jinja2 + HTMX.

Automatically merges data from local DB and remote API.
No org switching needed — projects don't overlap between deployments.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from services import task_service, domain_service, knowledge_service, overview_service

router = APIRouter()

# Which org does THIS deployment serve?
LOCAL_ORG = os.environ.get("ATDD_ORG", "00000000-0000-0000-0000-000000000001")

# Remote dashboard URL for org switcher (empty = no switcher)
REMOTE_DASHBOARD_URL = os.environ.get("REMOTE_DASHBOARD_URL", "")

# Status → column mapping
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


def _period_start(period: str):
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
        "sidebar_domains": domain_service.list_sidebar_domains(LOCAL_ORG),
        "sidebar_projects": task_service.list_projects(LOCAL_ORG),
        **extra,
    }


# ── Pages ──


@router.get("/", response_class=HTMLResponse)
def overview(request: Request, period: str = "30d", project: str = ""):
    templates = request.app.state.templates
    is_htmx = request.headers.get("HX-Request") == "true"

    start = _period_start(period)
    projects = task_service.list_projects(LOCAL_ORG)

    type_status = overview_service.get_type_status_aggregation(LOCAL_ORG, start, project)
    weekly = overview_service.get_weekly_trends(LOCAL_ORG, start, project)
    cost_by_type = overview_service.get_cost_by_type(LOCAL_ORG, start, project)

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
    projects = task_service.list_projects(LOCAL_ORG)

    domains = domain_service.list_domains(LOCAL_ORG, project=project)
    couplings = domain_service.list_couplings(LOCAL_ORG, project=project)

    return templates.TemplateResponse("pages/domain_health.html", _base_ctx(
        request, "domains",
        project=project, projects=projects, domains=domains, couplings=couplings,
    ))


@router.get("/domains/{domain_name:path}", response_class=HTMLResponse)
def domain_detail(request: Request, domain_name: str, project: str = ""):
    templates = request.app.state.templates

    domain = domain_service.get_domain_by_name(LOCAL_ORG, domain_name, project)
    tasks = domain_service.get_domain_tasks(LOCAL_ORG, domain_name)
    knowledge = domain_service.get_domain_knowledge_stats(LOCAL_ORG, domain_name)
    couplings = domain_service.list_couplings_for_domain(LOCAL_ORG, domain_name)
    fix_timeline = domain_service.get_domain_fix_timeline(LOCAL_ORG, domain_name)

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
    projects = task_service.list_projects(LOCAL_ORG)

    all_tasks = task_service.list_tasks_for_board(LOCAL_ORG, project, type, domain)

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

    task = task_service.get_task(task_id)
    history = task_service.list_task_history(task_id)

    return templates.TemplateResponse("partials/_task_modal.html", {
        "request": request,
        "task": task,
        "history": history,
    })


@router.get("/knowledge", response_class=HTMLResponse)
def knowledge_browser(request: Request, project: str = "", domain: str = "", file_type: str = ""):
    templates = request.app.state.templates
    projects = task_service.list_projects(LOCAL_ORG)

    type_stats = knowledge_service.get_type_stats(LOCAL_ORG, project, domain, file_type)
    grouped = knowledge_service.list_entries_grouped(LOCAL_ORG, project, domain, file_type)
    terms = knowledge_service.list_terms(LOCAL_ORG, project, domain)
    all_domains = knowledge_service.list_all_domains(LOCAL_ORG)

    total_entries = sum(r["cnt"] for r in type_stats)
    migration_stats = knowledge_service.get_migration_stats(LOCAL_ORG)

    return templates.TemplateResponse("pages/knowledge.html", _base_ctx(
        request, "knowledge",
        project=project, domain=domain, file_type=file_type,
        projects=projects, all_domains=all_domains,
        type_stats=type_stats, total_entries=total_entries,
        grouped=grouped, terms=terms,
        migration_stats=migration_stats,
    ))


@router.get("/causation", response_class=HTMLResponse)
def causation_explorer(request: Request, project: str = ""):
    templates = request.app.state.templates
    projects = task_service.list_projects(LOCAL_ORG)

    fix_tasks = task_service.list_fix_tasks_with_causation(LOCAL_ORG, project)

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
