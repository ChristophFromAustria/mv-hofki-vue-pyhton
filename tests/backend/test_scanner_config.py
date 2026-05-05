"""Tests for ScannerConfigEntry ORM model."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.models.scanner_config_entry import ScannerConfigEntry
from mv_hofki.services.scanner_config import (
    get_config_entries,
    get_effective_config,
    reset_config_keys,
    update_config_values,
)
from mv_hofki.services.scanner_config_registry import (
    SCANNER_CONFIG_REGISTRY,
    sync_config_registry,
)


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


# ── Registry + sync tests ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_sync_creates_entries_from_registry(db_session: AsyncSession):
    """sync_config_registry should create all registry entries in the DB."""
    await sync_config_registry(db_session)

    result = await db_session.execute(select(ScannerConfigEntry))
    rows = {r.key: r for r in result.scalars().all()}

    assert len(rows) == len(SCANNER_CONFIG_REGISTRY)
    # Spot-check a known entry
    ct = rows["confidence_threshold"]
    assert ct.value == "0.6"
    assert ct.default_value == "0.6"
    assert ct.type == "number"
    assert ct.min == 0.0
    assert ct.max == 1.0


@pytest.mark.asyncio
async def test_sync_preserves_user_value(db_session: AsyncSession):
    """sync_config_registry should not overwrite user-changed values."""
    entry = ScannerConfigEntry(
        key="confidence_threshold",
        value="0.9",
        default_value="0.6",
        type="number",
        label="Old label",
        group_path="Old Group",
        min=0.0,
        max=1.0,
        step=0.05,
        sort_order=10,
    )
    db_session.add(entry)
    await db_session.flush()

    await sync_config_registry(db_session)

    result = await db_session.execute(
        select(ScannerConfigEntry).where(
            ScannerConfigEntry.key == "confidence_threshold"
        )
    )
    row = result.scalar_one()
    assert row.value == "0.9"  # Value preserved
    assert row.label == "Konfidenz-Schwellwert"  # Metadata updated
    assert row.group_path == "Template Matching"  # Metadata updated


@pytest.mark.asyncio
async def test_sync_deletes_removed_keys(db_session: AsyncSession):
    """sync_config_registry should remove keys no longer in the registry."""
    orphan = ScannerConfigEntry(
        key="old_removed_key",
        value="42",
        default_value="42",
        type="number",
        label="Gone",
        sort_order=0,
    )
    db_session.add(orphan)
    await db_session.flush()

    await sync_config_registry(db_session)

    result = await db_session.execute(
        select(ScannerConfigEntry).where(ScannerConfigEntry.key == "old_removed_key")
    )
    assert result.scalar_one_or_none() is None


# ── Service CRUD tests ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_config_entries(db_session: AsyncSession):
    await sync_config_registry(db_session)
    entries = await get_config_entries(db_session)
    assert len(entries) == len(SCANNER_CONFIG_REGISTRY)
    ct = next(e for e in entries if e["key"] == "confidence_threshold")
    assert ct["value"] == 0.6
    assert ct["default_value"] == 0.6
    assert ct["is_modified"] is False
    assert ct["type"] == "number"
    assert ct["min"] == 0.0
    assert ct["max"] == 1.0
    assert ct["step"] == 0.05
    ms = next(e for e in entries if e["key"] == "multi_scale_enabled")
    assert ms["value"] is False
    assert ms["type"] == "toggle"
    mm = next(e for e in entries if e["key"] == "matching_method")
    assert isinstance(mm["options"], list)
    assert mm["options"][0]["value"] == "TM_CCOEFF_NORMED"


@pytest.mark.asyncio
async def test_update_config_values(db_session: AsyncSession):
    await sync_config_registry(db_session)
    entries = await update_config_values(
        db_session, {"confidence_threshold": 0.8, "dewarp_enabled": True}
    )
    ct = next(e for e in entries if e["key"] == "confidence_threshold")
    assert ct["value"] == 0.8
    assert ct["is_modified"] is True
    dw = next(e for e in entries if e["key"] == "dewarp_enabled")
    assert dw["value"] is True
    assert dw["is_modified"] is True


@pytest.mark.asyncio
async def test_update_validates_min_max(db_session: AsyncSession):
    await sync_config_registry(db_session)
    with pytest.raises(ValueError, match="out of range"):
        await update_config_values(db_session, {"confidence_threshold": 5.0})


@pytest.mark.asyncio
async def test_update_validates_select_option(db_session: AsyncSession):
    await sync_config_registry(db_session)
    with pytest.raises(ValueError, match="not a valid option"):
        await update_config_values(db_session, {"matching_method": "INVALID"})


@pytest.mark.asyncio
async def test_reset_config_keys(db_session: AsyncSession):
    await sync_config_registry(db_session)
    await update_config_values(db_session, {"confidence_threshold": 0.9})
    entries = await reset_config_keys(db_session, ["confidence_threshold"])
    ct = next(e for e in entries if e["key"] == "confidence_threshold")
    assert ct["value"] == 0.6
    assert ct["is_modified"] is False


@pytest.mark.asyncio
async def test_reset_all_keys(db_session: AsyncSession):
    await sync_config_registry(db_session)
    await update_config_values(
        db_session, {"confidence_threshold": 0.9, "dewarp_enabled": True}
    )
    entries = await reset_config_keys(db_session, [])
    assert all(e["is_modified"] is False for e in entries)


@pytest.mark.asyncio
async def test_get_effective_config_returns_dict(db_session: AsyncSession):
    await sync_config_registry(db_session)
    await update_config_values(db_session, {"confidence_threshold": 0.75})
    config = await get_effective_config(db_session)
    assert config["confidence_threshold"] == 0.75
    assert config["multi_scale_enabled"] is False
    assert config["matching_method"] == "TM_CCOEFF_NORMED"
    assert isinstance(config["canny_low"], int)


# ── API route tests ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_api_get_config_entries(client):
    """GET /api/v1/scanner/config returns entries with metadata."""
    resp = await client.get("/api/v1/scanner/config")
    assert resp.status_code == 200
    data = resp.json()
    assert "entries" in data
    assert len(data["entries"]) == len(SCANNER_CONFIG_REGISTRY)
    ct = next(e for e in data["entries"] if e["key"] == "confidence_threshold")
    assert ct["value"] == 0.6
    assert ct["is_modified"] is False
    assert ct["type"] == "number"
    assert ct["min"] == 0.0


@pytest.mark.asyncio
async def test_api_put_config(client):
    """PUT /api/v1/scanner/config updates values."""
    resp = await client.put(
        "/api/v1/scanner/config",
        json={"values": {"confidence_threshold": 0.8, "dewarp_enabled": True}},
    )
    assert resp.status_code == 200
    data = resp.json()
    ct = next(e for e in data["entries"] if e["key"] == "confidence_threshold")
    assert ct["value"] == 0.8
    assert ct["is_modified"] is True


@pytest.mark.asyncio
async def test_api_put_config_validation_error(client):
    """PUT /api/v1/scanner/config returns 422 for invalid values."""
    resp = await client.put(
        "/api/v1/scanner/config",
        json={"values": {"confidence_threshold": 5.0}},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_api_post_reset(client):
    """POST /api/v1/scanner/config/reset resets specific keys."""
    await client.put(
        "/api/v1/scanner/config",
        json={"values": {"confidence_threshold": 0.9}},
    )
    resp = await client.post(
        "/api/v1/scanner/config/reset",
        json={"keys": ["confidence_threshold"]},
    )
    assert resp.status_code == 200
    ct = next(e for e in resp.json()["entries"] if e["key"] == "confidence_threshold")
    assert ct["value"] == 0.6
    assert ct["is_modified"] is False
