"""FastAPI application entry point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from mv_hofki.api.routes.clothing_types import router as clothing_types_router
from mv_hofki.api.routes.currencies import router as currencies_router
from mv_hofki.api.routes.dashboard import router as dashboard_router
from mv_hofki.api.routes.health import router as health_router
from mv_hofki.api.routes.instrument_types import router as instrument_types_router
from mv_hofki.api.routes.invoices import router as invoices_router
from mv_hofki.api.routes.item_images import router as item_images_router
from mv_hofki.api.routes.item_invoices import router as item_invoices_router
from mv_hofki.api.routes.items import router as items_router
from mv_hofki.api.routes.loans import router as loans_router
from mv_hofki.api.routes.musicians import router as musicians_router
from mv_hofki.api.routes.sheet_music_genres import router as sheet_music_genres_router
from mv_hofki.core.config import settings
from mv_hofki.db.engine import async_session_factory
from mv_hofki.db.seed import seed_data

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with async_session_factory() as session:
        await seed_data(session)
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    root_path=settings.BASE_PATH if settings.BASE_PATH != "/" else "",
    lifespan=lifespan,
)

app.include_router(health_router)
app.include_router(currencies_router)
app.include_router(instrument_types_router)
app.include_router(clothing_types_router)
app.include_router(sheet_music_genres_router)
app.include_router(items_router)
app.include_router(item_images_router)
app.include_router(item_invoices_router)
app.include_router(invoices_router)
app.include_router(musicians_router)
app.include_router(loans_router)
app.include_router(dashboard_router)

_uploads_dir = settings.PROJECT_ROOT / "data" / "uploads"
_uploads_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(_uploads_dir)), name="uploads")

_frontend_dist = settings.PROJECT_ROOT / "src" / "frontend" / "dist"
if _frontend_dist.exists():
    _index_html = _frontend_dist / "index.html"
    app.mount(
        "/assets",
        StaticFiles(directory=str(_frontend_dist / "assets")),
        name="frontend-assets",
    )

    @app.get("/{full_path:path}")
    async def _spa_fallback(request: Request, full_path: str):
        """Serve static files or fall back to index.html for SPA routing."""
        file_path = _frontend_dist / full_path
        if full_path and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(_index_html)
