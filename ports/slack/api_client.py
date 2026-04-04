"""HTTP client for ATDD API Server.

Used by the Slack Bot to write task/domain data through the API
instead of directly writing files.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Optional
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

logger = logging.getLogger("api-client")

API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")
DEFAULT_ORG = os.environ.get("ATDD_ORG", "00000000-0000-0000-0000-000000000001")


def _request(method: str, path: str, data: dict | None = None,
             params: dict | None = None) -> dict | list | None:
    """Make an HTTP request to the API."""
    url = f"{API_BASE_URL}{path}"
    if params:
        qs = "&".join(f"{k}={v}" for k, v in params.items() if v is not None)
        if qs:
            url = f"{url}?{qs}"

    body = json.dumps(data).encode() if data else None
    req = Request(url, data=body, method=method)
    req.add_header("Content-Type", "application/json")

    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except HTTPError as e:
        body = e.read().decode()
        logger.error(f"API {method} {path} → {e.code}: {body[:200]}")
        return None
    except URLError as e:
        logger.error(f"API {method} {path} → connection error: {e}")
        return None


# ── Task API ──


def create_task(project: str, task_type: str, description: str,
                domain: str | None = None, **kwargs) -> dict | None:
    """Create a task via API."""
    data = {
        "project": project,
        "type": task_type,
        "description": description,
        "domain": domain,
    }
    data.update(kwargs)
    return _request("POST", "/api/v1/tasks", data=data,
                    params={"org_id": DEFAULT_ORG})


def update_task(task_id: str, **kwargs) -> dict | None:
    """Update a task via API."""
    return _request("PATCH", f"/api/v1/tasks/{task_id}", data=kwargs)


def get_task(task_id: str) -> dict | None:
    """Get a task by ID."""
    return _request("GET", f"/api/v1/tasks/{task_id}")


def list_tasks(project: str | None = None, status: str | None = None) -> list:
    """List tasks."""
    result = _request("GET", "/api/v1/tasks",
                      params={"org_id": DEFAULT_ORG, "project": project, "status": status})
    if result and isinstance(result, dict):
        return result.get("items", [])
    return []


def add_task_history(task_id: str, phase: str | None = None,
                     status: str | None = None, agent: str | None = None,
                     note: str | None = None) -> dict | None:
    """Add a history event to a task."""
    return _request("POST", f"/api/v1/tasks/{task_id}/history", data={
        "phase": phase, "status": status, "agent": agent, "note": note,
    })


# ── Domain API ──


def upsert_domain(project: str, name: str, health_score: float | None = None,
                  status: str | None = None) -> dict | None:
    """Create or update a domain."""
    return _request("PUT", "/api/v1/domains", data={
        "project": project, "name": name,
        "health_score": health_score, "status": status,
    }, params={"org_id": DEFAULT_ORG})


def list_domains(project: str | None = None) -> list:
    """List domains."""
    result = _request("GET", "/api/v1/domains",
                      params={"org_id": DEFAULT_ORG, "project": project})
    return result if isinstance(result, list) else []


# ── Health Check ──


def health() -> bool:
    """Check if API is reachable."""
    result = _request("GET", "/health")
    return result is not None and result.get("status") == "ok"
