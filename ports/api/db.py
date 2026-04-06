"""Database connection pool (raw psycopg2, sync).

Supports multi-org routing: each org_id can map to a different PostgreSQL.
- Local: personal org → local DB, company org → remote server DB
- Server: all orgs → local DB
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Optional

import psycopg2
import psycopg2.pool
import psycopg2.extras

# Register UUID adapter
psycopg2.extras.register_uuid()

# ── Org → DB URL mapping ──
# Default (local) database
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://atdd:atdd@localhost:5432/atdd",
)

# Remote database for company org (optional)
DATABASE_URL_COMPANY = os.environ.get("DATABASE_URL_COMPANY", "")

# Org IDs
ORG_PERSONAL = "00000000-0000-0000-0000-000000000001"
ORG_COMPANY = "00000000-0000-0000-0000-000000000002"

# ── Connection Pools ──
_pools: dict[str, psycopg2.pool.ThreadedConnectionPool] = {}


def _org_db_url(org_id: str) -> str:
    """Resolve org_id to database URL."""
    if org_id == ORG_COMPANY and DATABASE_URL_COMPANY:
        return DATABASE_URL_COMPANY
    return DATABASE_URL


def init_pool(min_conn: int = 2, max_conn: int = 10):
    """Initialize connection pools for all configured databases."""
    global _pools

    # Always init local pool
    _pools["default"] = psycopg2.pool.ThreadedConnectionPool(
        min_conn, max_conn, DATABASE_URL
    )

    # Init company pool if configured
    if DATABASE_URL_COMPANY:
        _pools[ORG_COMPANY] = psycopg2.pool.ThreadedConnectionPool(
            min_conn, max_conn, DATABASE_URL_COMPANY
        )


def close_pool():
    """Close all connection pools."""
    global _pools
    for pool in _pools.values():
        pool.closeall()
    _pools = {}


def _get_pool(org_id: Optional[str] = None) -> psycopg2.pool.ThreadedConnectionPool:
    """Get the connection pool for an org. Falls back to default."""
    if org_id and org_id in _pools:
        return _pools[org_id]
    return _pools["default"]


@contextmanager
def get_conn(org_id: Optional[str] = None):
    """Get a connection from the pool. Auto-commits on success, rollbacks on error."""
    pool = _get_pool(org_id)
    conn = pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


@contextmanager
def get_cursor(org_id: Optional[str] = None, cursor_factory=None):
    """Get a cursor with DictCursor by default.

    Args:
        org_id: Route to the correct DB pool. None = default (local).
        cursor_factory: Override cursor factory. Default: RealDictCursor.
    """
    factory = cursor_factory or psycopg2.extras.RealDictCursor
    with get_conn(org_id) as conn:
        cur = conn.cursor(cursor_factory=factory)
        try:
            yield cur
        finally:
            cur.close()
