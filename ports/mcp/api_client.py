"""HTTP client for ATDD API Server — used by MCP tools.

Dual-API routing:
- Local API: personal org (side projects)
- Server API: company org (company projects)
- Resource-level: 404 on local → auto-fallback to server
- Project-level: known company projects → write directly to server
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

logger = logging.getLogger("mcp-api")

# Local API
API_BASE_URL = os.environ.get("ATDD_API_URL", "http://localhost:8001")
API_KEY = os.environ.get("ATDD_API_KEY", "")
DEFAULT_ORG = os.environ.get("ATDD_ORG", "00000000-0000-0000-0000-000000000001")

# Server API
SERVER_API_URL = os.environ.get("ATDD_SERVER_API_URL", "")
SERVER_API_KEY = os.environ.get("ATDD_SERVER_API_KEY", "")
SERVER_ORG = os.environ.get("ATDD_SERVER_ORG", "00000000-0000-0000-0000-000000000002")

# Company projects — these always route to server
# Loaded once from server API on first use, cached
_company_projects: set[str] | None = None


def _get_company_projects() -> set[str]:
    """Fetch list of projects from server to determine routing."""
    global _company_projects
    if _company_projects is not None:
        return _company_projects

    if not SERVER_API_URL:
        _company_projects = set()
        return _company_projects

    try:
        result = _do_request(
            SERVER_API_URL, SERVER_API_KEY, "GET",
            "/api/v1/tasks",
            params={"org_id": SERVER_ORG, "limit": "1"},
        )
        # Get distinct projects from server
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
        _company_projects = projects
        logger.info(f"Company projects: {projects}")
    except Exception:
        _company_projects = set()
    return _company_projects


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


def _is_company_project(data: dict | None, params: dict | None) -> bool:
    """Check if this request is for a company project."""
    project = None
    if data and isinstance(data, dict):
        project = data.get("project")
    if not project and params:
        project = params.get("project")
    if project and project in _get_company_projects():
        return True
    return False


def request(method: str, path: str, data: dict | None = None,
            params: dict | None = None) -> Any:
    """Route request to the correct API.

    Routing logic:
    1. If data contains a known company project → go to server directly
    2. Otherwise try local first
    3. If local returns 404 → fallback to server
    """
    # For creates with a known company project, go straight to server
    if SERVER_API_URL and _is_company_project(data, params):
        server_params = dict(params) if params else {}
        server_params["org_id"] = SERVER_ORG
        return _do_request(SERVER_API_URL, SERVER_API_KEY, method, path, data, server_params)

    try:
        return _do_request(API_BASE_URL, API_KEY, method, path, data, params)
    except APIError as e:
        if e.status == 404 and SERVER_API_URL:
            server_params = dict(params) if params else {}
            if "org_id" in server_params:
                server_params["org_id"] = SERVER_ORG
            return _do_request(SERVER_API_URL, SERVER_API_KEY, method, path, data, server_params)
        raise


# ── Convenience helpers ──

def get(path: str, **params) -> Any:
    return request("GET", path, params={"org_id": DEFAULT_ORG, **params})

def post(path: str, data: dict, **params) -> Any:
    return request("POST", path, data=data, params={"org_id": DEFAULT_ORG, **params})

def patch(path: str, data: dict) -> Any:
    return request("PATCH", path, data=data)

def put(path: str, data: dict, **params) -> Any:
    return request("PUT", path, data=data, params={"org_id": DEFAULT_ORG, **params})

def delete(path: str) -> Any:
    return request("DELETE", path)
