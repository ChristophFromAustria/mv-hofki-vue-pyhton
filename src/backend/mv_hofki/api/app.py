"""FastAPI application entry point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from mv_hofki.api.routes.currencies import router as currencies_router
from mv_hofki.api.routes.health import router as health_router
from mv_hofki.api.routes.instrument_types import router as instrument_types_router
from mv_hofki.api.routes.instruments import router as instruments_router
from mv_hofki.api.routes.musicians import router as musicians_router
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
app.include_router(instruments_router)
app.include_router(musicians_router)

_frontend_dist = settings.PROJECT_ROOT / "src" / "frontend" / "dist"
if _frontend_dist.exists():
    app.mount(
        "/",
        StaticFiles(directory=str(_frontend_dist), html=True),
        name="frontend",
    )
