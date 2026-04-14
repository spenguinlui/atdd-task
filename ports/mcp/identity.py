"""Resolve the identity of who triggered an MCP write.

Resolution chain (first match wins):
1. ATDD_USER env var       — explicit override (bot/CI/orchestrator)
2. .atdd/user.json (cwd)   — project-local
3. ~/.atdd/user.json       — user-global
4. git config user.email   — last fallback
5. 'claude:unknown'        — nothing worked

Resolved identity is stored at module import time and returned by
get_identity(). MCP tools call this to auto-fill updated_by.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from pathlib import Path

logger = logging.getLogger("mcp-identity")


def _read_json_config(path: Path) -> str | None:
    """Return human:<name> or human:<email> if config readable."""
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
    except Exception as e:
        logger.warning(f"Failed to parse {path}: {e}")
        return None
    # Prefer name over email for display
    if name := data.get("name"):
        return f"human:{name}"
    if email := data.get("email"):
        return f"human:{email}"
    return None


def _git_user_email() -> str | None:
    try:
        email = subprocess.check_output(
            ["git", "config", "user.email"],
            text=True, stderr=subprocess.DEVNULL, timeout=2,
        ).strip()
        return email or None
    except Exception:
        return None


def resolve_identity() -> str:
    """Resolve identity once, following the priority chain."""
    # 1. Explicit env override
    if user := os.environ.get("ATDD_USER"):
        logger.info(f"Identity from ATDD_USER: {user}")
        return user

    # 2. Project-local config
    if ident := _read_json_config(Path(".atdd/user.json")):
        logger.info(f"Identity from project config: {ident}")
        return ident

    # 3. User-global config
    if ident := _read_json_config(Path.home() / ".atdd/user.json"):
        logger.info(f"Identity from home config: {ident}")
        return ident

    # 4. Git user.email fallback
    if email := _git_user_email():
        logger.info(f"Identity from git: human:{email}")
        return f"human:{email}"

    # 5. Nothing
    logger.warning("No identity resolved, using claude:unknown")
    return "claude:unknown"


# Resolved once at import time
IDENTITY: str = resolve_identity()


def get_identity() -> str:
    """Return the current resolved identity."""
    return IDENTITY
