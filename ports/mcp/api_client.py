"""HTTP client for ATDD API Server — used by MCP tools.

Dual-API routing:
- Local API: personal org (side projects)
- Server API: company org (company projects)
- 404 on local → auto-fallback to server (all methods)
- Writes follow the data: task on server → write to server
"""

from __future__ import annotations

import json
import os
from typing import Any
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

# Local API
API_BASE_URL = os.environ.get("ATDD_API_URL", "http://localhost:8001")
API_KEY = os.environ.get("ATDD_API_KEY", "")
DEFAULT_ORG = os.environ.get("ATDD_ORG", "00000000-0000-0000-0000-000000000001")

# Server API
SERVER_API_URL = os.environ.get("ATDD_SERVER_API_URL", "")
SERVER_API_KEY = os.environ.get("ATDD_SERVER_API_KEY", "")
SERVER_ORG = os.environ.get("ATDD_SERVER_ORG", "00000000-0000-0000-0000-000000000002")


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


def request(method: str, path: str, data: dict | None = None,
            params: dict | None = None) -> Any:
    """Route request: try local first, fallback to server on 404."""
    try:
        return _do_request(API_BASE_URL, API_KEY, method, path, data, params)
    except APIError as e:
        if e.status == 404 and SERVER_API_URL:
            # Resource not on local → try server with server org
            server_params = dict(params) if params else {}
            if "org_id" in server_params:
                server_params["org_id"] = SERVER_ORG
            return _do_request(SERVER_API_URL, SERVER_API_KEY, method, path, data, server_params)
        raise


# ── Convenience helpers ──
# List/create use org_id param; get/patch/delete use resource path (no org needed)

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
