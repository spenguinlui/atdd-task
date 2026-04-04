#!/usr/bin/env python3
"""Run DB migrations on startup."""

import os
import sys

# Add parent directory for migration runner
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "data", "db"))

from migrate import run_migrations

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://atdd:atdd@localhost:5432/atdd",
)

if __name__ == "__main__":
    run_migrations(DATABASE_URL)
else:
    # Called from Dockerfile CMD
    run_migrations(DATABASE_URL)
