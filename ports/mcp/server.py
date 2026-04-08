"""ATDD MCP Server — core tools for daily task workflows.

9 high-frequency tools used by commands/agents.
Low-frequency tools (knowledge CRUD, reports, diagnostics) are in server_admin.py.

Run via stdio: python server.py
"""

from __future__ import annotations

import functools
import logging

from mcp.server.fastmcp import FastMCP

import api_client as api

logger = logging.getLogger("mcp-server")


def safe_api_call(fn):
    """Catch API/connection errors so the MCP server stays alive."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except api.APIError as e:
            return {"error": True, "status": e.status, "detail": e.detail}
        except Exception as e:
            logger.exception(f"Tool {fn.__name__} failed")
            return {"error": True, "detail": f"Connection failed: {e}"}
    return wrapper

mcp = FastMCP(
    "atdd",
    instructions="ATDD Platform tools for managing tasks, domains, knowledge, and reports.",
)


# ════════════════════════════════════════════════════════════════
# Task Tools
# ════════════════════════════════════════════════════════════════


@mcp.tool()
@safe_api_call
def atdd_task_list(
    project: str | None = None,
    status: str | None = None,
    domain: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """List tasks with optional filters.

    Args:
        project: Filter by project name
        status: Filter by status (requirement, pending_spec, specifying, pending_dev, developing,
                pending_review, reviewing, gate, deployed, verified, escaped,
                completed, aborted, specification, testing, development, review, failed)
        domain: Filter by domain name
        limit: Max results (default 50, max 200)
        offset: Pagination offset
    """
    params = {"project": project, "status": status, "domain": domain,
              "limit": str(limit), "offset": str(offset)}
    return api.get("/api/v1/tasks", **params)


@mcp.tool()
@safe_api_call
def atdd_task_get(task_id: str) -> dict:
    """Get a single task by its UUID.

    Args:
        task_id: Task UUID
    """
    return api.request("GET", f"/api/v1/tasks/{task_id}")


@mcp.tool()
@safe_api_call
def atdd_task_create(
    project: str,
    type: str,
    description: str | None = None,
    domain: str | None = None,
    related_domains: list[str] | None = None,
    requirement: str | None = None,
    causation: dict | None = None,
    metadata: dict | None = None,
) -> dict:
    """Create a new task.

    Args:
        project: Project name (e.g. "core_web", "sf_project")
        type: Task type — feature, fix, refactor, test, or epic
        description: Task description
        domain: Primary domain name
        related_domains: List of related domain names
        requirement: Requirement text
        causation: Causation data (causedBy, rootCauseType, discoveredIn, etc.)
        metadata: Additional metadata as key-value pairs
    """
    data = {"project": project, "type": type}
    if description is not None:
        data["description"] = description
    if domain is not None:
        data["domain"] = domain
    if related_domains is not None:
        data["related_domains"] = related_domains
    if requirement is not None:
        data["requirement"] = requirement
    if causation is not None:
        data["causation"] = causation
    if metadata is not None:
        data["metadata"] = metadata
    return api.post("/api/v1/tasks", data)


@mcp.tool()
@safe_api_call
def atdd_task_update(
    task_id: str,
    status: str | None = None,
    phase: str | None = None,
    domain: str | None = None,
    related_domains: list[str] | None = None,
    description: str | None = None,
    requirement: str | None = None,
    causation: dict | None = None,
    metadata: dict | None = None,
) -> dict:
    """Update a task (partial update — only provided fields are changed).

    Args:
        task_id: Task UUID
        status: New status (requirement, pending_spec, specifying, pending_dev, developing,
                pending_review, reviewing, gate, deployed, verified, escaped,
                completed, aborted, specification, testing, development, review, failed)
        phase: Current phase (e.g. "requirement", "spec", "dev", "review", "gate")
        domain: Primary domain name
        related_domains: Related domain names
        description: Task description
        requirement: Requirement text
        causation: Causation data
        metadata: Metadata to merge (existing keys preserved, new keys added)
    """
    data = {}
    if status is not None:
        data["status"] = status
    if phase is not None:
        data["phase"] = phase
    if domain is not None:
        data["domain"] = domain
    if related_domains is not None:
        data["related_domains"] = related_domains
    if description is not None:
        data["description"] = description
    if requirement is not None:
        data["requirement"] = requirement
    if causation is not None:
        data["causation"] = causation
    if metadata is not None:
        data["metadata"] = metadata
    return api.patch(f"/api/v1/tasks/{task_id}", data)


@mcp.tool()
@safe_api_call
def atdd_task_add_history(
    task_id: str,
    phase: str | None = None,
    status: str | None = None,
    agent: str | None = None,
    note: str | None = None,
) -> dict:
    """Add a history event to a task.

    Args:
        task_id: Task UUID
        phase: Phase name (requirement, spec, dev, review, gate, deploy, etc.)
        status: Status at this point
        agent: Agent name (specist, coder, tester, risk-reviewer, gatekeeper, etc.)
        note: Free-text note about what happened
    """
    data = {"phase": phase, "status": status, "agent": agent, "note": note}
    return api.request("POST", f"/api/v1/tasks/{task_id}/history", data=data)


@mcp.tool()
@safe_api_call
def atdd_task_add_metrics(
    task_id: str,
    agent: str,
    tool_uses: int | None = None,
    tokens: int | None = None,
    duration: int | None = None,
) -> dict:
    """Record agent resource usage metrics for a task.

    Args:
        task_id: Task UUID
        agent: Agent name
        tool_uses: Number of tool calls
        tokens: Token count
        duration: Duration in seconds
    """
    data = {"agent": agent, "tool_uses": tool_uses, "tokens": tokens, "duration": duration}
    return api.request("POST", f"/api/v1/tasks/{task_id}/metrics", data=data)


# ════════════════════════════════════════════════════════════════
# Domain Tools
# ════════════════════════════════════════════════════════════════


@mcp.tool()
@safe_api_call
def atdd_domain_list(
    project: str | None = None,
    status: str | None = None,
) -> list:
    """List domains with health scores.

    Args:
        project: Filter by project name
        status: Filter by health status — healthy, degraded, or critical
    """
    return api.get("/api/v1/domains", project=project, status=status)


@mcp.tool()
@safe_api_call
def atdd_knowledge_list(
    project: str | None = None,
    domain: str | None = None,
    file_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """List knowledge entries with optional filters.

    Args:
        project: Filter by project name
        domain: Filter by domain name
        file_type: Filter by type — strategic, tactical, business-rules, domain-map
        limit: Max results (default 50, max 200)
        offset: Pagination offset
    """
    params = {"project": project, "domain": domain, "file_type": file_type,
              "limit": str(limit), "offset": str(offset)}
    return api.get("/api/v1/knowledge/entries", **params)


@mcp.tool()
@safe_api_call
def atdd_term_list(
    project: str | None = None,
    domain: str | None = None,
) -> list:
    """List Ubiquitous Language (UL) terms.

    Args:
        project: Filter by project name
        domain: Filter by domain name
    """
    return api.get("/api/v1/knowledge/terms", project=project, domain=domain)


if __name__ == "__main__":
    mcp.run()
