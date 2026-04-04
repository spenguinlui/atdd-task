"""Auto git commit + push for atdd-hub changes."""

import logging
import os
import subprocess

logger = logging.getLogger("git-sync")

ATDD_HUB_PATH = os.environ.get("ATDD_HUB_PATH", os.path.expanduser("~/atdd-hub"))


def sync(message: str = "bot: auto sync") -> str | None:
    """Commit and push any changes in atdd-hub. Returns error message or None."""
    try:
        # Ensure we're on master
        subprocess.run(
            ["git", "checkout", "master"],
            cwd=ATDD_HUB_PATH, capture_output=True, text=True, timeout=10,
        )

        # Check for changes
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=ATDD_HUB_PATH, capture_output=True, text=True, timeout=10,
        )
        if not status.stdout.strip():
            logger.info("No changes to sync")
            return None

        logger.info(f"Changes detected:\n{status.stdout.strip()}")

        # Stage all changes under domains/, tasks/, requirements/, specs/
        subprocess.run(
            ["git", "add", "domains/", "tasks/", "requirements/", "specs/", "epics/"],
            cwd=ATDD_HUB_PATH, capture_output=True, text=True, timeout=10,
        )

        # Check if anything staged
        diff = subprocess.run(
            ["git", "diff", "--cached", "--stat"],
            cwd=ATDD_HUB_PATH, capture_output=True, text=True, timeout=10,
        )
        if not diff.stdout.strip():
            logger.info("Nothing staged to commit")
            return None

        # Commit
        commit = subprocess.run(
            ["git", "commit", "-m", message],
            cwd=ATDD_HUB_PATH, capture_output=True, text=True, timeout=10,
        )
        if commit.returncode != 0:
            return f"git commit failed: {commit.stderr.strip()}"

        logger.info(f"Committed: {message}")

        # Push
        push = subprocess.run(
            ["git", "push"],
            cwd=ATDD_HUB_PATH, capture_output=True, text=True, timeout=30,
        )
        if push.returncode != 0:
            return f"git push failed: {push.stderr.strip()}"

        logger.info("Pushed to remote")
        return None

    except subprocess.TimeoutExpired:
        return "git sync timed out"
    except Exception as e:
        return f"git sync error: {str(e)}"
