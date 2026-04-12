"""Org routing — merge data from local DB and remote API.

Since local and server have no overlapping projects, dashboard pages
query both sources and merge the results.

Write operations (create/update/delete) always go to local DB only.
"""

from __future__ import annotations

import logging
import remote_client

logger = logging.getLogger("org-routing")


def merge_lists(local: list, remote_path: str, **params) -> list:
    """Merge local DB results with remote API results."""
    if not remote_client.is_configured():
        return local
    try:
        remote = remote_client.get(remote_path, **params)
        if isinstance(remote, list):
            return local + remote
        # Paginated response
        return local + remote.get("items", [])
    except Exception:
        logger.warning(f"Failed to fetch remote {remote_path}, using local only")
        return local


def merge_paginated(local: dict, remote_path: str, **params) -> dict:
    """Merge paginated results from local DB and remote API."""
    if not remote_client.is_configured():
        return local

    local_items = local.get("items", [])
    try:
        remote = remote_client.get(remote_path, **params)
        remote_items = remote.get("items", []) if isinstance(remote, dict) else remote
        return {
            "items": local_items + remote_items,
            "total": local.get("total", 0) + (remote.get("total", 0) if isinstance(remote, dict) else len(remote_items)),
            "limit": local.get("limit", 50),
            "offset": local.get("offset", 0),
        }
    except Exception:
        logger.warning(f"Failed to fetch remote {remote_path}, using local only")
        return local


def merge_dicts(local: dict, remote_path: str, **params) -> dict:
    """Merge dict results (e.g. grouped data) from local DB and remote API."""
    if not remote_client.is_configured():
        return local
    try:
        remote = remote_client.get(remote_path, **params)
        if isinstance(remote, dict):
            merged = dict(local)
            for k, v in remote.items():
                if k in merged:
                    merged[k] = merged[k] + v
                else:
                    merged[k] = v
            return merged
        return local
    except Exception:
        logger.warning(f"Failed to fetch remote {remote_path}, using local only")
        return local
