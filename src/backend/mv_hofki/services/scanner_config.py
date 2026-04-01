"""Scanner config service — get/update global pipeline settings."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.models.scanner_config import ScannerConfig
from mv_hofki.schemas.scanner_config import ScannerConfigRead, ScannerConfigUpdate


async def get_config(session: AsyncSession) -> ScannerConfig:
    """Return the global scanner config, creating a default row if needed."""
    result = await session.execute(select(ScannerConfig).limit(1))
    config = result.scalar_one_or_none()
    if config is None:
        config = ScannerConfig()
        session.add(config)
        await session.flush()
    return config


async def update_config(
    session: AsyncSession, data: ScannerConfigUpdate
) -> ScannerConfig:
    """Update global scanner config with the provided fields."""
    config = await get_config(session)
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(config, key, value)
    await session.commit()
    await session.refresh(config)
    return config


async def get_effective_config(session: AsyncSession) -> dict:
    """Return global scanner config as a dict for PipelineContext.config."""
    config = await get_config(session)
    return ScannerConfigRead.model_validate(config).model_dump()
