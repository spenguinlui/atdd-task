#!/usr/bin/env python3
"""Causation Tracer — git blame → commit → task 反查

供 specist 在 fix 任務調查階段使用。
給定問題檔案和行號，追溯到造成問題的原始任務。

Usage:
    python3 causation-tracer.py <project-repo-path> <file> <line>

    # Example: 追溯 app/services/erp_period_service.rb 第 42 行
    python3 causation-tracer.py ~/repos/core_web app/services/erp_period_service.rb 42

Output (JSON):
    {
        "commit": "abc123",
        "author": "liu",
        "date": "2026-03-11",
        "message": "feat: monthly split for ERP electric bills",
        "task": {
            "taskId": "a8a9f6d2-...",
            "description": "monthly split",
            "type": "feature",
            "domain": "Tools::ErpPeriod",
            "completedAt": "2026-03-11T15:30:00Z"
        }
    }

    If no matching task found, "task" will be null.
"""

import json
import os
import subprocess
import sys

# Add ports/mcp to path for api_client
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "ports", "mcp"))
import api_client as api


def git_blame_line(repo_path, file_path, line_number):
    """Run git blame on a specific line, return commit info."""
    try:
        result = subprocess.run(
            ["git", "blame", "-L", f"{line_number},{line_number}", "--porcelain", file_path],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return None

        lines = result.stdout.strip().split("\n")
        if not lines:
            return None

        commit_hash = lines[0].split()[0]

        info = {"commit": commit_hash}
        for line in lines[1:]:
            if line.startswith("author "):
                info["author"] = line[len("author "):]
            elif line.startswith("author-time "):
                import datetime
                ts = int(line[len("author-time "):])
                info["date"] = datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
            elif line.startswith("summary "):
                info["message"] = line[len("summary "):]

        return info
    except (subprocess.TimeoutExpired, Exception) as e:
        print(f"Error running git blame: {e}", file=sys.stderr)
        return None


def fetch_all_tasks():
    """Fetch all tasks from API with pagination."""
    all_tasks = []
    offset = 0
    limit = 200
    while True:
        result = api.get("/api/v1/tasks", limit=str(limit), offset=str(offset))
        items = result.get("items", [])
        if not items:
            break
        all_tasks.extend(items)
        if len(items) < limit:
            break
        offset += limit
    return all_tasks


def find_task_by_commit(tasks, commit_hash):
    """Search tasks for a matching commitHash in metadata."""
    for task in tasks:
        metadata = task.get("metadata") or {}
        context = metadata.get("context", {})
        task_commit = context.get("commitHash", "")
        if task_commit and commit_hash.startswith(task_commit[:7]):
            return {
                "taskId": task.get("id"),
                "description": task.get("description"),
                "type": task.get("type"),
                "domain": task.get("domain"),
                "completedAt": context.get("completedAt"),
            }
    return None


def find_task_by_commit_message(tasks, commit_message):
    """Fallback: try to match commit message keywords to task descriptions."""
    if not commit_message:
        return None

    msg_lower = commit_message.lower()
    for prefix in ["feat:", "fix:", "refactor:", "chore:", "sync:"]:
        if msg_lower.startswith(prefix):
            msg_lower = msg_lower[len(prefix):].strip()
            break

    candidates = []
    for task in tasks:
        if task.get("status") not in ("completed", "verified", "deployed", "escaped"):
            continue
        desc = (task.get("description") or "").lower()
        words = [w for w in msg_lower.split() if len(w) > 3]
        matches = sum(1 for w in words if w in desc)
        if matches >= 2 or (len(words) <= 2 and matches >= 1):
            candidates.append((matches, task))

    if candidates:
        candidates.sort(key=lambda x: -x[0])
        task = candidates[0][1]
        metadata = task.get("metadata") or {}
        context = metadata.get("context", {})
        return {
            "taskId": task.get("id"),
            "description": task.get("description"),
            "type": task.get("type"),
            "domain": task.get("domain"),
            "completedAt": context.get("completedAt"),
            "_matchType": "fuzzy",
        }

    return None


def main():
    if len(sys.argv) < 4:
        print("Usage: python3 causation-tracer.py <repo-path> <file> <line>")
        sys.exit(1)

    from pathlib import Path
    repo_path = Path(sys.argv[1])
    file_path = sys.argv[2]
    line_number = sys.argv[3]

    # Step 1: git blame
    blame_info = git_blame_line(repo_path, file_path, line_number)
    if not blame_info:
        print(json.dumps({"error": f"Could not git blame {file_path}:{line_number}"}, ensure_ascii=False))
        sys.exit(1)

    # Step 2: fetch tasks from API
    try:
        tasks = fetch_all_tasks()
    except api.APIError as e:
        print(json.dumps({"error": f"API Error: {e}"}, ensure_ascii=False))
        sys.exit(1)

    # Step 3: find task by commit hash
    task = find_task_by_commit(tasks, blame_info["commit"])

    # Step 4: fallback to commit message matching
    if not task and blame_info.get("message"):
        task = find_task_by_commit_message(tasks, blame_info["message"])

    # Output
    result = {
        "commit": blame_info.get("commit"),
        "author": blame_info.get("author"),
        "date": blame_info.get("date"),
        "message": blame_info.get("message"),
        "task": task,
    }

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
