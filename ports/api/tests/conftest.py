"""Shared fixtures for API tests.

Uses real local DB (integration tests).
"""

from __future__ import annotations

import os
import pytest
from fastapi.testclient import TestClient

# Use local DB with correct role
os.environ.setdefault("DATABASE_URL", "postgresql://liu@localhost:5432/atdd")

import db
import main as main_module
from main import app


@pytest.fixture(scope="session", autouse=True)
def _db_pool():
    """Initialize DB pool once for the entire test session.

    Patches close_pool to no-op during tests so TestClient lifespan
    doesn't destroy the pool between tests.
    """
    db.init_pool()

    # main.py captured close_pool at import time, patch both references
    _noop = lambda: None
    original_db_close = db.close_pool
    original_main_close = getattr(main_module, "close_pool", None)
    db.close_pool = _noop
    main_module.close_pool = _noop

    yield

    db.close_pool = original_db_close
    if original_main_close:
        main_module.close_pool = original_main_close
    db.close_pool()


@pytest.fixture()
def client():
    """FastAPI test client."""
    with TestClient(app) as c:
        yield c
