"""ATDD API Server — Phase 2 + Phase 4 Dashboard."""

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from db import init_pool, close_pool
from routers import tasks, domains, reports, knowledge, views, events, workers

# ── API Key Authentication ──
API_KEY = os.environ.get("API_KEY", "")

# Paths that don't require authentication
# SSE stream uses cookie auth (browsers can't send headers with EventSource)
PUBLIC_PATHS = ("/health", "/static/", "/docs", "/openapi.json", "/redoc",
                "/api/v1/events/stream")

BASE_DIR = Path(__file__).resolve().parent


def _format_date(value, fmt="%Y-%m-%d"):
    """Jinja2 filter: handle both datetime objects and ISO strings."""
    if not value:
        return "—"
    if isinstance(value, str):
        # ISO string: return date part, or date+time if requested
        if "%H" in fmt or "%M" in fmt:
            return value[:16].replace("T", " ")
        return value[:10]
    return value.strftime(fmt)


def _format_identity(value) -> str:
    """Jinja2 filter: render updated_by identity for display.

    Format convention:
        human:<name>    → name
        slack:<U123>    → Slack: U123
        bot:<name>      → 🤖 name
        claude:*        → legacy, show as-is
        None / empty    → —
    """
    if not value:
        return "—"
    if value.startswith("human:"):
        return value[6:]
    if value.startswith("slack:"):
        return f"Slack: {value[6:]}"
    if value.startswith("bot:"):
        return f"🤖 {value[4:]}"
    return value


def _compute_asset_version() -> str:
    """Compute a cache-busting version string from static file mtimes."""
    import hashlib
    static_dir = BASE_DIR / "static"
    h = hashlib.md5()
    if static_dir.exists():
        for p in sorted(static_dir.rglob("*")):
            if p.is_file():
                h.update(str(p.relative_to(static_dir)).encode())
                h.update(str(int(p.stat().st_mtime)).encode())
    return h.hexdigest()[:8]


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_pool()
    # Make templates available via app.state
    templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
    templates.env.filters["fdate"] = _format_date
    templates.env.filters["fidentity"] = _format_identity
    templates.env.globals["asset_version"] = _compute_asset_version()
    app.state.templates = templates
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

    # Check API key: header > query param > cookie
    key = (
        request.headers.get("X-API-Key")
        or request.query_params.get("api_key")
        or request.cookies.get("atdd_key")
    )
    if key != API_KEY:
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid or missing API key"},
        )

    # If authenticated via query param and no cookie yet → set cookie and redirect to clean URL
    if request.query_params.get("api_key") and not request.cookies.get("atdd_key"):
        clean_url = str(request.url).split("?")[0]
        other_params = {k: v for k, v in request.query_params.items() if k != "api_key"}
        if other_params:
            clean_url += "?" + "&".join(f"{k}={v}" for k, v in other_params.items())
        redirect = RedirectResponse(clean_url, status_code=302)
        redirect.set_cookie("atdd_key", API_KEY, httponly=True, secure=True, samesite="lax", max_age=86400 * 30)
        return redirect

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
