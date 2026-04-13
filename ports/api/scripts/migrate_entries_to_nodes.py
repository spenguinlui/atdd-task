#!/usr/bin/env python3
"""Migrate knowledge_entries to knowledge_nodes (semi-automatic).

For each unmigrated entry, prints a suggested node mapping.
In interactive mode, curator can approve/edit/skip each one.

Usage:
    python3 migrate_entries_to_nodes.py [--project core_web] [--domain "Crowdfund::TaxInfo"]
    python3 migrate_entries_to_nodes.py --dry-run
    python3 migrate_entries_to_nodes.py --entry-id <uuid>
    python3 migrate_entries_to_nodes.py --auto  # non-interactive, apply all suggestions
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from db import init_pool, close_pool, get_cursor
from services.knowledge_schemas import validate_attrs, NODE_TYPE_REGISTRY

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("migrate-entries")

FILE_TYPE_TO_LAYER = {
    "strategic": "strategic",
    "tactical": "tactical",
    "business-rules": "rule",
    "domain-map": "strategic",
}

SKIP_SECTIONS = {
    "Change History",
}

INDEX_SECTIONS = {
    "核心概念",
    "商務規則",
}


def suggest_node(entry: dict) -> dict | None:
    """Suggest a node mapping for an entry. Returns None if entry should be skipped."""
    section = entry.get("section", "") or ""
    file_type = entry.get("file_type", "") or ""
    content = entry.get("content", "") or ""

    if section in SKIP_SECTIONS:
        return None

    if section in INDEX_SECTIONS and len(content) < 500:
        return None

    layer = FILE_TYPE_TO_LAYER.get(file_type, "strategic")

    node_type = _guess_node_type(file_type, section, content)
    slug = _slugify(section)
    title = section
    summary = content[:200].replace("\n", " ").strip()
    if len(content) > 200:
        summary = summary[:197] + "..."

    return {
        "layer": layer,
        "node_type": node_type,
        "slug": slug,
        "title": title,
        "summary": summary,
        "attrs": _build_default_attrs(layer, node_type, content),
        "body_md": content,
    }


def _guess_node_type(file_type: str, section: str, content: str) -> str:
    if file_type == "business-rules":
        if any(kw in content.lower() for kw in ["cardinality", "1:1", "invariant"]):
            return "invariant"
        return "business_rule"
    if file_type == "domain-map":
        if "context mapping" in section.lower() or "context map" in content.lower():
            return "context_map"
        if "subdomain" in section.lower() or "supporting" in content.lower():
            return "subdomain"
        return "bounded_context"
    if file_type == "tactical":
        if "aggregate" in section.lower():
            return "aggregate"
        if "entity" in section.lower():
            return "entity"
        if "value object" in section.lower() or "vo" in section.lower():
            return "value_object"
        if "service" in section.lower():
            return "domain_service"
        if "repository" in section.lower():
            return "repository"
        if "event" in section.lower():
            return "domain_event"
        return "entity"
    if file_type == "strategic":
        if "商務依賴" in section or "dependency" in section.lower():
            return "context_map"
        if any(kw in section for kw in ["範疇", "商務目的", "商務能力", "常見問題"]):
            return "bounded_context"
        return "bounded_context"
    return "bounded_context"


def _slugify(text: str) -> str:
    import re
    slug = text.lower().strip()
    slug = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", slug)
    slug = slug.strip("-")
    return slug or "unnamed"


def _build_default_attrs(layer: str, node_type: str, content: str) -> dict:
    key = (layer, node_type)
    if key not in NODE_TYPE_REGISTRY:
        return {}
    model_cls = NODE_TYPE_REGISTRY[key]
    fields = model_cls.model_fields
    attrs = {}
    for name, field in fields.items():
        if field.is_required():
            if field.annotation == str or (hasattr(field.annotation, '__origin__') is False and field.annotation is str):
                attrs[name] = f"[TODO from migration: {name}]"
            elif "list" in str(field.annotation).lower():
                attrs[name] = []
            else:
                attrs[name] = f"[TODO: {name}]"
    return attrs


def get_unmigrated_entries(project: str = "", domain: str = "",
                           entry_id: str = "") -> list[dict]:
    conditions = ["COALESCE(migrated, false) = false"]
    params: list = []

    if entry_id:
        conditions.append("id = %s")
        params.append(entry_id)
    else:
        if project:
            conditions.append("project = %s")
            params.append(project)
        if domain:
            conditions.append("domain = %s")
            params.append(domain)

    where = " AND ".join(conditions)

    with get_cursor() as cur:
        cur.execute(f"""
            SELECT * FROM knowledge_entries
            WHERE {where}
            ORDER BY domain, file_type, section
        """, params)
        return list(cur.fetchall())


def apply_migration(entry: dict, node_data: dict, org_id: str, dry_run: bool = False):
    if dry_run:
        logger.info(f"  [DRY RUN] Would create node: {node_data['layer']}/{node_data['node_type']}/{node_data['slug']}")
        return

    with get_cursor() as cur:
        try:
            validated = validate_attrs(node_data["layer"], node_data["node_type"], node_data["attrs"])
        except Exception as e:
            logger.warning(f"  Attrs validation failed: {e}. Storing with empty attrs placeholder.")
            validated = node_data["attrs"]

        cur.execute("""
            INSERT INTO knowledge_nodes
                (org_id, project, domain, layer, node_type, slug,
                 title, summary, attrs, body_md, legacy_entry_id, updated_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (org_id, project, domain, layer, node_type, slug) DO NOTHING
            RETURNING id
        """, (
            org_id, entry["project"], entry.get("domain", ""),
            node_data["layer"], node_data["node_type"], node_data["slug"],
            node_data["title"], node_data["summary"],
            json.dumps(validated, default=str, ensure_ascii=False),
            node_data.get("body_md"),
            str(entry["id"]),
            "claude:migration-script",
        ))
        result = cur.fetchone()

        if result:
            node_id = result["id"]
            cur.execute("""
                INSERT INTO knowledge_node_revisions
                    (node_id, version, attrs, body_md, change_reason, changed_by)
                VALUES (%s, 1, %s, %s, %s, %s)
            """, (
                node_id,
                json.dumps(validated, default=str, ensure_ascii=False),
                node_data.get("body_md"),
                "migrated from knowledge_entries",
                "claude:migration-script",
            ))

            cur.execute("""
                UPDATE knowledge_entries
                SET migrated = true, migrated_to_node_id = %s
                WHERE id = %s
            """, (node_id, entry["id"]))
            logger.info(f"  Created node {node_id} and marked entry as migrated")
        else:
            cur.execute("""
                UPDATE knowledge_entries SET migrated = true WHERE id = %s
            """, (entry["id"],))
            logger.info(f"  Node already exists (conflict), marked entry as migrated")


def mark_skipped(entry_id: str, dry_run: bool = False):
    if dry_run:
        logger.info(f"  [DRY RUN] Would mark entry {entry_id} as migrated (no node)")
        return
    with get_cursor() as cur:
        cur.execute("""
            UPDATE knowledge_entries
            SET migrated = true, migrated_to_node_id = NULL
            WHERE id = %s
        """, (entry_id,))
    logger.info(f"  Marked entry as migrated (no node created)")


def main():
    parser = argparse.ArgumentParser(description="Migrate knowledge_entries to knowledge_nodes")
    parser.add_argument("--project", default="")
    parser.add_argument("--domain", default="")
    parser.add_argument("--entry-id", default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--auto", action="store_true", help="Non-interactive, apply all suggestions")
    parser.add_argument("--org-id", default="00000000-0000-0000-0000-000000000002")
    args = parser.parse_args()

    init_pool()

    try:
        entries = get_unmigrated_entries(args.project, args.domain, args.entry_id)
        logger.info(f"Found {len(entries)} unmigrated entries")

        for i, entry in enumerate(entries, 1):
            logger.info(f"\n[{i}/{len(entries)}] {entry.get('file_type')}: {entry.get('section', '(no section)')}")
            logger.info(f"  Domain: {entry.get('domain')}, Content length: {len(entry.get('content', ''))}")

            suggestion = suggest_node(entry)

            if suggestion is None:
                logger.info(f"  -> SKIP (index/history section)")
                if args.auto:
                    mark_skipped(str(entry["id"]), args.dry_run)
                elif not args.dry_run:
                    resp = input("  Skip this entry? [Y/n] ").strip().lower()
                    if resp in ("", "y", "yes"):
                        mark_skipped(str(entry["id"]), args.dry_run)
                else:
                    mark_skipped(str(entry["id"]), args.dry_run)
                continue

            logger.info(f"  -> Suggested: {suggestion['layer']}/{suggestion['node_type']}/{suggestion['slug']}")
            logger.info(f"     Title: {suggestion['title']}")
            logger.info(f"     Summary: {suggestion['summary'][:100]}...")

            if args.auto or args.dry_run:
                apply_migration(entry, suggestion, args.org_id, args.dry_run)
            else:
                resp = input("  Apply? [Y/n/s(kip)] ").strip().lower()
                if resp in ("", "y", "yes"):
                    apply_migration(entry, suggestion, args.org_id, False)
                elif resp in ("s", "skip"):
                    mark_skipped(str(entry["id"]), False)
                else:
                    logger.info("  Skipped (not marked)")

        logger.info("\nMigration complete.")

    finally:
        close_pool()


if __name__ == "__main__":
    main()
