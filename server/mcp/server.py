"""ATDD MCP Server — Phase 3.

Exposes ATDD API as MCP tools for Claude Code.
Run via stdio: python server.py
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

import api_client as api

mcp = FastMCP(
    "atdd",
    instructions="ATDD Platform tools for managing tasks, domains, knowledge, and reports.",
)


# ════════════════════════════════════════════════════════════════
# Task Tools
# ════════════════════════════════════════════════════════════════


@mcp.tool()
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
        status: Filter by status (pending_spec, specifying, pending_dev, developing,
                pending_review, reviewing, gate, deployed, verified, escaped, completed, aborted)
        domain: Filter by domain name
        limit: Max results (default 50, max 200)
        offset: Pagination offset
    """
    params = {"project": project, "status": status, "domain": domain,
              "limit": str(limit), "offset": str(offset)}
    return api.get("/api/v1/tasks", **params)


@mcp.tool()
def atdd_task_get(task_id: str) -> dict:
    """Get a single task by its UUID.

    Args:
        task_id: Task UUID
    """
    return api.request("GET", f"/api/v1/tasks/{task_id}")


@mcp.tool()
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
        status: New status
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
def atdd_task_history(task_id: str) -> list:
    """Get the event history for a task.

    Args:
        task_id: Task UUID
    """
    return api.request("GET", f"/api/v1/tasks/{task_id}/history")


@mcp.tool()
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
def atdd_domain_get(domain_id: str) -> dict:
    """Get a single domain by UUID.

    Args:
        domain_id: Domain UUID
    """
    return api.request("GET", f"/api/v1/domains/{domain_id}")


@mcp.tool()
def atdd_domain_upsert(
    project: str,
    name: str,
    health_score: float | None = None,
    status: str | None = None,
    fix_rate: float | None = None,
    coupling_rate: float | None = None,
    change_frequency: float | None = None,
    knowledge_coverage: float | None = None,
    escape_rate: float | None = None,
) -> dict:
    """Create or update a domain health record (upsert by project + name).

    Args:
        project: Project name
        name: Domain name (e.g. "Accounting::AccountsPayable")
        health_score: Overall health score (0-100)
        status: Health status — healthy (>=70), degraded (40-69), critical (<40)
        fix_rate: fix_count / feature_count ratio
        coupling_rate: cross_domain_tasks / total_tasks ratio
        change_frequency: Recent change frequency ratio
        knowledge_coverage: Knowledge documentation coverage ratio
        escape_rate: Production escape ratio
    """
    data = {"project": project, "name": name}
    if health_score is not None:
        data["health_score"] = health_score
    if status is not None:
        data["status"] = status
    if fix_rate is not None:
        data["fix_rate"] = fix_rate
    if coupling_rate is not None:
        data["coupling_rate"] = coupling_rate
    if change_frequency is not None:
        data["change_frequency"] = change_frequency
    if knowledge_coverage is not None:
        data["knowledge_coverage"] = knowledge_coverage
    if escape_rate is not None:
        data["escape_rate"] = escape_rate
    return api.put("/api/v1/domains", data)


@mcp.tool()
def atdd_coupling_list(project: str | None = None) -> list:
    """List domain coupling relationships (sorted by co-occurrence count descending).

    Args:
        project: Filter by project name
    """
    return api.get("/api/v1/domains/couplings/list", project=project)


# ════════════════════════════════════════════════════════════════
# Knowledge Tools
# ════════════════════════════════════════════════════════════════


@mcp.tool()
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
def atdd_knowledge_get(entry_id: str) -> dict:
    """Get a single knowledge entry by UUID.

    Args:
        entry_id: Knowledge entry UUID
    """
    return api.request("GET", f"/api/v1/knowledge/entries/{entry_id}")


@mcp.tool()
def atdd_knowledge_create(
    project: str,
    content: str,
    domain: str | None = None,
    file_type: str | None = None,
    section: str | None = None,
    updated_by: str | None = None,
) -> dict:
    """Create a knowledge entry.

    Args:
        project: Project name
        content: Knowledge content (markdown supported)
        domain: Domain name this knowledge belongs to
        file_type: Type — strategic, tactical, business-rules, domain-map
        section: Section heading within the knowledge file
        updated_by: Who created this — "claude:session_xxx" or "slack:U123"
    """
    data = {"project": project, "content": content}
    if domain is not None:
        data["domain"] = domain
    if file_type is not None:
        data["file_type"] = file_type
    if section is not None:
        data["section"] = section
    if updated_by is not None:
        data["updated_by"] = updated_by
    return api.post("/api/v1/knowledge/entries", data)


@mcp.tool()
def atdd_knowledge_update(
    entry_id: str,
    content: str | None = None,
    domain: str | None = None,
    file_type: str | None = None,
    section: str | None = None,
    updated_by: str | None = None,
) -> dict:
    """Update a knowledge entry (partial update, auto-increments version).

    Args:
        entry_id: Knowledge entry UUID
        content: New content
        domain: New domain
        file_type: New file type
        section: New section heading
        updated_by: Who made this update
    """
    data = {}
    if content is not None:
        data["content"] = content
    if domain is not None:
        data["domain"] = domain
    if file_type is not None:
        data["file_type"] = file_type
    if section is not None:
        data["section"] = section
    if updated_by is not None:
        data["updated_by"] = updated_by
    return api.patch(f"/api/v1/knowledge/entries/{entry_id}", data)


@mcp.tool()
def atdd_knowledge_delete(entry_id: str) -> str:
    """Delete a knowledge entry.

    Args:
        entry_id: Knowledge entry UUID
    """
    api.delete(f"/api/v1/knowledge/entries/{entry_id}")
    return f"Deleted entry {entry_id}"


@mcp.tool()
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


@mcp.tool()
def atdd_term_upsert(
    project: str,
    english_term: str,
    chinese_term: str,
    domain: str | None = None,
    context: str | None = None,
    source: str | None = None,
) -> dict:
    """Create or update a UL term (upsert by project + english_term).

    Args:
        project: Project name
        english_term: English term name
        chinese_term: Chinese translation
        domain: Domain this term belongs to
        context: Usage context or definition
        source: Where this term came from — ul.md, slack, code
    """
    data = {"project": project, "english_term": english_term, "chinese_term": chinese_term}
    if domain is not None:
        data["domain"] = domain
    if context is not None:
        data["context"] = context
    if source is not None:
        data["source"] = source
    return api.put("/api/v1/knowledge/terms", data)


# ════════════════════════════════════════════════════════════════
# Report Tools
# ════════════════════════════════════════════════════════════════


@mcp.tool()
def atdd_report_list(
    project: str | None = None,
    type: str | None = None,
    limit: int = 20,
) -> list:
    """List reports.

    Args:
        project: Filter by project name
        type: Filter by report type — weekly, monthly, domain-health, causation
        limit: Max results (default 20, max 100)
    """
    return api.get("/api/v1/reports", project=project, type=type, limit=str(limit))


@mcp.tool()
def atdd_report_get(report_id: str) -> dict:
    """Get a single report by UUID.

    Args:
        report_id: Report UUID
    """
    return api.request("GET", f"/api/v1/reports/{report_id}")


@mcp.tool()
def atdd_report_create(
    project: str,
    type: str,
    data: dict,
    period: str | None = None,
) -> dict:
    """Create a report.

    Args:
        project: Project name
        type: Report type — weekly, monthly, domain-health, causation
        data: Report data as a JSON object
        period: Time period — "2026-W14" for weekly, "2026-03" for monthly
    """
    body = {"project": project, "type": type, "data": data}
    if period is not None:
        body["period"] = period
    return api.post("/api/v1/reports", body)


# ════════════════════════════════════════════════════════════════
# Health Check
# ════════════════════════════════════════════════════════════════


@mcp.tool()
def atdd_health() -> dict:
    """Check if the ATDD API server is reachable and healthy."""
    return api.request("GET", "/health")


if __name__ == "__main__":
    mcp.run()
