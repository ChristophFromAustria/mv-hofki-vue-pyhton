"""Tests for ScannerConfigEntry ORM model."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.models.scanner_config_entry import ScannerConfigEntry


@pytest.mark.asyncio
async def test_scanner_config_entry_model(db_session: AsyncSession):
    """A number-type entry should store all fields correctly."""
    entry = ScannerConfigEntry(
        key="confidence_threshold",
        value="0.75",
        default_value="0.6",
        type="number",
        label="Confidence Threshold",
        group_path="Template Matching",
        min=0.0,
        max=1.0,
        step=0.05,
        options=None,
        sort_order=1,
    )
    db_session.add(entry)
    await db_session.flush()

    result = await db_session.execute(
        select(ScannerConfigEntry).where(
            ScannerConfigEntry.key == "confidence_threshold"
        )
    )
    row = result.scalar_one()

    assert row.key == "confidence_threshold"
    assert row.value == "0.75"
    assert row.default_value == "0.6"
    assert row.type == "number"
    assert row.label == "Confidence Threshold"
    assert row.group_path == "Template Matching"
    assert row.min == 0.0
    assert row.max == 1.0
    assert row.step == 0.05
    assert row.options is None
    assert row.sort_order == 1


@pytest.mark.asyncio
async def test_scanner_config_entry_select_type(db_session: AsyncSession):
    """A select-type entry should store JSON options string."""
    options_json = '["TM_CCOEFF_NORMED","TM_CCORR_NORMED","TM_SQDIFF_NORMED"]'
    entry = ScannerConfigEntry(
        key="matching_method",
        value="TM_CCOEFF_NORMED",
        default_value="TM_CCOEFF_NORMED",
        type="select",
        label="Matching Method",
        group_path="Template Matching",
        min=None,
        max=None,
        step=None,
        options=options_json,
        sort_order=2,
    )
    db_session.add(entry)
    await db_session.flush()

    result = await db_session.execute(
        select(ScannerConfigEntry).where(ScannerConfigEntry.key == "matching_method")
    )
    row = result.scalar_one()

    assert row.key == "matching_method"
    assert row.value == "TM_CCOEFF_NORMED"
    assert row.type == "select"
    assert row.options == options_json
    assert row.min is None
    assert row.max is None
    assert row.step is None
