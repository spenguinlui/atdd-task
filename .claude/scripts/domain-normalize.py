#!/usr/bin/env python3
"""Domain Name Normalization Script

透過 API 修正任務的 domain 命名不一致問題。

Usage:
    python3 domain-normalize.py [--dry-run]
"""

import json
import os
import sys

# Add ports/mcp to path for api_client
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "ports", "mcp"))
import api_client as api

# Normalization mapping: old_name → new_name
DOMAIN_MAP = {
    "ErpPeriod": "Tools::ErpPeriod",
    "DigiwinErp": "Tools::DigiwinErp",
    "Tool::Receipt": "Receipt",
    "ProjectManagement": "Project::Management",
    "ProjectManagement::Project": "Project::Management",
    "infrastructure": "InfrastructureAutomation",
}


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


def normalize_task(task, dry_run):
    """Normalize domain name for a single task. Returns change info or None."""
    domain = task.get("domain", "")
    if not domain:
        return None

    task_id = task["id"]
    changes = {}

    # Case 1: Comma-separated multi-domain
    if "," in domain:
        parts = [p.strip() for p in domain.split(",")]
        primary = parts[0]
        secondary = parts[1:]

        if primary in DOMAIN_MAP:
            primary = DOMAIN_MAP[primary]

        changes["old_domain"] = domain
        changes["new_domain"] = primary
        changes["added_related"] = secondary

        if not dry_run:
            api.patch(f"/api/v1/tasks/{task_id}", {
                "domain": primary,
                "related_domains": secondary,
            })

        return changes

    # Case 2: Simple rename
    if domain in DOMAIN_MAP:
        new_domain = DOMAIN_MAP[domain]
        changes["old_domain"] = domain
        changes["new_domain"] = new_domain

        if not dry_run:
            api.patch(f"/api/v1/tasks/{task_id}", {
                "domain": new_domain,
            })

        return changes

    return None


def main():
    dry_run = "--dry-run" in sys.argv

    print("=== Domain Name Normalization ===")
    print(f"Dry run: {dry_run}")
    print()
    print("Mapping:")
    for old, new in DOMAIN_MAP.items():
        print(f"  {old} → {new}")
    print("  (comma-separated) → split into domain + relatedDomains")
    print()

    try:
        tasks = fetch_all_tasks()
    except api.APIError as e:
        print(f"API Error: {e}", file=sys.stderr)
        sys.exit(1)

    modified = 0
    errors = 0

    for task in tasks:
        try:
            result = normalize_task(task, dry_run)
            if result:
                modified += 1
                task_id = task["id"][:8]
                old = result["old_domain"]
                new = result["new_domain"]
                extra = ""
                if "added_related" in result:
                    extra = f" (+relatedDomains: {result['added_related']})"
                prefix = "[DRY-RUN]" if dry_run else "[FIXED]"
                print(f"  {prefix} [{task_id}] {task.get('description', '')}")
                print(f"    '{old}' → '{new}'{extra}")
        except Exception as e:
            errors += 1
            print(f"  [ERROR] [{task['id'][:8]}]: {e}")

    print()
    print("=== Summary ===")
    print(f"Modified: {modified}")
    print(f"Errors: {errors}")
    print(f"Dry run: {dry_run}")

    if dry_run and modified > 0:
        print("\nRun without --dry-run to apply changes.")


if __name__ == "__main__":
    main()
