"""HTTP client for ATDD API Server — used by MCP tools."""

from __future__ import annotations

import json
import os
from typing import Any
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

API_BASE_URL = os.environ.get("ATDD_API_URL", "http://localhost:8000")
DEFAULT_ORG = os.environ.get("ATDD_ORG", "00000000-0000-0000-0000-000000000001")


class APIError(Exception):
    def __init__(self, status: int, detail: str):
        self.status = status
        self.detail = detail
        super().__init__(f"API {status}: {detail}")


def request(method: str, path: str, data: dict | None = None,
            params: dict | None = None) -> Any:
    """Make an HTTP request to the API. Raises APIError on failure."""
    url = f"{API_BASE_URL}{path}"

    # Build query string
    if params:
        qs = "&".join(f"{k}={v}" for k, v in params.items() if v is not None)
        if qs:
            url = f"{url}?{qs}"

    body = json.dumps(data, default=str).encode() if data else None
    req = Request(url, data=body, method=method)
    req.add_header("Content-Type", "application/json")

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


# Convenience helpers

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
