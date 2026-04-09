"""Jira Cloud REST API v3 client for Triage Bot."""

import base64
import json
import logging
import os
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

logger = logging.getLogger("jira-client")

JIRA_BASE_URL = os.environ.get("JIRA_BASE_URL", "")
JIRA_EMAIL = os.environ.get("JIRA_EMAIL", "")
JIRA_TOKEN = os.environ.get("JIRA_API_TOKEN", "")
JIRA_PROJECT_KEY = os.environ.get("JIRA_PROJECT_KEY", "CORE")
JIRA_ISSUE_TYPE = os.environ.get("JIRA_ISSUE_TYPE", "Bug")


class JiraError(Exception):
    """Jira API error."""
    def __init__(self, status: int, detail: str):
        self.status = status
        self.detail = detail
        super().__init__(f"Jira {status}: {detail}")


def _auth_header() -> str:
    """Return Basic Auth header for Jira API."""
    credentials = f"{JIRA_EMAIL}:{JIRA_TOKEN}"
    encoded = base64.b64encode(credentials.encode()).decode()
    return f"Basic {encoded}"


def _request(method: str, path: str, data: dict | None = None) -> dict | list:
    """Make HTTP request to Jira API.

    Args:
        method: HTTP method (GET, POST, etc.)
        path: API path (e.g., "/rest/api/3/issue")
        data: Request body (will be JSON-encoded)

    Returns:
        Parsed JSON response

    Raises:
        JiraError: If API returns error
    """
    url = f"{JIRA_BASE_URL}{path}"
    body = json.dumps(data, default=str).encode() if data else None

    req = Request(url, data=body, method=method)
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", _auth_header())

    try:
        with urlopen(req, timeout=30) as resp:
            raw = resp.read()
            if not raw:
                return {}
            return json.loads(raw)
    except HTTPError as e:
        detail = e.read().decode()[:500]
        logger.error(f"Jira API {e.code}: {detail}")
        raise JiraError(e.code, detail)
    except URLError as e:
        logger.error(f"Jira connection error: {e}")
        raise JiraError(0, f"Connection error: {e}")


def search_similar(project_key: str, keywords: str, limit: int = 5) -> list[dict]:
    """Search for similar Jira issues by keywords.

    Uses JQL to find recent issues matching keywords.

    Args:
        project_key: Jira project key (e.g., "CORE")
        keywords: Search keywords (comma-separated or phrases)
        limit: Max results

    Returns:
        List of issue dicts with key, summary, created, priority
    """
    # Escape keywords for JQL
    safe_keywords = keywords.replace('"', '\\"').replace("'", "\\'")

    # JQL: search in summary + description, order by created DESC
    jql = f'project = {project_key} AND text ~ "{safe_keywords}" ORDER BY created DESC'

    try:
        response = _request("POST", "/rest/api/3/search", {
            "jql": jql,
            "maxResults": limit,
            "fields": ["key", "summary", "created", "priority", "status"],
        })
    except JiraError as e:
        logger.warning(f"Search similar issues failed: {e.detail}")
        return []

    issues = []
    for issue in response.get("issues", []):
        issues.append({
            "key": issue.get("key"),
            "summary": issue.get("fields", {}).get("summary", ""),
            "created": issue.get("fields", {}).get("created", "")[:10],  # Date only
            "priority": issue.get("fields", {}).get("priority", {}).get("name", ""),
            "status": issue.get("fields", {}).get("status", {}).get("name", ""),
        })

    return issues


def _build_adf_document(sections: dict) -> dict:
    """Build Atlassian Document Format (ADF) for Jira description.

    Args:
        sections: Dict with keys like "problem", "steps", "expected", "actual", "analysis"

    Returns:
        ADF document (nested dict structure)
    """
    content = []

    # Problem description
    if sections.get("problem"):
        content.append({
            "type": "heading",
            "attrs": {"level": 2},
            "content": [{"type": "text", "text": "問題描述"}],
        })
        content.append({
            "type": "paragraph",
            "content": [{"type": "text", "text": sections["problem"]}],
        })

    # Steps to reproduce
    if sections.get("steps"):
        content.append({
            "type": "heading",
            "attrs": {"level": 2},
            "content": [{"type": "text", "text": "重現步驟"}],
        })
        for i, step in enumerate(sections["steps"], 1):
            content.append({
                "type": "paragraph",
                "content": [{"type": "text", "text": f"{i}. {step}"}],
            })

    # Expected vs Actual
    if sections.get("expected") or sections.get("actual"):
        content.append({
            "type": "heading",
            "attrs": {"level": 2},
            "content": [{"type": "text", "text": "預期 vs 實際"}],
        })
        if sections.get("expected"):
            content.append({
                "type": "paragraph",
                "content": [{"type": "text", "text": f"• 預期: {sections['expected']}"}],
            })
        if sections.get("actual"):
            content.append({
                "type": "paragraph",
                "content": [{"type": "text", "text": f"• 實際: {sections['actual']}"}],
            })

    # Affected scope
    if sections.get("impact"):
        content.append({
            "type": "heading",
            "attrs": {"level": 2},
            "content": [{"type": "text", "text": "受影響範圍"}],
        })
        content.append({
            "type": "paragraph",
            "content": [{"type": "text", "text": sections["impact"]}],
        })

    # AI Triage analysis
    if sections.get("analysis"):
        content.append({
            "type": "heading",
            "attrs": {"level": 2},
            "content": [{"type": "text", "text": "AI Triage 分析報告"}],
        })
        content.append({
            "type": "paragraph",
            "content": [{"type": "text", "text": sections["analysis"]}],
        })

    # Footer
    content.append({
        "type": "paragraph",
        "content": [{"type": "text", "text": "_AI Triage Bot 自動生成 | 需 PM 確認_"}],
    })

    return {
        "version": 1,
        "type": "doc",
        "content": content,
    }


def create_issue(
    summary: str,
    sections: dict,
    priority: str = "Medium",
    labels: list[str] | None = None,
    project_key: str | None = None,
    issue_type: str | None = None,
) -> dict:
    """Create a Jira issue.

    Args:
        summary: Issue title
        sections: Dict with problem, steps, expected, actual, impact, analysis
        priority: Priority name (Highest, High, Medium, Low)
        labels: List of labels (will add "triage-auto")
        project_key: Override default project
        issue_type: Override default issue type

    Returns:
        Dict with keys: key, id, url

    Raises:
        JiraError: If API call fails
    """
    pkey = project_key or JIRA_PROJECT_KEY
    itype = issue_type or JIRA_ISSUE_TYPE

    # Add triage label
    all_labels = ["triage-auto", "awaiting-pm-review"] + (labels or [])

    # Build ADF description
    description = _build_adf_document(sections)

    fields = {
        "project": {"key": pkey},
        "issuetype": {"name": itype},
        "summary": f"[Triage] {summary}",
        "priority": {"name": priority},
        "description": description,
        "labels": all_labels,
    }

    try:
        response = _request("POST", "/rest/api/3/issues", {"fields": fields})
    except JiraError as e:
        logger.error(f"Create issue failed: {e.detail}")
        raise

    return {
        "key": response.get("key", ""),
        "id": response.get("id", ""),
        "url": f"{JIRA_BASE_URL}/browse/{response.get('key', '')}",
    }
