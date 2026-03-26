"""Tests for scanner config model, service, and API."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.models.scanner_config import ScannerConfig
from mv_hofki.schemas.scanner_config import ScannerConfigUpdate
from mv_hofki.services.scanner_config import (
    get_config,
    get_effective_config,
    update_config,
)


@pytest.mark.asyncio
async def test_scanner_config_defaults(db_session: AsyncSession):
    """A new ScannerConfig row should have sensible defaults."""
    config = ScannerConfig()
    db_session.add(config)
    await db_session.flush()

    result = await db_session.execute(select(ScannerConfig))
    row = result.scalar_one()

    assert row.confidence_threshold == 0.6
    assert row.matching_method == "TM_CCOEFF_NORMED"
    assert row.multi_scale_enabled is False
    assert row.multi_scale_range == 0.05
    assert row.multi_scale_steps == 3
    assert row.edge_matching_enabled is False
    assert row.canny_low == 50
    assert row.canny_high == 150
    assert row.staff_removal_before_matching is False
    assert row.masked_matching_enabled is False
    assert row.mask_threshold == 200
    assert row.nms_iou_threshold == 0.3
    assert row.nms_method == "standard"
    assert row.adaptive_threshold_block_size == 15
    assert row.adaptive_threshold_c == 10
    assert row.morphology_kernel_size == 2
    assert row.auto_verify_confidence == 0.85


@pytest.mark.asyncio
async def test_get_config_creates_default_if_missing(db_session: AsyncSession):
    """get_config should create and return a default row if none exists."""
    config = await get_config(db_session)
    assert config.confidence_threshold == 0.6
    assert config.id is not None


@pytest.mark.asyncio
async def test_get_config_returns_existing(db_session: AsyncSession):
    """get_config should return the existing row."""
    row = ScannerConfig(confidence_threshold=0.8)
    db_session.add(row)
    await db_session.flush()

    config = await get_config(db_session)
    assert config.confidence_threshold == 0.8


@pytest.mark.asyncio
async def test_update_config(db_session: AsyncSession):
    """update_config should persist partial updates."""
    await get_config(db_session)  # ensure row exists
    updated = await update_config(
        db_session,
        ScannerConfigUpdate(confidence_threshold=0.75, edge_matching_enabled=True),
    )
    assert updated.confidence_threshold == 0.75
    assert updated.edge_matching_enabled is True
    # Unchanged fields keep defaults
    assert updated.multi_scale_enabled is False


@pytest.mark.asyncio
async def test_get_effective_config_with_overrides(db_session: AsyncSession):
    """Overrides should take precedence over global values."""
    effective = await get_effective_config(
        db_session,
        overrides=ScannerConfigUpdate(confidence_threshold=0.9),
    )
    assert effective["confidence_threshold"] == 0.9
    # Non-overridden values come from global
    assert effective["edge_matching_enabled"] is False


@pytest.mark.asyncio
async def test_api_get_config(client):
    """GET /api/v1/scanner/config should return defaults."""
    resp = await client.get("/api/v1/scanner/config")
    assert resp.status_code == 200
    data = resp.json()
    assert data["confidence_threshold"] == 0.6
    assert data["matching_method"] == "TM_CCOEFF_NORMED"


@pytest.mark.asyncio
async def test_api_update_config(client):
    """PUT /api/v1/scanner/config should update and return new values."""
    resp = await client.put(
        "/api/v1/scanner/config",
        json={"confidence_threshold": 0.7, "edge_matching_enabled": True},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["confidence_threshold"] == 0.7
    assert data["edge_matching_enabled"] is True

    # Verify persistence
    resp2 = await client.get("/api/v1/scanner/config")
    assert resp2.json()["confidence_threshold"] == 0.7
