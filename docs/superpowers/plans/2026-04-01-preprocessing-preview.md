# Preprocessing Preview & Adjustments Rework — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a lightweight preprocessing preview endpoint, restructure `adjustments_json` into grouped format, wire all adjustment values into the pipeline, and remove the unused "Korrigiert" view.

**Architecture:** Data migration converts flat JSON to `{ preprocessing: { ... } }` structure. New `POST /preview` endpoint runs only `PreprocessStage` and returns the processed image path. Frontend adds morphology slider, preview button, and loads saved values into controls.

**Tech Stack:** FastAPI, SQLAlchemy/Alembic, OpenCV, Vue 3

---

### Task 1: Alembic data migration — restructure `adjustments_json`

**Files:**
- Create: `alembic/versions/XXXX_restructure_adjustments_json.py` (auto-generated)

- [ ] **Step 1: Generate migration**

```bash
cd /workspaces/mv_hofki
PYTHONPATH=src/backend alembic revision -m "restructure_adjustments_json_to_grouped_format"
```

- [ ] **Step 2: Write the migration**

In the generated file, replace the `upgrade()` and `downgrade()` functions:

```python
"""restructure adjustments_json to grouped format"""

import json

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "<auto>"
down_revision = "<auto>"
branch_labels = None
depends_on = None

# Ad-hoc table reference for data migration
t_scans = sa.table(
    "sheet_music_scans",
    sa.column("id", sa.Integer),
    sa.column("adjustments_json", sa.Text),
)

PREPROCESSING_KEYS = {"brightness", "contrast", "threshold", "rotation", "morphology_kernel_size"}


def upgrade() -> None:
    conn = op.get_bind()
    rows = conn.execute(
        sa.select(t_scans.c.id, t_scans.c.adjustments_json).where(
            t_scans.c.adjustments_json.isnot(None)
        )
    ).fetchall()

    for row_id, raw in rows:
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue

        # Already migrated
        if "preprocessing" in data:
            continue

        preprocessing = {}
        leftover = {}
        for k, v in data.items():
            if k in PREPROCESSING_KEYS:
                preprocessing[k] = v
            else:
                leftover[k] = v

        new_data = {"preprocessing": preprocessing, **leftover}
        conn.execute(
            t_scans.update()
            .where(t_scans.c.id == row_id)
            .values(adjustments_json=json.dumps(new_data))
        )


def downgrade() -> None:
    conn = op.get_bind()
    rows = conn.execute(
        sa.select(t_scans.c.id, t_scans.c.adjustments_json).where(
            t_scans.c.adjustments_json.isnot(None)
        )
    ).fetchall()

    for row_id, raw in rows:
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue

        if "preprocessing" not in data:
            continue

        preprocessing = data.pop("preprocessing", {})
        flat = {**preprocessing, **data}
        conn.execute(
            t_scans.update()
            .where(t_scans.c.id == row_id)
            .values(adjustments_json=json.dumps(flat))
        )
```

- [ ] **Step 3: Run migration**

```bash
PYTHONPATH=src/backend alembic upgrade head
```

Expected: migration completes, any existing `adjustments_json` values are now wrapped in `{ "preprocessing": { ... } }`.

- [ ] **Step 4: Verify**

```bash
cd /workspaces/mv_hofki
python -c "
import sqlite3, json
conn = sqlite3.connect('data/mv_hofki.db')
rows = conn.execute('SELECT id, adjustments_json FROM sheet_music_scans WHERE adjustments_json IS NOT NULL').fetchall()
for r in rows:
    data = json.loads(r[1])
    assert 'preprocessing' in data, f'Scan {r[0]} not migrated: {data}'
    print(f'Scan {r[0]}: {data}')
print('All OK' if rows else 'No rows with adjustments')
"
```

- [ ] **Step 5: Commit**

```bash
git add alembic/versions/*restructure_adjustments_json*
git commit -m "migrate: restructure adjustments_json into grouped preprocessing format"
```

---

### Task 2: Add rotation to `PreprocessStage`

**Files:**
- Modify: `src/backend/mv_hofki/services/scanner/stages/preprocess.py:21-72`
- Test: `tests/backend/test_preprocess.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/backend/test_preprocess.py`:

```python
"""Tests for PreprocessStage — rotation support."""

import numpy as np

from mv_hofki.services.scanner.stages.base import PipelineContext
from mv_hofki.services.scanner.stages.preprocess import PreprocessStage


def _make_ctx(img: np.ndarray, **config_overrides) -> PipelineContext:
    config = {"deskew_method": "none", "morphology_kernel_size": 1, **config_overrides}
    return PipelineContext(image=img, config=config)


def test_rotation_90_rotates_image():
    """A 100x200 image rotated 90° CW becomes 200x100."""
    img = np.full((100, 200), 200, dtype=np.uint8)
    # Draw a marker in top-left corner
    img[0:10, 0:10] = 0

    ctx = _make_ctx(img, rotation=90, threshold=128)
    result = PreprocessStage().process(ctx)

    assert result.processed_image.shape == (200, 100), (
        f"Expected (200, 100), got {result.processed_image.shape}"
    )


def test_rotation_0_no_change():
    """No rotation leaves dimensions unchanged."""
    img = np.full((100, 200), 200, dtype=np.uint8)
    ctx = _make_ctx(img, rotation=0, threshold=128)
    result = PreprocessStage().process(ctx)
    assert result.processed_image.shape[0] == 100
    assert result.processed_image.shape[1] == 200


def test_rotation_not_set_no_change():
    """Missing rotation config leaves dimensions unchanged."""
    img = np.full((100, 200), 200, dtype=np.uint8)
    ctx = _make_ctx(img, threshold=128)
    result = PreprocessStage().process(ctx)
    assert result.processed_image.shape[0] == 100
    assert result.processed_image.shape[1] == 200
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /workspaces/mv_hofki
python -m pytest tests/backend/test_preprocess.py -v
```

Expected: `test_rotation_90_rotates_image` FAILS (rotation not implemented yet).

- [ ] **Step 3: Implement rotation in PreprocessStage**

Edit `src/backend/mv_hofki/services/scanner/stages/preprocess.py`. Replace the `process` method body (lines 21–72):

```python
    def process(self, ctx: PipelineContext) -> PipelineContext:
        assert ctx.image is not None
        img = ctx.image
        ctx.original_image = img.copy()

        # Apply 90-degree rotation if configured
        rotation = ctx.config.get("rotation", 0)
        rotate_map = {
            90: cv2.ROTATE_90_CLOCKWISE,
            180: cv2.ROTATE_180,
            270: cv2.ROTATE_90_COUNTERCLOCKWISE,
        }
        if rotation in rotate_map:
            img = cv2.rotate(img, rotate_map[rotation])

        # Convert to grayscale if needed
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            gray = img.copy()

        # Apply brightness/contrast adjustments from config
        brightness = ctx.config.get("brightness", 0)
        contrast = ctx.config.get("contrast", 1.0)
        if brightness != 0 or contrast != 1.0:
            gray = cv2.convertScaleAbs(gray, alpha=contrast, beta=brightness)

        # Binarize: use global threshold if provided, otherwise adaptive
        threshold_val = ctx.config.get("threshold")
        if threshold_val is not None:
            _, binary = cv2.threshold(gray, int(threshold_val), 255, cv2.THRESH_BINARY)
        else:
            block_size = ctx.config.get("adaptive_threshold_block_size", 15)
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

        # Deskew using configured strategy
        method = ctx.config.get("deskew_method", "none")
        deskew_fn = _DESKEW_STRATEGIES.get(method)
        if deskew_fn is not None:
            binary = deskew_fn(binary)
            ctx.log(f"Deskew angewendet (Methode: {method})")

        # Morphological noise removal
        k_size = ctx.config.get("morphology_kernel_size", 2)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k_size, k_size))
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)

        ctx.processed_image = binary
        ctx.image = binary
        return ctx
```

Key changes vs. original:
- Added rotation block at the top (before grayscale conversion)
- Removed `ctx.corrected_image = deskew_fn(gray)` (the duplicate deskew on grayscale)

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/backend/test_preprocess.py -v
```

Expected: all 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/backend/mv_hofki/services/scanner/stages/preprocess.py tests/backend/test_preprocess.py
git commit -m "feat: add rotation support to PreprocessStage, remove duplicate deskew"
```

---

### Task 3: Fix `run_pipeline()` to merge all preprocessing values

**Files:**
- Modify: `src/backend/mv_hofki/services/sheet_music_scan.py:196-199` and `316-322`

- [ ] **Step 1: Write the failing test**

Create `tests/backend/test_pipeline_config_merge.py`:

```python
"""Tests for adjustment merging in run_pipeline config assembly."""

import json


def test_preprocessing_values_merged():
    """All preprocessing keys should be extracted from the grouped JSON."""
    adjustments_json = json.dumps({
        "preprocessing": {
            "brightness": 10,
            "contrast": 1.5,
            "threshold": 140,
            "rotation": 90,
            "morphology_kernel_size": 3,
        }
    })
    adjustments = json.loads(adjustments_json)
    preprocessing = adjustments.get("preprocessing", {})

    config = {"brightness": 0, "contrast": 1.0, "morphology_kernel_size": 2}
    for key in ("brightness", "contrast", "threshold", "rotation", "morphology_kernel_size"):
        if key in preprocessing:
            config[key] = preprocessing[key]

    assert config["brightness"] == 10
    assert config["contrast"] == 1.5
    assert config["threshold"] == 140
    assert config["rotation"] == 90
    assert config["morphology_kernel_size"] == 3


def test_empty_adjustments_keeps_defaults():
    """Missing adjustments_json should not override config defaults."""
    adjustments_json = None
    adjustments = json.loads(adjustments_json) if adjustments_json else {}
    preprocessing = adjustments.get("preprocessing", {})

    config = {"brightness": 0, "contrast": 1.0, "morphology_kernel_size": 2}
    for key in ("brightness", "contrast", "threshold", "rotation", "morphology_kernel_size"):
        if key in preprocessing:
            config[key] = preprocessing[key]

    assert config["brightness"] == 0
    assert config["contrast"] == 1.0
    assert "threshold" not in config
    assert "rotation" not in config
    assert config["morphology_kernel_size"] == 2
```

- [ ] **Step 2: Run test to verify it passes**

```bash
python -m pytest tests/backend/test_pipeline_config_merge.py -v
```

Expected: PASS (this tests the logic pattern, not yet the integration).

- [ ] **Step 3: Update `run_pipeline()` config merging**

Edit `src/backend/mv_hofki/services/sheet_music_scan.py`. Replace lines 196–199:

```python
    # Merge scan-level adjustments (user threshold from UI)
    adjustments = json.loads(scan.adjustments_json) if scan.adjustments_json else {}
    if "threshold" in adjustments:
        config["threshold"] = adjustments["threshold"]
```

With:

```python
    # Merge scan-level preprocessing adjustments into pipeline config
    adjustments = json.loads(scan.adjustments_json) if scan.adjustments_json else {}
    preprocessing = adjustments.get("preprocessing", {})
    for key in ("brightness", "contrast", "threshold", "rotation", "morphology_kernel_size"):
        if key in preprocessing:
            config[key] = preprocessing[key]
```

- [ ] **Step 4: Remove corrected image saving**

Edit `src/backend/mv_hofki/services/sheet_music_scan.py`. Delete lines 316–322:

```python
    # Save corrected (rotated grayscale) image for frontend preview
    if ctx.corrected_image is not None:
        corrected_path = _scan_dir(project_id, part_id, scan_id) / "corrected.png"
        cv2.imwrite(str(corrected_path), ctx.corrected_image)
        scan.corrected_image_path = str(
            corrected_path.relative_to(settings.PROJECT_ROOT)
        )
```

- [ ] **Step 5: Run existing tests**

```bash
python -m pytest tests/backend/ -v -k "scan"
```

Expected: existing scan tests still pass.

- [ ] **Step 6: Commit**

```bash
git add src/backend/mv_hofki/services/sheet_music_scan.py tests/backend/test_pipeline_config_merge.py
git commit -m "fix: merge all preprocessing adjustments into pipeline config, drop corrected image"
```

---

### Task 4: Add preview endpoint

**Files:**
- Modify: `src/backend/mv_hofki/api/routes/scan_processing.py`
- Modify: `src/backend/mv_hofki/services/sheet_music_scan.py`

- [ ] **Step 1: Add `run_preview()` service function**

Add at the end of `src/backend/mv_hofki/services/sheet_music_scan.py` (after `run_pipeline`):

```python
async def run_preview(
    session: AsyncSession,
    scan_id: int,
    adjustments_json: str | None = None,
) -> str:
    """Run only preprocessing and return the processed image path.

    Saves the adjustments and the resulting binary image but does NOT
    run stave detection, template matching, or any later pipeline stages.
    """
    import json

    import cv2

    from mv_hofki.services.scanner.stages.base import PipelineContext
    from mv_hofki.services.scanner.stages.preprocess import PreprocessStage
    from mv_hofki.services.scanner_config import get_effective_config

    scan = await session.get(SheetMusicScan, scan_id)
    if scan is None:
        raise HTTPException(status_code=404, detail="Scan nicht gefunden")

    # Persist adjustments
    if adjustments_json is not None:
        scan.adjustments_json = adjustments_json

    img_path = settings.PROJECT_ROOT / scan.image_path
    img = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise HTTPException(status_code=400, detail="Bild konnte nicht geladen werden")

    # Build config: global defaults + scan-level preprocessing overrides
    config = await get_effective_config(session)
    adjustments = json.loads(scan.adjustments_json) if scan.adjustments_json else {}
    preprocessing = adjustments.get("preprocessing", {})
    for key in ("brightness", "contrast", "threshold", "rotation", "morphology_kernel_size"):
        if key in preprocessing:
            config[key] = preprocessing[key]

    ctx = PipelineContext(image=img, config=config)
    ctx = PreprocessStage().process(ctx)

    # Resolve scan directory from existing image path
    part = await session.get(
        __import__("mv_hofki.models.scan_part", fromlist=["ScanPart"]).ScanPart,
        scan.part_id,
    )
    scan_dir = _scan_dir(part.project_id, part.id, scan.id)
    scan_dir.mkdir(parents=True, exist_ok=True)

    processed_path = scan_dir / "processed.png"
    cv2.imwrite(str(processed_path), ctx.processed_image)
    scan.processed_image_path = str(processed_path.relative_to(settings.PROJECT_ROOT))

    await session.commit()
    return scan.processed_image_path
```

- [ ] **Step 2: Add the route**

Add in `src/backend/mv_hofki/api/routes/scan_processing.py`, after the existing `/scans/{scan_id}/process` route (after line 65):

```python
class PreviewRequest(BaseModel):
    adjustments_json: str | None = None


@router.post("/scans/{scan_id}/preview")
async def preview_preprocessing(
    scan_id: int,
    body: PreviewRequest | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Run only preprocessing and return the processed image path."""
    adjustments = body.adjustments_json if body else None
    path = await scan_service.run_preview(db, scan_id, adjustments_json=adjustments)
    return {"processed_image_path": path}
```

Add `BaseModel` to the pydantic import at the top of the file:

```python
from pydantic import BaseModel
```

- [ ] **Step 3: Fix the import in `run_preview`**

The `__import__` pattern is fragile. Instead, add a proper import. In `run_preview`, replace:

```python
    part = await session.get(
        __import__("mv_hofki.models.scan_part", fromlist=["ScanPart"]).ScanPart,
        scan.part_id,
    )
```

With:

```python
    from mv_hofki.models.scan_part import ScanPart

    part = await session.get(ScanPart, scan.part_id)
```

- [ ] **Step 4: Test the endpoint manually**

```bash
server-restart
# Wait a few seconds, then test with an existing scan ID (replace 1 with a real ID):
curl -s -X POST http://localhost:8000/api/v1/scanner/scans/1/preview \
  -H "Content-Type: application/json" \
  -d '{"adjustments_json": "{\"preprocessing\": {\"brightness\": 0, \"contrast\": 1.0, \"threshold\": 128, \"rotation\": 0, \"morphology_kernel_size\": 2}}"}' | python -m json.tool
```

Expected: `{ "processed_image_path": "data/scans/..." }`

- [ ] **Step 5: Commit**

```bash
git add src/backend/mv_hofki/services/sheet_music_scan.py src/backend/mv_hofki/api/routes/scan_processing.py
git commit -m "feat: add lightweight preview endpoint for preprocessing-only pipeline"
```

---

### Task 5: Frontend — Update `ImageAdjustBar` with morphology slider and preview button

**Files:**
- Modify: `src/frontend/src/components/ImageAdjustBar.vue`

- [ ] **Step 1: Add morphology slider, initialValues prop, and preview event**

Replace the full `<script setup>` section of `src/frontend/src/components/ImageAdjustBar.vue`:

```js
<script setup>
import { ref, watch } from "vue";

const props = defineProps({
  zoomLevel: { type: Number, default: 1.0 },
  initialValues: {
    type: Object,
    default: () => null,
  },
});

const emit = defineEmits(["adjust", "analyze", "preview", "zoom-in", "zoom-out"]);

const brightness = ref(props.initialValues?.brightness ?? 0);
const contrast = ref(props.initialValues?.contrast ?? 1.0);
const rotation = ref(props.initialValues?.rotation ?? 0);
const threshold = ref(props.initialValues?.threshold ?? 128);
const morphologyKernelSize = ref(props.initialValues?.morphology_kernel_size ?? 2);

function emitAdjust() {
  emit("adjust", {
    preprocessing: {
      brightness: brightness.value,
      contrast: contrast.value,
      rotation: rotation.value,
      threshold: threshold.value,
      morphology_kernel_size: morphologyKernelSize.value,
    },
  });
}

function rotate(deg) {
  rotation.value = (((rotation.value + deg) % 360) + 360) % 360;
  emitAdjust();
}

watch([brightness, contrast, threshold, morphologyKernelSize], emitAdjust);
</script>
```

- [ ] **Step 2: Add morphology slider and preview button to the template**

In the `<template>` section, add the morphology slider after the threshold slider (after the `Schwellwert` group, before the rotation group):

```html
    <div class="adjust-group">
      <label class="adjust-label">
        Rauschfilter
        <span class="adjust-value">{{ morphologyKernelSize }}</span>
      </label>
      <input
        v-model.number="morphologyKernelSize"
        type="range"
        min="1"
        max="5"
        step="1"
        class="adjust-slider"
      />
    </div>
```

Replace the "Analyse starten" button:

```html
    <button class="btn btn-secondary" @click="emit('preview')">Vorschau</button>
    <button class="btn btn-primary" @click="emit('analyze')">Analyse starten</button>
```

- [ ] **Step 3: Verify build**

```bash
frontend-logs
```

Expected: no build errors.

- [ ] **Step 4: Commit**

```bash
git add src/frontend/src/components/ImageAdjustBar.vue
git commit -m "feat: add morphology kernel slider, preview button, and initialValues prop"
```

---

### Task 6: Frontend — Wire preview into `ScanEditorPage` and remove "Korrigiert"

**Files:**
- Modify: `src/frontend/src/pages/ScanEditorPage.vue`
- Modify: `src/frontend/src/components/ScanCanvas.vue`

- [ ] **Step 1: Update adjustments structure and loading in `ScanEditorPage.vue`**

Replace the `adjustments` ref (line 26):

```js
const adjustments = ref({ preprocessing: { brightness: 0, contrast: 1.0, rotation: 0, threshold: 128, morphology_kernel_size: 2 } });
```

Replace the `initialValues` computed (add after `adjustments` ref):

```js
const initialPreprocessing = computed(() => adjustments.value.preprocessing ?? null);
```

Replace the loading logic (lines 90–96). Change:

```js
    if (foundScan?.adjustments_json) {
      try {
        adjustments.value = JSON.parse(foundScan.adjustments_json);
      } catch {
        // ignore parse errors
      }
    }
```

To:

```js
    if (foundScan?.adjustments_json) {
      try {
        const parsed = JSON.parse(foundScan.adjustments_json);
        adjustments.value = parsed;
      } catch {
        // ignore parse errors
      }
    }
```

(This stays functionally the same — the new grouped structure is already what gets saved.)

- [ ] **Step 2: Add preview handler**

Add after `onAdjust` function (after line 192):

```js
async function startPreview() {
  if (processing.value) return;
  try {
    const result = await post(`/scanner/scans/${props.scanId}/preview`, {
      adjustments_json: JSON.stringify(adjustments.value),
    });
    if (result.processed_image_path && scan.value) {
      scan.value.processed_image_path = result.processed_image_path;
    }
    viewMode.value = "binary";
    showStaves.value = false;
  } catch (e) {
    statusMessage.value = `Vorschau-Fehler: ${e.message}`;
  }
}
```

Also add `showStaves` ref if it doesn't exist (check current code — it's used in `:show-staves`). It already exists.

- [ ] **Step 3: Remove "Korrigiert" button from template**

Delete the "Korrigiert" button block (lines 483–490):

```html
              <button
                class="btn btn-sm"
                :class="{ 'btn-active': viewMode === 'corrected' }"
                :disabled="!scan?.corrected_image_path"
                @click="viewMode = 'corrected'"
              >
                Korrigiert
              </button>
```

- [ ] **Step 4: Update `ImageAdjustBar` usage in template**

Find the `<ImageAdjustBar` component in the template and add the new props/events:

```html
          <ImageAdjustBar
            :zoom-level="currentZoom"
            :initial-values="initialPreprocessing"
            @adjust="onAdjust"
            @analyze="startAnalysis"
            @preview="startPreview"
            @zoom-in="onZoomIn"
            @zoom-out="onZoomOut"
          />
```

- [ ] **Step 5: Remove `corrected-image-path` from ScanCanvas usage**

In the `<ScanCanvas>` tag (around line 518–533), remove the `:corrected-image-path` prop:

```html
          <ScanCanvas
            ref="scanCanvasRef"
            :image-path="scan?.image_path ?? null"
            :processed-image-path="scan?.processed_image_path ?? null"
            :staves="staves"
            :symbols="filteredSymbols"
            :adjustments="adjustments"
            :selected-symbol-id="selectedSymbol?.id ?? null"
            :show-staves="showStaves"
            :show-symbols="true"
            :capture-mode="captureMode"
            :view-mode="viewMode"
            @select-symbol="onSelectSymbol"
            @capture-box="onCaptureBox"
          />
```

- [ ] **Step 6: Update ScanCanvas.vue — remove corrected view**

Edit `src/frontend/src/components/ScanCanvas.vue`.

Remove the `correctedImagePath` prop (line 6):

```js
  correctedImagePath: { type: String, default: null },
```

Update `activeImageUrl` computed (lines 31–39). Replace:

```js
const activeImageUrl = computed(() => {
  if (props.viewMode === "corrected" && props.correctedImagePath) {
    return resolveImageUrl(props.correctedImagePath);
  }
  if (props.viewMode === "binary" && props.processedImagePath) {
    return resolveImageUrl(props.processedImagePath);
  }
  return resolveImageUrl(props.imagePath);
});
```

With:

```js
const activeImageUrl = computed(() => {
  if (props.viewMode === "binary" && props.processedImagePath) {
    return resolveImageUrl(props.processedImagePath);
  }
  return resolveImageUrl(props.imagePath);
});
```

- [ ] **Step 7: Update threshold preview to use nested structure**

In `ScanCanvas.vue`, `applyThreshold()` reads `props.adjustments.threshold` (line 117). Update to:

```js
  const t = props.adjustments.preprocessing?.threshold ?? props.adjustments.threshold ?? 128;
```

And the watcher (line 132–135):

```js
watch(
  () => props.adjustments.preprocessing?.threshold ?? props.adjustments.threshold,
  () => {
    if (props.viewMode === "original") applyThreshold();
  },
);
```

This is backwards-compatible with both old and new structures during the transition.

- [ ] **Step 8: Verify build and test manually**

```bash
frontend-logs
```

Expected: no build errors. Open the scan editor in the browser, verify:
- Morphology slider is visible
- "Vorschau" button triggers preview and switches to binary view
- "Korrigiert" button is gone
- Saved slider values load correctly when reopening a scan

- [ ] **Step 9: Commit**

```bash
git add src/frontend/src/pages/ScanEditorPage.vue src/frontend/src/components/ScanCanvas.vue
git commit -m "feat: wire preview endpoint, load saved adjustments, remove Korrigiert view"
```

---

### Task 7: Clean up `corrected_image_path` references in schema

**Files:**
- Modify: `src/backend/mv_hofki/schemas/sheet_music_scan.py:17`

- [ ] **Step 1: Remove `corrected_image_path` from read schema**

Edit `src/backend/mv_hofki/schemas/sheet_music_scan.py`. Remove line 17:

```python
    corrected_image_path: str | None
```

The DB column stays (no breaking migration), but the API no longer returns it.

- [ ] **Step 2: Run linter and tests**

```bash
pre-commit run --all-files
python -m pytest tests/backend/ -v -k "scan"
```

Expected: all pass.

- [ ] **Step 3: Commit**

```bash
git add src/backend/mv_hofki/schemas/sheet_music_scan.py
git commit -m "chore: remove corrected_image_path from API schema"
```

---

### Task 8: End-to-end verification

- [ ] **Step 1: Restart backend**

```bash
server-restart
```

- [ ] **Step 2: Run all backend tests**

```bash
python -m pytest tests/backend/ -v
```

Expected: all pass.

- [ ] **Step 3: Run frontend tests**

```bash
cd /workspaces/mv_hofki/src/frontend && npx vitest run
```

Expected: all pass.

- [ ] **Step 4: Run pre-commit**

```bash
cd /workspaces/mv_hofki
pre-commit run --all-files
```

Expected: all pass.

- [ ] **Step 5: Manual E2E test**

Open the scan editor in the browser:
1. Load a scan with existing adjustments → sliders show saved values
2. Load a scan without adjustments → sliders show defaults
3. Adjust morphology slider → value updates in toolbar
4. Click "Vorschau" → binary preview appears, overlays hidden
5. Adjust threshold → click "Vorschau" again → updated binary preview
6. Click "Analyse starten" → full pipeline runs with current slider values
7. Verify "Korrigiert" button is gone, only "Original" and "Binär" remain
