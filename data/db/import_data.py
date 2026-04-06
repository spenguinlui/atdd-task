#!/usr/bin/env python3
"""Import historical data from atdd-hub into PostgreSQL.

Usage:
    python import_data.py                              # Default paths
    python import_data.py --hub ~/atdd-hub             # Custom hub path
    python import_data.py --db postgresql://...         # Custom DB URL
    python import_data.py --dry-run                    # Preview only
"""

from __future__ import annotations

import argparse
import glob
import json
import logging
import os
import re
import sys
from typing import Optional

import psycopg2
import psycopg2.extras

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("import")

DEFAULT_DB_URL = os.environ.get(
    "DATABASE_URL", "postgresql://atdd:atdd@localhost:5432/atdd"
)
DEFAULT_HUB = os.environ.get("ATDD_HUB_PATH", os.path.expanduser("~/atdd-hub"))
DEFAULT_ORG = os.environ.get(
    "ATDD_ORG", "00000000-0000-0000-0000-000000000001"
)

# Map task JSON status values → DB enum
STATUS_MAP = {
    "completed": "completed",
    "active": "developing",
    "closed": "completed",
    "failed": "aborted",
    "aborted": "aborted",
    "pending_spec": "pending_spec",
    "specifying": "specifying",
    "pending_dev": "pending_dev",
    "developing": "developing",
    "pending_review": "pending_review",
    "reviewing": "reviewing",
    "gate": "gate",
    "deployed": "deployed",
    "verified": "verified",
    "escaped": "escaped",
}

# Map task JSON type values → DB enum
TYPE_MAP = {
    "feature": "feature",
    "fix": "fix",
    "refactor": "refactor",
    "test": "test",
    "epic": "epic",
}


# ── Task Import ──


def find_task_files(hub_path: str) -> list[str]:
    """Find all task JSON files under tasks/."""
    pattern = os.path.join(hub_path, "tasks", "**", "*.json")
    return sorted(glob.glob(pattern, recursive=True))


def parse_task(filepath: str) -> dict | None:
    """Parse a task JSON file into DB-ready dict."""
    try:
        with open(filepath) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Skip {filepath}: {e}")
        return None

    task_id = data.get("id")
    if not task_id:
        logger.warning(f"Skip {filepath}: no id")
        return None

    # Pad short IDs to valid UUID format (some early tasks have 8-char IDs)
    if len(task_id) < 36:
        task_id = task_id.ljust(32, "0")
        task_id = f"{task_id[:8]}-{task_id[8:12]}-{task_id[12:16]}-{task_id[16:20]}-{task_id[20:32]}"

    task_type = TYPE_MAP.get(data.get("type", ""), "feature")

    # Derive status from directory if JSON status is ambiguous
    raw_status = data.get("status", "")
    status = STATUS_MAP.get(raw_status)
    if not status:
        # Infer from directory name
        parent_dir = os.path.basename(os.path.dirname(filepath))
        status = STATUS_MAP.get(parent_dir, "completed")

    project = data.get("projectId") or data.get("projectName") or ""

    # Extract domain info
    domain = data.get("domain")
    context = data.get("context") or {}
    related = context.get("relatedDomains") or []
    if isinstance(related, str):
        related = [r.strip() for r in related.split(",") if r.strip()]

    # Build causation
    causation = data.get("causation")

    # Everything else goes to metadata
    metadata = {}
    for key in ("git", "workflow", "acceptance", "jira", "epic"):
        if data.get(key):
            metadata[key] = data[key]
    # Store file paths
    for key in ("requirementPath", "baReportPath", "specPath",
                "testFiles", "deletedFiles", "modifiedFiles",
                "commitHash", "changes"):
        if context.get(key):
            metadata[key] = context[key]

    # History events
    history = []
    for entry in data.get("history", []):
        history.append({
            "phase": entry.get("phase"),
            "status": entry.get("status"),
            "agent": entry.get("agent"),
            "note": entry.get("note"),
            "timestamp": entry.get("timestamp") or entry.get("at"),
        })

    return {
        "id": task_id,
        "project": project,
        "type": task_type,
        "status": status,
        "phase": (data.get("workflow") or {}).get("currentAgent"),
        "domain": domain,
        "related_domains": related or None,
        "description": data.get("description"),
        "requirement": context.get("requirementPath"),
        "causation": causation,
        "metadata": metadata,
        "created_at": data.get("createdAt"),
        "updated_at": data.get("updatedAt"),
        "history": history,
    }


def import_tasks(conn, hub_path: str, dry_run: bool = False) -> int:
    """Import task JSONs into DB. Returns count."""
    files = find_task_files(hub_path)
    logger.info(f"Found {len(files)} task files")

    imported = 0
    skipped = 0

    for filepath in files:
        task = parse_task(filepath)
        if not task:
            skipped += 1
            continue

        if dry_run:
            logger.info(f"  [dry] {task['id'][:8]} {task['type']:10} {task['status']:15} {task['project']}")
            imported += 1
            continue

        cur = conn.cursor()
        try:
            # Upsert task
            cur.execute(
                """
                INSERT INTO tasks (id, org_id, project, type, status, phase, domain,
                                   related_domains, description, requirement,
                                   causation, metadata, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        COALESCE(%s::timestamptz, now()),
                        COALESCE(%s::timestamptz, now()))
                ON CONFLICT (id) DO UPDATE SET
                    status = EXCLUDED.status,
                    phase = EXCLUDED.phase,
                    domain = EXCLUDED.domain,
                    related_domains = EXCLUDED.related_domains,
                    causation = EXCLUDED.causation,
                    metadata = EXCLUDED.metadata,
                    updated_at = EXCLUDED.updated_at
                """,
                (
                    task["id"], DEFAULT_ORG, task["project"], task["type"],
                    task["status"], task["phase"], task["domain"],
                    task["related_domains"], task["description"],
                    task["requirement"],
                    json.dumps(task["causation"]) if task["causation"] else None,
                    json.dumps(task["metadata"]),
                    task["created_at"], task["updated_at"],
                ),
            )

            # Insert history
            for h in task["history"]:
                cur.execute(
                    """
                    INSERT INTO task_history (task_id, phase, status, agent, note, timestamp)
                    VALUES (%s, %s, %s, %s, %s, COALESCE(%s::timestamptz, now()))
                    """,
                    (task["id"], h["phase"], h["status"], h["agent"],
                     h["note"], h["timestamp"]),
                )

            conn.commit()
            imported += 1
        except Exception as e:
            conn.rollback()
            logger.warning(f"Failed {task['id'][:8]}: {e}")
            skipped += 1
        finally:
            cur.close()

    logger.info(f"Tasks: {imported} imported, {skipped} skipped")
    return imported


# ── Knowledge Import ──


def import_knowledge(conn, hub_path: str, dry_run: bool = False) -> int:
    """Import domain knowledge files into DB."""
    domains_dir = os.path.join(hub_path, "domains")
    if not os.path.isdir(domains_dir):
        logger.warning(f"No domains directory at {domains_dir}")
        return 0

    imported = 0

    for project in os.listdir(domains_dir):
        project_dir = os.path.join(domains_dir, project)
        if not os.path.isdir(project_dir):
            continue

        # Import UL terms
        ul_path = os.path.join(project_dir, "ul.md")
        if os.path.isfile(ul_path):
            imported += _import_ul(conn, project, ul_path, dry_run)

        # Import knowledge markdown files
        for file_type in ("strategic", "tactical"):
            type_dir = os.path.join(project_dir, file_type)
            if not os.path.isdir(type_dir):
                continue
            for md_file in glob.glob(os.path.join(type_dir, "*.md")):
                domain_name = os.path.splitext(os.path.basename(md_file))[0]
                imported += _import_knowledge_file(
                    conn, project, domain_name, file_type, md_file, dry_run
                )

        # Import top-level files (domain-map, business-rules)
        for filename in ("domain-map.md", "business-rules.md"):
            filepath = os.path.join(project_dir, filename)
            if os.path.isfile(filepath):
                file_type = filename.replace(".md", "")
                imported += _import_knowledge_file(
                    conn, project, None, file_type, filepath, dry_run
                )

    logger.info(f"Knowledge: {imported} entries imported")
    return imported


def _import_ul(conn, project: str, filepath: str, dry_run: bool) -> int:
    """Parse ul.md and import terms."""
    try:
        with open(filepath) as f:
            content = f.read()
    except OSError:
        return 0

    # Common UL patterns:
    #   | English | 中文 | ... |
    #   - **EnglishTerm**: 中文說明
    #   EnglishTerm = 中文
    terms = []

    # Pattern 1: Markdown table rows  | English | Chinese | ... |
    for match in re.finditer(
        r"^\|?\s*`?(\w[\w:]+)`?\s*\|\s*(.+?)\s*\|",
        content, re.MULTILINE
    ):
        eng, chi = match.group(1).strip(), match.group(2).strip()
        if eng.lower() in ("english", "term", "code", "name", "---"):
            continue
        if chi and not chi.startswith("-"):
            terms.append((eng, chi))

    # Pattern 2: **English**: Chinese
    for match in re.finditer(
        r"\*\*(\w[\w:]+)\*\*[：:]\s*(.+?)$",
        content, re.MULTILINE
    ):
        eng, chi = match.group(1).strip(), match.group(2).strip()
        terms.append((eng, chi))

    if dry_run:
        logger.info(f"  [dry] UL {project}: {len(terms)} terms")
        return len(terms)

    count = 0
    cur = conn.cursor()
    for eng, chi in terms:
        try:
            cur.execute(
                """
                INSERT INTO knowledge_terms (org_id, project, english_term, chinese_term, source)
                VALUES (%s, %s, %s, %s, 'ul.md')
                ON CONFLICT (org_id, project, english_term) DO UPDATE SET
                    chinese_term = EXCLUDED.chinese_term
                """,
                (DEFAULT_ORG, project, eng, chi),
            )
            count += 1
        except Exception as e:
            logger.warning(f"UL term {eng}: {e}")
            conn.rollback()
    conn.commit()
    cur.close()
    return count


def _import_knowledge_file(
    conn, project: str, domain: str | None, file_type: str,
    filepath: str, dry_run: bool,
) -> int:
    """Import a knowledge markdown file as sections."""
    try:
        with open(filepath) as f:
            content = f.read()
    except OSError:
        return 0

    # Split by ## headings into sections
    sections = _split_sections(content)
    if not sections:
        sections = [("full", content)]

    if dry_run:
        name = os.path.basename(filepath)
        logger.info(f"  [dry] {project}/{file_type}/{name}: {len(sections)} sections")
        return len(sections)

    count = 0
    cur = conn.cursor()
    for section_name, section_content in sections:
        if not section_content.strip():
            continue
        try:
            cur.execute(
                """
                INSERT INTO knowledge_entries
                    (org_id, project, domain, file_type, section, content, updated_by)
                VALUES (%s, %s, %s, %s, %s, %s, 'import')
                """,
                (DEFAULT_ORG, project, domain, file_type, section_name, section_content.strip()),
            )
            count += 1
        except Exception as e:
            logger.warning(f"Knowledge section {section_name}: {e}")
            conn.rollback()
    conn.commit()
    cur.close()
    return count


def _split_sections(content: str) -> list[tuple[str, str]]:
    """Split markdown content by ## headings."""
    sections = []
    current_heading = None
    current_lines = []

    for line in content.split("\n"):
        if line.startswith("## "):
            if current_heading is not None:
                sections.append((current_heading, "\n".join(current_lines)))
            current_heading = line[3:].strip()
            current_lines = []
        else:
            current_lines.append(line)

    if current_heading is not None:
        sections.append((current_heading, "\n".join(current_lines)))

    return sections


# ── Domain Health Import ──


def import_domain_health(conn, hub_path: str, dry_run: bool = False) -> int:
    """Import domain-health.json into domains + domain_couplings tables."""
    health_path = os.path.join(hub_path, "domain-health.json")
    if not os.path.isfile(health_path):
        logger.warning(f"No domain-health.json at {health_path}")
        return 0

    with open(health_path) as f:
        data = json.load(f)

    imported = 0
    cur = conn.cursor() if conn else None

    # Import domains — data["domains"] is a dict keyed by domain name
    domains_data = data.get("domains", {})
    for name, domain_data in domains_data.items():
        project = domain_data.get("project", "")
        score = domain_data.get("healthScore")
        status = domain_data.get("status")  # healthy, degraded, critical
        scores = domain_data.get("scores", {})

        # Helper: extract raw rate, cap infinite/NaN values to None
        def _rate(key):
            val = scores.get(key, {}).get("raw")
            if val is None:
                return None
            try:
                val = float(val)
                if val != val or abs(val) == float("inf"):
                    return None
            except (TypeError, ValueError):
                return None
            return val

        if dry_run:
            logger.info(f"  [dry] Domain {project}/{name}: {score} ({status})")
            imported += 1
            continue

        try:
            cur.execute(
                """
                INSERT INTO domains (org_id, project, name, health_score, status,
                                     fix_rate, coupling_rate, change_frequency,
                                     knowledge_coverage, escape_rate)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (org_id, project, name) DO UPDATE SET
                    health_score = EXCLUDED.health_score,
                    status = EXCLUDED.status,
                    fix_rate = EXCLUDED.fix_rate,
                    coupling_rate = EXCLUDED.coupling_rate,
                    change_frequency = EXCLUDED.change_frequency,
                    knowledge_coverage = EXCLUDED.knowledge_coverage,
                    escape_rate = EXCLUDED.escape_rate,
                    calculated_at = now()
                """,
                (
                    DEFAULT_ORG, project, name, score, status,
                    _rate("fixRate"),
                    _rate("couplingRate"),
                    _rate("changeFrequency"),
                    _rate("knowledgeCoverage"),
                    _rate("escapeRate"),
                ),
            )
            imported += 1
        except Exception as e:
            logger.warning(f"Domain {name}: {e}")
            conn.rollback()

    if conn:
        conn.commit()

    # Build domain→project lookup
    domain_project = {name: d.get("project", "") for name, d in domains_data.items()}

    # Import couplings — data["couplings"] is a list of {pair: [a, b], count: N}
    for coupling in data.get("couplings", []):
        pair = coupling.get("pair", [])
        if len(pair) < 2:
            continue
        a, b = pair[0], pair[1]
        count = coupling.get("count", 0)
        # Derive project from domain_a
        c_project = domain_project.get(a, domain_project.get(b, ""))

        if dry_run:
            logger.info(f"  [dry] Coupling {a} ↔ {b}: {count}")
            imported += 1
            continue

        try:
            cur.execute(
                """
                INSERT INTO domain_couplings (org_id, project, domain_a, domain_b, co_occurrence_count)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (org_id, project, domain_a, domain_b) DO UPDATE SET
                    co_occurrence_count = EXCLUDED.co_occurrence_count,
                    updated_at = now()
                """,
                (DEFAULT_ORG, c_project, a, b, count),
            )
            imported += 1
        except Exception as e:
            logger.warning(f"Coupling {a}↔{b}: {e}")
            conn.rollback()

    if conn:
        conn.commit()
    if cur:
        cur.close()

    logger.info(f"Domain health: {imported} entries imported")
    return imported


# ── Main ──


def main():
    parser = argparse.ArgumentParser(description="Import atdd-hub data into PostgreSQL")
    parser.add_argument("--hub", default=DEFAULT_HUB, help="atdd-hub path")
    parser.add_argument("--db", default=DEFAULT_DB_URL, help="Database URL")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--tasks-only", action="store_true")
    parser.add_argument("--knowledge-only", action="store_true")
    parser.add_argument("--health-only", action="store_true")
    parser.add_argument("--org", default=DEFAULT_ORG, help="Organization ID")
    args = parser.parse_args()

    # Allow --org to override the global DEFAULT_ORG
    global DEFAULT_ORG
    DEFAULT_ORG = args.org

    logger.info(f"Hub: {args.hub}")
    logger.info(f"DB:  {args.db}")
    logger.info(f"Org: {DEFAULT_ORG}")
    if args.dry_run:
        logger.info("DRY RUN — no writes")

    conn = None
    if not args.dry_run:
        conn = psycopg2.connect(args.db)

    run_all = not (args.tasks_only or args.knowledge_only or args.health_only)

    if run_all or args.tasks_only:
        import_tasks(conn, args.hub, args.dry_run)

    if run_all or args.knowledge_only:
        import_knowledge(conn, args.hub, args.dry_run)

    if run_all or args.health_only:
        import_domain_health(conn, args.hub, args.dry_run)

    if conn:
        conn.close()

    logger.info("Done.")


if __name__ == "__main__":
    main()
