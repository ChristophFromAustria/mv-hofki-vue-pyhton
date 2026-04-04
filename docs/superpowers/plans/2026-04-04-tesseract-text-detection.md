# Tesseract Text Detection + UI Overlay Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the heuristic CC-clustering text detection with Tesseract's `image_to_data()`, persist results in a new DB table, expose via API, and render as a toggleable overlay in the frontend.

**Architecture:** `TextMaskingStage` is rewritten to call `pytesseract.image_to_data()` globally, replacing all CC-heuristic code. Results are persisted in `detected_text_regions` table (like measures), exposed via a new GET endpoint, and rendered as SVG rect+text overlays in `ScanCanvas.vue` with a toggle in `FilterDropdown.vue`.

**Tech Stack:** pytesseract, SQLAlchemy 2.0, Alembic, FastAPI, Pydantic, Vue 3, SVG

---

### Task 1: Add `confidence` field to TextRegionData

**Files:**
- Modify: `src/backend/mv_hofki/services/scanner/stages/base.py:64-73`
- Test: `tests/backend/test_pipeline_stages.py`

- [ ] **Step 1: Write failing test**

Add to `tests/backend/test_pipeline_stages.py`:

```python
def test_text_region_data_has_confidence_field():
    from mv_hofki.services.scanner.stages.base import TextRegionData

    region = TextRegionData(staff_index=0, x=10, y=20, width=50, height=15)
    assert region.confidence is None

    region_with_conf = TextRegionData(
        staff_index=0, x=10, y=20, width=50, height=15, confidence=92.5
    )
    assert region_with_conf.confidence == 92.5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/backend/test_pipeline_stages.py::test_text_region_data_has_confidence_field -v`
Expected: FAIL

- [ ] **Step 3: Add confidence field**

In `src/backend/mv_hofki/services/scanner/stages/base.py`, change `TextRegionData`:

```python
@dataclass
class TextRegionData:
    """Data for a detected text region."""

    staff_index: int
    x: int
    y: int
    width: int
    height: int
    text: str | None = None
    confidence: float | None = None
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/backend/test_pipeline_stages.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/backend/mv_hofki/services/scanner/stages/base.py tests/backend/test_pipeline_stages.py
git commit -m "feat: add confidence field to TextRegionData"
```

---

### Task 2: Rewrite TextMaskingStage to use Tesseract

**Files:**
- Modify: `src/backend/mv_hofki/services/scanner/stages/text_masking.py`
- Test: `tests/backend/test_text_masking.py`

- [ ] **Step 1: Write failing test for Tesseract-based detection**

Replace the entire content of `tests/backend/test_text_masking.py` with:

```python
"""Tests for the text masking pipeline stage."""

import numpy as np

from mv_hofki.services.scanner.stages.base import PipelineContext, StaffData


def _make_staff_image():
    """Create a binary image with staff lines."""
    img = np.full((300, 800), 255, dtype=np.uint8)
    for y in [50, 60, 70, 80, 90]:
        img[y : y + 2, 20:780] = 0
    staff = StaffData(
        staff_index=0,
        y_top=20,
        y_bottom=200,
        line_positions=[50, 60, 70, 80, 90],
        line_spacing=10.0,
    )
    return img, staff


def _mock_image_to_data(*_args, **_kwargs):
    """Return a fake Tesseract image_to_data result."""
    return {
        "left": [100, 250],
        "top": [120, 120],
        "width": [80, 40],
        "height": [15, 15],
        "text": ["cresc.", "Trio"],
        "conf": [85.0, 90.0],
    }


def _mock_image_to_data_empty(*_args, **_kwargs):
    """Return empty Tesseract result."""
    return {"left": [], "top": [], "width": [], "height": [], "text": [], "conf": []}


def test_text_masking_uses_tesseract(monkeypatch):
    from mv_hofki.services.scanner.stages import text_masking
    from mv_hofki.services.scanner.stages.text_masking import TextMaskingStage

    monkeypatch.setattr(text_masking, "_run_tesseract", _mock_image_to_data)

    img, staff = _make_staff_image()
    ctx = PipelineContext(image=img, processed_image=img.copy(), staves=[staff])

    stage = TextMaskingStage()
    result = stage.process(ctx)

    assert len(result.text_regions) == 2
    assert result.text_regions[0].text == "cresc."
    assert result.text_regions[0].confidence == 85.0
    assert result.text_regions[1].text == "Trio"
    assert result.text_regions[1].confidence == 90.0


def test_text_masking_masks_detected_regions(monkeypatch):
    from mv_hofki.services.scanner.stages import text_masking
    from mv_hofki.services.scanner.stages.text_masking import TextMaskingStage

    monkeypatch.setattr(text_masking, "_run_tesseract", _mock_image_to_data)

    img, staff = _make_staff_image()
    ctx = PipelineContext(image=img, processed_image=img.copy(), staves=[staff])

    stage = TextMaskingStage()
    result = stage.process(ctx)

    # Region at x=100, y=120, w=80, h=15 should be white
    region = result.processed_image[120:135, 100:180]
    assert np.all(region == 255)


def test_text_masking_assigns_nearest_staff(monkeypatch):
    from mv_hofki.services.scanner.stages import text_masking
    from mv_hofki.services.scanner.stages.text_masking import TextMaskingStage

    monkeypatch.setattr(text_masking, "_run_tesseract", _mock_image_to_data)

    img = np.full((500, 800), 255, dtype=np.uint8)
    staff0 = StaffData(
        staff_index=0, y_top=20, y_bottom=150,
        line_positions=[50, 60, 70, 80, 90], line_spacing=10.0,
    )
    staff1 = StaffData(
        staff_index=1, y_top=200, y_bottom=350,
        line_positions=[250, 260, 270, 280, 290], line_spacing=10.0,
    )
    ctx = PipelineContext(
        image=img, processed_image=img.copy(), staves=[staff0, staff1]
    )

    stage = TextMaskingStage()
    result = stage.process(ctx)

    # Mock data has y=120 which is closer to staff0 (center ~70) than staff1 (center ~270)
    for r in result.text_regions:
        assert r.staff_index == 0


def test_text_masking_filters_low_confidence(monkeypatch):
    from mv_hofki.services.scanner.stages import text_masking
    from mv_hofki.services.scanner.stages.text_masking import TextMaskingStage

    def mock_low_conf(*_args, **_kwargs):
        return {
            "left": [100, 250],
            "top": [120, 120],
            "width": [80, 40],
            "height": [15, 15],
            "text": ["noise", "real"],
            "conf": [10.0, 85.0],
        }

    monkeypatch.setattr(text_masking, "_run_tesseract", mock_low_conf)

    img, staff = _make_staff_image()
    ctx = PipelineContext(image=img, processed_image=img.copy(), staves=[staff])

    stage = TextMaskingStage()
    result = stage.process(ctx)

    assert len(result.text_regions) == 1
    assert result.text_regions[0].text == "real"


def test_text_masking_no_results_on_empty(monkeypatch):
    from mv_hofki.services.scanner.stages import text_masking
    from mv_hofki.services.scanner.stages.text_masking import TextMaskingStage

    monkeypatch.setattr(text_masking, "_run_tesseract", _mock_image_to_data_empty)

    img, staff = _make_staff_image()
    ctx = PipelineContext(image=img, processed_image=img.copy(), staves=[staff])

    stage = TextMaskingStage()
    result = stage.process(ctx)

    assert len(result.text_regions) == 0


def test_text_masking_validate():
    from mv_hofki.services.scanner.stages.text_masking import TextMaskingStage

    stage = TextMaskingStage()

    ctx = PipelineContext(image=None, processed_image=None)
    assert stage.validate(ctx) is False

    img = np.zeros((100, 100), dtype=np.uint8)
    ctx = PipelineContext(image=img, processed_image=img)
    assert stage.validate(ctx) is False

    staff = StaffData(
        staff_index=0, y_top=0, y_bottom=100,
        line_positions=[20, 30, 40, 50, 60], line_spacing=10.0,
    )
    ctx = PipelineContext(image=img, processed_image=img, staves=[staff])
    assert stage.validate(ctx) is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/backend/test_text_masking.py -v`
Expected: FAIL (functions not found)

- [ ] **Step 3: Rewrite text_masking.py**

Replace the entire content of `src/backend/mv_hofki/services/scanner/stages/text_masking.py`:

```python
"""Text masking: detect and remove text regions via Tesseract OCR."""

from __future__ import annotations

import cv2
import numpy as np
import pytesseract  # type: ignore[import-not-found]
from pytesseract import Output  # type: ignore[import-not-found]

from mv_hofki.services.scanner.stages.base import (
    PipelineContext,
    ProcessingStage,
    TextRegionData,
)

MIN_CONFIDENCE = 30


class TextMaskingStage(ProcessingStage):
    """Detect text regions via Tesseract and mask them in the binary image."""

    name = "text_masking"

    def process(self, ctx: PipelineContext) -> PipelineContext:
        binary = ctx.processed_image
        if binary is None:
            return ctx

        staves = sorted(ctx.staves, key=lambda s: s.staff_index)
        staff_centers = [
            (s.staff_index, float(np.mean(s.line_positions))) for s in staves
        ]

        data = _run_tesseract(binary)

        for i in range(len(data["text"])):
            conf = float(data["conf"][i])
            text = data["text"][i].strip()
            if conf < MIN_CONFIDENCE or not text:
                continue

            x = int(data["left"][i])
            y = int(data["top"][i])
            w = int(data["width"][i])
            h = int(data["height"][i])

            # Assign to nearest staff
            center_y = y + h / 2
            staff_idx = min(
                staff_centers, key=lambda sc: abs(sc[1] - center_y)
            )[0]

            ctx.text_regions.append(
                TextRegionData(
                    staff_index=staff_idx,
                    x=x,
                    y=y,
                    width=w,
                    height=h,
                    text=text,
                    confidence=conf,
                )
            )

        # Mask detected text regions in the binary image
        for region in ctx.text_regions:
            binary[
                region.y : region.y + region.height,
                region.x : region.x + region.width,
            ] = 255

        ctx.log(
            f"Text-Maskierung: {len(ctx.text_regions)} Textregionen "
            f"in {len(staves)} Systemen erkannt"
        )
        return ctx

    def validate(self, ctx: PipelineContext) -> bool:
        return ctx.processed_image is not None and len(ctx.staves) > 0


def _run_tesseract(binary: np.ndarray) -> dict:
    """Run Tesseract on the full image and return word-level data."""
    inverted = cv2.bitwise_not(binary)
    return pytesseract.image_to_data(
        inverted, lang="deu", config="--psm 6", output_type=Output.DICT
    )
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/backend/test_text_masking.py -v`
Expected: all 6 tests PASS

- [ ] **Step 5: Run linter**

Run: `pre-commit run --files src/backend/mv_hofki/services/scanner/stages/text_masking.py`

- [ ] **Step 6: Commit**

```bash
git add src/backend/mv_hofki/services/scanner/stages/text_masking.py tests/backend/test_text_masking.py
git commit -m "feat: rewrite TextMaskingStage to use Tesseract image_to_data"
```

---

### Task 3: Create DB model, schema, and migration

**Files:**
- Create: `src/backend/mv_hofki/models/detected_text_region.py`
- Create: `src/backend/mv_hofki/schemas/detected_text_region.py`
- Create: `alembic/versions/..._add_detected_text_regions.py`

- [ ] **Step 1: Create DB model**

Create `src/backend/mv_hofki/models/detected_text_region.py`:

```python
"""DetectedTextRegion ORM model."""

from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from mv_hofki.db.base import Base


class DetectedTextRegion(Base):
    __tablename__ = "detected_text_regions"

    id: Mapped[int] = mapped_column(primary_key=True)
    scan_id: Mapped[int] = mapped_column(
        ForeignKey("sheet_music_scans.id", ondelete="CASCADE"), nullable=False
    )
    staff_index: Mapped[int] = mapped_column(Integer, nullable=False)
    x: Mapped[int] = mapped_column(Integer, nullable=False)
    y: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str | None] = mapped_column(String(500))
    confidence: Mapped[float | None] = mapped_column(Float)
```

- [ ] **Step 2: Create Pydantic schema**

Create `src/backend/mv_hofki/schemas/detected_text_region.py`:

```python
"""DetectedTextRegion Pydantic schemas."""

from __future__ import annotations

from pydantic import BaseModel


class DetectedTextRegionRead(BaseModel):
    id: int
    scan_id: int
    staff_index: int
    x: int
    y: int
    width: int
    height: int
    text: str | None
    confidence: float | None

    model_config = {"from_attributes": True}
```

- [ ] **Step 3: Generate Alembic migration**

Run: `PYTHONPATH=src/backend alembic revision --autogenerate -m "add detected_text_regions table"`

If autogenerate doesn't pick up the model, check that it's imported in the alembic env.py or models `__init__.py`. You may need to add `from mv_hofki.models.detected_text_region import DetectedTextRegion` to `src/backend/mv_hofki/models/__init__.py` (or wherever models are collected).

- [ ] **Step 4: Run migration**

Run: `PYTHONPATH=src/backend alembic upgrade head`
Expected: migration applies successfully

- [ ] **Step 5: Verify table exists**

Run: `python -c "import sqlite3; c=sqlite3.connect('data/mv_hofki.db'); print([r[0] for r in c.execute(\"SELECT name FROM sqlite_master WHERE type='table' AND name='detected_text_regions'\").fetchall()])"`
Expected: `['detected_text_regions']`

- [ ] **Step 6: Run linter**

Run: `pre-commit run --files src/backend/mv_hofki/models/detected_text_region.py src/backend/mv_hofki/schemas/detected_text_region.py`

- [ ] **Step 7: Commit**

```bash
git add src/backend/mv_hofki/models/detected_text_region.py src/backend/mv_hofki/schemas/detected_text_region.py alembic/versions/*detected_text_regions*.py
git commit -m "feat: add detected_text_regions DB table, model, and schema"
```

---

### Task 4: Persist text regions and add API endpoint

**Files:**
- Modify: `src/backend/mv_hofki/services/sheet_music_scan.py`
- Modify: `src/backend/mv_hofki/api/routes/scan_processing.py`

- [ ] **Step 1: Add text region persistence to sheet_music_scan.py**

In `src/backend/mv_hofki/services/sheet_music_scan.py`, find the block where debug lines are saved (around line 385, after `(scan_dir / "hairpin_debug.json").write_text(...)`). Add after it:

```python
    # Persist text regions
    from mv_hofki.models.detected_text_region import DetectedTextRegion

    await session.execute(
        sa_select(DetectedTextRegion)
        .where(DetectedTextRegion.scan_id == scan_id)
        .execution_options(synchronize_session="fetch")
    )
    # Delete old text regions for this scan
    from sqlalchemy import delete

    await session.execute(
        delete(DetectedTextRegion).where(DetectedTextRegion.scan_id == scan_id)
    )

    for tr in ctx.text_regions:
        session.add(
            DetectedTextRegion(
                scan_id=scan_id,
                staff_index=tr.staff_index,
                x=tr.x,
                y=tr.y,
                width=tr.width,
                height=tr.height,
                text=tr.text,
                confidence=tr.confidence,
            )
        )
```

- [ ] **Step 2: Add API endpoint**

In `src/backend/mv_hofki/api/routes/scan_processing.py`, add the endpoint (near the other scan data endpoints, e.g. after the measures endpoint around line 390):

```python
@router.get(
    "/scans/{scan_id}/text-regions",
    response_model=list[DetectedTextRegionRead],
)
async def get_detected_text_regions(
    scan_id: int, db: AsyncSession = Depends(get_db)
):
    """Get all detected text regions for a scan."""
    from sqlalchemy import select

    from mv_hofki.models.detected_text_region import DetectedTextRegion
    from mv_hofki.models.sheet_music_scan import SheetMusicScan
    from mv_hofki.schemas.detected_text_region import DetectedTextRegionRead  # noqa: F811

    scan = await db.get(SheetMusicScan, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan nicht gefunden")

    result = await db.execute(
        select(DetectedTextRegion)
        .where(DetectedTextRegion.scan_id == scan_id)
        .order_by(DetectedTextRegion.x)
    )
    return list(result.scalars().all())
```

Add the import for `DetectedTextRegionRead` at the top of the file with the other schema imports.

- [ ] **Step 3: Run linter**

Run: `pre-commit run --files src/backend/mv_hofki/services/sheet_music_scan.py src/backend/mv_hofki/api/routes/scan_processing.py`

- [ ] **Step 4: Commit**

```bash
git add src/backend/mv_hofki/services/sheet_music_scan.py src/backend/mv_hofki/api/routes/scan_processing.py
git commit -m "feat: persist text regions to DB and add API endpoint"
```

---

### Task 5: Frontend — text overlay in ScanCanvas.vue

**Files:**
- Modify: `src/frontend/src/components/ScanCanvas.vue`

- [ ] **Step 1: Add props**

In `ScanCanvas.vue`, add to the `defineProps` block (around line 20, after `hairpinDebugLines`):

```javascript
  textRegions: { type: Array, default: () => [] },
  showTextRegions: { type: Boolean, default: true },
```

- [ ] **Step 2: Add SVG overlay**

In `ScanCanvas.vue`, after the hairpin debug lines template block (around line 546), add:

```vue
    <!-- Text region overlay -->
    <template v-if="showTextRegions && textRegions.length">
      <g
        v-for="(tr, idx) in textRegions"
        :key="`tr-${idx}`"
      >
        <rect
          :x="tr.x"
          :y="tr.y"
          :width="tr.width"
          :height="tr.height"
          fill="#10b981"
          fill-opacity="0.15"
          stroke="#10b981"
          stroke-width="1"
          opacity="0.8"
        />
        <text
          :x="tr.x + 2"
          :y="tr.y + tr.height - 2"
          fill="#10b981"
          font-size="10"
          opacity="0.9"
        >{{ tr.text }}</text>
      </g>
    </template>
```

- [ ] **Step 3: Run linter**

Run: `cd src/frontend && npx eslint src/components/ScanCanvas.vue && cd ../..`

- [ ] **Step 4: Commit**

```bash
git add src/frontend/src/components/ScanCanvas.vue
git commit -m "feat: add text region overlay to ScanCanvas"
```

---

### Task 6: Frontend — fetch data and add filter toggle

**Files:**
- Modify: `src/frontend/src/pages/ScanEditorPage.vue`
- Modify: `src/frontend/src/components/FilterDropdown.vue`

- [ ] **Step 1: Add state and fetch in ScanEditorPage.vue**

In `ScanEditorPage.vue`, after `const hairpinDebugLines = ref([]);` (line 41), add:

```javascript
const textRegions = ref([]);
const showTextRegions = ref(true);
```

In the `fetchScanData()` function, in the `Promise.all` array (around line 84), add a new fetch:

```javascript
    get(`/scanner/scans/${props.scanId}/text-regions`).catch(() => []),
```

And after `hairpinDebugLines.value = hairpinLinesData || [];` (around line 108), add:

```javascript
textRegions.value = textRegionsData || [];
```

Make sure to destructure the new value from `Promise.all` — update the destructuring to include it.

Do the same in `onAnalysisDone()` (around line 203) — add the text-regions fetch there too.

- [ ] **Step 2: Pass props to ScanCanvas**

In the `<ScanCanvas>` template (around line 631), add:

```vue
            :text-regions="textRegions"
            :show-text-regions="showTextRegions"
```

- [ ] **Step 3: Add toggle to FilterDropdown.vue**

In `FilterDropdown.vue`, add new prop and emit:

Props (after `showVoltas`):
```javascript
  showTextRegions: { type: Boolean, default: true },
```

Emits (add to `defineEmits` array):
```javascript
  "update:showTextRegions",
```

In the template, after the "Volta-Klammern anzeigen" checkbox (around line 133), add:

```vue
        <label class="filter-item">
          <span class="filter-label">Text anzeigen</span>
          <input
            type="checkbox"
            :checked="showTextRegions"
            @change="emit('update:showTextRegions', $event.target.checked)"
          />
        </label>
```

- [ ] **Step 4: Wire FilterDropdown props in ScanEditorPage.vue**

In the `<FilterDropdown>` template, add:

```vue
              :show-text-regions="showTextRegions"
              @update:show-text-regions="showTextRegions = $event"
```

- [ ] **Step 5: Run frontend linter**

Run: `cd src/frontend && npx eslint src/pages/ScanEditorPage.vue src/components/FilterDropdown.vue src/components/ScanCanvas.vue && cd ../..`

- [ ] **Step 6: Commit**

```bash
git add src/frontend/src/pages/ScanEditorPage.vue src/frontend/src/components/FilterDropdown.vue
git commit -m "feat: fetch text regions and add filter toggle in UI"
```

---

### Task 7: Manual verification with "47er Regimentsmarsch - Tuba 1"

**Files:** none (manual test via UI)

- [ ] **Step 1: Restart the backend server**

Run: `tmux send-keys -t server C-c && sleep 1 && tmux send-keys -t server 'PYTHONPATH=src/backend python -m uvicorn mv_hofki.api.app:app --host 0.0.0.0 --port 8000 --reload' Enter`

- [ ] **Step 2: Run a scan on "47er Regimentsmarsch - Tuba 1" via the UI**

- [ ] **Step 3: Verify results**

1. No musical symbols are deleted from the binary image
2. Text regions overlay shows green boxes with recognized text content
3. "Trio" is recognized and visible in the overlay
4. Copyright and "bearb." text are recognized
5. Toggle "Text anzeigen" in filter dropdown hides/shows the overlay
6. Hairpin detection still finds 4 Crescendo/Decrescendo
