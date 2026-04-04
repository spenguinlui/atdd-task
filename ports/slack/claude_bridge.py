"""Bridge between Slack bot and Claude CLI."""

import json
import logging
import os
import subprocess

logger = logging.getLogger("claude-bridge")

ATDD_HUB_PATH = os.environ.get("ATDD_HUB_PATH", os.path.expanduser("~/atdd-hub"))
REPOS_PATH = os.environ.get("REPOS_PATH", os.path.expanduser("~/repos"))
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")
ALLOWED_TOOLS = "Read,Write,Edit,Glob,Grep,Bash"


# Project name → repo directory mapping
PROJECT_REPO_MAP = {
    "core_web": "core_web",
    "sf_project": "sf_project",
    "e_trading": "e_trading",
    "jv_project": "jv_project",
}


def pull_project(project: str) -> str | None:
    """Git pull latest for a project repo. Returns error message or None."""
    repo_dir = PROJECT_REPO_MAP.get(project)
    if not repo_dir:
        return f"Unknown project: {project}"

    repo_path = os.path.join(REPOS_PATH, repo_dir)
    if not os.path.isdir(repo_path):
        return f"Repo not found: {repo_path}"

    try:
        result = subprocess.run(
            ["git", "pull", "--ff-only"],
            cwd=repo_path,
            capture_output=True, text=True, timeout=30,
        )
        logger.info(f"git pull {project}: {result.stdout.strip()}")
        if result.returncode != 0:
            return f"git pull failed: {result.stderr.strip()}"
        return None
    except subprocess.TimeoutExpired:
        return "git pull timed out"


def get_project_path(project: str) -> str | None:
    """Get the local repo path for a project."""
    repo_dir = PROJECT_REPO_MAP.get(project)
    if not repo_dir:
        return None
    path = os.path.join(REPOS_PATH, repo_dir)
    return path if os.path.isdir(path) else None


def run_claude(prompt: str, session_id: str | None = None) -> dict:
    """Run claude CLI in print mode and return parsed result.

    Returns dict with keys:
        - result: str (Claude's text response)
        - session_id: str
        - questions: list[dict] | None (extracted from AskUserQuestion denials)
        - is_error: bool
        - raw: dict (full JSON response)
    """
    cmd = ["claude", "-p", prompt, "--model", CLAUDE_MODEL,
           "--output-format", "json", "--allowedTools", ALLOWED_TOOLS]

    if session_id:
        cmd.extend(["--resume", session_id])

    logger.info(f"Running: claude -p (session={session_id or 'new'}, prompt={prompt[:80]}...)")

    try:
        proc = subprocess.run(
            cmd,
            cwd=ATDD_HUB_PATH,
            capture_output=True,
            text=True,
            timeout=300,  # 5 min max
        )
    except subprocess.TimeoutExpired:
        return {
            "result": "Claude CLI timed out after 5 minutes.",
            "session_id": session_id,
            "questions": None,
            "is_error": True,
            "raw": {},
        }

    # Parse JSON output
    try:
        raw = json.loads(proc.stdout)
    except (json.JSONDecodeError, ValueError):
        logger.error(f"Failed to parse CLI output: {proc.stdout[:500]}")
        return {
            "result": f"Failed to parse Claude response.\nstdout: {proc.stdout[:300]}\nstderr: {proc.stderr[:300]}",
            "session_id": session_id,
            "questions": None,
            "is_error": True,
            "raw": {},
        }

    result_text = raw.get("result", "")
    sid = raw.get("session_id", session_id)
    is_error = raw.get("is_error", False)

    # Extract AskUserQuestion from permission_denials
    questions = _extract_questions(raw.get("permission_denials", []))

    logger.info(f"CLI done: session={sid}, is_error={is_error}, "
                f"questions={len(questions) if questions else 0}, "
                f"result={result_text[:100]}...")

    return {
        "result": result_text,
        "session_id": sid,
        "questions": questions if questions else None,
        "is_error": is_error,
        "raw": raw,
    }


def _extract_questions(denials: list) -> list[dict]:
    """Extract AskUserQuestion data from permission_denials."""
    questions = []
    for denial in denials:
        if denial.get("tool_name") == "AskUserQuestion":
            tool_input = denial.get("tool_input", {})
            qs = tool_input.get("questions", [])
            if qs:
                questions.extend(qs)
    return questions
