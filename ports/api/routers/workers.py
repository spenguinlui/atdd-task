"""Worker trigger endpoints.

讓 cron、Dashboard、或 MCP 能觸發 worker 任務。
"""

from __future__ import annotations

import sys
import os
from typing import Optional

from fastapi import APIRouter, Query, BackgroundTasks

# Allow importing worker modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "worker"))

router = APIRouter()


@router.post("/weekly-report")
def trigger_weekly_report(
    project: Optional[str] = None,
    week: Optional[str] = None,
    save: bool = True,
    bg: BackgroundTasks = None,
):
    """Generate weekly report. Can run in background."""
    from weekly_report import generate_weekly_report, save_report

    data = generate_weekly_report(project, week)
    report_id = None
    if save:
        report_id = save_report(data)

    # Broadcast SSE event
    try:
        from routers.events import broadcast_event
        broadcast_event("report.generated", {
            "type": "weekly",
            "week": data["week"],
            "project": data["project"],
        })
    except Exception:
        pass

    return {"report_id": str(report_id) if report_id else None, "data": data}


@router.post("/auto-verify")
def trigger_auto_verify(dry_run: bool = False, slack_notify: bool = False):
    """Run auto-verify on deployed tasks."""
    from auto_verify import run

    result = run(dry_run=dry_run, slack_notify=slack_notify)

    # Broadcast SSE events for verified tasks
    try:
        from routers.events import broadcast_event
        if result["auto_verified"] > 0:
            broadcast_event("deploy.verified", {"count": result["auto_verified"]})
        if result["alerts"] > 0:
            broadcast_event("deploy.alert", {"count": result["alerts"]})
    except Exception:
        pass

    return result


@router.post("/domain-health")
def trigger_domain_health_recalc(project: Optional[str] = None, dry_run: bool = False):
    """Recalculate domain health scores."""
    from domain_health_recalc import recalculate

    results = recalculate(project=project, dry_run=dry_run)

    # Broadcast SSE event
    try:
        from routers.events import broadcast_event
        broadcast_event("domain.recalculated", {
            "count": len(results),
            "project": project or "all",
        })
    except Exception:
        pass

    return {
        "recalculated": len(results),
        "summary": {
            "healthy": len([r for r in results if r["status"] == "healthy"]),
            "degraded": len([r for r in results if r["status"] == "degraded"]),
            "critical": len([r for r in results if r["status"] == "critical"]),
        },
    }
