"""Deployed Task Auto-Verify Worker.

掃描 deployed 任務，根據風險等級自動 verify 或發送提醒。

Risk levels:
  low:    7 天無 fix 票 → 自動 verified
  medium: 14 天無 fix 票 → 自動 verified
  high:   不自動 verify，超過 14 天 → 發送提醒

Usage:
    python3 auto_verify.py [--dry-run] [--slack-notify]
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))

from db import init_pool, close_pool, get_cursor

logger = logging.getLogger("auto-verify")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

DEFAULT_ORG = os.environ.get("ATDD_ORG", "00000000-0000-0000-0000-000000000001")

# Days before auto-verify by risk level
AUTO_VERIFY_DAYS = {
    "low": 7,
    "medium": 14,
    "high": None,  # Never auto-verify
}

# Alert after this many days for high-risk
HIGH_RISK_ALERT_DAYS = 14


def get_deployed_tasks(org_id: str = DEFAULT_ORG):
    """Get all tasks in 'deployed' status with their deployed timestamp."""
    with get_cursor() as cur:
        cur.execute("""
            SELECT t.id, t.project, t.type, t.domain, t.description,
                   t.metadata,
                   th.timestamp as deployed_at
            FROM tasks t
            JOIN task_history th ON th.task_id = t.id AND th.status = 'deployed'
            WHERE t.org_id = %s AND t.status = 'deployed'
            ORDER BY th.timestamp ASC
        """, (org_id,))
        return [dict(row) for row in cur.fetchall()]


def get_risk_level(task: dict) -> str:
    """Determine risk level from task metadata or domain health."""
    metadata = task.get("metadata") or {}
    if isinstance(metadata, str):
        metadata = json.loads(metadata)

    # Check if risk_level was explicitly set
    context = metadata.get("context", {})
    if context.get("riskLevel"):
        return context["riskLevel"]

    # Fallback: check domain health
    domain = task.get("domain")
    if domain:
        with get_cursor() as cur:
            cur.execute(
                "SELECT status FROM domains WHERE org_id = %s AND name = %s",
                (DEFAULT_ORG, domain),
            )
            row = cur.fetchone()
            if row:
                domain_status = row["status"]
                if domain_status == "critical":
                    return "high"
                elif domain_status == "degraded":
                    return "medium"

    # Default based on type
    if task.get("type") == "refactor":
        return "low"
    return "medium"


def check_for_related_fixes(task_id: str, since: datetime) -> bool:
    """Check if any fix tasks were created referencing this task since deployment."""
    with get_cursor() as cur:
        cur.execute("""
            SELECT count(*) as cnt
            FROM tasks t
            WHERE t.causation->>'causedBy' IS NOT NULL
              AND (t.causation->'causedBy'->>'taskId')::text = %s
              AND t.created_at >= %s
        """, (task_id, since))
        return cur.fetchone()["cnt"] > 0


def auto_verify_task(task_id: str):
    """Mark a deployed task as verified."""
    with get_cursor() as cur:
        cur.execute(
            "UPDATE tasks SET status = 'verified' WHERE id = %s RETURNING *",
            (str(task_id),),
        )
        cur.execute("""
            INSERT INTO task_history (task_id, phase, status, note)
            VALUES (%s, 'verified', 'verified', 'Auto-verified: no issues found within observation period')
        """, (str(task_id),))


def run(dry_run: bool = False, slack_notify: bool = False):
    """Main worker loop."""
    now = datetime.now(timezone.utc)
    deployed_tasks = get_deployed_tasks()

    auto_verified = []
    alerts = []

    for task in deployed_tasks:
        deployed_at = task["deployed_at"]
        if deployed_at.tzinfo is None:
            deployed_at = deployed_at.replace(tzinfo=timezone.utc)

        days_deployed = (now - deployed_at).days
        risk_level = get_risk_level(task)
        has_fix = check_for_related_fixes(str(task["id"]), deployed_at)

        desc = task["description"] or ""
        label = f"[{task['project']}] {desc[:40]}"

        if has_fix:
            logger.info(f"SKIP {label} — has related fix ticket")
            continue

        threshold = AUTO_VERIFY_DAYS.get(risk_level)

        if threshold and days_deployed >= threshold:
            # Auto-verify
            if dry_run:
                logger.info(f"[DRY-RUN] Would auto-verify: {label} (risk={risk_level}, {days_deployed}d)")
            else:
                auto_verify_task(task["id"])
                logger.info(f"AUTO-VERIFIED: {label} (risk={risk_level}, {days_deployed}d)")
            auto_verified.append(task)

        elif risk_level == "high" and days_deployed >= HIGH_RISK_ALERT_DAYS:
            logger.warning(f"ALERT: {label} — high-risk, deployed {days_deployed}d, needs manual /verify")
            alerts.append(task)

        else:
            remaining = (threshold - days_deployed) if threshold else "∞"
            logger.info(f"OK: {label} (risk={risk_level}, {days_deployed}d, auto-verify in {remaining}d)")

    # Summary
    logger.info(f"=== Summary: {len(auto_verified)} auto-verified, {len(alerts)} alerts, "
                f"{len(deployed_tasks) - len(auto_verified) - len(alerts)} waiting ===")

    # Slack notification
    if slack_notify and (auto_verified or alerts):
        _send_slack_summary(auto_verified, alerts)

    return {"auto_verified": len(auto_verified), "alerts": len(alerts)}


def _send_slack_summary(auto_verified: list, alerts: list):
    """Send summary to Slack (uses bot's api_client pattern)."""
    try:
        from urllib.request import Request, urlopen
        webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
        if not webhook_url:
            logger.warning("SLACK_WEBHOOK_URL not set, skipping notification")
            return

        lines = ["*ATDD Auto-Verify Summary*\n"]
        if auto_verified:
            lines.append(f"✅ Auto-verified: {len(auto_verified)} tasks")
            for t in auto_verified[:5]:
                lines.append(f"  • [{t['project']}] {t.get('description', '')[:50]}")
        if alerts:
            lines.append(f"\n⚠️ Needs manual /verify: {len(alerts)} tasks")
            for t in alerts[:5]:
                lines.append(f"  • [{t['project']}] {t.get('description', '')[:50]}")

        payload = json.dumps({"text": "\n".join(lines)})
        req = Request(webhook_url, data=payload.encode(), method="POST")
        req.add_header("Content-Type", "application/json")
        urlopen(req, timeout=10)
    except Exception as e:
        logger.error(f"Slack notification failed: {e}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Auto-verify deployed tasks")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--slack-notify", action="store_true")
    args = parser.parse_args()

    init_pool()
    try:
        run(dry_run=args.dry_run, slack_notify=args.slack_notify)
    finally:
        close_pool()


if __name__ == "__main__":
    main()
