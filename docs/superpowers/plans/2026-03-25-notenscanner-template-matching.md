# Notenscanner Template Matching Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace automated segmentation/matching with user-controlled monochrome threshold, manual template capture via box drawing, and sliding-window template matching.

**Architecture:** User adjusts a global binarization threshold (frontend slider + backend `cv2.threshold`), draws boxes on the scan to capture symbol templates with height-in-staff-lines metadata, and the new `TemplateMatchingStage` uses `cv2.matchTemplate` to find occurrences. Zoom support enables precise box drawing.

**Tech Stack:** FastAPI, OpenCV (`cv2.matchTemplate`, `cv2.threshold`), SQLAlchemy, Vue 3 Composition API, SVG overlays

**Spec:** `docs/superpowers/specs/2026-03-25-notenscanner-template-matching-design.md`

---

## File Structure

| Action | File | Purpose |
|--------|------|---------|
| Modify | `src/backend/mv_hofki/models/symbol_variant.py` | Add `height_in_lines` column |
| Modify | `src/backend/mv_hofki/schemas/symbol_variant.py` | Add `height_in_lines` to read schema |
| Modify | `src/backend/mv_hofki/schemas/symbol_template.py` | Add capture request schema |
| Modify | `src/backend/mv_hofki/services/symbol_library.py` | Add `capture_template` function |
| Modify | `src/backend/mv_hofki/api/routes/symbol_library.py` | Add capture endpoint |
| Modify | `src/backend/mv_hofki/services/scanner/stages/preprocess.py` | Add global threshold mode |
| Create | `src/backend/mv_hofki/services/scanner/stages/template_matching.py` | Sliding window matching stage |
| Modify | `src/backend/mv_hofki/services/sheet_music_scan.py` | Update `run_pipeline` to use new stage |
| Create | `tests/backend/test_template_matching.py` | Tests for new matching stage |
| Modify | `src/frontend/src/components/ImageAdjustBar.vue` | Add threshold slider |
| Modify | `src/frontend/src/components/ScanCanvas.vue` | Add zoom + box drawing + threshold preview |
| Modify | `src/frontend/src/pages/ScanEditorPage.vue` | Add capture mode, capture dialog, zoom controls |

---

### Task 1: Add `height_in_lines` to SymbolVariant model + migration

**Files:**
- Modify: `src/backend/mv_hofki/models/symbol_variant.py`
- Modify: `src/backend/mv_hofki/schemas/symbol_variant.py`

- [ ] **Step 1: Add `height_in_lines` column to model**

In `src/backend/mv_hofki/models/symbol_variant.py`, add after the `usage_count` line:

```python
from sqlalchemy import Float
```

(add `Float` to the existing sqlalchemy import)

```python
    height_in_lines: Mapped[float | None] = mapped_column(Float)
```

- [ ] **Step 2: Add field to read schema**

In `src/backend/mv_hofki/schemas/symbol_variant.py`, add `height_in_lines` to `SymbolVariantRead`:

```python
class SymbolVariantRead(BaseModel):
    id: int
    template_id: int
    image_path: str
    source: str
    usage_count: int
    height_in_lines: float | None
    created_at: datetime

    model_config = {"from_attributes": True}
```

- [ ] **Step 3: Create Alembic migration**

Run: `cd /workspaces/mv_hofki && PYTHONPATH=src/backend alembic revision --autogenerate -m "add height_in_lines to symbol_variants"`

- [ ] **Step 4: Run migration**

Run: `cd /workspaces/mv_hofki && PYTHONPATH=src/backend alembic upgrade head`

- [ ] **Step 5: Run tests**

Run: `cd /workspaces/mv_hofki && python -m pytest tests/backend/ -v --tb=short`
Expected: All existing tests pass (138 pass, 1 pre-existing failure)

- [ ] **Step 6: Commit**

```bash
git add src/backend/mv_hofki/models/symbol_variant.py src/backend/mv_hofki/schemas/symbol_variant.py alembic/versions/
git commit -m "feat(scanner): add height_in_lines to SymbolVariant for scale-aware matching"
```

---

### Task 2: Add template capture endpoint

**Files:**
- Modify: `src/backend/mv_hofki/schemas/symbol_template.py`
- Modify: `src/backend/mv_hofki/services/symbol_library.py`
- Modify: `src/backend/mv_hofki/api/routes/symbol_library.py`
- Create: `tests/backend/test_template_capture.py`

- [ ] **Step 1: Write failing test**

Create `tests/backend/test_template_capture.py`:

```python
"""Tests for template capture endpoint."""

import io
import struct
import zlib

import pytest


def _fake_png():
    """Minimal valid 10x10 white PNG."""
    header = b"\x89PNG\r\n\x1a\n"
    width, height = 10, 10
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    ihdr_crc = zlib.crc32(b"IHDR" + ihdr_data) & 0xFFFFFFFF
    ihdr = struct.pack(">I", 13) + b"IHDR" + ihdr_data + struct.pack(">I", ihdr_crc)
    raw_rows = b""
    for _ in range(height):
        raw_rows += b"\x00" + b"\xff\xff\xff" * width
    raw = zlib.compress(raw_rows)
    idat_crc = zlib.crc32(b"IDAT" + raw) & 0xFFFFFFFF
    idat = struct.pack(">I", len(raw)) + b"IDAT" + raw + struct.pack(">I", idat_crc)
    iend_crc = zlib.crc32(b"IEND") & 0xFFFFFFFF
    iend = struct.pack(">I", 0) + b"IEND" + struct.pack(">I", iend_crc)
    return header + ihdr + idat + iend


@pytest.fixture
async def scan_id(client):
    """Create a project/part/scan to capture from."""
    resp = await client.post("/api/v1/scanner/projects", json={"name": "Test"})
    project_id = resp.json()["id"]
    resp = await client.post(
        f"/api/v1/scanner/projects/{project_id}/parts",
        json={"part_name": "Flügelhorn"},
    )
    part_id = resp.json()["id"]
    resp = await client.post(
        f"/api/v1/scanner/projects/{project_id}/parts/{part_id}/scans",
        files={"file": ("test.png", io.BytesIO(_fake_png()), "image/png")},
    )
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_capture_template(client, scan_id):
    resp = await client.post(
        "/api/v1/scanner/library/templates/capture",
        json={
            "scan_id": scan_id,
            "x": 0,
            "y": 0,
            "width": 5,
            "height": 8,
            "name": "Viertelnote",
            "category": "note",
            "musicxml_element": "<note/>",
            "height_in_lines": 4.0,
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Viertelnote"
    assert data["category"] == "note"


@pytest.mark.asyncio
async def test_capture_template_missing_name(client, scan_id):
    resp = await client.post(
        "/api/v1/scanner/library/templates/capture",
        json={
            "scan_id": scan_id,
            "x": 0,
            "y": 0,
            "width": 5,
            "height": 8,
            "name": "",
            "category": "note",
            "height_in_lines": 4.0,
        },
    )
    assert resp.status_code == 422
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /workspaces/mv_hofki && python -m pytest tests/backend/test_template_capture.py -v`
Expected: FAIL

- [ ] **Step 3: Add capture request schema**

In `src/backend/mv_hofki/schemas/symbol_template.py`, add:

```python
class TemplateCaptureRequest(BaseModel):
    scan_id: int
    x: int
    y: int
    width: int
    height: int
    name: str
    category: str
    musicxml_element: str | None = None
    height_in_lines: float

    @field_validator("name")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Darf nicht leer sein")
        return v.strip()
```

Add the `field_validator` import at the top:
```python
from pydantic import BaseModel, field_validator
```

- [ ] **Step 4: Add `capture_template` service function**

In `src/backend/mv_hofki/services/symbol_library.py`, add:

```python
import cv2
import numpy as np

from mv_hofki.core.config import settings
from mv_hofki.models.symbol_variant import SymbolVariant
from mv_hofki.models.sheet_music_scan import SheetMusicScan


async def capture_template(
    session: AsyncSession,
    *,
    scan_id: int,
    x: int,
    y: int,
    width: int,
    height: int,
    name: str,
    category: str,
    musicxml_element: str | None,
    height_in_lines: float,
) -> SymbolTemplate:
    """Capture a template from a scan region."""
    scan = await session.get(SheetMusicScan, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan nicht gefunden")

    # Load the scan image
    img_path = settings.PROJECT_ROOT / scan.image_path
    img = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise HTTPException(status_code=400, detail="Bild konnte nicht geladen werden")

    # Apply threshold if stored in adjustments
    import json
    adjustments = json.loads(scan.adjustments_json) if scan.adjustments_json else {}
    threshold_val = adjustments.get("threshold")
    if threshold_val is not None:
        _, img = cv2.threshold(img, int(threshold_val), 255, cv2.THRESH_BINARY)

    # Crop the region
    crop = img[y : y + height, x : x + width]
    if crop.size == 0:
        raise HTTPException(status_code=400, detail="Ungültiger Ausschnitt")

    # Create or find template
    existing = await session.execute(
        select(SymbolTemplate).where(SymbolTemplate.name == name)
    )
    template = existing.scalar_one_or_none()
    if template is None:
        template = SymbolTemplate(
            category=category,
            name=name,
            display_name=name,
            musicxml_element=musicxml_element,
            is_seed=False,
        )
        session.add(template)
        await session.flush()

    # Save variant image
    variant_dir = settings.PROJECT_ROOT / "data" / "symbol_library" / str(template.id)
    variant_dir.mkdir(parents=True, exist_ok=True)

    import uuid
    variant_filename = f"{uuid.uuid4().hex}.png"
    variant_path = variant_dir / variant_filename
    cv2.imwrite(str(variant_path), crop)

    variant = SymbolVariant(
        template_id=template.id,
        image_path=str(variant_path.relative_to(settings.PROJECT_ROOT)),
        source="user_capture",
        height_in_lines=height_in_lines,
    )
    session.add(variant)
    await session.commit()
    await session.refresh(template)
    return template
```

- [ ] **Step 5: Add capture route**

In `src/backend/mv_hofki/api/routes/symbol_library.py`, add:

```python
from mv_hofki.schemas.symbol_template import TemplateCaptureRequest


@router.post("/templates/capture", response_model=SymbolTemplateRead, status_code=201)
async def capture_template(
    data: TemplateCaptureRequest, db: AsyncSession = Depends(get_db)
):
    return await lib_service.capture_template(
        db,
        scan_id=data.scan_id,
        x=data.x,
        y=data.y,
        width=data.width,
        height=data.height,
        name=data.name,
        category=data.category,
        musicxml_element=data.musicxml_element,
        height_in_lines=data.height_in_lines,
    )
```

- [ ] **Step 6: Run tests**

Run: `cd /workspaces/mv_hofki && python -m pytest tests/backend/test_template_capture.py -v`
Expected: All tests pass

- [ ] **Step 7: Commit**

```bash
git add src/backend/mv_hofki/schemas/symbol_template.py src/backend/mv_hofki/services/symbol_library.py src/backend/mv_hofki/api/routes/symbol_library.py tests/backend/test_template_capture.py
git commit -m "feat(scanner): add template capture endpoint for user-drawn symbol boxes"
```

---

### Task 3: Add global threshold to PreprocessStage

**Files:**
- Modify: `src/backend/mv_hofki/services/scanner/stages/preprocess.py`
- Modify: `tests/backend/test_pipeline_stages.py`

- [ ] **Step 1: Write failing test**

Add to `tests/backend/test_pipeline_stages.py`:

```python
def test_preprocess_global_threshold():
    from mv_hofki.services.scanner.stages.preprocess import PreprocessStage

    img = np.full((100, 100), 180, dtype=np.uint8)
    img[30:70, 30:70] = 40

    ctx = PipelineContext(image=img, config={"threshold": 128})
    stage = PreprocessStage()
    result = stage.process(ctx)

    assert result.processed_image is not None
    unique = np.unique(result.processed_image)
    assert all(v in (0, 255) for v in unique)
    # With global threshold=128: pixels at 180 → white, pixels at 40 → black
    assert result.processed_image[50, 50] == 0  # dark area → black
    assert result.processed_image[5, 5] == 255  # light area → white
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /workspaces/mv_hofki && python -m pytest tests/backend/test_pipeline_stages.py::test_preprocess_global_threshold -v`
Expected: FAIL

- [ ] **Step 3: Implement global threshold mode**

In `src/backend/mv_hofki/services/scanner/stages/preprocess.py`, replace the thresholding section (lines 33-41) with:

```python
        # Binarize: use global threshold if provided, otherwise adaptive
        threshold_val = ctx.config.get("threshold")
        if threshold_val is not None:
            _, binary = cv2.threshold(
                gray, int(threshold_val), 255, cv2.THRESH_BINARY
            )
        else:
            binary = cv2.adaptiveThreshold(
                gray,
                255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                blockSize=15,
                C=10,
            )
```

- [ ] **Step 4: Run tests**

Run: `cd /workspaces/mv_hofki && python -m pytest tests/backend/test_pipeline_stages.py -v`
Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add src/backend/mv_hofki/services/scanner/stages/preprocess.py tests/backend/test_pipeline_stages.py
git commit -m "feat(scanner): add user-controlled global threshold to PreprocessStage"
```

---

### Task 4: Create TemplateMatchingStage

**Files:**
- Create: `src/backend/mv_hofki/services/scanner/stages/template_matching.py`
- Create: `tests/backend/test_template_matching.py`

- [ ] **Step 1: Write failing tests**

Create `tests/backend/test_template_matching.py`:

```python
"""Tests for sliding window template matching stage."""

import cv2
import numpy as np
import pytest

from mv_hofki.services.scanner.stages.base import PipelineContext, StaffData
from mv_hofki.services.scanner.stages.template_matching import TemplateMatchingStage


def _make_staff(line_spacing=20):
    """Create a staff with known line spacing."""
    return StaffData(
        staff_index=0,
        y_top=10,
        y_bottom=10 + int(line_spacing * 8),
        line_positions=[10 + int(line_spacing * i) for i in range(5)],
        line_spacing=float(line_spacing),
    )


def test_template_matching_finds_exact_match():
    """A template placed in the image should be found."""
    spacing = 20
    staff = _make_staff(spacing)

    # Create a blank image
    img = np.full((200, 400), 255, dtype=np.uint8)

    # Create a "symbol" — a filled circle
    symbol = np.full((40, 20), 255, dtype=np.uint8)
    cv2.circle(symbol, (10, 20), 8, 0, -1)

    # Place it at position (100, 30) in the image
    img[30:70, 100:120] = symbol

    # The template is the same circle, declared as 2 lines high
    template_img = symbol.copy()
    height_in_lines = 2.0

    stage = TemplateMatchingStage(
        variant_images=[template_img],
        variant_template_ids=[42],
        variant_heights=[height_in_lines],
        confidence_threshold=0.5,
    )

    ctx = PipelineContext(image=img, staves=[staff])
    result = stage.process(ctx)

    assert len(result.symbols) > 0
    # Should find a match near x=100
    xs = [s.x for s in result.symbols]
    assert any(95 <= x <= 125 for x in xs), f"Expected match near x=100, got {xs}"


def test_template_matching_respects_threshold():
    """No matches should be found if confidence threshold is very high."""
    spacing = 20
    staff = _make_staff(spacing)
    img = np.full((200, 400), 255, dtype=np.uint8)
    # Add some random noise
    rng = np.random.RandomState(42)
    noise = rng.randint(200, 255, img.shape, dtype=np.uint8)
    img = np.minimum(img, noise)

    template = np.full((40, 20), 255, dtype=np.uint8)
    cv2.circle(template, (10, 20), 8, 0, -1)

    stage = TemplateMatchingStage(
        variant_images=[template],
        variant_template_ids=[1],
        variant_heights=[2.0],
        confidence_threshold=0.99,
    )

    ctx = PipelineContext(image=img, staves=[staff])
    result = stage.process(ctx)
    assert len(result.symbols) == 0


def test_template_matching_scales_template():
    """Template should be scaled based on height_in_lines and staff spacing."""
    stage = TemplateMatchingStage(
        variant_images=[], variant_template_ids=[], variant_heights=[],
    )
    template = np.full((40, 20), 255, dtype=np.uint8)
    # height_in_lines=4, spacing=10 → target height=40 (same size, no scale)
    scaled = stage._scale_template(template, height_in_lines=4.0, line_spacing=10.0)
    assert scaled.shape[0] == 40

    # height_in_lines=4, spacing=20 → target height=80
    scaled2 = stage._scale_template(template, height_in_lines=4.0, line_spacing=20.0)
    assert scaled2.shape[0] == 80
    assert scaled2.shape[1] == 40  # width scales proportionally
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /workspaces/mv_hofki && python -m pytest tests/backend/test_template_matching.py -v`
Expected: FAIL

- [ ] **Step 3: Implement TemplateMatchingStage**

Create `src/backend/mv_hofki/services/scanner/stages/template_matching.py`:

```python
"""Template matching stage: sliding window with cv2.matchTemplate."""

from __future__ import annotations

import cv2
import numpy as np

from mv_hofki.services.scanner.stages.base import (
    PipelineContext,
    ProcessingStage,
    SymbolData,
)


class TemplateMatchingStage(ProcessingStage):
    """Find symbols using scaled template matching across each staff region."""

    name = "template_matching"

    def __init__(
        self,
        variant_images: list[np.ndarray],
        variant_template_ids: list[int],
        variant_heights: list[float],
        confidence_threshold: float = 0.6,
    ) -> None:
        self._variant_images = variant_images
        self._variant_template_ids = variant_template_ids
        self._variant_heights = variant_heights
        self._confidence_threshold = confidence_threshold

    def process(self, ctx: PipelineContext) -> PipelineContext:
        assert ctx.image is not None
        img = ctx.image
        if len(img.shape) == 3:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        for staff in ctx.staves:
            region = img[staff.y_top : staff.y_bottom, :]

            for i, tmpl_img in enumerate(self._variant_images):
                template_id = self._variant_template_ids[i]
                height_in_lines = self._variant_heights[i]

                scaled = self._scale_template(
                    tmpl_img, height_in_lines, staff.line_spacing
                )
                if scaled is None:
                    continue

                # Skip if template is larger than the region
                if scaled.shape[0] > region.shape[0] or scaled.shape[1] > region.shape[1]:
                    continue

                # Run template matching
                result = cv2.matchTemplate(
                    region, scaled, cv2.TM_CCOEFF_NORMED
                )

                # Find all locations above threshold
                locations = np.where(result >= self._confidence_threshold)

                for pt_y, pt_x in zip(locations[0], locations[1]):
                    confidence = float(result[pt_y, pt_x])
                    ctx.symbols.append(
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

        # Sort by staff, then left to right
        ctx.symbols.sort(key=lambda s: (s.staff_index, s.x))
        for i, sym in enumerate(ctx.symbols):
            sym.sequence_order = i

        return ctx

    def validate(self, ctx: PipelineContext) -> bool:
        return ctx.image is not None and len(ctx.staves) > 0

    @staticmethod
    def _scale_template(
        template: np.ndarray,
        height_in_lines: float,
        line_spacing: float,
    ) -> np.ndarray | None:
        """Scale template to match the staff's line spacing."""
        target_height = int(height_in_lines * line_spacing)
        if target_height < 3:
            return None

        h, w = template.shape[:2]
        scale = target_height / h
        target_width = max(1, int(w * scale))

        if len(template.shape) == 3:
            template = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)

        scaled = cv2.resize(
            template, (target_width, target_height), interpolation=cv2.INTER_AREA
        )
        return scaled
```

- [ ] **Step 4: Run tests**

Run: `cd /workspaces/mv_hofki && python -m pytest tests/backend/test_template_matching.py -v`
Expected: All 3 tests pass

- [ ] **Step 5: Commit**

```bash
git add src/backend/mv_hofki/services/scanner/stages/template_matching.py tests/backend/test_template_matching.py
git commit -m "feat(scanner): add TemplateMatchingStage with sliding window cv2.matchTemplate"
```

---

### Task 5: Wire new pipeline into `run_pipeline`

**Files:**
- Modify: `src/backend/mv_hofki/services/sheet_music_scan.py:127-184`

- [ ] **Step 1: Update `run_pipeline` to use TemplateMatchingStage**

In `src/backend/mv_hofki/services/sheet_music_scan.py`, update the `run_pipeline` function. Replace the stage imports and pipeline construction (lines ~143-183):

Replace the import of old stages:
```python
    from mv_hofki.services.scanner.stages.matching import MatchingStage
    from mv_hofki.services.scanner.stages.segmentation import SegmentationStage
    from mv_hofki.services.scanner.stages.staff_removal import StaffRemovalStage
```

With:
```python
    from mv_hofki.services.scanner.stages.template_matching import TemplateMatchingStage
```

Replace the variant loading section (the loop that loads variant images and template_ids) with:

```python
    # Load symbol library variants that have height_in_lines (user-captured templates)
    result = await session.execute(
        sa_select(SymbolVariant).where(SymbolVariant.height_in_lines.isnot(None))
    )
    variants = list(result.scalars().all())

    variant_images = []
    variant_template_ids = []
    variant_heights = []
    for v in variants:
        v_path = settings.PROJECT_ROOT / v.image_path
        v_img = cv2.imread(str(v_path), cv2.IMREAD_GRAYSCALE)
        if v_img is not None:
            variant_images.append(v_img)
            variant_template_ids.append(v.template_id)
            variant_heights.append(v.height_in_lines)
```

Replace the stages list with:

```python
    # Pass the user's threshold into the pipeline config
    adjustments = json.loads(scan.adjustments_json) if scan.adjustments_json else {}
    config = json.loads(scan.pipeline_config_json) if scan.pipeline_config_json else {}
    if "threshold" in adjustments:
        config["threshold"] = adjustments["threshold"]

    stages = [
        PreprocessStage(),
        StaveDetectionStage(),
        TemplateMatchingStage(
            variant_images=variant_images,
            variant_template_ids=variant_template_ids,
            variant_heights=variant_heights,
            confidence_threshold=config.get("confidence_threshold", 0.6),
        ),
    ]
```

- [ ] **Step 2: Run all backend tests**

Run: `cd /workspaces/mv_hofki && python -m pytest tests/backend/ -v --tb=short`
Expected: All tests pass

- [ ] **Step 3: Commit**

```bash
git add src/backend/mv_hofki/services/sheet_music_scan.py
git commit -m "feat(scanner): wire TemplateMatchingStage into pipeline, pass threshold from adjustments"
```

---

### Task 6: Add threshold slider to ImageAdjustBar

**Files:**
- Modify: `src/frontend/src/components/ImageAdjustBar.vue`

- [ ] **Step 1: Add threshold ref and emit it**

In the `<script setup>`, add a `threshold` ref and include it in `emitAdjust`:

```javascript
const threshold = ref(128);
```

Update `emitAdjust` to include threshold:
```javascript
function emitAdjust() {
  emit("adjust", {
    brightness: brightness.value,
    contrast: contrast.value,
    rotation: rotation.value,
    threshold: threshold.value,
  });
}
```

Add `threshold` to the watch array:
```javascript
watch([brightness, contrast, threshold], emitAdjust);
```

- [ ] **Step 2: Add threshold slider to template**

Add after the contrast group, before the rotation group:

```html
    <div class="adjust-group">
      <label class="adjust-label">
        Schwellwert
        <span class="adjust-value">{{ threshold }}</span>
      </label>
      <input
        v-model.number="threshold"
        type="range"
        min="0"
        max="255"
        step="1"
        class="adjust-slider"
      />
    </div>
```

- [ ] **Step 3: Verify frontend builds**

Run: `cd /workspaces/mv_hofki/src/frontend && npx vite build`
Expected: Build succeeds

- [ ] **Step 4: Commit**

```bash
git add src/frontend/src/components/ImageAdjustBar.vue
git commit -m "feat(scanner): add monochrome threshold slider to ImageAdjustBar"
```

---

### Task 7: Add zoom support and threshold preview to ScanCanvas

**Files:**
- Modify: `src/frontend/src/components/ScanCanvas.vue`

- [ ] **Step 1: Add zoom state and controls**

Replace the entire `ScanCanvas.vue` with the updated version. Key changes from the current file:

**Script additions:**
- `zoom` ref (default 1.0)
- `ZOOM_STEPS` array: `[0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0]`
- `zoomIn()` / `zoomOut()` functions that step through the array
- `onWheel(e)` handler for mouse wheel zoom (`e.deltaY < 0` → zoom in)
- `canvasWrapRef` ref for the scrollable container
- Threshold preview via a `<canvas>` element that applies the threshold client-side: load image, draw to canvas, read pixels, apply threshold, write back. Recompute when `adjustments.threshold` changes.

**Template changes:**
- The `.canvas-wrap` div gets `@wheel.prevent="onWheel"` and `ref="canvasWrapRef"`
- Replace `<img>` with a `<canvas>` element (`ref="previewCanvas"`) for the threshold preview
- The image container gets `:style="{ width: naturalWidth * zoom + 'px' }"` to control zoom
- Both the canvas and SVG overlay scale with zoom
- Zoom indicator: `<div class="zoom-indicator">{{ Math.round(zoom * 100) }}%</div>`

**Style changes:**
- `.scan-image` gets `width: 100%` (fills the zoomed container)
- `.zoom-indicator` positioned absolute in bottom-right corner
- `.canvas-wrap` keeps `overflow: auto` so it scrolls when zoomed

The full implementation: the `<canvas>` replaces the `<img>` for the preview. On image load, draw the image to canvas, then apply the threshold pixel-by-pixel in JavaScript. When threshold changes, redraw. The SVG overlay remains on top with `viewBox` matching the natural image dimensions.

```javascript
// Core zoom logic
const ZOOM_STEPS = [0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0];
const zoom = ref(1.0);

function zoomIn() {
  const idx = ZOOM_STEPS.indexOf(zoom.value);
  if (idx < ZOOM_STEPS.length - 1) zoom.value = ZOOM_STEPS[idx + 1];
}

function zoomOut() {
  const idx = ZOOM_STEPS.indexOf(zoom.value);
  if (idx > 0) zoom.value = ZOOM_STEPS[idx - 1];
}

function onWheel(e) {
  if (e.deltaY < 0) zoomIn();
  else zoomOut();
}
```

```javascript
// Threshold preview via canvas
const previewCanvas = ref(null);
const imgData = ref(null); // cached original ImageData

function loadImage() {
  if (!imageUrl.value) return;
  const img = new Image();
  img.crossOrigin = "anonymous";
  img.onload = () => {
    naturalWidth.value = img.naturalWidth;
    naturalHeight.value = img.naturalHeight;
    const canvas = previewCanvas.value;
    if (!canvas) return;
    canvas.width = img.naturalWidth;
    canvas.height = img.naturalHeight;
    const ctx = canvas.getContext("2d");
    ctx.drawImage(img, 0, 0);
    imgData.value = ctx.getImageData(0, 0, canvas.width, canvas.height);
    applyThreshold();
  };
  img.src = imageUrl.value;
}

function applyThreshold() {
  if (!imgData.value || !previewCanvas.value) return;
  const canvas = previewCanvas.value;
  const ctx = canvas.getContext("2d");
  const src = imgData.value;
  const dst = ctx.createImageData(src.width, src.height);
  const t = props.adjustments.threshold ?? 128;
  for (let i = 0; i < src.data.length; i += 4) {
    // Convert to grayscale
    const gray = src.data[i] * 0.299 + src.data[i + 1] * 0.587 + src.data[i + 2] * 0.114;
    const val = gray >= t ? 255 : 0;
    dst.data[i] = val;
    dst.data[i + 1] = val;
    dst.data[i + 2] = val;
    dst.data[i + 3] = 255;
  }
  ctx.putImageData(dst, 0, 0);
}

watch(() => props.imagePath, loadImage);
watch(() => props.adjustments.threshold, applyThreshold);
onMounted(loadImage);
```

**Template:** Replace the `<img>` with:
```html
<canvas
  ref="previewCanvas"
  class="scan-image"
  :style="{ width: naturalWidth * zoom + 'px', height: naturalHeight * zoom + 'px' }"
/>
```

- [ ] **Step 2: Verify frontend builds**

Run: `cd /workspaces/mv_hofki/src/frontend && npx vite build`
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
git add src/frontend/src/components/ScanCanvas.vue
git commit -m "feat(scanner): add zoom support and monochrome threshold preview to ScanCanvas"
```

---

### Task 8: Add box drawing mode and capture dialog to ScanEditorPage

**Files:**
- Modify: `src/frontend/src/components/ScanCanvas.vue` (add box drawing)
- Modify: `src/frontend/src/pages/ScanEditorPage.vue` (add capture mode + dialog)

- [ ] **Step 1: Add box drawing to ScanCanvas**

Add to ScanCanvas props:
```javascript
captureMode: { type: Boolean, default: false },
```

Add new emit:
```javascript
const emit = defineEmits(["select-symbol", "capture-box"]);
```

Add box drawing state and handlers:
```javascript
const drawing = ref(false);
const drawStart = ref({ x: 0, y: 0 });
const drawEnd = ref({ x: 0, y: 0 });
const svgEl = ref(null);

function toImageCoords(e) {
  // Convert mouse event to image pixel coordinates
  const svg = svgEl.value;
  if (!svg) return { x: 0, y: 0 };
  const rect = svg.getBoundingClientRect();
  const x = ((e.clientX - rect.left) / rect.width) * naturalWidth.value;
  const y = ((e.clientY - rect.top) / rect.height) * naturalHeight.value;
  return { x: Math.round(x), y: Math.round(y) };
}

function onMouseDown(e) {
  if (!props.captureMode) return;
  drawing.value = true;
  drawStart.value = toImageCoords(e);
  drawEnd.value = drawStart.value;
}

function onMouseMove(e) {
  if (!drawing.value) return;
  drawEnd.value = toImageCoords(e);
}

function onMouseUp() {
  if (!drawing.value) return;
  drawing.value = false;
  const x = Math.min(drawStart.value.x, drawEnd.value.x);
  const y = Math.min(drawStart.value.y, drawEnd.value.y);
  const w = Math.abs(drawEnd.value.x - drawStart.value.x);
  const h = Math.abs(drawEnd.value.y - drawStart.value.y);
  if (w > 3 && h > 3) {
    emit("capture-box", { x, y, width: w, height: h });
  }
}
```

Add `ref="svgEl"` to the SVG element and mouse handlers:
```html
<svg
  ref="svgEl"
  ...
  @mousedown="onMouseDown"
  @mousemove="onMouseMove"
  @mouseup="onMouseUp"
  :style="{ cursor: captureMode ? 'crosshair' : 'default', pointerEvents: captureMode ? 'all' : 'none' }"
>
```

Add drawing rectangle to SVG (at the end, before `</svg>`):
```html
<!-- Drawing rectangle (capture mode) -->
<rect
  v-if="drawing"
  :x="Math.min(drawStart.x, drawEnd.x)"
  :y="Math.min(drawStart.y, drawEnd.y)"
  :width="Math.abs(drawEnd.x - drawStart.x)"
  :height="Math.abs(drawEnd.y - drawStart.y)"
  fill="rgba(251, 191, 36, 0.15)"
  stroke="#f59e0b"
  stroke-width="2"
  stroke-dasharray="6 3"
/>
```

- [ ] **Step 2: Add capture mode and dialog to ScanEditorPage**

Add state:
```javascript
const captureMode = ref(false);
const captureBox = ref(null);
const showCaptureDialog = ref(false);
const captureForm = ref({ name: "", category: "note", musicxml_element: "", height_in_lines: 4.0 });
```

Add handler:
```javascript
function onCaptureBox(box) {
  captureBox.value = box;
  showCaptureDialog.value = true;
}

async function saveCapturedTemplate() {
  if (!captureBox.value || !captureForm.value.name.trim()) return;
  await post("/scanner/library/templates/capture", {
    scan_id: parseInt(props.scanId),
    ...captureBox.value,
    name: captureForm.value.name.trim(),
    category: captureForm.value.category,
    musicxml_element: captureForm.value.musicxml_element || null,
    height_in_lines: captureForm.value.height_in_lines,
  });
  showCaptureDialog.value = false;
  captureMode.value = false;
  captureForm.value = { name: "", category: "note", musicxml_element: "", height_in_lines: 4.0 };
  // Refresh library
  const data = await get("/scanner/library/templates?limit=200");
  libraryTemplates.value = data.items || [];
}
```

Add to ScanCanvas props in template:
```html
:capture-mode="captureMode"
@capture-box="onCaptureBox"
```

Add toolbar button (in `.toolbar-extras`):
```html
<button
  class="btn btn-sm"
  :class="{ 'btn-active': captureMode }"
  @click="captureMode = !captureMode"
>
  {{ captureMode ? 'Erfassung beenden' : 'Vorlage erfassen' }}
</button>
```

Add capture dialog modal:
```html
<!-- Capture dialog -->
<div v-if="showCaptureDialog" class="modal-backdrop" @click.self="showCaptureDialog = false">
  <div class="modal">
    <h2>Vorlage erfassen</h2>
    <p class="capture-info">
      Ausschnitt: {{ captureBox?.width }}×{{ captureBox?.height }} px
    </p>
    <label>
      Name
      <input v-model="captureForm.name" type="text" placeholder="z.B. Viertelnote" />
    </label>
    <label>
      Kategorie
      <select v-model="captureForm.category">
        <option value="note">Note</option>
        <option value="rest">Pause</option>
        <option value="accidental">Vorzeichen</option>
        <option value="clef">Schlüssel</option>
        <option value="time_sig">Taktart</option>
        <option value="barline">Taktstrich</option>
        <option value="dynamic">Dynamik</option>
        <option value="ornament">Verzierung</option>
        <option value="other">Sonstiges</option>
      </select>
    </label>
    <label>
      Höhe in Notenlinien
      <input v-model.number="captureForm.height_in_lines" type="number" min="0.5" max="10" step="0.5" />
    </label>
    <label>
      MusicXML (optional)
      <textarea v-model="captureForm.musicxml_element" rows="3" placeholder="<note>...</note>" />
    </label>
    <div class="modal-actions">
      <button class="btn" @click="showCaptureDialog = false">Abbrechen</button>
      <button class="btn btn-primary" @click="saveCapturedTemplate" :disabled="!captureForm.name.trim()">
        Speichern
      </button>
    </div>
  </div>
</div>
```

Add styles for capture dialog form elements (add to existing `<style scoped>`):
```css
.capture-info {
  color: var(--color-muted);
  font-size: 0.85rem;
  margin-bottom: 1rem;
}

.modal label {
  display: block;
  margin-bottom: 0.75rem;
  font-size: 0.9rem;
  color: var(--color-muted);
}

.modal input,
.modal select,
.modal textarea {
  display: block;
  width: 100%;
  margin-top: 0.25rem;
  padding: 0.5rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  background: var(--color-bg);
  color: var(--color-text);
  font-family: inherit;
}

.modal-actions {
  display: flex;
  gap: 0.5rem;
  justify-content: flex-end;
  margin-top: 1rem;
}
```

- [ ] **Step 3: Also save adjustments (including threshold) to backend when analysis starts**

In `ScanEditorPage.vue`, update `startAnalysis` to save adjustments before triggering:

```javascript
async function startAnalysis() {
  if (processing.value) return;
  processing.value = true;
  statusMessage.value = "Analyse wird gestartet...";
  try {
    // Save current adjustments to the scan first
    if (scan.value) {
      // Find the part ID for this scan
      const partsData = await get(`/scanner/projects/${props.projectId}/parts`);
      for (const part of partsData) {
        const scansData = await get(`/scanner/projects/${props.projectId}/parts/${part.id}/scans`);
        const found = scansData.find((s) => String(s.id) === String(props.scanId));
        if (found) {
          await put(`/scanner/projects/${props.projectId}/parts/${part.id}/scans/${props.scanId}`, {
            adjustments_json: JSON.stringify(adjustments.value),
          });
          break;
        }
      }
    }
    await post(`/scanner/scans/${props.scanId}/process`, {});
    // ... rest of polling unchanged
```

- [ ] **Step 4: Verify frontend builds**

Run: `cd /workspaces/mv_hofki/src/frontend && npx vite build`
Expected: Build succeeds

- [ ] **Step 5: Commit**

```bash
git add src/frontend/src/components/ScanCanvas.vue src/frontend/src/pages/ScanEditorPage.vue
git commit -m "feat(scanner): add box drawing capture mode, capture dialog, and threshold-aware analysis"
```

---

### Task 9: Final verification

**Files:** None (verification only)

- [ ] **Step 1: Run backend tests**

Run: `cd /workspaces/mv_hofki && python -m pytest tests/backend/ -v`
Expected: All tests pass (previous + new template matching + capture tests)

- [ ] **Step 2: Run frontend build**

Run: `cd /workspaces/mv_hofki/src/frontend && npx vite build`
Expected: Build succeeds

- [ ] **Step 3: Run linters**

Run: `cd /workspaces/mv_hofki && pre-commit run --all-files`
Expected: All checks pass

- [ ] **Step 4: Final commit if lint fixes needed**

```bash
git add -A
git commit -m "chore: lint fixes for template matching feature"
```
