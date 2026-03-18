"""FastAPI application entry point.

Run with:
    PYTHONPATH=src/backend uvicorn mv_hofki.api.app:app --reload --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from mv_hofki.api.routes.health import router as health_router
from mv_hofki.core.config import settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    root_path=settings.BASE_PATH if settings.BASE_PATH != "/" else "",
)

app.include_router(health_router)

# Serve the compiled frontend — only if it has been built.
# API routes above take priority; this catch-all is last.
_frontend_dist = settings.PROJECT_ROOT / "src" / "frontend" / "dist"
if _frontend_dist.exists():
    app.mount(
        "/",
        StaticFiles(directory=str(_frontend_dist), html=True),
        name="frontend",
    )
