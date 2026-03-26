"""Tests for scanner config model, service, and API."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.models.scanner_config import ScannerConfig


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
