"""Org routing — decide whether to query local DB or remote API.

Each service function calls `is_remote(org_id)` to decide the data source.
When remote, the service calls remote_client instead of get_cursor().
"""

from __future__ import annotations

import os

LOCAL_ORG = os.environ.get("ATDD_ORG", "00000000-0000-0000-0000-000000000001")


def is_remote(org_id: str) -> bool:
    """True if org_id is not the local deployment's org."""
    return org_id != LOCAL_ORG
