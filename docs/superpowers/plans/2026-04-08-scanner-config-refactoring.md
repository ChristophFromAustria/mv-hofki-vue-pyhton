# Scanner Config Refactoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the column-per-field `scanner_config` table with a row-per-entry `scanner_config_entry` table, making all field metadata (min, max, step, label, group, options) backend-driven so new config fields never require migrations.

**Architecture:** Single DB table `scanner_config_entry` with one row per config key. A Python registry (`SCANNER_CONFIG_REGISTRY`) defines all entries with defaults and metadata. Seeding syncs registry → DB on startup (insert new, update metadata, delete removed, never touch user values). Frontend renders config UI dynamically from API response.

**Tech Stack:** SQLAlchemy 2.0 async, Alembic, FastAPI, Pydantic, Vue 3 Composition API

---

## File Structure

### New Files
- `src/backend/mv_hofki/models/scanner_config_entry.py` — ORM model for `scanner_config_entry` table
- `src/backend/mv_hofki/schemas/scanner_config_entry.py` — Pydantic schemas (EntryRead, ConfigResponse, ConfigUpdate, ConfigReset)
- `src/backend/mv_hofki/services/scanner_config_registry.py` — Registry list + seeding function
- `alembic/versions/xxxx_replace_scanner_config_with_entries.py` — Migration: create new table, migrate values, drop old table, clear adjustments_json

### Modified Files
- `src/backend/mv_hofki/services/scanner_config.py` — Rewrite: CRUD + get_effective_config using new table
- `src/backend/mv_hofki/api/routes/scanner_config.py` — Rewrite: GET entries, PUT values, POST reset
- `src/backend/mv_hofki/models/__init__.py` — Replace ScannerConfig import with ScannerConfigEntry
- `src/backend/mv_hofki/db/seed.py` — Replace old seeding with registry sync call
- `src/backend/mv_hofki/api/app.py` — No change needed (router import name stays)
- `src/backend/mv_hofki/services/sheet_music_scan.py` — Update get_effective_config import (function signature unchanged)
- `src/frontend/src/pages/ScannerConfigPage.vue` — Full rewrite: dynamic from API, nested groups, modified indicator, single-value reset
- `src/frontend/src/components/ScannerConfigModal.vue` — Full rewrite: dynamic from API, nested groups, override logic adapted
- `src/frontend/src/pages/ScanEditorPage.vue` — Minor: adjustments.analysis check stays, no structural change

### Deleted Files
- `src/backend/mv_hofki/models/scanner_config.py` — Replaced by scanner_config_entry.py
- `src/backend/mv_hofki/schemas/scanner_config.py` — Replaced by scanner_config_entry.py
- `src/frontend/src/lib/scanner-config.js` — No longer needed, metadata comes from API

### Unchanged
- All pipeline stages (`ctx.config.get()` stays identical)
- `src/backend/mv_hofki/services/sheet_music_scan.py` merge_scan_adjustments() — logic unchanged
- `src/backend/mv_hofki/api/routes/scan_processing.py`
- `src/backend/mv_hofki/api/routes/scans.py`

---

### Task 1: ORM Model for scanner_config_entry

**Files:**
- Create: `src/backend/mv_hofki/models/scanner_config_entry.py`
- Test: `tests/backend/test_scanner_config.py` (rewrite)

- [ ] **Step 1: Write the failing test**

```python
# tests/backend/test_scanner_config.py — replace entire file
"""Tests for scanner_config_entry model and services."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.models.scanner_config_entry import ScannerConfigEntry


@pytest.mark.asyncio
async def test_scanner_config_entry_model(db_session: AsyncSession):
    """A ScannerConfigEntry row stores key, value, metadata."""
    entry = ScannerConfigEntry(
        key="confidence_threshold",
        value="0.6",
        default_value="0.6",
        type="number",
        label="Konfidenz-Schwellwert",
        group_path="Template Matching",
        min=0.0,
        max=1.0,
        step=0.05,
        sort_order=10,
    )
    db_session.add(entry)
    await db_session.flush()

    result = await db_session.execute(
        select(ScannerConfigEntry).where(ScannerConfigEntry.key == "confidence_threshold")
    )
    row = result.scalar_one()

    assert row.key == "confidence_threshold"
    assert row.value == "0.6"
    assert row.default_value == "0.6"
    assert row.type == "number"
    assert row.label == "Konfidenz-Schwellwert"
    assert row.group_path == "Template Matching"
    assert row.min == 0.0
    assert row.max == 1.0
    assert row.step == 0.05
    assert row.options is None
    assert row.sort_order == 10


@pytest.mark.asyncio
async def test_scanner_config_entry_select_type(db_session: AsyncSession):
    """Select-type entries store options as JSON string."""
    entry = ScannerConfigEntry(
        key="nms_method",
        value="standard",
        default_value="standard",
        type="select",
        label="NMS-Methode",
        group_path="Non-Maximum Suppression",
        options='[{"value":"standard","label":"Standard (IoU)"},{"value":"dilate","label":"Dilate"}]',
        sort_order=10,
    )
    db_session.add(entry)
    await db_session.flush()

    result = await db_session.execute(
        select(ScannerConfigEntry).where(ScannerConfigEntry.key == "nms_method")
    )
    row = result.scalar_one()
    assert row.options is not None
    assert "standard" in row.options
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/backend/test_scanner_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'mv_hofki.models.scanner_config_entry'`

- [ ] **Step 3: Write the ORM model**

```python
# src/backend/mv_hofki/models/scanner_config_entry.py
"""ScannerConfigEntry ORM model — one row per config key."""

from __future__ import annotations

from sqlalchemy import Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from mv_hofki.db.base import Base


class ScannerConfigEntry(Base):
    __tablename__ = "scanner_config_entry"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    default_value: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(String(10), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    group_path: Mapped[str | None] = mapped_column(String(200), nullable=True)
    min: Mapped[float | None] = mapped_column(Float, nullable=True)
    max: Mapped[float | None] = mapped_column(Float, nullable=True)
    step: Mapped[float | None] = mapped_column(Float, nullable=True)
    options: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
```

- [ ] **Step 4: Update models/__init__.py**

Replace the `ScannerConfig` import and `__all__` entry in `src/backend/mv_hofki/models/__init__.py`:

Change:
```python
from mv_hofki.models.scanner_config import ScannerConfig
```
to:
```python
from mv_hofki.models.scanner_config_entry import ScannerConfigEntry
```

And in `__all__`, change `"ScannerConfig"` to `"ScannerConfigEntry"`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/backend/test_scanner_config.py -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Commit**

```bash
git add src/backend/mv_hofki/models/scanner_config_entry.py src/backend/mv_hofki/models/__init__.py tests/backend/test_scanner_config.py
git commit -m "feat: add ScannerConfigEntry ORM model (row-per-key)"
```

---

### Task 2: Registry + Seeding Service

**Files:**
- Create: `src/backend/mv_hofki/services/scanner_config_registry.py`
- Test: `tests/backend/test_scanner_config.py` (append)

- [ ] **Step 1: Write failing tests for seeding**

Append to `tests/backend/test_scanner_config.py`:

```python
from mv_hofki.services.scanner_config_registry import (
    SCANNER_CONFIG_REGISTRY,
    sync_config_registry,
)


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
    # Pre-create an entry with a user-modified value
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
        select(ScannerConfigEntry).where(ScannerConfigEntry.key == "confidence_threshold")
    )
    row = result.scalar_one()
    # Value preserved
    assert row.value == "0.9"
    # Metadata updated from registry
    assert row.label == "Konfidenz-Schwellwert"
    assert row.group_path == "Template Matching"


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/backend/test_scanner_config.py::test_sync_creates_entries_from_registry -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write the registry and sync function**

```python
# src/backend/mv_hofki/services/scanner_config_registry.py
"""Scanner config registry — single source of truth for all config entries."""

from __future__ import annotations

import json

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.models.scanner_config_entry import ScannerConfigEntry

SCANNER_CONFIG_REGISTRY: list[dict] = [
    # ── Template Matching ────────────────────────────────────────────
    {
        "key": "confidence_threshold",
        "default_value": "0.6",
        "type": "number",
        "label": "Konfidenz-Schwellwert",
        "group_path": "Template Matching",
        "min": 0.0,
        "max": 1.0,
        "step": 0.05,
        "sort_order": 10,
    },
    {
        "key": "matching_method",
        "default_value": "TM_CCOEFF_NORMED",
        "type": "select",
        "label": "Matching-Methode",
        "group_path": "Template Matching",
        "options": [
            {"value": "TM_CCOEFF_NORMED", "label": "Kreuzkorrelationskoeffizient (Standard)"},
            {"value": "TM_CCORR_NORMED", "label": "Kreuzkorrelation"},
            {"value": "TM_SQDIFF_NORMED", "label": "Quadratische Differenz"},
        ],
        "sort_order": 20,
    },
    {
        "key": "auto_verify_confidence",
        "default_value": "0.85",
        "type": "number",
        "label": "Auto-Verifizierung ab",
        "group_path": "Template Matching",
        "min": 0.0,
        "max": 1.0,
        "step": 0.05,
        "sort_order": 30,
    },
    # ── Multi-Scale ──────────────────────────────────────────────────
    {
        "key": "multi_scale_enabled",
        "default_value": "false",
        "type": "toggle",
        "label": "Multi-Scale-Suche",
        "group_path": "Multi-Scale",
        "sort_order": 10,
    },
    {
        "key": "multi_scale_range",
        "default_value": "0.05",
        "type": "number",
        "label": "Suchbereich (+/-)",
        "group_path": "Multi-Scale",
        "min": 0.01,
        "max": 0.5,
        "step": 0.01,
        "sort_order": 20,
    },
    {
        "key": "multi_scale_steps",
        "default_value": "3",
        "type": "number",
        "label": "Stufen",
        "group_path": "Multi-Scale",
        "min": 1.0,
        "max": 20.0,
        "step": 1.0,
        "sort_order": 30,
    },
    # ── Kanten-Matching ──────────────────────────────────────────────
    {
        "key": "edge_matching_enabled",
        "default_value": "false",
        "type": "toggle",
        "label": "Kanten-Matching",
        "group_path": "Kanten-Matching",
        "sort_order": 10,
    },
    {
        "key": "canny_low",
        "default_value": "50",
        "type": "number",
        "label": "Canny unterer Schwellwert",
        "group_path": "Kanten-Matching",
        "min": 0.0,
        "max": 500.0,
        "step": 10.0,
        "sort_order": 20,
    },
    {
        "key": "canny_high",
        "default_value": "150",
        "type": "number",
        "label": "Canny oberer Schwellwert",
        "group_path": "Kanten-Matching",
        "min": 0.0,
        "max": 500.0,
        "step": 10.0,
        "sort_order": 30,
    },
    # ── Scanbereich ──────────────────────────────────────────────────
    {
        "key": "staff_margin_top",
        "default_value": "4.0",
        "type": "number",
        "label": "Scanbereich oben (\u00d7 Linienabstand)",
        "group_path": "Scanbereich",
        "min": 1.0,
        "max": 20.0,
        "step": 0.5,
        "sort_order": 10,
    },
    {
        "key": "staff_margin_bottom",
        "default_value": "4.0",
        "type": "number",
        "label": "Scanbereich unten (\u00d7 Linienabstand)",
        "group_path": "Scanbereich",
        "min": 1.0,
        "max": 20.0,
        "step": 0.5,
        "sort_order": 20,
    },
    # ── Notenlinien-Entfernung ───────────────────────────────────────
    {
        "key": "staff_removal_before_matching",
        "default_value": "false",
        "type": "toggle",
        "label": "Notenlinien vor Matching entfernen",
        "group_path": "Notenlinien-Entfernung",
        "sort_order": 10,
    },
    {
        "key": "staff_removal_thickness_pct",
        "default_value": "100",
        "type": "number",
        "label": "Liniendicke-Korrektur (%)",
        "group_path": "Notenlinien-Entfernung",
        "min": 50.0,
        "max": 300.0,
        "step": 10.0,
        "sort_order": 20,
    },
    {
        "key": "staff_removal_symbol_padding",
        "default_value": "0",
        "type": "number",
        "label": "Symbol-Abstand (px)",
        "group_path": "Notenlinien-Entfernung",
        "min": 0.0,
        "max": 50.0,
        "step": 1.0,
        "sort_order": 30,
    },
    # ── Krümmungskorrektur ───────────────────────────────────────────
    {
        "key": "dewarp_enabled",
        "default_value": "false",
        "type": "toggle",
        "label": "Krümmungskorrektur",
        "group_path": "Krümmungskorrektur",
        "sort_order": 10,
    },
    {
        "key": "dewarp_smoothing",
        "default_value": "50",
        "type": "number",
        "label": "Glättung (px)",
        "group_path": "Krümmungskorrektur",
        "min": 5.0,
        "max": 200.0,
        "step": 5.0,
        "sort_order": 20,
    },
    # ── Maskiertes Matching ──────────────────────────────────────────
    {
        "key": "masked_matching_enabled",
        "default_value": "false",
        "type": "toggle",
        "label": "Maskiertes Matching",
        "group_path": "Maskiertes Matching",
        "sort_order": 10,
    },
    {
        "key": "mask_threshold",
        "default_value": "200",
        "type": "number",
        "label": "Masken-Schwellwert",
        "group_path": "Maskiertes Matching",
        "min": 0.0,
        "max": 255.0,
        "step": 5.0,
        "sort_order": 20,
    },
    # ── Non-Maximum Suppression ──────────────────────────────────────
    {
        "key": "nms_iou_threshold",
        "default_value": "0.3",
        "type": "number",
        "label": "NMS IoU-Schwellwert",
        "group_path": "Non-Maximum Suppression",
        "min": 0.0,
        "max": 1.0,
        "step": 0.05,
        "sort_order": 10,
    },
    {
        "key": "nms_method",
        "default_value": "standard",
        "type": "select",
        "label": "NMS-Methode",
        "group_path": "Non-Maximum Suppression",
        "options": [
            {"value": "standard", "label": "Standard (IoU)"},
            {"value": "dilate", "label": "Dilate (Proximity)"},
        ],
        "sort_order": 20,
    },
    # ── Preprocessing ────────────────────────────────────────────────
    {
        "key": "adaptive_threshold_block_size",
        "default_value": "15",
        "type": "number",
        "label": "Adaptiver Schwellwert Blockgröße",
        "group_path": "Preprocessing",
        "min": 3.0,
        "max": 99.0,
        "step": 2.0,
        "sort_order": 10,
    },
    {
        "key": "adaptive_threshold_c",
        "default_value": "10",
        "type": "number",
        "label": "Adaptiver Schwellwert Konstante",
        "group_path": "Preprocessing",
        "min": 0.0,
        "max": 50.0,
        "step": 1.0,
        "sort_order": 20,
    },
    {
        "key": "morphology_kernel_size",
        "default_value": "2",
        "type": "number",
        "label": "Morphologie Kernel-Größe",
        "group_path": "Preprocessing",
        "min": 1.0,
        "max": 10.0,
        "step": 1.0,
        "sort_order": 30,
    },
    # ── Deskew ───────────────────────────────────────────────────────
    {
        "key": "deskew_method",
        "default_value": "projection",
        "type": "select",
        "label": "Entzerrungsmethode",
        "group_path": "Deskew",
        "options": [
            {"value": "none", "label": "Keine"},
            {"value": "hough", "label": "Hough-Transformation"},
            {"value": "projection", "label": "Projektionsprofil"},
        ],
        "sort_order": 10,
    },
    # ── Text-Maskierung ──────────────────────────────────────────────
    {
        "key": "text_masking_min_confidence",
        "default_value": "30",
        "type": "number",
        "label": "Minimale Konfidenz",
        "group_path": "Text-Maskierung",
        "min": 0.0,
        "max": 100.0,
        "step": 5.0,
        "sort_order": 10,
    },
    # ── Keil-Erkennung (Hairpin) ─────────────────────────────────────
    {
        "key": "hairpin_min_width_factor",
        "default_value": "3.0",
        "type": "number",
        "label": "Min. Linien-Breite (\u00d7 Linienabstand)",
        "group_path": "Keil-Erkennung",
        "min": 0.5,
        "max": 10.0,
        "step": 0.5,
        "sort_order": 10,
    },
    {
        "key": "hairpin_min_hitbox_width_factor",
        "default_value": "3.0",
        "type": "number",
        "label": "Min. Hitbox-Breite (\u00d7 Linienabstand)",
        "group_path": "Keil-Erkennung",
        "min": 0.5,
        "max": 10.0,
        "step": 0.5,
        "sort_order": 20,
    },
    {
        "key": "hairpin_min_confidence",
        "default_value": "0.3",
        "type": "number",
        "label": "Min. Konfidenz",
        "group_path": "Keil-Erkennung",
        "min": 0.0,
        "max": 1.0,
        "step": 0.05,
        "sort_order": 30,
    },
    # ── LilyPond Layout ─────────────────────────────────────────────
    {
        "key": "ly_top_margin",
        "default_value": "1",
        "type": "number",
        "label": "Oberer Rand (mm)",
        "group_path": "LilyPond Layout",
        "min": 0.0,
        "max": 50.0,
        "step": 1.0,
        "sort_order": 10,
    },
    {
        "key": "ly_bottom_margin",
        "default_value": "4",
        "type": "number",
        "label": "Unterer Rand (mm)",
        "group_path": "LilyPond Layout",
        "min": 0.0,
        "max": 50.0,
        "step": 1.0,
        "sort_order": 20,
    },
    {
        "key": "ly_left_margin",
        "default_value": "16",
        "type": "number",
        "label": "Linker Rand (mm)",
        "group_path": "LilyPond Layout",
        "min": 0.0,
        "max": 50.0,
        "step": 1.0,
        "sort_order": 30,
    },
    {
        "key": "ly_right_margin",
        "default_value": "16",
        "type": "number",
        "label": "Rechter Rand (mm)",
        "group_path": "LilyPond Layout",
        "min": 0.0,
        "max": 50.0,
        "step": 1.0,
        "sort_order": 40,
    },
    {
        "key": "ly_staff_size",
        "default_value": "17",
        "type": "number",
        "label": "Notensystem-Größe",
        "group_path": "LilyPond Layout",
        "min": 8.0,
        "max": 30.0,
        "step": 1.0,
        "sort_order": 50,
    },
    {
        "key": "ly_system_distance",
        "default_value": "6",
        "type": "number",
        "label": "System-Abstand",
        "group_path": "LilyPond Layout",
        "min": 1.0,
        "max": 20.0,
        "step": 1.0,
        "sort_order": 60,
    },
    {
        "key": "ly_system_padding",
        "default_value": "0.6",
        "type": "number",
        "label": "System-Padding",
        "group_path": "LilyPond Layout",
        "min": 0.0,
        "max": 5.0,
        "step": 0.1,
        "sort_order": 70,
    },
]


def _cast_value(raw: str, entry_type: str, *, step: float | None = None, min_val: float | None = None, max_val: float | None = None):
    """Cast a string value to its native Python type based on entry type."""
    if entry_type == "toggle":
        return raw.lower() == "true"
    if entry_type == "number":
        f = float(raw)
        if step is not None and step >= 1 and (min_val is None or min_val == int(min_val)) and (max_val is None or max_val == int(max_val)):
            return int(f)
        return f
    return raw


def _serialize_value(value, entry_type: str) -> str:
    """Serialize a native Python value to string for DB storage."""
    if entry_type == "toggle":
        return "true" if value else "false"
    return str(value)


async def sync_config_registry(session: AsyncSession) -> None:
    """Sync registry entries to DB: insert new, update metadata, delete removed."""
    registry_keys = {e["key"] for e in SCANNER_CONFIG_REGISTRY}

    # Load existing entries
    result = await session.execute(select(ScannerConfigEntry))
    existing = {row.key: row for row in result.scalars().all()}

    for entry_def in SCANNER_CONFIG_REGISTRY:
        key = entry_def["key"]
        options_str = json.dumps(entry_def["options"]) if entry_def.get("options") else None

        if key in existing:
            # Update metadata only, preserve value
            row = existing[key]
            row.default_value = entry_def["default_value"]
            row.type = entry_def["type"]
            row.label = entry_def["label"]
            row.group_path = entry_def.get("group_path")
            row.min = entry_def.get("min")
            row.max = entry_def.get("max")
            row.step = entry_def.get("step")
            row.options = options_str
            row.sort_order = entry_def.get("sort_order", 0)
        else:
            # Insert new entry with default value
            row = ScannerConfigEntry(
                key=key,
                value=entry_def["default_value"],
                default_value=entry_def["default_value"],
                type=entry_def["type"],
                label=entry_def["label"],
                group_path=entry_def.get("group_path"),
                min=entry_def.get("min"),
                max=entry_def.get("max"),
                step=entry_def.get("step"),
                options=options_str,
                sort_order=entry_def.get("sort_order", 0),
            )
            session.add(row)

    # Delete keys no longer in registry
    orphan_keys = set(existing.keys()) - registry_keys
    if orphan_keys:
        await session.execute(
            delete(ScannerConfigEntry).where(ScannerConfigEntry.key.in_(orphan_keys))
        )

    await session.flush()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/backend/test_scanner_config.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add src/backend/mv_hofki/services/scanner_config_registry.py tests/backend/test_scanner_config.py
git commit -m "feat: add scanner config registry with sync_config_registry seeding"
```

---

### Task 3: Pydantic Schemas + Service CRUD

**Files:**
- Create: `src/backend/mv_hofki/schemas/scanner_config_entry.py`
- Modify: `src/backend/mv_hofki/services/scanner_config.py` (rewrite)
- Test: `tests/backend/test_scanner_config.py` (append)

- [ ] **Step 1: Write failing tests for service + schemas**

Append to `tests/backend/test_scanner_config.py`:

```python
from mv_hofki.services.scanner_config import (
    get_config_entries,
    update_config_values,
    reset_config_keys,
    get_effective_config,
)


@pytest.mark.asyncio
async def test_get_config_entries(db_session: AsyncSession):
    """get_config_entries returns all entries with casted values and is_modified."""
    await sync_config_registry(db_session)

    entries = await get_config_entries(db_session)
    assert len(entries) == len(SCANNER_CONFIG_REGISTRY)

    # Find confidence_threshold
    ct = next(e for e in entries if e["key"] == "confidence_threshold")
    assert ct["value"] == 0.6
    assert ct["default_value"] == 0.6
    assert ct["is_modified"] is False
    assert ct["type"] == "number"
    assert ct["min"] == 0.0
    assert ct["max"] == 1.0
    assert ct["step"] == 0.05

    # Find a toggle
    ms = next(e for e in entries if e["key"] == "multi_scale_enabled")
    assert ms["value"] is False
    assert ms["type"] == "toggle"

    # Find a select with parsed options
    mm = next(e for e in entries if e["key"] == "matching_method")
    assert isinstance(mm["options"], list)
    assert mm["options"][0]["value"] == "TM_CCOEFF_NORMED"


@pytest.mark.asyncio
async def test_update_config_values(db_session: AsyncSession):
    """update_config_values should update specific keys and return updated entries."""
    await sync_config_registry(db_session)

    entries = await update_config_values(db_session, {
        "confidence_threshold": 0.8,
        "dewarp_enabled": True,
    })

    ct = next(e for e in entries if e["key"] == "confidence_threshold")
    assert ct["value"] == 0.8
    assert ct["is_modified"] is True

    dw = next(e for e in entries if e["key"] == "dewarp_enabled")
    assert dw["value"] is True
    assert dw["is_modified"] is True


@pytest.mark.asyncio
async def test_update_validates_min_max(db_session: AsyncSession):
    """update_config_values should reject values outside min/max."""
    await sync_config_registry(db_session)

    with pytest.raises(ValueError, match="out of range"):
        await update_config_values(db_session, {"confidence_threshold": 5.0})


@pytest.mark.asyncio
async def test_update_validates_select_option(db_session: AsyncSession):
    """update_config_values should reject invalid select options."""
    await sync_config_registry(db_session)

    with pytest.raises(ValueError, match="not a valid option"):
        await update_config_values(db_session, {"matching_method": "INVALID"})


@pytest.mark.asyncio
async def test_reset_config_keys(db_session: AsyncSession):
    """reset_config_keys should set value back to default."""
    await sync_config_registry(db_session)
    await update_config_values(db_session, {"confidence_threshold": 0.9})

    entries = await reset_config_keys(db_session, ["confidence_threshold"])
    ct = next(e for e in entries if e["key"] == "confidence_threshold")
    assert ct["value"] == 0.6
    assert ct["is_modified"] is False


@pytest.mark.asyncio
async def test_reset_all_keys(db_session: AsyncSession):
    """reset_config_keys with empty list should reset all."""
    await sync_config_registry(db_session)
    await update_config_values(db_session, {"confidence_threshold": 0.9, "dewarp_enabled": True})

    entries = await reset_config_keys(db_session, [])
    assert all(e["is_modified"] is False for e in entries)


@pytest.mark.asyncio
async def test_get_effective_config_returns_dict(db_session: AsyncSession):
    """get_effective_config should return {key: casted_value} dict."""
    await sync_config_registry(db_session)
    await update_config_values(db_session, {"confidence_threshold": 0.75})

    config = await get_effective_config(db_session)
    assert config["confidence_threshold"] == 0.75
    assert config["multi_scale_enabled"] is False
    assert config["matching_method"] == "TM_CCOEFF_NORMED"
    assert isinstance(config["canny_low"], int)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/backend/test_scanner_config.py::test_get_config_entries -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Write Pydantic schemas**

```python
# src/backend/mv_hofki/schemas/scanner_config_entry.py
"""Pydantic schemas for scanner config entries."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ConfigEntryRead(BaseModel):
    """One config entry with metadata and casted values."""

    key: str
    value: int | float | bool | str
    default_value: int | float | bool | str
    is_modified: bool
    type: str
    label: str
    group_path: str | None
    min: float | None
    max: float | None
    step: float | None
    options: list[dict[str, str]] | None
    sort_order: int


class ConfigResponse(BaseModel):
    """Full config response — list of all entries."""

    entries: list[ConfigEntryRead]


class ConfigUpdate(BaseModel):
    """Partial update — key-value pairs."""

    values: dict[str, Any]


class ConfigReset(BaseModel):
    """Reset specific keys (or all if keys is empty/omitted)."""

    keys: list[str] = []
```

- [ ] **Step 4: Rewrite the scanner_config service**

Replace the entire content of `src/backend/mv_hofki/services/scanner_config.py`:

```python
"""Scanner config service — CRUD for row-based config entries."""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.models.scanner_config_entry import ScannerConfigEntry
from mv_hofki.services.scanner_config_registry import _cast_value, _serialize_value


async def get_config_entries(session: AsyncSession) -> list[dict]:
    """Return all config entries as dicts with casted values."""
    result = await session.execute(select(ScannerConfigEntry))
    rows = result.scalars().all()
    return [_row_to_dict(row) for row in rows]


async def update_config_values(session: AsyncSession, values: dict) -> list[dict]:
    """Update config values by key. Validates against metadata."""
    result = await session.execute(select(ScannerConfigEntry))
    entries = {row.key: row for row in result.scalars().all()}

    for key, value in values.items():
        if key not in entries:
            raise ValueError(f"Unknown config key: {key}")
        row = entries[key]
        _validate_value(row, value)
        row.value = _serialize_value(value, row.type)

    await session.flush()
    return [_row_to_dict(row) for row in entries.values()]


async def reset_config_keys(session: AsyncSession, keys: list[str]) -> list[dict]:
    """Reset specific keys to default, or all if keys is empty."""
    result = await session.execute(select(ScannerConfigEntry))
    rows = result.scalars().all()

    for row in rows:
        if not keys or row.key in keys:
            row.value = row.default_value

    await session.flush()
    return [_row_to_dict(row) for row in rows]


async def get_effective_config(session: AsyncSession) -> dict:
    """Return {key: casted_value} dict for PipelineContext.config."""
    result = await session.execute(select(ScannerConfigEntry))
    rows = result.scalars().all()
    return {
        row.key: _cast_value(row.value, row.type, step=row.step, min_val=row.min, max_val=row.max)
        for row in rows
    }


def _row_to_dict(row: ScannerConfigEntry) -> dict:
    """Convert a DB row to a dict with casted values and is_modified flag."""
    value = _cast_value(row.value, row.type, step=row.step, min_val=row.min, max_val=row.max)
    default = _cast_value(row.default_value, row.type, step=row.step, min_val=row.min, max_val=row.max)
    options = json.loads(row.options) if row.options else None
    return {
        "key": row.key,
        "value": value,
        "default_value": default,
        "is_modified": row.value != row.default_value,
        "type": row.type,
        "label": row.label,
        "group_path": row.group_path,
        "min": row.min,
        "max": row.max,
        "step": row.step,
        "options": options,
        "sort_order": row.sort_order,
    }


def _validate_value(row: ScannerConfigEntry, value) -> None:
    """Validate a value against entry metadata. Raises ValueError."""
    if row.type == "toggle":
        if not isinstance(value, bool):
            raise ValueError(f"{row.key}: expected bool, got {type(value).__name__}")
    elif row.type == "number":
        if not isinstance(value, (int, float)):
            raise ValueError(f"{row.key}: expected number, got {type(value).__name__}")
        if row.min is not None and value < row.min:
            raise ValueError(f"{row.key}: {value} out of range [{row.min}, {row.max}]")
        if row.max is not None and value > row.max:
            raise ValueError(f"{row.key}: {value} out of range [{row.min}, {row.max}]")
    elif row.type == "select":
        options = json.loads(row.options) if row.options else []
        valid = {o["value"] for o in options}
        if value not in valid:
            raise ValueError(f"{row.key}: '{value}' not a valid option (valid: {valid})")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/backend/test_scanner_config.py -v`
Expected: PASS (13 tests)

- [ ] **Step 6: Commit**

```bash
git add src/backend/mv_hofki/schemas/scanner_config_entry.py src/backend/mv_hofki/services/scanner_config.py tests/backend/test_scanner_config.py
git commit -m "feat: add config entry schemas and CRUD service with validation"
```

---

### Task 4: API Routes

**Files:**
- Modify: `src/backend/mv_hofki/api/routes/scanner_config.py` (rewrite)
- Test: `tests/backend/test_scanner_config.py` (append)

- [ ] **Step 1: Write failing API tests**

Append to `tests/backend/test_scanner_config.py`:

```python
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
    # First update a value
    await client.put(
        "/api/v1/scanner/config",
        json={"values": {"confidence_threshold": 0.9}},
    )
    # Then reset it
    resp = await client.post(
        "/api/v1/scanner/config/reset",
        json={"keys": ["confidence_threshold"]},
    )
    assert resp.status_code == 200
    ct = next(e for e in resp.json()["entries"] if e["key"] == "confidence_threshold")
    assert ct["value"] == 0.6
    assert ct["is_modified"] is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/backend/test_scanner_config.py::test_api_get_config_entries -v`
Expected: FAIL — API returns old format or 500

- [ ] **Step 3: Rewrite the API routes**

Replace the entire content of `src/backend/mv_hofki/api/routes/scanner_config.py`:

```python
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
    return ConfigResponse(entries=entries)


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
    return ConfigResponse(entries=entries)


@router.post("/config/reset", response_model=ConfigResponse)
async def reset_scanner_config(
    data: ConfigReset,
    db: AsyncSession = Depends(get_db),
):
    """Reset config keys to defaults (all if keys is empty)."""
    entries = await config_service.reset_config_keys(db, data.keys)
    await db.commit()
    return ConfigResponse(entries=entries)
```

- [ ] **Step 4: Run tests to verify they pass**

The API tests need the registry synced. The `client` fixture uses the app lifespan which calls `seed_data`. Update seeding in the next step — for now, ensure the DB has entries by running sync in the test's setup. But the API tests use the `client` fixture which triggers the lifespan. So we need to update seed.py first. Do that now:

Replace the scanner config section in `src/backend/mv_hofki/db/seed.py`:

Change the import:
```python
from mv_hofki.models.scanner_config import ScannerConfig
```
to:
```python
from mv_hofki.services.scanner_config_registry import sync_config_registry
```

Replace the scanner config seeding block (lines 103-106):
```python
    # Seed default scanner config if not present
    result = await session.execute(select(ScannerConfig).limit(1))
    if result.scalar_one_or_none() is None:
        session.add(ScannerConfig())
```
with:
```python
    # Sync scanner config registry (insert new, update metadata, delete orphans)
    await sync_config_registry(session)
```

- [ ] **Step 5: Run all tests to verify they pass**

Run: `python -m pytest tests/backend/test_scanner_config.py -v`
Expected: PASS (17 tests)

- [ ] **Step 6: Commit**

```bash
git add src/backend/mv_hofki/api/routes/scanner_config.py src/backend/mv_hofki/db/seed.py tests/backend/test_scanner_config.py
git commit -m "feat: rewrite scanner config API routes + update seeding"
```

---

### Task 5: Alembic Migration

**Files:**
- Create: `alembic/versions/xxxx_replace_scanner_config_with_entries.py`
- Delete: `src/backend/mv_hofki/models/scanner_config.py`
- Delete: `src/backend/mv_hofki/schemas/scanner_config.py`

- [ ] **Step 1: Generate the migration**

Run: `PYTHONPATH=src/backend alembic revision --autogenerate -m "replace scanner_config with scanner_config_entry"`

This should detect: create `scanner_config_entry`, drop `scanner_config`.

- [ ] **Step 2: Edit the migration to migrate values**

The autogenerated migration will need manual editing. Open the generated file and ensure it:

1. Creates `scanner_config_entry` table
2. Reads existing values from `scanner_config` (if the table exists)
3. Inserts entries from the registry, using migrated values where they differ from defaults
4. Drops `scanner_config` table
5. Sets all `adjustments_json` in `sheet_music_scans` to NULL

The `upgrade()` function should look like:

```python
def upgrade() -> None:
    # 1. Create new table
    op.create_table(
        "scanner_config_entry",
        sa.Column("key", sa.String(100), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("default_value", sa.Text(), nullable=False),
        sa.Column("type", sa.String(10), nullable=False),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("group_path", sa.String(200), nullable=True),
        sa.Column("min", sa.Float(), nullable=True),
        sa.Column("max", sa.Float(), nullable=True),
        sa.Column("step", sa.Float(), nullable=True),
        sa.Column("options", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
    )

    # 2. Migrate values from old table
    conn = op.get_bind()
    old_row = conn.execute(sa.text("SELECT * FROM scanner_config LIMIT 1")).mappings().first()

    from mv_hofki.services.scanner_config_registry import SCANNER_CONFIG_REGISTRY
    import json

    for entry in SCANNER_CONFIG_REGISTRY:
        key = entry["key"]
        default_val = entry["default_value"]
        value = default_val

        # If old table had this column and it differs from default, keep user value
        if old_row and key in old_row:
            old_val = str(old_row[key])
            if entry["type"] == "toggle":
                old_val = "true" if old_row[key] else "false"
            value = old_val

        options_str = json.dumps(entry["options"]) if entry.get("options") else None
        conn.execute(
            sa.text(
                "INSERT INTO scanner_config_entry (key, value, default_value, type, label, group_path, min, max, step, options, sort_order) "
                "VALUES (:key, :value, :default_value, :type, :label, :group_path, :min, :max, :step, :options, :sort_order)"
            ),
            {
                "key": key,
                "value": value,
                "default_value": default_val,
                "type": entry["type"],
                "label": entry["label"],
                "group_path": entry.get("group_path"),
                "min": entry.get("min"),
                "max": entry.get("max"),
                "step": entry.get("step"),
                "options": options_str,
                "sort_order": entry.get("sort_order", 0),
            },
        )

    # 3. Drop old table
    op.drop_table("scanner_config")

    # 4. Clear scan-specific overrides
    conn.execute(sa.text("UPDATE sheet_music_scans SET adjustments_json = NULL"))


def downgrade() -> None:
    # Downgrade not supported for this migration
    raise NotImplementedError("Downgrade not supported — old scanner_config schema is gone")
```

- [ ] **Step 3: Delete old model and schema files**

```bash
rm src/backend/mv_hofki/models/scanner_config.py
rm src/backend/mv_hofki/schemas/scanner_config.py
```

- [ ] **Step 4: Run the migration**

Run: `PYTHONPATH=src/backend alembic upgrade head`
Expected: Migration applies successfully

- [ ] **Step 5: Run all backend tests**

Run: `python -m pytest tests/backend/test_scanner_config.py tests/backend/test_config_merge.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: migrate scanner_config to row-based scanner_config_entry table"
```

---

### Task 6: Update sheet_music_scan service import

**Files:**
- Modify: `src/backend/mv_hofki/services/sheet_music_scan.py:184`

- [ ] **Step 1: Verify the import already works**

The import at line 184 is:
```python
from mv_hofki.services.scanner_config import get_effective_config
```

This function still exists with the same name and signature in the rewritten `scanner_config.py`. No change needed.

- [ ] **Step 2: Run config_merge tests to confirm nothing broke**

Run: `python -m pytest tests/backend/test_config_merge.py -v`
Expected: PASS (6 tests)

- [ ] **Step 3: Run full backend test suite**

Run: `python -m pytest tests/backend/ -v`
Expected: PASS (no regressions)

- [ ] **Step 4: Commit (only if any changes were needed)**

If no changes needed, skip this step.

---

### Task 7: Frontend — ScannerConfigPage.vue (dynamic from API)

**Files:**
- Modify: `src/frontend/src/pages/ScannerConfigPage.vue` (full rewrite)
- Delete: `src/frontend/src/lib/scanner-config.js`

- [ ] **Step 1: Delete scanner-config.js**

```bash
rm src/frontend/src/lib/scanner-config.js
```

- [ ] **Step 2: Rewrite ScannerConfigPage.vue**

Replace the entire content of `src/frontend/src/pages/ScannerConfigPage.vue`:

```vue
<script setup>
import { ref, computed, onMounted } from "vue";
import { get, put, post } from "../lib/api.js";

const entries = ref([]);
const loading = ref(true);
const saving = ref(false);
const error = ref(null);
const successMsg = ref(null);
const collapsedGroups = ref(new Set());

// Build nested group tree from flat entries
const groupTree = computed(() => {
  // Collect entries by group_path
  const byGroup = new Map();
  for (const entry of entries.value) {
    const path = entry.group_path || "";
    if (!byGroup.has(path)) byGroup.set(path, []);
    byGroup.get(path).push(entry);
  }

  // Sort entries within each group by sort_order
  for (const list of byGroup.values()) {
    list.sort((a, b) => a.sort_order - b.sort_order);
  }

  // Build tree: split group_path on "\"
  const roots = [];
  const nodeMap = new Map();

  // Collect all unique group paths (including parent segments)
  const allPaths = new Set();
  for (const path of byGroup.keys()) {
    if (!path) continue;
    const parts = path.split("\\");
    for (let i = 1; i <= parts.length; i++) {
      allPaths.add(parts.slice(0, i).join("\\"));
    }
  }

  // Sort paths alphabetically
  const sortedPaths = [...allPaths].sort((a, b) => a.localeCompare(b, "de"));

  // Create nodes
  for (const path of sortedPaths) {
    const parts = path.split("\\");
    const label = parts[parts.length - 1];
    const node = { path, label, children: [], entries: byGroup.get(path) || [] };
    nodeMap.set(path, node);

    if (parts.length === 1) {
      roots.push(node);
    } else {
      const parentPath = parts.slice(0, -1).join("\\");
      const parent = nodeMap.get(parentPath);
      if (parent) parent.children.push(parent.children, node);
    }
  }

  // Fix: push to parent.children properly
  for (const path of sortedPaths) {
    const parts = path.split("\\");
    if (parts.length > 1) {
      const parentPath = parts.slice(0, -1).join("\\");
      const parent = nodeMap.get(parentPath);
      const node = nodeMap.get(path);
      if (parent && !parent.children.includes(node)) {
        parent.children.push(node);
      }
    }
  }
  // Remove duplicates from incorrect push above
  for (const node of nodeMap.values()) {
    node.children = [...new Set(node.children.filter(c => c && c.path))];
    node.children.sort((a, b) => a.label.localeCompare(b.label, "de"));
  }

  // Root-level entries (no group)
  const rootEntries = byGroup.get("") || [];

  return { roots, rootEntries };
});

onMounted(async () => {
  await loadConfig();
  // Collapse all groups by default
  for (const node of groupTree.value.roots) {
    collapsedGroups.value.add(node.path);
    for (const child of node.children) {
      collapsedGroups.value.add(child.path);
    }
  }
});

async function loadConfig() {
  loading.value = true;
  error.value = null;
  try {
    const data = await get("/scanner/config");
    entries.value = data.entries;
  } catch (e) {
    error.value = e.message;
  } finally {
    loading.value = false;
  }
}

async function saveConfig() {
  saving.value = true;
  error.value = null;
  successMsg.value = null;
  try {
    const values = {};
    for (const entry of entries.value) {
      values[entry.key] = entry.value;
    }
    const data = await put("/scanner/config", { values });
    entries.value = data.entries;
    successMsg.value = "Konfiguration gespeichert";
    setTimeout(() => { successMsg.value = null; }, 3000);
  } catch (e) {
    error.value = e.message;
  } finally {
    saving.value = false;
  }
}

async function resetSingle(key) {
  error.value = null;
  try {
    const data = await post("/scanner/config/reset", { keys: [key] });
    entries.value = data.entries;
  } catch (e) {
    error.value = e.message;
  }
}

function toggleGroup(path) {
  if (collapsedGroups.value.has(path)) {
    collapsedGroups.value.delete(path);
  } else {
    collapsedGroups.value.add(path);
  }
}

function getEntry(key) {
  return entries.value.find((e) => e.key === key);
}

function updateValue(key, val) {
  const entry = getEntry(key);
  if (entry) entry.value = val;
}
</script>

<template>
  <div>
    <div class="page-header">
      <h1>Scanner-Konfiguration</h1>
      <button class="btn btn-primary" :disabled="saving || loading" @click="saveConfig">
        {{ saving ? "Speichert..." : "Speichern" }}
      </button>
    </div>

    <div v-if="error" class="msg msg-error">{{ error }}</div>
    <div v-if="successMsg" class="msg msg-success">{{ successMsg }}</div>

    <div v-if="loading" style="text-align: center; padding: 2rem; color: var(--color-muted)">
      Laden...
    </div>

    <div v-else class="config-grid">
      <!-- Root-level entries (no group) -->
      <div v-if="groupTree.rootEntries.length" class="card config-card">
        <div class="card-fields">
          <div v-for="entry in groupTree.rootEntries" :key="entry.key" class="field-row">
            <ConfigField :entry="entry" @update="updateValue" @reset="resetSingle" />
          </div>
        </div>
      </div>

      <!-- Grouped entries -->
      <template v-for="node in groupTree.roots" :key="node.path">
        <div class="card config-card">
          <h2 class="card-title" @click="toggleGroup(node.path)">
            <span class="group-chevron">{{ collapsedGroups.has(node.path) ? "\u25B8" : "\u25BE" }}</span>
            {{ node.label }}
          </h2>
          <div v-show="!collapsedGroups.has(node.path)">
            <!-- Direct entries of this group -->
            <div class="card-fields">
              <div v-for="entry in node.entries" :key="entry.key" class="field-row">
                <ConfigField :entry="entry" @update="updateValue" @reset="resetSingle" />
              </div>
            </div>
            <!-- Subgroups -->
            <div v-for="child in node.children" :key="child.path" class="subgroup">
              <h3 class="subgroup-title" @click="toggleGroup(child.path)">
                <span class="group-chevron">{{ collapsedGroups.has(child.path) ? "\u25B8" : "\u25BE" }}</span>
                {{ child.label }}
              </h3>
              <div v-show="!collapsedGroups.has(child.path)" class="card-fields">
                <div v-for="entry in child.entries" :key="entry.key" class="field-row">
                  <ConfigField :entry="entry" @update="updateValue" @reset="resetSingle" />
                </div>
              </div>
            </div>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script>
// Inline ConfigField as a render component to avoid a new file
const ConfigField = {
  props: {
    entry: { type: Object, required: true },
  },
  emits: ["update", "reset"],
  template: `
    <div class="config-field-wrapper" :class="{ 'is-modified': entry.is_modified }">
      <!-- Toggle -->
      <template v-if="entry.type === 'toggle'">
        <label class="toggle-row">
          <input
            type="checkbox"
            class="toggle-checkbox"
            :checked="entry.value"
            @change="$emit('update', entry.key, $event.target.checked)"
          />
          <span>{{ entry.label }}</span>
          <span v-if="entry.is_modified" class="modified-dot" title="Geändert"></span>
          <button v-if="entry.is_modified" class="reset-btn" title="Zurücksetzen" @click.prevent="$emit('reset', entry.key)">↺</button>
        </label>
      </template>

      <!-- Select -->
      <template v-else-if="entry.type === 'select'">
        <label class="select-row">
          <span class="field-name">
            {{ entry.label }}
            <span v-if="entry.is_modified" class="modified-dot" title="Geändert"></span>
            <button v-if="entry.is_modified" class="reset-btn" title="Zurücksetzen" @click.prevent="$emit('reset', entry.key)">↺</button>
          </span>
          <select :value="entry.value" @change="$emit('update', entry.key, $event.target.value)">
            <option v-for="opt in entry.options" :key="opt.value" :value="opt.value">
              {{ opt.label }}
            </option>
          </select>
          <span v-if="entry.is_modified" class="default-hint">Standard: {{ entry.options?.find(o => o.value === entry.default_value)?.label || entry.default_value }}</span>
        </label>
      </template>

      <!-- Number -->
      <template v-else-if="entry.type === 'number'">
        <label class="number-row">
          <span class="field-name">
            {{ entry.label }}
            <span class="field-value-group">
              <strong>{{ entry.value }}</strong>
              <span v-if="entry.is_modified" class="default-hint">(Std: {{ entry.default_value }})</span>
              <span v-if="entry.is_modified" class="modified-dot" title="Geändert"></span>
              <button v-if="entry.is_modified" class="reset-btn" title="Zurücksetzen" @click.prevent="$emit('reset', entry.key)">↺</button>
            </span>
          </span>
          <input
            type="range"
            :value="entry.value"
            :min="entry.min"
            :max="entry.max"
            :step="entry.step"
            @input="$emit('update', entry.key, Number($event.target.value))"
          />
        </label>
      </template>
    </div>
  `,
};

export default {
  components: { ConfigField },
};
</script>

<style scoped>
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1.5rem;
}

.msg {
  padding: 0.5rem 0.75rem;
  border-radius: var(--radius);
  font-size: 0.85rem;
  margin-bottom: 1rem;
}

.msg-error {
  color: var(--color-danger);
  background: rgba(220, 38, 38, 0.08);
}

.msg-success {
  color: #16a34a;
  background: rgba(22, 163, 74, 0.08);
}

.config-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 1rem;
}

.config-card {
  padding: 1.25rem;
}

.card-title {
  font-size: 0.95rem;
  font-weight: 600;
  margin-bottom: 1rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid var(--color-border);
  cursor: pointer;
  user-select: none;
  display: flex;
  align-items: center;
  gap: 0.3rem;
}

.card-title:hover {
  color: var(--color-primary);
}

.group-chevron {
  font-size: 0.7rem;
  width: 0.8rem;
  text-align: center;
}

.subgroup {
  margin-top: 0.75rem;
  margin-left: 0.75rem;
  padding-left: 0.75rem;
  border-left: 2px solid var(--color-border);
}

.subgroup-title {
  font-size: 0.8rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--color-muted);
  margin-bottom: 0.5rem;
  cursor: pointer;
  user-select: none;
  display: flex;
  align-items: center;
  gap: 0.3rem;
}

.subgroup-title:hover {
  color: var(--color-text);
}

.card-fields {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.field-row {
  padding: 0.1rem 0;
}

.config-field-wrapper.is-modified {
  border-left: 2px solid var(--color-primary);
  padding-left: 0.5rem;
}

.toggle-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
  font-size: 0.9rem;
}

.toggle-checkbox {
  width: 1.1rem;
  height: 1.1rem;
  accent-color: var(--color-primary);
  cursor: pointer;
}

.select-row {
  display: block;
  font-size: 0.85rem;
  color: var(--color-muted);
}

.select-row select {
  display: block;
  width: 100%;
  margin-top: 0.25rem;
  padding: 0.4rem 0.5rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  background: var(--color-bg);
  color: var(--color-text);
  font-family: inherit;
  font-size: 0.85rem;
}

.number-row {
  display: block;
  font-size: 0.85rem;
  color: var(--color-muted);
}

.field-name {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 0.25rem;
}

.field-name strong {
  color: var(--color-text);
}

.field-value-group {
  display: flex;
  align-items: baseline;
  gap: 0.35rem;
}

.number-row input[type="range"] {
  width: 100%;
  margin-top: 0.2rem;
  accent-color: var(--color-primary);
}

.modified-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-primary);
  flex-shrink: 0;
}

.default-hint {
  font-size: 0.75rem;
  color: var(--color-muted);
  font-weight: normal;
}

.reset-btn {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 0.85rem;
  color: var(--color-muted);
  padding: 0 0.15rem;
  line-height: 1;
}

.reset-btn:hover {
  color: var(--color-primary);
}
</style>
```

- [ ] **Step 3: Verify frontend builds**

Run: `frontend-logs` (check for build errors in the vite watcher)

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat: rewrite ScannerConfigPage to dynamic API-driven config UI"
```

---

### Task 8: Frontend — ScannerConfigModal.vue (dynamic from API)

**Files:**
- Modify: `src/frontend/src/components/ScannerConfigModal.vue` (full rewrite)

- [ ] **Step 1: Rewrite ScannerConfigModal.vue**

Replace the entire content of `src/frontend/src/components/ScannerConfigModal.vue`:

```vue
<script setup>
import { ref, watch } from "vue";
import { get, put, post } from "../lib/api.js";

const props = defineProps({
  open: { type: Boolean, default: false },
  scanId: { type: [Number, String], default: null },
  projectId: { type: [Number, String], default: null },
  adjustments: { type: Object, default: () => ({}) },
});

const emit = defineEmits(["close", "update-adjustments"]);

const entries = ref([]);
const loading = ref(false);
const saving = ref(false);
const error = ref(null);
const successMsg = ref(null);
const scanSpecific = ref(false);
const collapsedGroups = ref(new Set());

watch(
  () => props.open,
  async (isOpen) => {
    if (!isOpen) return;
    successMsg.value = null;
    error.value = null;

    const analysis = props.adjustments?.analysis;
    scanSpecific.value = analysis?.enabled === true;

    await loadGlobalConfig();

    // If scan has specific values, overlay them onto the loaded global config
    if (analysis && analysis.enabled) {
      for (const entry of entries.value) {
        if (entry.key in analysis) {
          entry.value = analysis[entry.key];
          entry.is_modified = true;
        }
      }
    }
  },
);

watch(scanSpecific, (isScanSpecific) => {
  if (!isScanSpecific) {
    loadGlobalConfig();
  }
});

async function loadGlobalConfig() {
  loading.value = true;
  error.value = null;
  try {
    const data = await get("/scanner/config");
    entries.value = data.entries;
    // Collapse all groups by default
    collapsedGroups.value = new Set(
      entries.value.map((e) => e.group_path).filter(Boolean)
    );
    // Also collapse parent paths
    for (const e of entries.value) {
      if (e.group_path && e.group_path.includes("\\")) {
        const parts = e.group_path.split("\\");
        for (let i = 1; i < parts.length; i++) {
          collapsedGroups.value.add(parts.slice(0, i).join("\\"));
        }
      }
    }
  } catch (e) {
    error.value = e.message;
  } finally {
    loading.value = false;
  }
}

// Build nested group structure
function getGroupTree() {
  const byGroup = new Map();
  for (const entry of entries.value) {
    const path = entry.group_path || "";
    if (!byGroup.has(path)) byGroup.set(path, []);
    byGroup.get(path).push(entry);
  }
  for (const list of byGroup.values()) {
    list.sort((a, b) => a.sort_order - b.sort_order);
  }

  const roots = [];
  const nodeMap = new Map();
  const allPaths = new Set();
  for (const path of byGroup.keys()) {
    if (!path) continue;
    const parts = path.split("\\");
    for (let i = 1; i <= parts.length; i++) {
      allPaths.add(parts.slice(0, i).join("\\"));
    }
  }
  const sortedPaths = [...allPaths].sort((a, b) => a.localeCompare(b, "de"));
  for (const path of sortedPaths) {
    const parts = path.split("\\");
    const label = parts[parts.length - 1];
    nodeMap.set(path, { path, label, children: [], entries: byGroup.get(path) || [] });
  }
  for (const path of sortedPaths) {
    const parts = path.split("\\");
    const node = nodeMap.get(path);
    if (parts.length === 1) {
      roots.push(node);
    } else {
      const parentPath = parts.slice(0, -1).join("\\");
      const parent = nodeMap.get(parentPath);
      if (parent && !parent.children.includes(node)) {
        parent.children.push(node);
      }
    }
  }
  for (const node of nodeMap.values()) {
    node.children.sort((a, b) => a.label.localeCompare(b.label, "de"));
  }
  return { roots, rootEntries: byGroup.get("") || [] };
}

async function saveGlobal() {
  saving.value = true;
  error.value = null;
  successMsg.value = null;
  try {
    const values = {};
    for (const entry of entries.value) {
      values[entry.key] = entry.value;
    }
    const data = await put("/scanner/config", { values });
    entries.value = data.entries;
    successMsg.value = "Global gespeichert";
    setTimeout(() => { successMsg.value = null; }, 2000);
  } catch (e) {
    error.value = e.message;
  } finally {
    saving.value = false;
  }
}

async function saveScanSpecific() {
  saving.value = true;
  error.value = null;
  successMsg.value = null;
  try {
    const analysis = { enabled: true };
    for (const entry of entries.value) {
      analysis[entry.key] = entry.value;
    }
    const updated = { ...props.adjustments, analysis };
    // Find the part that contains this scan
    const partsData = await get(`/scanner/projects/${props.projectId}/parts`);
    for (const part of partsData) {
      const scansData = await get(`/scanner/projects/${props.projectId}/parts/${part.id}/scans`);
      const found = scansData.find((s) => String(s.id) === String(props.scanId));
      if (found) {
        await put(`/scanner/projects/${props.projectId}/parts/${part.id}/scans/${props.scanId}`, {
          adjustments_json: JSON.stringify(updated),
        });
        break;
      }
    }
    emit("update-adjustments", updated);
    successMsg.value = "Für diesen Scan gespeichert";
    setTimeout(() => { successMsg.value = null; }, 2000);
  } catch (e) {
    error.value = e.message;
  } finally {
    saving.value = false;
  }
}

async function resetDefaults() {
  await loadGlobalConfig();
}

function toggleGroup(path) {
  if (collapsedGroups.value.has(path)) {
    collapsedGroups.value.delete(path);
  } else {
    collapsedGroups.value.add(path);
  }
}

function updateValue(key, val) {
  const entry = entries.value.find((e) => e.key === key);
  if (entry) entry.value = val;
}

async function resetSingle(key) {
  error.value = null;
  try {
    const data = await post("/scanner/config/reset", { keys: [key] });
    entries.value = data.entries;
  } catch (e) {
    error.value = e.message;
  }
}
</script>

<template>
  <div v-if="open" class="modal-backdrop" @click.self="emit('close')">
    <div class="modal modal-config">
      <div class="modal-header">
        <h2>Scanner-Konfiguration</h2>
        <button class="close-btn" title="Schließen" @click="emit('close')">&#10005;</button>
      </div>

      <div v-if="loading" class="modal-loading">Laden...</div>

      <div v-else class="modal-body">
        <div v-if="error" class="config-error">{{ error }}</div>
        <div v-if="successMsg" class="config-success">{{ successMsg }}</div>

        <!-- Scan-specific toggle -->
        <div v-if="scanId" class="scan-toggle">
          <label class="toggle-label">
            <input v-model="scanSpecific" type="checkbox" class="toggle-input" />
            <span class="toggle-text">Scan-spezifische Parameter verwenden</span>
          </label>
        </div>

        <template v-for="node in getGroupTree().roots" :key="node.path">
          <div class="config-group">
            <h3 class="group-title" @click="toggleGroup(node.path)">
              <span class="group-chevron">{{ collapsedGroups.has(node.path) ? "\u25B8" : "\u25BE" }}</span>
              {{ node.label }}
            </h3>
            <div v-show="!collapsedGroups.has(node.path)" class="group-fields">
              <div v-for="entry in node.entries" :key="entry.key" class="config-field">
                <ModalField :entry="entry" @update="updateValue" @reset="resetSingle" />
              </div>
              <!-- Subgroups -->
              <div v-for="child in node.children" :key="child.path" class="subgroup">
                <h4 class="subgroup-title" @click="toggleGroup(child.path)">
                  <span class="group-chevron">{{ collapsedGroups.has(child.path) ? "\u25B8" : "\u25BE" }}</span>
                  {{ child.label }}
                </h4>
                <div v-show="!collapsedGroups.has(child.path)" class="group-fields">
                  <div v-for="entry in child.entries" :key="entry.key" class="config-field">
                    <ModalField :entry="entry" @update="updateValue" @reset="resetSingle" />
                  </div>
                </div>
              </div>
            </div>
          </div>
        </template>
      </div>

      <div class="modal-footer">
        <button class="btn" :disabled="loading" @click="resetDefaults">Zurücksetzen</button>
        <div class="footer-spacer"></div>
        <template v-if="scanSpecific && scanId">
          <button class="btn btn-primary" :disabled="loading || saving" @click="saveScanSpecific">
            {{ saving ? "Speichert..." : "Für diesen Scan speichern" }}
          </button>
        </template>
        <template v-else>
          <button class="btn btn-primary" :disabled="loading || saving" @click="saveGlobal">
            {{ saving ? "Speichert..." : "Global speichern" }}
          </button>
        </template>
      </div>
    </div>
  </div>
</template>

<script>
const ModalField = {
  props: {
    entry: { type: Object, required: true },
  },
  emits: ["update", "reset"],
  template: `
    <div :class="{ 'field-modified': entry.is_modified }">
      <!-- Toggle -->
      <template v-if="entry.type === 'toggle'">
        <label class="toggle-label">
          <input type="checkbox" class="toggle-input" :checked="entry.value" @change="$emit('update', entry.key, $event.target.checked)" />
          <span class="toggle-text">{{ entry.label }}</span>
          <span v-if="entry.is_modified" class="modified-dot"></span>
          <button v-if="entry.is_modified" class="reset-btn" title="Zurücksetzen" @click.prevent="$emit('reset', entry.key)">\u21BA</button>
        </label>
      </template>

      <!-- Select -->
      <template v-else-if="entry.type === 'select'">
        <label class="field-label">
          <span class="field-label-row">
            {{ entry.label }}
            <span v-if="entry.is_modified" class="modified-dot"></span>
            <button v-if="entry.is_modified" class="reset-btn" title="Zurücksetzen" @click.prevent="$emit('reset', entry.key)">\u21BA</button>
          </span>
          <select class="field-select" :value="entry.value" @change="$emit('update', entry.key, $event.target.value)">
            <option v-for="opt in entry.options" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
          </select>
          <span v-if="entry.is_modified" class="default-hint">Standard: {{ entry.options?.find(o => o.value === entry.default_value)?.label || entry.default_value }}</span>
        </label>
      </template>

      <!-- Number -->
      <template v-else-if="entry.type === 'number'">
        <label class="field-label">
          <span class="field-label-row">
            {{ entry.label }}
            <span class="field-value-group">
              <span class="field-value">{{ entry.value }}</span>
              <span v-if="entry.is_modified" class="default-hint">(Std: {{ entry.default_value }})</span>
              <span v-if="entry.is_modified" class="modified-dot"></span>
              <button v-if="entry.is_modified" class="reset-btn" title="Zurücksetzen" @click.prevent="$emit('reset', entry.key)">\u21BA</button>
            </span>
          </span>
          <input type="range" class="field-slider" :value="entry.value" :min="entry.min" :max="entry.max" :step="entry.step" @input="$emit('update', entry.key, Number($event.target.value))" />
        </label>
      </template>
    </div>
  `,
};

export default {
  components: { ModalField },
};
</script>

<style scoped>
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: var(--color-overlay);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 550;
}

.modal-config {
  background: var(--color-bg);
  border-radius: var(--radius);
  width: 100%;
  max-width: 520px;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1.25rem 1.5rem 0.75rem;
  border-bottom: 1px solid var(--color-border);
}

.modal-header h2 { margin: 0; font-size: 1.1rem; }

.close-btn {
  background: none; border: none; font-size: 1.2rem; cursor: pointer;
  color: var(--color-muted); padding: 0.25rem; line-height: 1;
}
.close-btn:hover { color: var(--color-text); }

.modal-loading { padding: 2rem; text-align: center; color: var(--color-muted); }

.modal-body { padding: 1rem 1.5rem; overflow-y: auto; flex: 1; }

.config-error {
  color: var(--color-danger); font-size: 0.85rem; margin-bottom: 0.75rem;
  padding: 0.5rem; background: rgba(220, 38, 38, 0.08); border-radius: var(--radius);
}

.config-success {
  color: #16a34a; font-size: 0.85rem; margin-bottom: 0.75rem;
  padding: 0.5rem; background: rgba(22, 163, 74, 0.08); border-radius: var(--radius);
}

.scan-toggle {
  margin-bottom: 1rem; padding: 0.75rem; background: var(--color-bg-soft);
  border-radius: var(--radius); border: 1px solid var(--color-border);
}

.config-group { margin-bottom: 1.25rem; }

.group-title {
  font-size: 0.8rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em;
  color: var(--color-muted); margin-bottom: 0.5rem; padding-bottom: 0.25rem;
  border-bottom: 1px solid var(--color-border); cursor: pointer; user-select: none;
  display: flex; align-items: center; gap: 0.3rem;
}
.group-title:hover { color: var(--color-text); }

.group-chevron { font-size: 0.7rem; width: 0.8rem; text-align: center; }

.subgroup {
  margin-top: 0.5rem; margin-left: 0.75rem; padding-left: 0.75rem;
  border-left: 2px solid var(--color-border);
}

.subgroup-title {
  font-size: 0.75rem; font-weight: 600; color: var(--color-muted); margin-bottom: 0.4rem;
  cursor: pointer; user-select: none; display: flex; align-items: center; gap: 0.3rem;
}
.subgroup-title:hover { color: var(--color-text); }

.group-fields { display: flex; flex-direction: column; gap: 0.5rem; }

.config-field { padding: 0.25rem 0; }

.field-modified { border-left: 2px solid var(--color-primary); padding-left: 0.5rem; }

.toggle-label {
  display: flex; align-items: center; gap: 0.5rem; cursor: pointer; font-size: 0.9rem;
}
.toggle-input { width: 1.1rem; height: 1.1rem; accent-color: var(--color-primary); cursor: pointer; }
.toggle-text { color: var(--color-text); }

.field-label { display: block; font-size: 0.85rem; color: var(--color-muted); }

.field-label-row { display: flex; justify-content: space-between; align-items: baseline; flex-wrap: wrap; gap: 0.25rem; }

.field-value { font-weight: 600; color: var(--color-text); font-size: 0.85rem; }

.field-value-group { display: flex; align-items: baseline; gap: 0.35rem; }

.field-select {
  display: block; width: 100%; margin-top: 0.2rem; padding: 0.4rem 0.5rem;
  border: 1px solid var(--color-border); border-radius: var(--radius);
  background: var(--color-bg); color: var(--color-text); font-family: inherit; font-size: 0.85rem;
}

.field-slider { width: 100%; margin-top: 0.2rem; accent-color: var(--color-primary); }

.modified-dot {
  display: inline-block; width: 6px; height: 6px; border-radius: 50%;
  background: var(--color-primary); flex-shrink: 0;
}

.default-hint { font-size: 0.75rem; color: var(--color-muted); font-weight: normal; }

.reset-btn {
  background: none; border: none; cursor: pointer; font-size: 0.85rem;
  color: var(--color-muted); padding: 0 0.15rem; line-height: 1;
}
.reset-btn:hover { color: var(--color-primary); }

.modal-footer {
  display: flex; align-items: center; gap: 0.5rem;
  padding: 0.75rem 1.5rem; border-top: 1px solid var(--color-border);
}
.footer-spacer { flex: 1; }
</style>
```

- [ ] **Step 2: Verify frontend builds**

Run: `frontend-logs` (check for build errors)

- [ ] **Step 3: Commit**

```bash
git add src/frontend/src/components/ScannerConfigModal.vue
git commit -m "feat: rewrite ScannerConfigModal to dynamic API-driven config UI"
```

---

### Task 9: Cleanup + Final Verification

**Files:**
- Verify: all imports, no references to old files

- [ ] **Step 1: Check for stale imports of old model/schema**

Run: `grep -r "scanner_config import ScannerConfig" src/backend/ --include="*.py"`
Run: `grep -r "from.*schemas.scanner_config import" src/backend/ --include="*.py"`
Run: `grep -r "scanner-config.js" src/frontend/ --include="*.vue" --include="*.js"`

Expected: No results. If any found, fix the imports.

- [ ] **Step 2: Run full backend test suite**

Run: `python -m pytest tests/backend/ -v`
Expected: All PASS

- [ ] **Step 3: Run frontend tests**

Run: `cd src/frontend && npx vitest run`
Expected: PASS (or no scanner-config-related failures)

- [ ] **Step 4: Run pre-commit**

Run: `pre-commit run --all-files`
Expected: PASS

- [ ] **Step 5: Manual smoke test**

1. Open the app in browser
2. Navigate to Scanner-Konfiguration page — should show all entries grouped with collapsible sections
3. Change a value → modified indicator appears, default shown, reset button visible
4. Click reset button → value returns to default
5. Save → success message
6. Open a scan → Config modal → should load entries dynamically
7. Toggle scan-specific → save → adjustments_json updated

- [ ] **Step 6: Final commit (if any fixes needed)**

```bash
git add -A
git commit -m "chore: cleanup stale imports and finalize scanner config refactoring"
```
