# Scanner Config & Template Matching Improvements

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the scanner pipeline fully configurable with persistent global settings, optional per-request overrides, and implement five new template matching features (edge-based matching, multi-scale search, staff removal before matching, masked matching, dilate-based NMS).

**Architecture:** A single-row `scanner_config` DB table stores global pipeline settings as typed columns. The process endpoint accepts an optional JSON body with the same schema — if provided, those values override the globals for that run only. A separate save endpoint persists overrides as the new globals. Each new matching feature is implemented as a togglable code path inside the existing `TemplateMatchingStage`, controlled by config flags read from `PipelineContext.config`.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async, Alembic, OpenCV (cv2), Pydantic v2, pytest

---

## File Structure

### New files

| File | Responsibility |
|------|---------------|
| `src/backend/mv_hofki/models/scanner_config.py` | ORM model — single-row table with all pipeline parameter columns |
| `src/backend/mv_hofki/schemas/scanner_config.py` | Pydantic schemas: `ScannerConfigRead`, `ScannerConfigUpdate` (all fields optional) |
| `src/backend/mv_hofki/services/scanner_config.py` | Service: `get_config()`, `update_config()`, `get_effective_config(overrides)` |
| `src/backend/mv_hofki/api/routes/scanner_config.py` | API: `GET /api/v1/scanner/config`, `PUT /api/v1/scanner/config` |
| `alembic/versions/xxxx_add_scanner_config.py` | Migration for the new table |
| `tests/backend/test_scanner_config.py` | Tests for config model, service, and API |
| `tests/backend/test_template_matching_features.py` | Tests for all five new matching features |

### Modified files

| File | Changes |
|------|---------|
| `src/backend/mv_hofki/models/__init__.py` | Add `ScannerConfig` import |
| `src/backend/mv_hofki/api/app.py` | Register `scanner_config_router` |
| `src/backend/mv_hofki/api/routes/scan_processing.py` | Accept optional `ScannerConfigUpdate` body on process endpoint |
| `src/backend/mv_hofki/services/sheet_music_scan.py` | Load global config, merge overrides, pass to pipeline stages |
| `src/backend/mv_hofki/services/scanner/stages/template_matching.py` | Add edge matching, multi-scale, masked matching, dilate NMS, read all params from config |
| `src/backend/mv_hofki/services/scanner/stages/preprocess.py` | Read `adaptive_threshold_block_size`, `adaptive_threshold_c`, `morphology_kernel_size` from config |
| `src/backend/mv_hofki/db/seed.py` | Seed default scanner config row on startup |

---

## Task 1: Scanner Config Model & Migration

**Files:**
- Create: `src/backend/mv_hofki/models/scanner_config.py`
- Modify: `src/backend/mv_hofki/models/__init__.py`
- Test: `tests/backend/test_scanner_config.py`

- [ ] **Step 1: Write the failing test — config model can be created**

Create `tests/backend/test_scanner_config.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/backend/test_scanner_config.py::test_scanner_config_defaults -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'mv_hofki.models.scanner_config'`

- [ ] **Step 3: Create the ORM model**

Create `src/backend/mv_hofki/models/scanner_config.py`:

```python
"""ScannerConfig ORM model — single-row global pipeline settings."""

from __future__ import annotations

from sqlalchemy import Boolean, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from mv_hofki.db.base import Base


class ScannerConfig(Base):
    __tablename__ = "scanner_config"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Template matching
    confidence_threshold: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.6
    )
    matching_method: Mapped[str] = mapped_column(
        String(30), nullable=False, default="TM_CCOEFF_NORMED"
    )

    # Multi-scale search
    multi_scale_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    multi_scale_range: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.05
    )
    multi_scale_steps: Mapped[int] = mapped_column(
        Integer, nullable=False, default=3
    )

    # Edge-based matching
    edge_matching_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    canny_low: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    canny_high: Mapped[int] = mapped_column(Integer, nullable=False, default=150)

    # Staff removal before matching
    staff_removal_before_matching: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    # Masked template matching
    masked_matching_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    mask_threshold: Mapped[int] = mapped_column(
        Integer, nullable=False, default=200
    )

    # NMS settings
    nms_iou_threshold: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.3
    )
    nms_method: Mapped[str] = mapped_column(
        String(20), nullable=False, default="standard"
    )

    # Preprocessing
    adaptive_threshold_block_size: Mapped[int] = mapped_column(
        Integer, nullable=False, default=15
    )
    adaptive_threshold_c: Mapped[int] = mapped_column(
        Integer, nullable=False, default=10
    )
    morphology_kernel_size: Mapped[int] = mapped_column(
        Integer, nullable=False, default=2
    )

    # Auto-verify
    auto_verify_confidence: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.85
    )
```

- [ ] **Step 4: Register model in `__init__.py`**

Add to `src/backend/mv_hofki/models/__init__.py`:

```python
from mv_hofki.models.scanner_config import ScannerConfig
```

And add `"ScannerConfig"` to the `__all__` list.

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/backend/test_scanner_config.py::test_scanner_config_defaults -v`
Expected: PASS

- [ ] **Step 6: Create alembic migration**

Run: `cd /workspaces/mv_hofki && PYTHONPATH=src/backend alembic revision --autogenerate -m "add scanner_config table"`

Then run: `PYTHONPATH=src/backend alembic upgrade head`

- [ ] **Step 7: Commit**

```bash
git add src/backend/mv_hofki/models/scanner_config.py src/backend/mv_hofki/models/__init__.py tests/backend/test_scanner_config.py alembic/versions/*scanner_config*
git commit -m "feat(scanner): add ScannerConfig model for global pipeline settings"
```

---

## Task 2: Scanner Config Schema & Service

**Files:**
- Create: `src/backend/mv_hofki/schemas/scanner_config.py`
- Create: `src/backend/mv_hofki/services/scanner_config.py`
- Test: `tests/backend/test_scanner_config.py` (append)

- [ ] **Step 1: Write the failing test — service get_config returns defaults when no row exists**

Append to `tests/backend/test_scanner_config.py`:

```python
from mv_hofki.services.scanner_config import get_config, update_config


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/backend/test_scanner_config.py -k "get_config" -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'mv_hofki.services.scanner_config'`

- [ ] **Step 3: Create the Pydantic schemas**

Create `src/backend/mv_hofki/schemas/scanner_config.py`:

```python
"""ScannerConfig Pydantic schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ScannerConfigRead(BaseModel):
    """Full scanner config — returned by GET."""

    confidence_threshold: float
    matching_method: str
    multi_scale_enabled: bool
    multi_scale_range: float
    multi_scale_steps: int
    edge_matching_enabled: bool
    canny_low: int
    canny_high: int
    staff_removal_before_matching: bool
    masked_matching_enabled: bool
    mask_threshold: int
    nms_iou_threshold: float
    nms_method: str
    adaptive_threshold_block_size: int
    adaptive_threshold_c: int
    morphology_kernel_size: int
    auto_verify_confidence: float

    model_config = {"from_attributes": True}


class ScannerConfigUpdate(BaseModel):
    """Partial update — all fields optional. Used for both save and per-request override."""

    confidence_threshold: float | None = Field(None, ge=0.0, le=1.0)
    matching_method: str | None = Field(None, pattern="^TM_(CCOEFF|CCORR|SQDIFF)_NORMED$")
    multi_scale_enabled: bool | None = None
    multi_scale_range: float | None = Field(None, gt=0.0, le=0.5)
    multi_scale_steps: int | None = Field(None, ge=1, le=20)
    edge_matching_enabled: bool | None = None
    canny_low: int | None = Field(None, ge=0, le=500)
    canny_high: int | None = Field(None, ge=0, le=500)
    staff_removal_before_matching: bool | None = None
    masked_matching_enabled: bool | None = None
    mask_threshold: int | None = Field(None, ge=0, le=255)
    nms_iou_threshold: float | None = Field(None, ge=0.0, le=1.0)
    nms_method: str | None = Field(None, pattern="^(standard|dilate)$")
    adaptive_threshold_block_size: int | None = Field(None, ge=3, le=99)
    adaptive_threshold_c: int | None = Field(None, ge=0, le=50)
    morphology_kernel_size: int | None = Field(None, ge=1, le=10)
    auto_verify_confidence: float | None = Field(None, ge=0.0, le=1.0)
```

- [ ] **Step 4: Create the service**

Create `src/backend/mv_hofki/services/scanner_config.py`:

```python
"""Scanner config service — get/update global pipeline settings."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.models.scanner_config import ScannerConfig
from mv_hofki.schemas.scanner_config import ScannerConfigUpdate


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


async def get_effective_config(
    session: AsyncSession, overrides: ScannerConfigUpdate | None = None
) -> dict:
    """Return a merged config dict: global defaults + any per-request overrides.

    The returned dict is ready to be placed into PipelineContext.config.
    """
    config = await get_config(session)
    result = ScannerConfigUpdate.model_validate(config).model_dump()
    if overrides:
        for key, value in overrides.model_dump(exclude_unset=True).items():
            result[key] = value
    return result
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/backend/test_scanner_config.py -v`
Expected: ALL PASS

- [ ] **Step 6: Write the failing test — update_config persists changes**

Append to `tests/backend/test_scanner_config.py`:

```python
from mv_hofki.schemas.scanner_config import ScannerConfigUpdate


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
    from mv_hofki.services.scanner_config import get_effective_config

    effective = await get_effective_config(
        db_session,
        overrides=ScannerConfigUpdate(confidence_threshold=0.9),
    )
    assert effective["confidence_threshold"] == 0.9
    # Non-overridden values come from global
    assert effective["edge_matching_enabled"] is False
```

- [ ] **Step 7: Run all config tests**

Run: `python -m pytest tests/backend/test_scanner_config.py -v`
Expected: ALL PASS

- [ ] **Step 8: Commit**

```bash
git add src/backend/mv_hofki/schemas/scanner_config.py src/backend/mv_hofki/services/scanner_config.py tests/backend/test_scanner_config.py
git commit -m "feat(scanner): add scanner config schema and service with get/update/merge"
```

---

## Task 3: Scanner Config API Endpoints

**Files:**
- Create: `src/backend/mv_hofki/api/routes/scanner_config.py`
- Modify: `src/backend/mv_hofki/api/app.py`
- Test: `tests/backend/test_scanner_config.py` (append)

- [ ] **Step 1: Write the failing test — GET returns config**

Append to `tests/backend/test_scanner_config.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/backend/test_scanner_config.py -k "api" -v`
Expected: FAIL — 404 (route not registered)

- [ ] **Step 3: Create the API routes**

Create `src/backend/mv_hofki/api/routes/scanner_config.py`:

```python
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
```

- [ ] **Step 4: Register the router in `app.py`**

Add to `src/backend/mv_hofki/api/app.py` imports:

```python
from mv_hofki.api.routes.scanner_config import router as scanner_config_router
```

Add after the `symbol_library_router` include:

```python
app.include_router(scanner_config_router)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/backend/test_scanner_config.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add src/backend/mv_hofki/api/routes/scanner_config.py src/backend/mv_hofki/api/app.py tests/backend/test_scanner_config.py
git commit -m "feat(scanner): add GET/PUT /api/v1/scanner/config endpoints"
```

---

## Task 4: Seed Default Config & Wire into Pipeline

**Files:**
- Modify: `src/backend/mv_hofki/db/seed.py`
- Modify: `src/backend/mv_hofki/services/sheet_music_scan.py`
- Modify: `src/backend/mv_hofki/api/routes/scan_processing.py`

- [ ] **Step 1: Add config seeding to `seed.py`**

Read `src/backend/mv_hofki/db/seed.py` first to understand the pattern, then add at the end of the `seed_data` function:

```python
from mv_hofki.models.scanner_config import ScannerConfig

# Seed default scanner config if not present
result = await session.execute(select(ScannerConfig).limit(1))
if result.scalar_one_or_none() is None:
    session.add(ScannerConfig())
    await session.commit()
```

- [ ] **Step 2: Modify process endpoint to accept optional config overrides**

In `src/backend/mv_hofki/api/routes/scan_processing.py`, change the `trigger_processing` function signature to accept an optional body:

```python
from mv_hofki.schemas.scanner_config import ScannerConfigUpdate

@router.post("/scans/{scan_id}/process", response_model=ScanStatusRead)
async def trigger_processing(
    scan_id: int,
    config_overrides: ScannerConfigUpdate | None = None,
    project_id: int | None = None,
    part_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
```

Pass `config_overrides` through to `run_pipeline`:

```python
await scan_service.run_pipeline(
    db, actual_project_id, actual_part_id, scan_id, config_overrides=config_overrides
)
```

- [ ] **Step 3: Modify `run_pipeline` to load global config and merge overrides**

In `src/backend/mv_hofki/services/sheet_music_scan.py`, update `run_pipeline` signature and config loading:

```python
async def run_pipeline(
    session: AsyncSession,
    project_id: int,
    part_id: int,
    scan_id: int,
    config_overrides: ScannerConfigUpdate | None = None,
) -> None:
```

Replace the existing config loading block (lines ~177-180) with:

```python
    from mv_hofki.schemas.scanner_config import ScannerConfigUpdate
    from mv_hofki.services.scanner_config import get_effective_config

    # Load global scanner config, merge any per-request overrides
    config = await get_effective_config(session, overrides=config_overrides)

    # Merge scan-level adjustments (user threshold from UI)
    adjustments = json.loads(scan.adjustments_json) if scan.adjustments_json else {}
    if "threshold" in adjustments:
        config["threshold"] = adjustments["threshold"]
```

Update stage construction to pass config values:

```python
    stages = [
        PreprocessStage(),
        StaveDetectionStage(),
        TemplateMatchingStage(
            variant_images=variant_images,
            variant_template_ids=variant_template_ids,
            variant_heights=variant_heights,
            variant_line_spacings=variant_line_spacings,
        ),
    ]
```

The `TemplateMatchingStage` no longer takes `confidence_threshold` as a constructor arg — it reads everything from `ctx.config`. Update the auto-verify line (around line 256-257) to use the config value:

```python
user_verified=sym_data.confidence is not None
and sym_data.confidence >= config.get("auto_verify_confidence", 0.85),
```

- [ ] **Step 4: Run existing tests to verify nothing is broken**

Run: `python -m pytest tests/backend/test_template_matching.py tests/backend/test_pipeline_stages.py -v`
Expected: ALL PASS (existing tests still work)

- [ ] **Step 5: Commit**

```bash
git add src/backend/mv_hofki/db/seed.py src/backend/mv_hofki/services/sheet_music_scan.py src/backend/mv_hofki/api/routes/scan_processing.py
git commit -m "feat(scanner): wire global config into pipeline with per-request overrides"
```

---

## Task 5: Edge-Based Matching

**Files:**
- Modify: `src/backend/mv_hofki/services/scanner/stages/template_matching.py`
- Test: `tests/backend/test_template_matching_features.py`

- [ ] **Step 1: Write the failing test**

Create `tests/backend/test_template_matching_features.py`:

```python
"""Tests for new template matching features."""

import cv2
import numpy as np

from mv_hofki.services.scanner.stages.base import PipelineContext, StaffData
from mv_hofki.services.scanner.stages.template_matching import TemplateMatchingStage


def _make_staff(line_spacing=20):
    return StaffData(
        staff_index=0,
        y_top=10,
        y_bottom=10 + int(line_spacing * 8),
        line_positions=[10 + int(line_spacing * i) for i in range(5)],
        line_spacing=float(line_spacing),
    )


def _make_image_with_symbol(img_shape=(200, 400), symbol_pos=(100, 30)):
    """Create a white image with a filled circle symbol."""
    img = np.full(img_shape, 255, dtype=np.uint8)
    symbol = np.full((40, 20), 255, dtype=np.uint8)
    cv2.circle(symbol, (10, 20), 8, 0, -1)
    x, y = symbol_pos
    img[y : y + 40, x : x + 20] = symbol
    return img, symbol.copy()


def test_edge_matching_finds_symbol():
    """Edge-based matching should find the same symbol as standard matching."""
    img, template = _make_image_with_symbol()
    staff = _make_staff()

    stage = TemplateMatchingStage(
        variant_images=[template],
        variant_template_ids=[42],
        variant_heights=[2.0],
    )
    config = {"edge_matching_enabled": True, "canny_low": 50, "canny_high": 150}
    ctx = PipelineContext(image=img, staves=[staff], config=config)
    result = stage.process(ctx)

    assert len(result.symbols) > 0
    xs = [s.x for s in result.symbols]
    assert any(90 <= x <= 120 for x in xs), f"Expected match near x=100, got {xs}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/backend/test_template_matching_features.py::test_edge_matching_finds_symbol -v`
Expected: FAIL — the stage ignores `edge_matching_enabled` config

- [ ] **Step 3: Implement edge-based matching in `TemplateMatchingStage`**

Modify `src/backend/mv_hofki/services/scanner/stages/template_matching.py`. The `__init__` method no longer takes `confidence_threshold` — all config comes from `ctx.config`. Refactor `process` to read config and apply Canny if enabled:

Replace the entire class with:

```python
class TemplateMatchingStage(ProcessingStage):
    """Find symbols using scaled template matching across each staff region."""

    name = "template_matching"

    def __init__(
        self,
        variant_images: list[np.ndarray],
        variant_template_ids: list[int],
        variant_heights: list[float],
        variant_line_spacings: list[float] | None = None,
    ) -> None:
        self._variant_images = variant_images
        self._variant_template_ids = variant_template_ids
        self._variant_heights = variant_heights
        self._variant_line_spacings = variant_line_spacings or [0.0] * len(
            variant_images
        )

    def process(self, ctx: PipelineContext) -> PipelineContext:
        assert ctx.image is not None
        img = ctx.image
        if len(img.shape) == 3:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        confidence_threshold = ctx.config.get("confidence_threshold", 0.6)
        edge_enabled = ctx.config.get("edge_matching_enabled", False)
        canny_low = ctx.config.get("canny_low", 50)
        canny_high = ctx.config.get("canny_high", 150)

        # Prepare edge image if edge matching is enabled
        edge_img = None
        if edge_enabled:
            edge_img = cv2.Canny(img, canny_low, canny_high)

        raw_detections: list[SymbolData] = []

        for staff in ctx.staves:
            if edge_enabled:
                region = edge_img[staff.y_top : staff.y_bottom, :]
            else:
                region = img[staff.y_top : staff.y_bottom, :]

            for i, tmpl_img in enumerate(self._variant_images):
                template_id = self._variant_template_ids[i]
                height_in_lines = self._variant_heights[i]
                source_ls = self._variant_line_spacings[i]

                scaled = self._scale_template(
                    tmpl_img,
                    height_in_lines,
                    staff.line_spacing,
                    source_line_spacing=source_ls,
                )
                if scaled is None:
                    continue

                # Apply edge detection to scaled template if enabled
                if edge_enabled:
                    scaled = cv2.Canny(scaled, canny_low, canny_high)

                if (
                    scaled.shape[0] > region.shape[0]
                    or scaled.shape[1] > region.shape[1]
                ):
                    continue

                result = cv2.matchTemplate(region, scaled, cv2.TM_CCOEFF_NORMED)

                locations = np.where(result >= confidence_threshold)
                n_hits = len(locations[0])

                if n_hits > _MAX_HITS_PER_VARIANT:
                    logger.warning(
                        "Variant tid=%d on staff %d produced %d hits (cap=%d), "
                        "keeping top %d by confidence",
                        template_id,
                        staff.staff_index,
                        n_hits,
                        _MAX_HITS_PER_VARIANT,
                        _MAX_HITS_PER_VARIANT,
                    )
                    confidences = result[locations]
                    top_indices = np.argpartition(
                        confidences, -_MAX_HITS_PER_VARIANT
                    )[-_MAX_HITS_PER_VARIANT:]
                    locations = (locations[0][top_indices], locations[1][top_indices])

                for pt_y, pt_x in zip(locations[0], locations[1]):
                    confidence = float(result[pt_y, pt_x])
                    raw_detections.append(
                        SymbolData(
                            staff_index=staff.staff_index,
                            x=int(pt_x),
                            y=int(staff.y_top + pt_y),
                            width=int(scaled.shape[1]),
                            height=int(scaled.shape[0]),
                            position_on_staff=None,
                            matched_template_id=template_id,
                            confidence=confidence,
                        )
                    )

        nms_iou = ctx.config.get("nms_iou_threshold", 0.3)
        ctx.symbols = self._nms_with_alternatives(raw_detections, iou_threshold=nms_iou)

        ctx.symbols.sort(key=lambda s: (s.staff_index, s.x))
        for i, sym in enumerate(ctx.symbols):
            sym.sequence_order = i

        return ctx
```

**Important:** Keep all helper methods (`_iou`, `_nms_with_alternatives`, `validate`, `_scale_template`) unchanged.

- [ ] **Step 4: Update existing tests for removed constructor param**

In `tests/backend/test_template_matching.py`, replace `confidence_threshold=0.5` in the constructor with config on the context:

For `test_template_matching_finds_exact_match`: remove `confidence_threshold=0.5` from constructor, add `config={"confidence_threshold": 0.5}` to `PipelineContext`.

For `test_template_matching_respects_threshold`: remove `confidence_threshold=0.99` from constructor, add `config={"confidence_threshold": 0.99}` to `PipelineContext`.

- [ ] **Step 5: Run all matching tests**

Run: `python -m pytest tests/backend/test_template_matching.py tests/backend/test_template_matching_features.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add src/backend/mv_hofki/services/scanner/stages/template_matching.py tests/backend/test_template_matching_features.py tests/backend/test_template_matching.py
git commit -m "feat(scanner): add edge-based matching via Canny, read all config from context"
```

---

## Task 6: Multi-Scale Search

**Files:**
- Modify: `src/backend/mv_hofki/services/scanner/stages/template_matching.py`
- Test: `tests/backend/test_template_matching_features.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/backend/test_template_matching_features.py`:

```python
def test_multi_scale_finds_slightly_misscaled_symbol():
    """Multi-scale search should find a symbol even when line spacing is slightly off."""
    img, template = _make_image_with_symbol()
    staff = _make_staff(line_spacing=20)

    # Template has source_line_spacing=19 (slightly off from staff's 20)
    # Without multi-scale this may still match, but we verify multi-scale works
    stage = TemplateMatchingStage(
        variant_images=[template],
        variant_template_ids=[42],
        variant_heights=[2.0],
        variant_line_spacings=[19.0],
    )
    config = {
        "multi_scale_enabled": True,
        "multi_scale_range": 0.1,
        "multi_scale_steps": 5,
        "confidence_threshold": 0.5,
    }
    ctx = PipelineContext(image=img, staves=[staff], config=config)
    result = stage.process(ctx)

    assert len(result.symbols) > 0


def test_multi_scale_disabled_uses_single_scale():
    """When disabled, only the exact computed scale should be used."""
    img, template = _make_image_with_symbol()
    staff = _make_staff()

    stage = TemplateMatchingStage(
        variant_images=[template],
        variant_template_ids=[42],
        variant_heights=[2.0],
    )
    config = {"multi_scale_enabled": False, "confidence_threshold": 0.5}
    ctx = PipelineContext(image=img, staves=[staff], config=config)
    result = stage.process(ctx)

    # Should still find the symbol at exact scale
    assert len(result.symbols) > 0
```

- [ ] **Step 2: Run tests to verify they fail (or pass — multi_scale_disabled should pass already)**

Run: `python -m pytest tests/backend/test_template_matching_features.py -k "multi_scale" -v`

- [ ] **Step 3: Extract matching loop into helper, add multi-scale logic**

In `src/backend/mv_hofki/services/scanner/stages/template_matching.py`, add a `_match_at_scales` method and call it from `process`. Inside the per-variant loop, replace the single `_scale_template` + `matchTemplate` call with:

```python
    def _match_at_scales(
        self,
        region: np.ndarray,
        tmpl_img: np.ndarray,
        height_in_lines: float,
        line_spacing: float,
        source_ls: float,
        confidence_threshold: float,
        edge_enabled: bool,
        canny_low: int,
        canny_high: int,
        multi_scale_enabled: bool,
        multi_scale_range: float,
        multi_scale_steps: int,
    ) -> list[tuple[int, int, float]]:
        """Run template matching at one or more scales.

        Returns list of (pt_x, pt_y, confidence).
        """
        base_scale = self._compute_scale(
            tmpl_img, height_in_lines, line_spacing, source_ls
        )
        if base_scale is None:
            return []

        if multi_scale_enabled and multi_scale_steps > 1:
            lo = base_scale * (1 - multi_scale_range)
            hi = base_scale * (1 + multi_scale_range)
            scales = np.linspace(lo, hi, multi_scale_steps)
        else:
            scales = [base_scale]

        best_per_location: dict[tuple[int, int], float] = {}

        for scale in scales:
            scaled = self._apply_scale(tmpl_img, scale)
            if scaled is None:
                continue

            if edge_enabled:
                scaled = cv2.Canny(scaled, canny_low, canny_high)

            if scaled.shape[0] > region.shape[0] or scaled.shape[1] > region.shape[1]:
                continue

            result = cv2.matchTemplate(region, scaled, cv2.TM_CCOEFF_NORMED)
            locations = np.where(result >= confidence_threshold)
            n_hits = len(locations[0])

            if n_hits > _MAX_HITS_PER_VARIANT:
                confidences = result[locations]
                top_indices = np.argpartition(
                    confidences, -_MAX_HITS_PER_VARIANT
                )[-_MAX_HITS_PER_VARIANT:]
                locations = (locations[0][top_indices], locations[1][top_indices])

            for pt_y, pt_x in zip(locations[0], locations[1]):
                conf = float(result[pt_y, pt_x])
                key = (int(pt_x), int(pt_y))
                if key not in best_per_location or conf > best_per_location[key]:
                    best_per_location[key] = conf

        return [(x, y, c) for (x, y), c in best_per_location.items()]

    @staticmethod
    def _compute_scale(
        template: np.ndarray,
        height_in_lines: float,
        line_spacing: float,
        source_line_spacing: float,
    ) -> float | None:
        """Compute the base scale factor."""
        if source_line_spacing and source_line_spacing > 0:
            return line_spacing / source_line_spacing
        target_height = int(height_in_lines * line_spacing)
        if target_height < 3:
            return None
        return target_height / template.shape[0]

    @staticmethod
    def _apply_scale(template: np.ndarray, scale: float) -> np.ndarray | None:
        """Resize template by scale factor."""
        h, w = template.shape[:2]
        target_h = max(3, int(h * scale))
        target_w = max(1, int(w * scale))

        if len(template.shape) == 3:
            template = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)

        return cv2.resize(
            template, (target_w, target_h), interpolation=cv2.INTER_AREA
        )
```

Update `process` to call `_match_at_scales` and build `SymbolData` from the returned tuples. Keep `_scale_template` for backward compatibility but it can delegate to `_compute_scale` + `_apply_scale`.

- [ ] **Step 4: Run all matching tests**

Run: `python -m pytest tests/backend/test_template_matching.py tests/backend/test_template_matching_features.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/backend/mv_hofki/services/scanner/stages/template_matching.py tests/backend/test_template_matching_features.py
git commit -m "feat(scanner): add multi-scale template search with configurable range"
```

---

## Task 7: Staff Removal Before Matching

**Files:**
- Modify: `src/backend/mv_hofki/services/sheet_music_scan.py`
- Test: `tests/backend/test_template_matching_features.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/backend/test_template_matching_features.py`:

```python
def test_staff_removal_before_matching_removes_lines():
    """When staff_removal_before_matching is enabled, staff lines should be
    removed from the image before template matching runs."""
    from mv_hofki.services.scanner.stages.staff_removal import StaffRemovalStage

    # Create image with horizontal staff lines and a symbol
    img = np.full((200, 400), 255, dtype=np.uint8)
    # Draw 5 staff lines
    for i in range(5):
        y = 30 + i * 20
        img[y : y + 2, 20:380] = 0
    # Draw a "note head" that crosses a line
    cv2.circle(img, (100, 70), 8, 0, -1)

    staff = StaffData(
        staff_index=0,
        y_top=0,
        y_bottom=180,
        line_positions=[30, 50, 70, 90, 110],
        line_spacing=20.0,
    )

    # Verify staff removal stage works on the image
    ctx = PipelineContext(image=img.copy(), staves=[staff])
    removal = StaffRemovalStage()
    result = removal.process(ctx)

    # After removal, lines should have fewer black pixels
    for line_y in [30, 50, 90, 110]:
        row_black_after = np.sum(result.image[line_y : line_y + 2, :] == 0)
        row_black_before = np.sum(img[line_y : line_y + 2, :] == 0)
        assert row_black_after < row_black_before
```

- [ ] **Step 2: Run test to verify it passes (this tests existing functionality)**

Run: `python -m pytest tests/backend/test_template_matching_features.py::test_staff_removal_before_matching_removes_lines -v`
Expected: PASS

- [ ] **Step 3: Wire staff removal into `run_pipeline` based on config**

In `src/backend/mv_hofki/services/sheet_music_scan.py`, add `StaffRemovalStage` import and conditionally insert it into the stages list:

```python
from mv_hofki.services.scanner.stages.staff_removal import StaffRemovalStage

stages = [
    PreprocessStage(),
    StaveDetectionStage(),
]

if config.get("staff_removal_before_matching", False):
    stages.append(StaffRemovalStage())

stages.append(
    TemplateMatchingStage(
        variant_images=variant_images,
        variant_template_ids=variant_template_ids,
        variant_heights=variant_heights,
        variant_line_spacings=variant_line_spacings,
    ),
)
```

- [ ] **Step 4: Run all tests**

Run: `python -m pytest tests/backend/ -v -k "template_matching or pipeline_stages or scanner_config"`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/backend/mv_hofki/services/sheet_music_scan.py tests/backend/test_template_matching_features.py
git commit -m "feat(scanner): conditionally run staff removal before template matching"
```

---

## Task 8: Masked Template Matching

**Files:**
- Modify: `src/backend/mv_hofki/services/scanner/stages/template_matching.py`
- Test: `tests/backend/test_template_matching_features.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/backend/test_template_matching_features.py`:

```python
def test_masked_matching_finds_symbol():
    """Masked matching should find symbols using only foreground pixels."""
    img, template = _make_image_with_symbol()
    staff = _make_staff()

    stage = TemplateMatchingStage(
        variant_images=[template],
        variant_template_ids=[42],
        variant_heights=[2.0],
    )
    config = {
        "masked_matching_enabled": True,
        "mask_threshold": 200,
        "confidence_threshold": 0.5,
    }
    ctx = PipelineContext(image=img, staves=[staff], config=config)
    result = stage.process(ctx)

    assert len(result.symbols) > 0
    xs = [s.x for s in result.symbols]
    assert any(90 <= x <= 120 for x in xs)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/backend/test_template_matching_features.py::test_masked_matching_finds_symbol -v`
Expected: FAIL — masked matching not implemented yet

- [ ] **Step 3: Add masked matching to `_match_at_scales`**

In `src/backend/mv_hofki/services/scanner/stages/template_matching.py`, update `_match_at_scales` to accept `masked_enabled` and `mask_threshold` params. When masked matching is enabled:

1. Switch from `TM_CCOEFF_NORMED` to `TM_CCORR_NORMED` (required by OpenCV for masked matching)
2. Create a binary mask from the template (pixels darker than `mask_threshold` = foreground)
3. Pass mask to `cv2.matchTemplate`

Add these parameters to `_match_at_scales`:

```python
    masked_enabled: bool = False,
    mask_threshold: int = 200,
```

Inside the matching loop, after scaling (and after edge detection if applicable):

```python
    mask = None
    method = cv2.TM_CCOEFF_NORMED
    if masked_enabled and not edge_enabled:
        # Create mask: foreground pixels (dark = symbol on white background)
        mask = np.where(scaled < mask_threshold, 255, 0).astype(np.uint8)
        method = cv2.TM_CCORR_NORMED

    if mask is not None:
        result = cv2.matchTemplate(region, scaled, method, mask=mask)
    else:
        result = cv2.matchTemplate(region, scaled, method)
```

Update `process` to pass `masked_enabled` and `mask_threshold` from `ctx.config`.

- [ ] **Step 4: Run all matching tests**

Run: `python -m pytest tests/backend/test_template_matching.py tests/backend/test_template_matching_features.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/backend/mv_hofki/services/scanner/stages/template_matching.py tests/backend/test_template_matching_features.py
git commit -m "feat(scanner): add masked template matching with foreground-only correlation"
```

---

## Task 9: Dilate-Based NMS

**Files:**
- Modify: `src/backend/mv_hofki/services/scanner/stages/template_matching.py`
- Test: `tests/backend/test_template_matching_features.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/backend/test_template_matching_features.py`:

```python
def test_dilate_nms_finds_symbol():
    """Dilate NMS method should produce results similar to standard NMS."""
    img, template = _make_image_with_symbol()
    staff = _make_staff()

    stage = TemplateMatchingStage(
        variant_images=[template],
        variant_template_ids=[42],
        variant_heights=[2.0],
    )
    config = {"nms_method": "dilate", "confidence_threshold": 0.5}
    ctx = PipelineContext(image=img, staves=[staff], config=config)
    result = stage.process(ctx)

    assert len(result.symbols) > 0
    xs = [s.x for s in result.symbols]
    assert any(90 <= x <= 120 for x in xs)


def test_dilate_nms_suppresses_duplicates():
    """Dilate NMS should not return multiple detections for the same symbol."""
    img, template = _make_image_with_symbol()
    staff = _make_staff()

    stage = TemplateMatchingStage(
        variant_images=[template],
        variant_template_ids=[42],
        variant_heights=[2.0],
    )
    # Very low threshold to get many raw hits around the symbol
    config = {"nms_method": "dilate", "confidence_threshold": 0.3}
    ctx = PipelineContext(image=img, staves=[staff], config=config)
    result = stage.process(ctx)

    # Should collapse nearby hits into one detection
    near_100 = [s for s in result.symbols if 80 <= s.x <= 130]
    assert len(near_100) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/backend/test_template_matching_features.py -k "dilate" -v`
Expected: FAIL — dilate NMS not implemented

- [ ] **Step 3: Implement dilate-based NMS**

In `src/backend/mv_hofki/services/scanner/stages/template_matching.py`, the `process` method currently always calls `_nms_with_alternatives`. Change it to branch on `nms_method`:

For dilate NMS, the approach differs from standard NMS — we need to collect the full result maps and find local maxima. Since we match per-variant and the result maps have different shapes, the dilate approach works best as a post-processing step on the raw detections (same input as standard NMS, different algorithm):

```python
    @staticmethod
    def _nms_dilate(
        detections: list[SymbolData],
        suppression_distance: int = 10,
    ) -> list[SymbolData]:
        """Proximity-based NMS: keep highest-confidence detection within each cluster."""
        if not detections:
            return []

        detections.sort(key=lambda d: d.confidence or 0, reverse=True)
        kept: list[SymbolData] = []
        suppressed = [False] * len(detections)

        for i, det in enumerate(detections):
            if suppressed[i]:
                continue
            kept.append(det)
            for j in range(i + 1, len(detections)):
                if suppressed[j]:
                    continue
                other = detections[j]
                dx = abs(det.x - other.x)
                dy = abs(det.y - other.y)
                if dx <= suppression_distance and dy <= suppression_distance:
                    suppressed[j] = True
                    if other.matched_template_id != det.matched_template_id:
                        existing_ids = {a[0] for a in det.alternatives}
                        if other.matched_template_id not in existing_ids:
                            det.alternatives.append(
                                (other.matched_template_id or 0, other.confidence or 0)
                            )

        return kept
```

In `process`, select NMS method:

```python
        nms_method = ctx.config.get("nms_method", "standard")
        nms_iou = ctx.config.get("nms_iou_threshold", 0.3)

        if nms_method == "dilate":
            ctx.symbols = self._nms_dilate(raw_detections)
        else:
            ctx.symbols = self._nms_with_alternatives(raw_detections, iou_threshold=nms_iou)
```

- [ ] **Step 4: Run all matching tests**

Run: `python -m pytest tests/backend/test_template_matching.py tests/backend/test_template_matching_features.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/backend/mv_hofki/services/scanner/stages/template_matching.py tests/backend/test_template_matching_features.py
git commit -m "feat(scanner): add dilate-based NMS as alternative to IoU NMS"
```

---

## Task 10: Configurable Preprocessing Parameters

**Files:**
- Modify: `src/backend/mv_hofki/services/scanner/stages/preprocess.py`
- Test: `tests/backend/test_pipeline_stages.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/backend/test_pipeline_stages.py`:

```python
def test_preprocess_reads_adaptive_params_from_config():
    """Preprocessing should use adaptive threshold params from config."""
    from mv_hofki.services.scanner.stages.preprocess import PreprocessStage

    img = np.full((200, 200), 180, dtype=np.uint8)
    img[50:150, 50:150] = 40

    ctx = PipelineContext(
        image=img,
        config={
            "adaptive_threshold_block_size": 25,
            "adaptive_threshold_c": 5,
            "morphology_kernel_size": 3,
        },
    )
    stage = PreprocessStage()
    result = stage.process(ctx)

    assert result.processed_image is not None
    unique = np.unique(result.processed_image)
    assert all(v in (0, 255) for v in unique)
```

- [ ] **Step 2: Run test to verify it passes or fails**

Run: `python -m pytest tests/backend/test_pipeline_stages.py::test_preprocess_reads_adaptive_params_from_config -v`

- [ ] **Step 3: Update `PreprocessStage` to read params from config**

In `src/backend/mv_hofki/services/scanner/stages/preprocess.py`, replace the hardcoded values with config reads:

```python
        # Binarize: use global threshold if provided, otherwise adaptive
        threshold_val = ctx.config.get("threshold")
        if threshold_val is not None:
            _, binary = cv2.threshold(gray, int(threshold_val), 255, cv2.THRESH_BINARY)
        else:
            block_size = ctx.config.get("adaptive_threshold_block_size", 15)
            # block_size must be odd
            if block_size % 2 == 0:
                block_size += 1
            c_val = ctx.config.get("adaptive_threshold_c", 10)
            binary = cv2.adaptiveThreshold(
                gray,
                255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                blockSize=block_size,
                C=c_val,
            )

        # Deskew using Hough line detection
        binary = self._deskew(binary)

        # Morphological noise removal
        k_size = ctx.config.get("morphology_kernel_size", 2)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k_size, k_size))
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
```

- [ ] **Step 4: Run all preprocessing tests**

Run: `python -m pytest tests/backend/test_pipeline_stages.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/backend/mv_hofki/services/scanner/stages/preprocess.py tests/backend/test_pipeline_stages.py
git commit -m "feat(scanner): make preprocessing params configurable via pipeline config"
```

---

## Task 11: Configurable Matching Method

**Files:**
- Modify: `src/backend/mv_hofki/services/scanner/stages/template_matching.py`
- Test: `tests/backend/test_template_matching_features.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/backend/test_template_matching_features.py`:

```python
def test_matching_method_sqdiff():
    """TM_SQDIFF_NORMED should find symbols (note: lower score = better match)."""
    img, template = _make_image_with_symbol()
    staff = _make_staff()

    stage = TemplateMatchingStage(
        variant_images=[template],
        variant_template_ids=[42],
        variant_heights=[2.0],
    )
    config = {
        "matching_method": "TM_SQDIFF_NORMED",
        "confidence_threshold": 0.5,
    }
    ctx = PipelineContext(image=img, staves=[staff], config=config)
    result = stage.process(ctx)

    assert len(result.symbols) > 0


def test_matching_method_ccorr():
    """TM_CCORR_NORMED should find symbols."""
    img, template = _make_image_with_symbol()
    staff = _make_staff()

    stage = TemplateMatchingStage(
        variant_images=[template],
        variant_template_ids=[42],
        variant_heights=[2.0],
    )
    config = {
        "matching_method": "TM_CCORR_NORMED",
        "confidence_threshold": 0.5,
    }
    ctx = PipelineContext(image=img, staves=[staff], config=config)
    result = stage.process(ctx)

    assert len(result.symbols) > 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/backend/test_template_matching_features.py -k "matching_method" -v`

- [ ] **Step 3: Add matching method selection**

In `src/backend/mv_hofki/services/scanner/stages/template_matching.py`, add a method map and use it in `_match_at_scales`:

```python
_METHOD_MAP = {
    "TM_CCOEFF_NORMED": cv2.TM_CCOEFF_NORMED,
    "TM_CCORR_NORMED": cv2.TM_CCORR_NORMED,
    "TM_SQDIFF_NORMED": cv2.TM_SQDIFF_NORMED,
}
```

In `process`, read the method and pass it through:

```python
        matching_method = ctx.config.get("matching_method", "TM_CCOEFF_NORMED")
```

In `_match_at_scales`, use the method map. For `TM_SQDIFF_NORMED`, the logic is inverted — lower is better:

```python
        method = _METHOD_MAP.get(matching_method_str, cv2.TM_CCOEFF_NORMED)
        is_sqdiff = method == cv2.TM_SQDIFF_NORMED

        # For SQDIFF: lower = better match, so invert the threshold logic
        if is_sqdiff:
            locations = np.where(result <= (1 - confidence_threshold))
            # Convert to confidence: conf = 1 - sqdiff_score
            for pt_y, pt_x in zip(locations[0], locations[1]):
                confidence = 1.0 - float(result[pt_y, pt_x])
                ...
        else:
            locations = np.where(result >= confidence_threshold)
            for pt_y, pt_x in zip(locations[0], locations[1]):
                confidence = float(result[pt_y, pt_x])
                ...
```

- [ ] **Step 4: Run all matching tests**

Run: `python -m pytest tests/backend/test_template_matching.py tests/backend/test_template_matching_features.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/backend/mv_hofki/services/scanner/stages/template_matching.py tests/backend/test_template_matching_features.py
git commit -m "feat(scanner): support configurable matching method (CCOEFF/CCORR/SQDIFF)"
```

---

## Task 12: Final Integration — Run Full Test Suite & Lint

**Files:**
- All modified files from previous tasks

- [ ] **Step 1: Run the complete backend test suite**

Run: `python -m pytest tests/backend/ -v`
Expected: ALL PASS

- [ ] **Step 2: Run linters**

Run: `pre-commit run --all-files`

Fix any issues found. Common fixes: import sorting, trailing whitespace, line length.

- [ ] **Step 3: Run tests again after lint fixes**

Run: `python -m pytest tests/backend/ -v`
Expected: ALL PASS

- [ ] **Step 4: Commit any lint fixes**

```bash
git add -u
git commit -m "style: fix lint issues from pre-commit"
```

---

## Summary of Config Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `confidence_threshold` | float | 0.6 | Minimum match score to keep a detection |
| `matching_method` | string | TM_CCOEFF_NORMED | OpenCV matching method |
| `multi_scale_enabled` | bool | false | Search narrow range around computed scale |
| `multi_scale_range` | float | 0.05 | +/- range (5% = 0.05) |
| `multi_scale_steps` | int | 3 | Number of scales to try |
| `edge_matching_enabled` | bool | false | Apply Canny to template and image before matching |
| `canny_low` | int | 50 | Canny low threshold |
| `canny_high` | int | 150 | Canny high threshold |
| `staff_removal_before_matching` | bool | false | Remove staff lines before template matching |
| `masked_matching_enabled` | bool | false | Use foreground mask (switches to TM_CCORR_NORMED) |
| `mask_threshold` | int | 200 | Pixel value below which = foreground |
| `nms_iou_threshold` | float | 0.3 | IoU threshold for standard NMS |
| `nms_method` | string | standard | "standard" (IoU) or "dilate" (proximity) |
| `adaptive_threshold_block_size` | int | 15 | Adaptive binarization block size |
| `adaptive_threshold_c` | int | 10 | Adaptive binarization constant |
| `morphology_kernel_size` | int | 2 | Noise removal kernel size |
| `auto_verify_confidence` | float | 0.85 | Auto-verify symbols above this confidence |

## API Flow

```
GET  /api/v1/scanner/config           → current global settings
PUT  /api/v1/scanner/config           → update global settings (partial)
POST /api/v1/scanner/scans/{id}/process
     body: null                        → uses global settings
     body: {"confidence_threshold":0.8} → uses global + these overrides (not saved)
```
