#!/usr/bin/env python3
"""Simple SQL migration runner for ATDD Server.

Usage:
    python migrate.py                      # Run pending migrations
    python migrate.py --status             # Show applied migrations
    python migrate.py --db postgresql://... # Custom DB URL
"""

import argparse
import glob
import os
import sys

import psycopg2

DEFAULT_DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://atdd:atdd@localhost:5432/atdd",
)

MIGRATIONS_DIR = os.path.join(os.path.dirname(__file__), "migrations")


def get_applied(conn) -> set[str]:
    """Get set of already-applied migration versions."""
    cur = conn.cursor()
    cur.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_name = 'schema_migrations'
        )
    """)
    if not cur.fetchone()[0]:
        return set()
    cur.execute("SELECT version FROM schema_migrations ORDER BY version")
    return {row[0] for row in cur.fetchall()}


def run_migrations(db_url: str):
    """Run all pending migrations in order."""
    conn = psycopg2.connect(db_url)
    conn.autocommit = False

    applied = get_applied(conn)
    files = sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql")))

    pending = []
    for f in files:
        version = os.path.basename(f).split("_")[0]  # "001"
        if version not in applied:
            pending.append((version, f))

    if not pending:
        print("No pending migrations.")
        conn.close()
        return

    for version, filepath in pending:
        name = os.path.basename(filepath)
        print(f"Applying {name}...", end=" ")
        with open(filepath) as f:
            sql = f.read()

        # Migrations with ALTER TYPE ... ADD VALUE cannot run inside a
        # transaction.  Detect this and switch to autocommit mode.
        needs_autocommit = "ADD VALUE" in sql

        try:
            if needs_autocommit:
                conn.autocommit = True
                cur = conn.cursor()
                for stmt in sql.split(";"):
                    stmt = stmt.strip()
                    if stmt and not stmt.startswith("--"):
                        cur.execute(stmt)
                conn.autocommit = False
            else:
                cur = conn.cursor()
                cur.execute(sql)
                conn.commit()
            print("OK")
        except Exception as e:
            if not needs_autocommit:
                conn.rollback()
            conn.autocommit = False
            print(f"FAILED: {e}")
            sys.exit(1)

    conn.close()
    print(f"\nDone. Applied {len(pending)} migration(s).")


def show_status(db_url: str):
    """Show migration status."""
    conn = psycopg2.connect(db_url)
    applied = get_applied(conn)
    files = sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql")))

    print(f"Database: {db_url}")
    print(f"Applied: {len(applied)} migration(s)\n")

    for f in files:
        version = os.path.basename(f).split("_")[0]
        name = os.path.basename(f)
        status = "✅" if version in applied else "⬜"
        print(f"  {status} {name}")

    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ATDD DB Migration Runner")
    parser.add_argument("--db", default=DEFAULT_DB_URL, help="Database URL")
    parser.add_argument("--status", action="store_true", help="Show status")
    args = parser.parse_args()

    if args.status:
        show_status(args.db)
    else:
        run_migrations(args.db)
