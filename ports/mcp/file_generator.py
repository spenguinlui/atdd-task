#!/usr/bin/env python3
"""File Generator: Sync DB tasks → local JSON files.

Generates local task JSON files from the ATDD API, maintaining backward
compatibility with subagents that read tasks/{project}/active/*.json.

Usage:
    python file_generator.py                    # Sync all active tasks
    python file_generator.py --project sf_project  # Sync one project
    python file_generator.py --task UUID        # Sync one task
    python file_generator.py --all              # Sync all (including completed)

Requires ATDD API to be running. Uses the same api_client as the MCP server.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Add server/mcp to path for api_client
sys.path.insert(0, os.path.dirname(__file__))
import api_client as api

# Default hub path — where task JSON files live
HUB_PATH = os.environ.get("ATDD_HUB_PATH", os.path.expanduser("~/atdd-hub"))

# Status → directory mapping
STATUS_DIR_MAP = {
    "requirement": "active",
    "specification": "active",
    "testing": "active",
    "development": "active",
    "review": "active",
    "gate": "active",
    "pending_spec": "active",
    "specifying": "active",
    "pending_dev": "active",
    "developing": "active",
    "pending_review": "active",
    "reviewing": "active",
    "deployed": "deployed",
    "completed": "completed",
    "verified": "completed",
    "aborted": "failed",
    "failed": "failed",
    "escaped": "escaped",
}

# Terminal statuses (skip unless --all)
TERMINAL_STATUSES = {"completed", "verified", "aborted", "failed"}


def task_to_json(task: dict) -> dict:
    """Convert API task response to local JSON format."""
    metadata = task.get("metadata") or {}

    return {
        "id": task["id"],
        "type": task["type"],
        "description": task.get("description", ""),
        "status": task["status"],
        "projectId": task["project"],
        "projectName": task["project"],
        "domain": task.get("domain", ""),
        "git": metadata.get("git", {"branch": ""}),
        "agents": metadata.get("agents", []),
        "workflow": metadata.get("workflow", {
            "mode": "guided",
            "currentAgent": None,
            "confidence": 0,
            "pendingAction": None,
        }),
        "acceptance": metadata.get("acceptance", {
            "profile": None,
            "testLayers": {},
            "fixture": None,
            "results": {},
            "verificationGuide": None,
        }),
        "history": metadata.get("history", []),
        "jira": metadata.get("jira", {"issueKey": None, "url": None}),
        "causation": task.get("causation") or {
            "causedBy": None,
            "rootCauseType": None,
            "discoveredIn": None,
            "discoveredAt": None,
            "timeSinceIntroduced": None,
        },
        "context": metadata.get("context", {
            "background": "",
            "relatedDomains": task.get("related_domains") or [],
            "deletedFiles": [],
            "modifiedFiles": [],
            "changes": [],
            "commitHash": "",
        }),
        "metrics": metadata.get("metrics"),
        "epic": metadata.get("epic"),
        "createdAt": task.get("created_at", ""),
        "updatedAt": task.get("updated_at", ""),
    }


def dir_for_status(status: str) -> str:
    """Get the directory name for a task status."""
    return STATUS_DIR_MAP.get(status, "active")


def write_task_file(task: dict, hub_path: str, dry_run: bool = False) -> str:
    """Write a single task JSON file. Returns the file path."""
    project = task["project"]
    task_id = task["id"]
    status = task["status"]
    subdir = dir_for_status(status)

    dir_path = Path(hub_path) / "tasks" / project / subdir
    file_path = dir_path / f"{task_id}.json"

    local_json = task_to_json(task)

    if dry_run:
        return f"[DRY-RUN] {file_path}"

    dir_path.mkdir(parents=True, exist_ok=True)

    # Remove from other directories (task may have moved status)
    for other_dir in ["active", "deployed", "completed", "failed", "escaped"]:
        if other_dir == subdir:
            continue
        other_path = Path(hub_path) / "tasks" / project / other_dir / f"{task_id}.json"
        if other_path.exists():
            other_path.unlink()

    with open(file_path, "w") as f:
        json.dump(local_json, f, indent=2, ensure_ascii=False, default=str)

    return str(file_path)


def sync_tasks(
    project: str | None = None,
    task_id: str | None = None,
    include_all: bool = False,
    hub_path: str = HUB_PATH,
    dry_run: bool = False,
) -> list[str]:
    """Sync tasks from API to local JSON files."""
    synced = []

    if task_id:
        # Single task
        task = api.request("GET", f"/api/v1/tasks/{task_id}")
        path = write_task_file(task, hub_path, dry_run)
        synced.append(path)
    else:
        # List tasks
        params = {}
        if project:
            params["project"] = project

        offset = 0
        limit = 200
        while True:
            result = api.get("/api/v1/tasks", limit=str(limit), offset=str(offset), **params)
            items = result.get("items", [])
            if not items:
                break

            for task in items:
                if not include_all and task["status"] in TERMINAL_STATUSES:
                    continue
                path = write_task_file(task, hub_path, dry_run)
                synced.append(path)

            if len(items) < limit:
                break
            offset += limit

    return synced


def main():
    parser = argparse.ArgumentParser(description="ATDD File Generator: DB → local JSON")
    parser.add_argument("--project", help="Sync only this project")
    parser.add_argument("--task", help="Sync a single task by UUID")
    parser.add_argument("--all", action="store_true", help="Include completed/aborted tasks")
    parser.add_argument("--hub-path", default=HUB_PATH, help=f"Hub path (default: {HUB_PATH})")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be written")
    args = parser.parse_args()

    try:
        synced = sync_tasks(
            project=args.project,
            task_id=args.task,
            include_all=args.all,
            hub_path=args.hub_path,
            dry_run=args.dry_run,
        )

        if synced:
            for path in synced:
                print(f"  {path}")
            print(f"\nSynced {len(synced)} task(s).")
        else:
            print("No tasks to sync.")

    except api.APIError as e:
        print(f"API Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
