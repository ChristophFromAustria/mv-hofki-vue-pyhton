"""Scanner config API routes — get/update/reset config entries."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.api.deps import get_db
from mv_hofki.schemas.scanner_config_entry import (
    ConfigReset,
    ConfigResponse,
    ConfigUpdate,
)
from mv_hofki.services import scanner_config as config_service

router = APIRouter(prefix="/api/v1/scanner", tags=["scanner-config"])


@router.get("/config", response_model=ConfigResponse)
async def get_scanner_config(db: AsyncSession = Depends(get_db)):
    """Return all scanner config entries with metadata."""
    entries = await config_service.get_config_entries(db)
    return ConfigResponse.model_validate({"entries": entries})


@router.put("/config", response_model=ConfigResponse)
async def update_scanner_config(
    data: ConfigUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update scanner config values (partial update by key)."""
    try:
        entries = await config_service.update_config_values(db, data.values)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    await db.commit()
    return ConfigResponse.model_validate({"entries": entries})


@router.post("/config/reset", response_model=ConfigResponse)
async def reset_scanner_config(
    data: ConfigReset,
    db: AsyncSession = Depends(get_db),
):
    """Reset config keys to defaults (all if keys is empty)."""
    entries = await config_service.reset_config_keys(db, data.keys)
    await db.commit()
    return ConfigResponse.model_validate({"entries": entries})
