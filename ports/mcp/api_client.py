"""HTTP client for ATDD API Server — used by MCP tools.

Dual-API routing by org:
- sunnyfounder (server): all registered company projects (core_web, sf_project, etc.)
- sideproject (local): personal side projects (none currently)

Routing rules:
- Project-based ops: route by project registration
- UUID-based ops (no project context): try server first, fallback to local
- Since all current projects are sunnyfounder, server is the default target
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

logger = logging.getLogger("mcp-api")

# ── Org: sideproject (local) ──
LOCAL_API_URL = os.environ.get("ATDD_API_URL", "http://localhost:8001")
LOCAL_API_KEY = os.environ.get("ATDD_API_KEY", "")
LOCAL_ORG = os.environ.get("ATDD_ORG", "00000000-0000-0000-0000-000000000001")

# ── Org: sunnyfounder (server) ──
SERVER_API_URL = os.environ.get("ATDD_SERVER_API_URL", "")
SERVER_API_KEY = os.environ.get("ATDD_SERVER_API_KEY", "")
SERVER_ORG = os.environ.get("ATDD_SERVER_ORG", "00000000-0000-0000-0000-000000000002")

# Known sunnyfounder projects — cached from server on first use
_sunnyfounder_projects: set[str] | None = None


def _get_sunnyfounder_projects() -> set[str]:
    """Fetch registered projects from server."""
    global _sunnyfounder_projects
    if _sunnyfounder_projects is not None:
        return _sunnyfounder_projects

    if not SERVER_API_URL:
        _sunnyfounder_projects = set()
        return _sunnyfounder_projects

    try:
        result = _do_request(
            SERVER_API_URL, SERVER_API_KEY, "GET",
            "/api/v1/domains",
            params={"org_id": SERVER_ORG},
        )
        projects = set()
        items = result if isinstance(result, list) else result.get("items", []) if isinstance(result, dict) else []
        for d in items:
            if isinstance(d, dict) and d.get("project"):
                projects.add(d["project"])
        _sunnyfounder_projects = projects
        logger.info(f"Sunnyfounder projects: {projects}")
    except Exception:
        _sunnyfounder_projects = set()
    return _sunnyfounder_projects


def _is_sunnyfounder(project: str | None) -> bool:
    """Check if a project belongs to sunnyfounder org."""
    return bool(project and project in _get_sunnyfounder_projects())


class APIError(Exception):
    def __init__(self, status: int, detail: str):
        self.status = status
        self.detail = detail
        super().__init__(f"API {status}: {detail}")


def _do_request(base_url: str, api_key: str, method: str, path: str,
                data: dict | None = None, params: dict | None = None) -> Any:
    url = f"{base_url}{path}"
    if params:
        qs = "&".join(f"{k}={v}" for k, v in params.items() if v is not None)
        if qs:
            url = f"{url}?{qs}"

    body = json.dumps(data, default=str).encode() if data else None
    req = Request(url, data=body, method=method)
    req.add_header("Content-Type", "application/json")
    if api_key:
        req.add_header("X-API-Key", api_key)

    try:
        with urlopen(req, timeout=30) as resp:
            raw = resp.read()
            if not raw:
                return None
            return json.loads(raw)
    except HTTPError as e:
        detail = e.read().decode()[:500]
        raise APIError(e.code, detail)
    except URLError as e:
        raise APIError(0, f"Connection error: {e}")


def _extract_project(data: dict | None, params: dict | None) -> str | None:
    """Extract project from request data or params."""
    if data and isinstance(data, dict):
        project = data.get("project")
        if project:
            return project
    if params:
        return params.get("project")
    return None


def _server_request(method: str, path: str, data: dict | None = None,
                    params: dict | None = None) -> Any:
    server_params = dict(params) if params else {}
    server_params["org_id"] = SERVER_ORG
    return _do_request(SERVER_API_URL, SERVER_API_KEY, method, path, data, server_params)


def _local_request(method: str, path: str, data: dict | None = None,
                   params: dict | None = None) -> Any:
    local_params = dict(params) if params else {}
    local_params["org_id"] = LOCAL_ORG
    return _do_request(LOCAL_API_URL, LOCAL_API_KEY, method, path, data, local_params)


def request(method: str, path: str, data: dict | None = None,
            params: dict | None = None) -> Any:
    """Route request to the correct API.

    Routing logic:
    1. If project is known sunnyfounder → server
    2. If project is present but not sunnyfounder → local (sideproject)
    3. No project context (UUID-based ops) → server first, fallback to local
    """
    if not SERVER_API_URL:
        return _local_request(method, path, data, params)

    project = _extract_project(data, params)

    # Explicit project routing
    if project:
        if _is_sunnyfounder(project):
            return _server_request(method, path, data, params)
        else:
            return _local_request(method, path, data, params)

    # No project context (e.g. GET/PATCH /tasks/{uuid}) → server first
    try:
        return _server_request(method, path, data, params)
    except APIError as e:
        if e.status == 404:
            return _local_request(method, path, data, params)
        raise


# ── Convenience helpers ──

def get(path: str, **params) -> Any:
    return request("GET", path, params=params)

def post(path: str, data: dict, **params) -> Any:
    return request("POST", path, data=data, params=params)

def patch(path: str, data: dict) -> Any:
    return request("PATCH", path, data=data)

def put(path: str, data: dict, **params) -> Any:
    return request("PUT", path, data=data, params=params)

def delete(path: str) -> Any:
    return request("DELETE", path)
