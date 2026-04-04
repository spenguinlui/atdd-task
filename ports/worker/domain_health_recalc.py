"""Domain Health Recalculator.

從 DB 的 tasks 表重新計算每個 domain 的 health score。
可由 cron（每日）或 task completion hook 觸發。

Usage:
    python3 domain_health_recalc.py [--project core_web] [--dry-run]
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))

from db import init_pool, close_pool, get_cursor

logger = logging.getLogger("domain-health")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

DEFAULT_ORG = "00000000-0000-0000-0000-000000000001"

WEIGHTS = {
    "fix_rate": 0.30,
    "coupling_rate": 0.25,
    "change_frequency": 0.15,
    "knowledge_coverage": 0.15,
    "escape_rate": 0.15,
}

RECENT_DAYS = 30


def recalculate(project: str | None = None, org_id: str = DEFAULT_ORG,
                dry_run: bool = False) -> list[dict]:
    """Recalculate health scores for all domains from DB."""
    now = datetime.now(timezone.utc)
    recent_cutoff = now - timedelta(days=RECENT_DAYS)

    project_filter = "AND t.project = %s" if project else ""
    base_params = [org_id] + ([project] if project else [])

    with get_cursor() as cur:
        # Get all domains and their task counts by type
        cur.execute(f"""
            SELECT t.domain, t.project, t.type, count(*) as cnt
            FROM tasks t
            WHERE t.org_id = %s {project_filter}
              AND t.domain IS NOT NULL AND t.domain != ''
              AND t.domain NOT IN ('N/A', 'PASS')
            GROUP BY t.domain, t.project, t.type
        """, base_params)

        domain_type_counts = {}
        for row in cur.fetchall():
            key = (row["domain"], row["project"])
            if key not in domain_type_counts:
                domain_type_counts[key] = {"feature": 0, "fix": 0, "refactor": 0, "test": 0, "total": 0}
            domain_type_counts[key][row["type"]] = row["cnt"]
            domain_type_counts[key]["total"] += row["cnt"]

        # Get cross-domain coupling per domain
        cur.execute(f"""
            SELECT t.domain, count(*) as cross_domain_count
            FROM tasks t
            WHERE t.org_id = %s {project_filter}
              AND t.domain IS NOT NULL AND t.domain != ''
              AND t.related_domains IS NOT NULL
              AND array_length(t.related_domains, 1) > 0
            GROUP BY t.domain
        """, base_params)
        coupling_counts = {row["domain"]: row["cross_domain_count"] for row in cur.fetchall()}

        # Get recent task counts per domain
        cur.execute(f"""
            SELECT t.domain, count(*) as recent_count
            FROM tasks t
            WHERE t.org_id = %s {project_filter}
              AND t.domain IS NOT NULL AND t.domain != ''
              AND t.created_at >= %s
            GROUP BY t.domain
        """, base_params + [recent_cutoff])
        recent_counts = {row["domain"]: row["recent_count"] for row in cur.fetchall()}

        # Get knowledge entry counts per domain
        cur.execute(f"""
            SELECT domain, count(DISTINCT file_type) as doc_types
            FROM knowledge_entries
            WHERE org_id = %s {("AND project = %s" if project else "")}
              AND domain IS NOT NULL
            GROUP BY domain
        """, base_params)
        knowledge_counts = {row["domain"]: row["doc_types"] for row in cur.fetchall()}

        # Get escape counts per domain (fix tasks discovered in production)
        cur.execute(f"""
            SELECT t.domain, count(*) as escape_count
            FROM tasks t
            WHERE t.org_id = %s {project_filter}
              AND t.type = 'fix'
              AND t.causation->>'discoveredIn' = 'production'
            GROUP BY t.domain
        """, base_params)
        escape_counts = {row["domain"]: row["escape_count"] for row in cur.fetchall()}

    # Calculate health scores
    results = []
    for (domain, proj), counts in sorted(domain_type_counts.items()):
        total = counts["total"]
        features = counts["feature"]
        fixes = counts["fix"]

        # Fix Rate Score (0-100, inverted)
        if features > 0:
            raw_fix_rate = fixes / features
            fix_rate_score = max(0, 100 - (raw_fix_rate * 100))
        elif fixes > 0:
            raw_fix_rate = float("inf")
            fix_rate_score = 0
        else:
            raw_fix_rate = 0
            fix_rate_score = 100

        # Coupling Score
        cross_domain = coupling_counts.get(domain, 0)
        raw_coupling = cross_domain / total if total > 0 else 0
        coupling_score = max(0, 100 - (raw_coupling * 100))

        # Change Frequency Score
        recent = recent_counts.get(domain, 0)
        raw_change_freq = recent / max(total, 1)
        change_score = max(0, 100 - (max(0, raw_change_freq - 0.5) * 200)) if raw_change_freq > 0.5 else 100

        # Knowledge Coverage Score
        existing_docs = knowledge_counts.get(domain, 0)
        knowledge_score = min(100, existing_docs / 4 * 100)  # 4 types expected

        # Escape Rate Score
        escapes = escape_counts.get(domain, 0)
        raw_escape_rate = escapes / max(fixes, 1) if fixes > 0 else 0
        escape_score = max(0, 100 - (raw_escape_rate * 100))

        # Weighted total
        health_score = round(
            fix_rate_score * WEIGHTS["fix_rate"]
            + coupling_score * WEIGHTS["coupling_rate"]
            + change_score * WEIGHTS["change_frequency"]
            + knowledge_score * WEIGHTS["knowledge_coverage"]
            + escape_score * WEIGHTS["escape_rate"]
        )

        status = "healthy" if health_score >= 70 else ("degraded" if health_score >= 40 else "critical")

        result = {
            "domain": domain,
            "project": proj,
            "health_score": health_score,
            "status": status,
            "fix_rate": round(raw_fix_rate, 2) if raw_fix_rate != float("inf") else 999,
            "coupling_rate": round(raw_coupling, 2),
            "change_frequency": round(raw_change_freq, 2),
            "knowledge_coverage": round(existing_docs / 4, 2),
            "escape_rate": round(raw_escape_rate, 2),
        }
        results.append(result)

        if dry_run:
            icon = {"healthy": "🟢", "degraded": "🟡", "critical": "🔴"}[status]
            logger.info(f"{icon} {domain:<45} score={health_score:>3} fix_rate={raw_fix_rate:.0%}")
        else:
            # Upsert to DB
            with get_cursor() as cur:
                cur.execute("""
                    INSERT INTO domains (org_id, project, name, health_score, status,
                                         fix_rate, coupling_rate, change_frequency,
                                         knowledge_coverage, escape_rate, calculated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
                    ON CONFLICT (org_id, project, name) DO UPDATE SET
                        health_score = EXCLUDED.health_score,
                        status = EXCLUDED.status,
                        fix_rate = EXCLUDED.fix_rate,
                        coupling_rate = EXCLUDED.coupling_rate,
                        change_frequency = EXCLUDED.change_frequency,
                        knowledge_coverage = EXCLUDED.knowledge_coverage,
                        escape_rate = EXCLUDED.escape_rate,
                        calculated_at = now()
                """, (org_id, proj, domain, health_score, status,
                      result["fix_rate"], result["coupling_rate"],
                      result["change_frequency"], result["knowledge_coverage"],
                      result["escape_rate"]))

    # Also recalculate coupling pairs
    if not dry_run:
        _recalculate_couplings(project, org_id)

    logger.info(f"Recalculated {len(results)} domains")
    return results


def _recalculate_couplings(project: str | None, org_id: str):
    """Recalculate domain coupling pairs from task related_domains."""
    project_filter = "AND t.project = %s" if project else ""
    base_params = [org_id] + ([project] if project else [])

    with get_cursor() as cur:
        cur.execute(f"""
            SELECT t.domain, t.project, unnest(t.related_domains) as related
            FROM tasks t
            WHERE t.org_id = %s {project_filter}
              AND t.domain IS NOT NULL
              AND t.related_domains IS NOT NULL
              AND array_length(t.related_domains, 1) > 0
        """, base_params)

        pairs = {}
        for row in cur.fetchall():
            a, b = sorted([row["domain"], row["related"]])
            key = (row["project"], a, b)
            pairs[key] = pairs.get(key, 0) + 1

        for (proj, a, b), count in pairs.items():
            cur.execute("""
                INSERT INTO domain_couplings (org_id, project, domain_a, domain_b, co_occurrence_count)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (org_id, project, domain_a, domain_b) DO UPDATE SET
                    co_occurrence_count = EXCLUDED.co_occurrence_count,
                    updated_at = now()
            """, (org_id, proj, a, b, count))


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Recalculate domain health scores")
    parser.add_argument("--project", help="Filter by project")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    init_pool()
    try:
        recalculate(project=args.project, dry_run=args.dry_run)
    finally:
        close_pool()


if __name__ == "__main__":
    main()
