#!/usr/bin/env python3
"""Domain Health Score Calculator

從 API 取得所有任務，計算每個 domain 的健康度指標。

Usage:
    python3 domain-health.py [--output <path>] [--format text|json]

Health Score Formula (weighted):
    Fix Rate:           30%  (fix_count / feature_count)
    Coupling Rate:      25%  (cross_domain_tasks / total_tasks)
    Change Frequency:   15%  (recent_tasks / total_tasks, 近30天)
    Knowledge Coverage: 15%  (existing_docs / expected_docs)
    Escape Rate:        15%  (discovered_in_production / total_fixes)

Thresholds:
    healthy:   score >= 70
    degraded:  40 <= score < 70
    critical:  score < 40
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone
from collections import defaultdict

# Add ports/mcp to path for api_client
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "ports", "mcp"))
import api_client as api

# Health score weights
WEIGHTS = {
    "fix_rate": 0.30,
    "coupling_rate": 0.25,
    "change_frequency": 0.15,
    "knowledge_coverage": 0.15,
    "escape_rate": 0.15,
}

# Expected knowledge files per domain
EXPECTED_DOCS = {"ul.md", "business-rules.md", "strategic", "tactical"}

RECENT_DAYS = 30

# Hub path for knowledge file checks
HUB_PATH = os.environ.get("ATDD_HUB_PATH", os.path.expanduser("~/atdd-hub"))


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


def check_knowledge(hub_path, project, domain):
    """Check what knowledge docs exist for a domain."""
    domain_dir = Path(hub_path) / "domains" / project
    if not domain_dir.exists():
        return 0, len(EXPECTED_DOCS)

    existing = 0
    total = len(EXPECTED_DOCS)

    if (domain_dir / "ul.md").exists():
        existing += 1
    if (domain_dir / "business-rules.md").exists():
        existing += 1
    if (domain_dir / "strategic").is_dir() and any((domain_dir / "strategic").iterdir()):
        existing += 1
    if (domain_dir / "tactical").is_dir() and any((domain_dir / "tactical").iterdir()):
        existing += 1

    return existing, total


def parse_timestamp(ts):
    """Parse ISO timestamp, return datetime or None."""
    if not ts:
        return None
    try:
        if isinstance(ts, str):
            ts = ts.replace("Z", "+00:00")
            return datetime.fromisoformat(ts)
        return None
    except (ValueError, TypeError):
        return None


def calculate_domain_health():
    """Calculate health scores for all domains."""
    tasks = fetch_all_tasks()
    now = datetime.now(timezone.utc)
    recent_cutoff = now - timedelta(days=RECENT_DAYS)

    # Group tasks by domain
    domain_tasks = defaultdict(list)
    for task in tasks:
        domain = task.get("domain", "")
        if not domain or domain in ("", "N/A", "PASS"):
            continue
        domain_tasks[domain].append(task)

    # Track cross-domain coupling
    domain_coupling_pairs = defaultdict(int)

    results = {}

    for domain, dtasks in sorted(domain_tasks.items()):
        project = dtasks[0].get("project", "unknown")

        # Count by type
        features = [t for t in dtasks if t.get("type") == "feature"]
        fixes = [t for t in dtasks if t.get("type") == "fix"]
        refactors = [t for t in dtasks if t.get("type") == "refactor"]
        tests = [t for t in dtasks if t.get("type") == "test"]

        total = len(dtasks)
        feature_count = len(features)
        fix_count = len(fixes)

        # Fix Rate (0-100, inverted: 0 fixes = 100 score)
        if feature_count > 0:
            raw_fix_rate = fix_count / feature_count
            fix_rate_score = max(0, 100 - (raw_fix_rate * 100))
        elif fix_count > 0:
            fix_rate_score = 0
            raw_fix_rate = float("inf")
        else:
            fix_rate_score = 100
            raw_fix_rate = 0

        # Coupling Rate (0-100, inverted: less coupling = higher score)
        cross_domain = 0
        for t in dtasks:
            related = t.get("related_domains") or []
            metadata = t.get("metadata") or {}
            context = metadata.get("context", {})
            related = related or context.get("relatedDomains", [])
            if related:
                cross_domain += 1
                for rd in related:
                    pair = tuple(sorted([domain, rd]))
                    domain_coupling_pairs[pair] += 1

        raw_coupling_rate = cross_domain / total if total > 0 else 0
        coupling_score = max(0, 100 - (raw_coupling_rate * 100))

        # Change Frequency (0-100, inverted: very hot = lower score)
        recent_count = 0
        for t in dtasks:
            created = parse_timestamp(t.get("created_at"))
            if created and created > recent_cutoff:
                recent_count += 1

        raw_change_freq = recent_count / max(total, 1)
        if raw_change_freq > 0.5:
            change_score = max(0, 100 - ((raw_change_freq - 0.5) * 200))
        else:
            change_score = 100

        # Knowledge Coverage (0-100)
        existing_docs, total_docs = check_knowledge(HUB_PATH, project, domain)
        knowledge_score = (existing_docs / total_docs * 100) if total_docs > 0 else 0

        # Escape Rate (0-100, inverted)
        production_discovered = 0
        for t in fixes:
            causation = t.get("causation") or {}
            if causation and causation.get("discoveredIn") == "production":
                production_discovered += 1
        if fix_count > 0:
            raw_escape_rate = production_discovered / fix_count
        else:
            raw_escape_rate = 0
        escape_score = max(0, 100 - (raw_escape_rate * 100))

        # Weighted total
        health_score = round(
            fix_rate_score * WEIGHTS["fix_rate"]
            + coupling_score * WEIGHTS["coupling_rate"]
            + change_score * WEIGHTS["change_frequency"]
            + knowledge_score * WEIGHTS["knowledge_coverage"]
            + escape_score * WEIGHTS["escape_rate"]
        )

        # Status
        if health_score >= 70:
            status = "healthy"
        elif health_score >= 40:
            status = "degraded"
        else:
            status = "critical"

        results[domain] = {
            "domain": domain,
            "project": project,
            "status": status,
            "healthScore": health_score,
            "taskCount": total,
            "breakdown": {
                "feature": feature_count,
                "fix": fix_count,
                "refactor": len(refactors),
                "test": len(tests),
            },
            "scores": {
                "fixRate": {
                    "score": round(fix_rate_score),
                    "raw": round(raw_fix_rate, 2) if raw_fix_rate != float("inf") else "inf",
                    "weight": WEIGHTS["fix_rate"],
                },
                "couplingRate": {
                    "score": round(coupling_score),
                    "raw": round(raw_coupling_rate, 2),
                    "weight": WEIGHTS["coupling_rate"],
                },
                "changeFrequency": {
                    "score": round(change_score),
                    "raw": round(raw_change_freq, 2),
                    "recentTasks": recent_count,
                    "weight": WEIGHTS["change_frequency"],
                },
                "knowledgeCoverage": {
                    "score": round(knowledge_score),
                    "existing": existing_docs,
                    "expected": total_docs,
                    "weight": WEIGHTS["knowledge_coverage"],
                },
                "escapeRate": {
                    "score": round(escape_score),
                    "raw": round(raw_escape_rate, 2),
                    "productionDiscovered": production_discovered,
                    "weight": WEIGHTS["escape_rate"],
                },
            },
            "calculatedAt": now.isoformat(),
        }

    # Add top coupling pairs
    top_couplings = sorted(domain_coupling_pairs.items(), key=lambda x: -x[1])[:20]

    return {
        "domains": results,
        "couplings": [
            {"pair": list(pair), "count": count}
            for pair, count in top_couplings
        ],
        "summary": {
            "totalDomains": len(results),
            "healthy": len([d for d in results.values() if d["status"] == "healthy"]),
            "degraded": len([d for d in results.values() if d["status"] == "degraded"]),
            "critical": len([d for d in results.values() if d["status"] == "critical"]),
            "totalTasks": len(tasks),
        },
        "calculatedAt": now.isoformat(),
    }


def format_text(data):
    """Format health data as readable text."""
    lines = []
    lines.append("=" * 65)
    lines.append("  ATDD Domain Health Report")
    lines.append(f"  Generated: {data['calculatedAt'][:10]}")
    lines.append("=" * 65)
    lines.append("")

    s = data["summary"]
    lines.append(f"  Domains: {s['totalDomains']}  "
                 f"(🟢 {s['healthy']} healthy, "
                 f"🟡 {s['degraded']} degraded, "
                 f"🔴 {s['critical']} critical)")
    lines.append(f"  Total Tasks: {s['totalTasks']}")
    lines.append("")

    sorted_domains = sorted(
        data["domains"].values(), key=lambda d: d["healthScore"]
    )

    for d in sorted_domains:
        icon = {"healthy": "🟢", "degraded": "🟡", "critical": "🔴"}[d["status"]]
        fix_rate = d["scores"]["fixRate"]["raw"]
        fix_rate_str = f"{fix_rate:.0%}" if fix_rate != "inf" else "∞"

        lines.append(f"  {icon} {d['domain']:<45} score: {d['healthScore']:>3}")
        lines.append(f"     tasks: {d['taskCount']:>3}  "
                     f"feat: {d['breakdown']['feature']:>2}  "
                     f"fix: {d['breakdown']['fix']:>2}  "
                     f"fix_rate: {fix_rate_str:>5}  "
                     f"coupling: {d['scores']['couplingRate']['raw']:.0%}")
        lines.append("")

    if data["couplings"]:
        lines.append("-" * 65)
        lines.append("  Top Domain Couplings:")
        for c in data["couplings"][:10]:
            lines.append(f"    {c['pair'][0]} ↔ {c['pair'][1]}: {c['count']} tasks")

    lines.append("")
    lines.append("=" * 65)
    return "\n".join(lines)


def main():
    args = sys.argv[1:]
    output_path = None
    fmt = "text"

    i = 0
    while i < len(args):
        if args[i] == "--output" and i + 1 < len(args):
            output_path = args[i + 1]
            i += 2
        elif args[i] == "--format" and i + 1 < len(args):
            fmt = args[i + 1]
            i += 2
        else:
            i += 1

    try:
        data = calculate_domain_health()
    except api.APIError as e:
        print(f"API Error: {e}", file=sys.stderr)
        sys.exit(1)

    if fmt == "json":
        output = json.dumps(data, ensure_ascii=False, indent=2)
    else:
        output = format_text(data)

    if output_path:
        with open(output_path, "w") as f:
            f.write(output)
            if fmt == "json":
                f.write("\n")
        print(f"Written to {output_path}")
    else:
        print(output)


if __name__ == "__main__":
    main()
