"""Scanner config API routes — get/update global pipeline settings."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.api.deps import get_db
from mv_hofki.schemas.scanner_config import ScannerConfigRead, ScannerConfigUpdate
from mv_hofki.services import scanner_config as config_service

router = APIRouter(prefix="/api/v1/scanner", tags=["scanner-config"])


@router.get("/config", response_model=ScannerConfigRead)
async def get_scanner_config(db: AsyncSession = Depends(get_db)):
    """Return the global scanner pipeline configuration."""
    return await config_service.get_config(db)


@router.put("/config", response_model=ScannerConfigRead)
async def update_scanner_config(
    data: ScannerConfigUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update global scanner pipeline configuration (partial update)."""
    return await config_service.update_config(db, data)
