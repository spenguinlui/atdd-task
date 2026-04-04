"""Database connection pool (raw psycopg2, sync)."""

from __future__ import annotations

import os
from contextlib import contextmanager

import psycopg2
import psycopg2.pool
import psycopg2.extras

# Register UUID adapter
psycopg2.extras.register_uuid()

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://atdd:atdd@localhost:5432/atdd",
)

_pool: psycopg2.pool.ThreadedConnectionPool | None = None


def init_pool(min_conn: int = 2, max_conn: int = 10):
    global _pool
    _pool = psycopg2.pool.ThreadedConnectionPool(min_conn, max_conn, DATABASE_URL)


def close_pool():
    global _pool
    if _pool:
        _pool.closeall()
        _pool = None


@contextmanager
def get_conn():
    """Get a connection from the pool. Auto-commits on success, rollbacks on error."""
    conn = _pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        _pool.putconn(conn)


@contextmanager
def get_cursor(cursor_factory=None):
    """Get a cursor with DictCursor by default."""
    factory = cursor_factory or psycopg2.extras.RealDictCursor
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=factory)
        try:
            yield cur
        finally:
            cur.close()
