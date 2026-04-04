"""ATDD API Server — Phase 2 + Phase 4 Dashboard."""

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from db import init_pool, close_pool
from routers import tasks, domains, reports, knowledge, views, events, workers

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
    version="0.2.0",
    lifespan=lifespan,
)

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
