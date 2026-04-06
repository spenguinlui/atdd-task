"""Weekly Report Generator.

從 DB 聚合計算週報指標，存入 reports 表。
可由 cron 或 API endpoint 觸發。

Usage:
    python3 weekly_report.py [--week 2026-W14] [--project core_web]
    python3 weekly_report.py --all-projects
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal


class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)

# Allow importing db module from api directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))

from db import init_pool, close_pool, get_cursor

DEFAULT_ORG = os.environ.get("ATDD_ORG", "00000000-0000-0000-0000-000000000001")


def get_week_range(week_str: str | None = None):
    """Parse ISO week string (2026-W14) or use current week. Returns (monday, sunday)."""
    if week_str:
        year, week = week_str.split("-W")
        # ISO week: Monday of that week
        monday = datetime.strptime(f"{year}-W{week}-1", "%G-W%V-%u")
    else:
        now = datetime.now(timezone.utc)
        monday = now - timedelta(days=now.weekday())
        monday = monday.replace(hour=0, minute=0, second=0, microsecond=0)

    sunday = monday + timedelta(days=6, hours=23, minutes=59, seconds=59)
    week_str = monday.strftime("%G-W%V")
    return week_str, monday, sunday


def generate_weekly_report(project: str | None, week_str: str | None = None,
                           org_id: str = DEFAULT_ORG) -> dict:
    """Generate weekly report data from DB."""
    week_label, week_start, week_end = get_week_range(week_str)

    with get_cursor() as cur:
        # --- Delivery metrics ---
        project_filter = "AND t.project = %s" if project else ""
        base_params = [org_id] + ([project] if project else [])

        # Completed this week
        cur.execute(f"""
            SELECT t.type, count(*) as cnt
            FROM tasks t
            JOIN task_history th ON th.task_id = t.id
            WHERE t.org_id = %s {project_filter}
              AND th.status IN ('completed', 'verified')
              AND th.timestamp BETWEEN %s AND %s
            GROUP BY t.type
        """, base_params + [week_start, week_end])
        completed_by_type = {row["type"]: row["cnt"] for row in cur.fetchall()}
        total_completed = sum(completed_by_type.values())

        # Created this week
        cur.execute(f"""
            SELECT t.type, count(*) as cnt
            FROM tasks t
            WHERE t.org_id = %s {project_filter}
              AND t.created_at BETWEEN %s AND %s
            GROUP BY t.type
        """, base_params + [week_start, week_end])
        created_by_type = {row["type"]: row["cnt"] for row in cur.fetchall()}
        total_created = sum(created_by_type.values())

        # --- Quality metrics ---
        # True completion rate: completed without subsequent fix in 14 days
        cur.execute(f"""
            SELECT count(*) as total_features
            FROM tasks t
            JOIN task_history th ON th.task_id = t.id
            WHERE t.org_id = %s {project_filter}
              AND t.type = 'feature'
              AND th.status IN ('completed', 'verified')
              AND th.timestamp BETWEEN %s AND %s
        """, base_params + [week_start, week_end])
        total_features = cur.fetchone()["total_features"]

        # Escaped tasks this week
        cur.execute(f"""
            SELECT count(*) as escaped
            FROM tasks t
            JOIN task_history th ON th.task_id = t.id
            WHERE t.org_id = %s {project_filter}
              AND th.status = 'escaped'
              AND th.timestamp BETWEEN %s AND %s
        """, base_params + [week_start, week_end])
        escaped_count = cur.fetchone()["escaped"]

        # Fix tasks created this week (escape rate proxy)
        fix_created = created_by_type.get("fix", 0)

        # Escape rate
        escape_rate = round(escaped_count / max(total_completed, 1) * 100, 1)

        # Fix cost ratio (fix tokens / total tokens this week)
        cur.execute(f"""
            SELECT t.type, coalesce(sum(tm.tokens), 0) as total_tokens
            FROM tasks t
            JOIN task_history th ON th.task_id = t.id
            LEFT JOIN task_metrics tm ON tm.task_id = t.id
            WHERE t.org_id = %s {project_filter}
              AND th.status IN ('completed', 'verified')
              AND th.timestamp BETWEEN %s AND %s
            GROUP BY t.type
        """, base_params + [week_start, week_end])
        tokens_by_type = {row["type"]: row["total_tokens"] for row in cur.fetchall()}
        total_tokens = sum(tokens_by_type.values())
        fix_tokens = tokens_by_type.get("fix", 0)
        fix_cost_ratio = round(fix_tokens / max(total_tokens, 1) * 100, 1)

        # --- Cycle time (avg hours from created to completed) ---
        cur.execute(f"""
            SELECT avg(extract(epoch from (th.timestamp - t.created_at)) / 3600) as avg_hours
            FROM tasks t
            JOIN task_history th ON th.task_id = t.id
            WHERE t.org_id = %s {project_filter}
              AND th.status IN ('completed', 'verified')
              AND th.timestamp BETWEEN %s AND %s
        """, base_params + [week_start, week_end])
        avg_cycle_hours = cur.fetchone()["avg_hours"]
        avg_cycle_hours = round(avg_cycle_hours, 1) if avg_cycle_hours else None

        # --- Domain hotspots (top 5 degraded/critical) ---
        cur.execute(f"""
            SELECT name, health_score, status, fix_rate, coupling_rate
            FROM domains
            WHERE org_id = %s {("AND project = %s" if project else "")}
              AND status IN ('degraded', 'critical')
            ORDER BY health_score ASC
            LIMIT 5
        """, base_params)
        domain_hotspots = [dict(row) for row in cur.fetchall()]

        # --- Pending deployed tasks ---
        cur.execute(f"""
            SELECT count(*) as cnt
            FROM tasks t
            WHERE t.org_id = %s {project_filter}
              AND t.status = 'deployed'
        """, base_params)
        pending_deployed = cur.fetchone()["cnt"]

    report_data = {
        "week": week_label,
        "project": project or "all",
        "delivery": {
            "completed": total_completed,
            "completedByType": completed_by_type,
            "created": total_created,
            "createdByType": created_by_type,
            "avgCycleTimeHours": avg_cycle_hours,
        },
        "quality": {
            "totalFeatures": total_features,
            "escapedCount": escaped_count,
            "escapeRate": escape_rate,
            "fixCreated": fix_created,
            "trueCompletionRate": round(
                (total_features - escaped_count) / max(total_features, 1) * 100, 1
            ) if total_features else None,
        },
        "cost": {
            "totalTokens": total_tokens,
            "tokensByType": tokens_by_type,
            "fixCostRatio": fix_cost_ratio,
        },
        "domainHotspots": domain_hotspots,
        "pendingDeployed": pending_deployed,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
    }

    return report_data


def save_report(report_data: dict, org_id: str = DEFAULT_ORG):
    """Save report to DB."""
    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO reports (org_id, project, type, period, data)
            VALUES (%s, %s, 'weekly', %s, %s)
            ON CONFLICT DO NOTHING
            RETURNING id
            """,
            (org_id, report_data["project"], report_data["week"],
             json.dumps(report_data, cls=DecimalEncoder)),
        )
        result = cur.fetchone()
        return result["id"] if result else None


def format_text(data: dict) -> str:
    """Format report as readable text for Slack."""
    d = data["delivery"]
    q = data["quality"]
    c = data["cost"]

    lines = [
        f"{'=' * 55}",
        f"  ATDD 週報 — {data['week']} ({data['project']})",
        f"{'=' * 55}",
        "",
        "📊 交付",
        f"  完成: {d['completed']} 任務 ({', '.join(f'{t} {n}' for t, n in d['completedByType'].items())})",
        f"  新建: {d['created']} 任務",
        f"  Cycle Time 中位: {d['avgCycleTimeHours']}h" if d["avgCycleTimeHours"] else "  Cycle Time: N/A",
        "",
        "✅ 品質",
        f"  Features 完成: {q['totalFeatures']}",
        f"  Escape Rate: {q['escapeRate']}%",
        f"  Fix 新增: {q['fixCreated']}",
    ]
    if q["trueCompletionRate"] is not None:
        lines.append(f"  True Completion Rate: {q['trueCompletionRate']}%")

    lines.extend([
        "",
        "💰 成本",
        f"  Total Tokens: {c['totalTokens']:,}",
        f"  Fix Cost Ratio: {c['fixCostRatio']}%",
        "",
    ])

    if data["domainHotspots"]:
        lines.append("🔴 Domain 風險熱區")
        for dh in data["domainHotspots"]:
            icon = "🔴" if dh["status"] == "critical" else "🟡"
            lines.append(f"  {icon} {dh['name']}: score {dh['health_score']}, fix rate {dh.get('fix_rate', 'N/A')}")
        lines.append("")

    if data["pendingDeployed"]:
        lines.append(f"⚠️ 待驗證: {data['pendingDeployed']} 個 deployed 任務")
        lines.append("")

    lines.append("=" * 55)
    return "\n".join(lines)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Generate weekly report")
    parser.add_argument("--week", help="ISO week (e.g., 2026-W14)")
    parser.add_argument("--project", help="Project filter")
    parser.add_argument("--all-projects", action="store_true")
    parser.add_argument("--save", action="store_true", help="Save to DB")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args()

    init_pool()
    try:
        if args.all_projects:
            # Get distinct projects
            with get_cursor() as cur:
                cur.execute(
                    "SELECT DISTINCT project FROM tasks WHERE org_id = %s",
                    (DEFAULT_ORG,),
                )
                projects = [row["project"] for row in cur.fetchall()]

            for proj in projects:
                data = generate_weekly_report(proj, args.week)
                if args.save:
                    rid = save_report(data)
                    print(f"Saved report for {proj}: {rid}")
                if args.format == "json":
                    print(json.dumps(data, ensure_ascii=False, indent=2))
                else:
                    print(format_text(data))
                    print()
        else:
            data = generate_weekly_report(args.project, args.week)
            if args.save:
                rid = save_report(data)
                print(f"Saved: {rid}")
            if args.format == "json":
                print(json.dumps(data, ensure_ascii=False, indent=2))
            else:
                print(format_text(data))
    finally:
        close_pool()


if __name__ == "__main__":
    main()
