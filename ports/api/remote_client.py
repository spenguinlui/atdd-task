"""HTTP client for calling remote ATDD API Server.

Used by service layer when org_id != local org — fetches data from
the remote deployment's REST API instead of querying the local DB.

Env vars (same as MCP's api_client):
- ATDD_SERVER_API_URL: Remote server base URL (e.g. http://server:8001)
- ATDD_SERVER_API_KEY: API key for the remote server
- ATDD_SERVER_ORG: org_id on the remote server
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

logger = logging.getLogger("remote-client")

SERVER_API_URL = os.environ.get("ATDD_SERVER_API_URL", "")
SERVER_API_KEY = os.environ.get("ATDD_SERVER_API_KEY", "")
SERVER_ORG = os.environ.get("ATDD_SERVER_ORG", "00000000-0000-0000-0000-000000000002")


class RemoteAPIError(Exception):
    def __init__(self, status: int, detail: str):
        self.status = status
        self.detail = detail
        super().__init__(f"Remote API {status}: {detail}")


def is_configured() -> bool:
    """Check if remote server is configured."""
    return bool(SERVER_API_URL)


def get(path: str, **params) -> Any:
    """GET request to remote server API."""
    params["org_id"] = SERVER_ORG
    return _request("GET", path, params=params)


def _request(method: str, path: str, data: dict = None, params: dict = None) -> Any:
    url = f"{SERVER_API_URL}{path}"
    if params:
        qs = "&".join(f"{k}={v}" for k, v in params.items() if v is not None and v != "")
        if qs:
            url = f"{url}?{qs}"

    body = json.dumps(data, default=str).encode() if data else None
    req = Request(url, data=body, method=method)
    req.add_header("Content-Type", "application/json")
    if SERVER_API_KEY:
        req.add_header("X-API-Key", SERVER_API_KEY)

    try:
        with urlopen(req, timeout=15) as resp:
            raw = resp.read()
            if not raw:
                return None
            return json.loads(raw)
    except HTTPError as e:
        detail = e.read().decode()[:500]
        raise RemoteAPIError(e.code, detail)
    except URLError as e:
        raise RemoteAPIError(0, f"Connection error: {e}")
