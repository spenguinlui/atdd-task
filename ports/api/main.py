"""ATDD API Server — Phase 2 + Phase 4 Dashboard."""

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from db import init_pool, close_pool
from routers import tasks, domains, reports, knowledge, views, events, workers

# ── API Key Authentication ──
API_KEY = os.environ.get("API_KEY", "")

# Paths that don't require authentication
PUBLIC_PATHS = ("/health", "/static/", "/docs", "/openapi.json", "/redoc")

BASE_DIR = Path(__file__).resolve().parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_pool()
    # Make templates available via app.state
    app.state.templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
    yield
    close_pool()


app = FastAPI(
    title="ATDD API",
    version="0.3.0",
    lifespan=lifespan,
)


@app.middleware("http")
async def api_key_middleware(request: Request, call_next):
    """Require API key for all /api/ and /dashboard/ routes when API_KEY is set."""
    if not API_KEY:
        # No key configured = development mode, skip auth
        return await call_next(request)

    path = request.url.path
    if any(path.startswith(p) for p in PUBLIC_PATHS):
        return await call_next(request)

    # Check API key from header or query param
    key = request.headers.get("X-API-Key") or request.query_params.get("api_key")
    if key != API_KEY:
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid or missing API key"},
        )

    return await call_next(request)

# Static files
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# API routers (Phase 2)
app.include_router(tasks.router, prefix="/api/v1/tasks", tags=["tasks"])
app.include_router(domains.router, prefix="/api/v1/domains", tags=["domains"])
app.include_router(reports.router, prefix="/api/v1/reports", tags=["reports"])
app.include_router(knowledge.router, prefix="/api/v1/knowledge", tags=["knowledge"])

# Dashboard views (Phase 4)
app.include_router(views.router, prefix="/dashboard", tags=["dashboard"])

# SSE + Worker triggers (Phase 5)
app.include_router(events.router, prefix="/api/v1/events", tags=["events"])
app.include_router(workers.router, prefix="/api/v1/workers", tags=["workers"])


@app.get("/health")
def health():
    return {"status": "ok"}
