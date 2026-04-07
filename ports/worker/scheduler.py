#!/usr/bin/env python3
"""Simple cron-like scheduler for ATDD workers.

Runs inside Docker container. No crontab needed.
Schedule: auto-verify daily 9am, domain-health daily 2am, weekly-report Monday 8am (Asia/Taipei).
"""

import logging
import os
import sys
import time
from datetime import datetime, timezone, timedelta

# Local: ports/worker/../api → ports/api
# Docker: /app/worker/.. → /app (where db.py lives)
for p in [
    os.path.join(os.path.dirname(__file__), "..", "api"),
    os.path.join(os.path.dirname(__file__), ".."),
]:
    if os.path.isdir(p) and p not in sys.path:
        sys.path.insert(0, p)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("scheduler")

TZ_OFFSET = timedelta(hours=8)  # Asia/Taipei = UTC+8


def now_taipei():
    return datetime.now(timezone.utc) + TZ_OFFSET


def run_job(name: str, func, **kwargs):
    logger.info(f"Running {name}...")
    try:
        func(**kwargs)
        logger.info(f"{name} completed")
    except Exception as e:
        logger.error(f"{name} failed: {e}")


def main():
    from db import init_pool, close_pool

    init_pool()
    logger.info("Scheduler started. Checking every 60 seconds.")

    last_run = {}

    try:
        while True:
            t = now_taipei()
            today = t.strftime("%Y-%m-%d")
            hour = t.hour

            # Daily 2:00 — Domain health recalc
            key = f"domain-health-{today}"
            if hour == 2 and key not in last_run:
                from domain_health_recalc import recalculate
                run_job("domain-health", recalculate)
                last_run[key] = True

            # Daily 9:00 — Auto-verify
            key = f"auto-verify-{today}"
            if hour == 9 and key not in last_run:
                from auto_verify import run
                run_job("auto-verify", run, slack_notify=True)
                last_run[key] = True

            # Monday 8:00 — Weekly report
            key = f"weekly-report-{today}"
            if t.weekday() == 0 and hour == 8 and key not in last_run:
                from weekly_report import generate_weekly_report, save_report
                def _weekly():
                    data = generate_weekly_report(None, None)
                    save_report(data)
                run_job("weekly-report", _weekly)
                last_run[key] = True

            # Cleanup old keys (keep last 7 days)
            cutoff = (t - timedelta(days=7)).strftime("%Y-%m-%d")
            last_run = {k: v for k, v in last_run.items() if k.split("-")[-1] >= cutoff or not k[-10:].replace("-","").isdigit()}

            time.sleep(60)

    except KeyboardInterrupt:
        logger.info("Scheduler stopped")
    finally:
        close_pool()


if __name__ == "__main__":
    main()
