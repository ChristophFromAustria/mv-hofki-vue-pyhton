# Staff-Line Deskew Enhancement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement two switchable deskew algorithms (Hough-based and projection-based), expose the choice as a scanner config option, save a corrected (rotated grayscale) image alongside the binary, and add a 3-state image view toggle in the frontend.

**Architecture:** The deskew logic is extracted from `PreprocessStage` into a dedicated `deskew` module with two strategy functions. `PreprocessStage` delegates to the selected strategy via `ctx.config["deskew_method"]`. The pipeline additionally saves `ctx.corrected_image` (rotated grayscale, pre-binarization) so the frontend can display it. A new `corrected_image_path` column on `SheetMusicScan` stores the path. The frontend `ScanCanvas` gains a 3-state view prop (`original` / `corrected` / `binary`) controlled by a segmented button in the toolbar.

**Tech Stack:** Python (OpenCV, NumPy), SQLAlchemy/Alembic, Vue 3

---

### Task 1: Create deskew module with both algorithms

**Files:**
- Create: `src/backend/mv_hofki/services/scanner/deskew.py`
- Test: `tests/backend/test_deskew.py`

- [ ] **Step 1: Write failing tests for both deskew strategies**

Create `tests/backend/test_deskew.py`:

```python
"""Tests for deskew algorithms."""

import numpy as np
import cv2

from mv_hofki.services.scanner.deskew import deskew_hough, deskew_projection


def _make_tilted_staff_image(angle_deg: float, width: int = 800, height: int = 400) -> np.ndarray:
    """Create a synthetic binary image with 5 tilted staff lines."""
    img = np.full((height, width), 255, dtype=np.uint8)
    center = (width // 2, height // 2)
    matrix = cv2.getRotationMatrix2D(center, -angle_deg, 1.0)

    # Draw 5 horizontal lines at even spacing
    line_ys = [150, 170, 190, 210, 230]
    straight = np.full((height, width), 255, dtype=np.uint8)
    for y in line_ys:
        cv2.line(straight, (0, y), (width, y), 0, 2)

    # Rotate to introduce tilt
    img = cv2.warpAffine(straight, matrix, (width, height), borderValue=255)
    return img


def test_deskew_hough_corrects_tilt():
    img = _make_tilted_staff_image(2.0)
    corrected = deskew_hough(img)
    # After correction, horizontal projection should have sharper peaks
    proj_before = np.sum(img == 0, axis=1).astype(float)
    proj_after = np.sum(corrected == 0, axis=1).astype(float)
    # Sharpness = max of projection (perfectly horizontal lines have highest peak)
    assert proj_after.max() > proj_before.max()


def test_deskew_hough_no_change_when_straight():
    img = _make_tilted_staff_image(0.0)
    corrected = deskew_hough(img)
    # Should be essentially unchanged
    diff = np.abs(img.astype(float) - corrected.astype(float))
    assert diff.mean() < 1.0


def test_deskew_projection_corrects_tilt():
    img = _make_tilted_staff_image(2.0)
    corrected = deskew_projection(img)
    proj_before = np.sum(img == 0, axis=1).astype(float)
    proj_after = np.sum(corrected == 0, axis=1).astype(float)
    assert proj_after.max() > proj_before.max()


def test_deskew_projection_corrects_negative_tilt():
    img = _make_tilted_staff_image(-1.5)
    corrected = deskew_projection(img)
    proj_before = np.sum(img == 0, axis=1).astype(float)
    proj_after = np.sum(corrected == 0, axis=1).astype(float)
    assert proj_after.max() > proj_before.max()


def test_deskew_projection_no_change_when_straight():
    img = _make_tilted_staff_image(0.0)
    corrected = deskew_projection(img)
    diff = np.abs(img.astype(float) - corrected.astype(float))
    assert diff.mean() < 1.0


def test_deskew_projection_handles_blank_image():
    blank = np.full((200, 400), 255, dtype=np.uint8)
    result = deskew_projection(blank)
    assert result.shape == blank.shape


def test_deskew_hough_handles_blank_image():
    blank = np.full((200, 400), 255, dtype=np.uint8)
    result = deskew_hough(blank)
    assert result.shape == blank.shape
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/backend/test_deskew.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'mv_hofki.services.scanner.deskew'`

- [ ] **Step 3: Implement the deskew module**

Create `src/backend/mv_hofki/services/scanner/deskew.py`:

```python
"""Deskew algorithms for staff line straightening.

Two strategies are available:
- ``deskew_hough``: Morphologically enhanced Hough line detection.
- ``deskew_projection``: Two-pass angle sweep maximising horizontal projection
  sharpness — more robust for staff-line-heavy sheet music.

Both accept a binary image (0 = black, 255 = white) and return a rotated copy.
"""

from __future__ import annotations

import cv2
import numpy as np


def _rotate(img: np.ndarray, angle_deg: float) -> np.ndarray:
    """Rotate *img* by *angle_deg* around its center, padding with white."""
    h, w = img.shape[:2]
    center = (w // 2, h // 2)
    matrix = cv2.getRotationMatrix2D(center, angle_deg, 1.0)
    return cv2.warpAffine(
        img, matrix, (w, h), flags=cv2.INTER_LINEAR, borderValue=255
    )


# ---------------------------------------------------------------------------
# Strategy A – Improved Hough
# ---------------------------------------------------------------------------

def deskew_hough(img: np.ndarray) -> np.ndarray:
    """Detect skew via morphologically filtered Hough lines and correct it.

    Improvements over the legacy deskew:
    * A long horizontal morphological closing emphasises staff lines and
      suppresses note heads, stems and text before edge detection.
    * Line length is weighted when computing the median angle so that
      short spurious segments have less influence.
    """
    # Emphasise horizontal structures with a wide closing kernel
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (80, 1))
    enhanced = cv2.morphologyEx(img, cv2.MORPH_CLOSE, kernel)

    edges = cv2.Canny(enhanced, 50, 150, apertureSize=3)
    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180,
        threshold=80,
        minLineLength=60,
        maxLineGap=10,
    )

    if lines is None:
        return img

    angles: list[float] = []
    weights: list[float] = []
    for line in lines:
        x1, y1, x2, y2 = line[0]
        angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))
        if abs(angle) < 5:
            length = np.hypot(x2 - x1, y2 - y1)
            angles.append(angle)
            weights.append(length)

    if not angles:
        return img

    # Weighted median: sort by angle, pick the value at cumulative-weight midpoint
    order = np.argsort(angles)
    sorted_angles = np.array(angles)[order]
    sorted_weights = np.array(weights)[order]
    cum = np.cumsum(sorted_weights)
    mid = cum[-1] / 2.0
    idx = int(np.searchsorted(cum, mid))
    median_angle = float(sorted_angles[idx])

    if abs(median_angle) < 0.05:
        return img

    return _rotate(img, median_angle)


# ---------------------------------------------------------------------------
# Strategy B – Projection-based angle sweep
# ---------------------------------------------------------------------------

def _projection_sharpness(img: np.ndarray, angle: float) -> float:
    """Return peak value of horizontal projection after rotating by *angle*."""
    rotated = _rotate(img, angle)
    projection = np.sum(rotated == 0, axis=1).astype(float)
    return float(projection.max())


def deskew_projection(img: np.ndarray) -> np.ndarray:
    """Find the rotation angle that maximises horizontal projection sharpness.

    Pass 1: coarse sweep from -3 to +3 degrees in 0.1-degree steps.
    Pass 2: fine sweep +/- 0.15 degrees around the best coarse angle in
    0.02-degree steps.
    """
    if np.all(img == 255):
        return img

    # Coarse pass
    coarse_angles = np.arange(-3.0, 3.05, 0.1)
    best_angle = 0.0
    best_score = -1.0
    for a in coarse_angles:
        score = _projection_sharpness(img, a)
        if score > best_score:
            best_score = score
            best_angle = float(a)

    # Fine pass
    fine_angles = np.arange(best_angle - 0.15, best_angle + 0.16, 0.02)
    for a in fine_angles:
        score = _projection_sharpness(img, a)
        if score > best_score:
            best_score = score
            best_angle = float(a)

    if abs(best_angle) < 0.02:
        return img

    return _rotate(img, best_angle)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/backend/test_deskew.py -v`
Expected: All 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/backend/mv_hofki/services/scanner/deskew.py tests/backend/test_deskew.py
git commit -m "feat(scanner): add hough and projection deskew strategies with tests"
```

---

### Task 2: Wire deskew module into PreprocessStage and save corrected image

**Files:**
- Modify: `src/backend/mv_hofki/services/scanner/stages/preprocess.py`
- Modify: `src/backend/mv_hofki/services/scanner/stages/base.py:44-56` (add `corrected_image` field)
- Modify: `tests/backend/test_pipeline_stages.py` (add preprocess deskew integration test)

- [ ] **Step 1: Add `corrected_image` field to PipelineContext**

In `src/backend/mv_hofki/services/scanner/stages/base.py`, add a new field after `processed_image`:

```python
    corrected_image: np.ndarray | None = None
```

This stores the rotated-but-not-binarized grayscale image for frontend preview.

- [ ] **Step 2: Write failing integration test**

Append to `tests/backend/test_pipeline_stages.py`:

```python
def test_preprocess_uses_configured_deskew_method():
    """PreprocessStage should delegate to the deskew method set in config."""
    from mv_hofki.services.scanner.stages.preprocess import PreprocessStage

    # Create a slightly tilted image with staff-like lines
    img = np.full((300, 600, 3), 255, dtype=np.uint8)
    for y in [100, 120, 140, 160, 180]:
        cv2.line(img, (0, y + 5), (600, y - 5), 0, 2)  # ~1° tilt

    # Test with projection method
    ctx = PipelineContext(image=img.copy(), config={"deskew_method": "projection"})
    stage = PreprocessStage()
    result = stage.process(ctx)
    assert result.corrected_image is not None
    assert result.corrected_image.shape[:2] == img.shape[:2]

    # Test with hough method
    ctx2 = PipelineContext(image=img.copy(), config={"deskew_method": "hough"})
    result2 = stage.process(ctx2)
    assert result2.corrected_image is not None

    # Test default (none = skip deskew, backward compatible)
    ctx3 = PipelineContext(image=img.copy(), config={"deskew_method": "none"})
    result3 = stage.process(ctx3)
    assert result3.corrected_image is None
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/backend/test_pipeline_stages.py::test_preprocess_uses_configured_deskew_method -v`
Expected: FAIL (corrected_image not set, deskew_method not recognized)

- [ ] **Step 4: Refactor PreprocessStage to use the deskew module**

Replace the full content of `src/backend/mv_hofki/services/scanner/stages/preprocess.py`:

```python
"""Preprocessing stage: binarization, deskew, noise removal."""

from __future__ import annotations

import cv2
import numpy as np

from mv_hofki.services.scanner.deskew import deskew_hough, deskew_projection
from mv_hofki.services.scanner.stages.base import PipelineContext, ProcessingStage

_DESKEW_STRATEGIES = {
    "hough": deskew_hough,
    "projection": deskew_projection,
}


class PreprocessStage(ProcessingStage):
    """Adaptive thresholding, deskew, and morphological noise removal."""

    name = "preprocess"

    def process(self, ctx: PipelineContext) -> PipelineContext:
        assert ctx.image is not None
        img = ctx.image
        ctx.original_image = img.copy()

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
            # Also rotate the grayscale image for frontend preview
            ctx.corrected_image = deskew_fn(gray)
            ctx.log(f"Deskew angewendet (Methode: {method})")

        # Morphological noise removal
        k_size = ctx.config.get("morphology_kernel_size", 2)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k_size, k_size))
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)

        ctx.processed_image = binary
        ctx.image = binary
        return ctx

    def validate(self, ctx: PipelineContext) -> bool:
        return ctx.image is not None
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/backend/test_pipeline_stages.py::test_preprocess_uses_configured_deskew_method -v`
Expected: PASS

- [ ] **Step 6: Run all existing pipeline tests to check for regressions**

Run: `python -m pytest tests/backend/test_pipeline_stages.py -v`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add src/backend/mv_hofki/services/scanner/stages/base.py src/backend/mv_hofki/services/scanner/stages/preprocess.py tests/backend/test_pipeline_stages.py
git commit -m "feat(scanner): wire deskew strategies into PreprocessStage, save corrected image"
```

---

### Task 3: Add `deskew_method` to scanner config (model, schema, migration)

**Files:**
- Modify: `src/backend/mv_hofki/models/scanner_config.py`
- Modify: `src/backend/mv_hofki/schemas/scanner_config.py`
- Create: `alembic/versions/<auto>_add_deskew_method_to_scanner_config.py`

- [ ] **Step 1: Add column to ORM model**

In `src/backend/mv_hofki/models/scanner_config.py`, add after the `morphology_kernel_size` field (in the Preprocessing section):

```python
    # Deskew
    deskew_method: Mapped[str] = mapped_column(
        String(20), nullable=False, default="projection"
    )
```

- [ ] **Step 2: Add field to Pydantic schemas**

In `src/backend/mv_hofki/schemas/scanner_config.py`:

Add to `ScannerConfigRead`:
```python
    deskew_method: str
```

Add to `ScannerConfigUpdate`:
```python
    deskew_method: str | None = Field(None, pattern="^(none|hough|projection)$")
```

- [ ] **Step 3: Generate Alembic migration**

Run:
```bash
cd /workspaces/mv_hofki && PYTHONPATH=src/backend alembic revision --autogenerate -m "add deskew_method to scanner_config"
```

- [ ] **Step 4: Run the migration**

Run:
```bash
cd /workspaces/mv_hofki && PYTHONPATH=src/backend alembic upgrade head
```

- [ ] **Step 5: Verify config round-trip with existing test**

Run: `python -m pytest tests/backend/test_scanner_config.py -v`
Expected: All PASS (the new field should be included in responses automatically)

- [ ] **Step 6: Commit**

```bash
git add src/backend/mv_hofki/models/scanner_config.py src/backend/mv_hofki/schemas/scanner_config.py alembic/versions/*deskew_method*
git commit -m "feat(scanner): add deskew_method config option (none/hough/projection)"
```

---

### Task 4: Save corrected image to disk and expose via API

**Files:**
- Modify: `src/backend/mv_hofki/models/sheet_music_scan.py` (add `corrected_image_path` column)
- Modify: `src/backend/mv_hofki/schemas/sheet_music_scan.py` (add field to read schema)
- Modify: `src/backend/mv_hofki/services/sheet_music_scan.py:289-295` (save corrected image)
- Create: `alembic/versions/<auto>_add_corrected_image_path.py`

- [ ] **Step 1: Add `corrected_image_path` to ORM model**

In `src/backend/mv_hofki/models/sheet_music_scan.py`, add after `processed_image_path`:

```python
    corrected_image_path: Mapped[str | None] = mapped_column(String(500))
```

- [ ] **Step 2: Add to Pydantic read schema**

In `src/backend/mv_hofki/schemas/sheet_music_scan.py`, add the field to the read schema:

```python
    corrected_image_path: str | None
```

- [ ] **Step 3: Save corrected image in the pipeline result handler**

In `src/backend/mv_hofki/services/sheet_music_scan.py`, after the existing processed image save block (around line 295), add:

```python
    # Save corrected (rotated grayscale) image for frontend preview
    if ctx.corrected_image is not None:
        corrected_path = _scan_dir(project_id, part_id, scan_id) / "corrected.png"
        cv2.imwrite(str(corrected_path), ctx.corrected_image)
        scan.corrected_image_path = str(
            corrected_path.relative_to(settings.PROJECT_ROOT)
        )
```

- [ ] **Step 4: Generate and run Alembic migration**

```bash
cd /workspaces/mv_hofki && PYTHONPATH=src/backend alembic revision --autogenerate -m "add corrected_image_path to sheet_music_scans"
cd /workspaces/mv_hofki && PYTHONPATH=src/backend alembic upgrade head
```

- [ ] **Step 5: Commit**

```bash
git add src/backend/mv_hofki/models/sheet_music_scan.py src/backend/mv_hofki/schemas/sheet_music_scan.py src/backend/mv_hofki/services/sheet_music_scan.py alembic/versions/*corrected_image_path*
git commit -m "feat(scanner): save corrected grayscale image and expose path via API"
```

---

### Task 5: Add deskew method selector to frontend config UI

**Files:**
- Modify: `src/frontend/src/lib/scanner-config.js`

- [ ] **Step 1: Add the deskew_method field definition**

In `src/frontend/src/lib/scanner-config.js`, add a new entry at the end of the `Vorverarbeitung` group (after the `morphology_kernel_size` entry, before the closing `]`):

```javascript
  {
    key: "deskew_method",
    label: "Deskew-Methode",
    group: "Vorverarbeitung",
    type: "select",
    options: [
      { value: "none", label: "Keine Korrektur" },
      { value: "hough", label: "Hough-Linien (schnell)" },
      { value: "projection", label: "Projektions-Optimierung (genau)" },
    ],
  },
```

No template changes needed — the `ScannerConfigModal` auto-generates from this array.

- [ ] **Step 2: Verify the config modal renders correctly**

Run: `frontend-logs` to confirm vite build succeeds. Open the app in the browser, navigate to a scan editor, open the config modal ("Konfig."). The "Vorverarbeitung" group should now show a "Deskew-Methode" dropdown with three options.

- [ ] **Step 3: Commit**

```bash
git add src/frontend/src/lib/scanner-config.js
git commit -m "feat(frontend): add deskew method selector to scanner config UI"
```

---

### Task 6: Add 3-state image view toggle to frontend

**Files:**
- Modify: `src/frontend/src/components/ScanCanvas.vue`
- Modify: `src/frontend/src/pages/ScanEditorPage.vue`

- [ ] **Step 1: Add `viewMode` and `correctedImagePath` props to ScanCanvas**

In `src/frontend/src/components/ScanCanvas.vue`, update the props:

```javascript
const props = defineProps({
  imagePath: { type: String, default: null },
  correctedImagePath: { type: String, default: null },
  processedImagePath: { type: String, default: null },
  staves: { type: Array, default: () => [] },
  symbols: { type: Array, default: () => [] },
  adjustments: {
    type: Object,
    default: () => ({ brightness: 0, contrast: 1.0, rotation: 0, threshold: 128 }),
  },
  selectedSymbolId: { type: Number, default: null },
  showStaves: { type: Boolean, default: true },
  showSymbols: { type: Boolean, default: true },
  captureMode: { type: Boolean, default: false },
  viewMode: { type: String, default: "original" }, // "original" | "corrected" | "binary"
});
```

- [ ] **Step 2: Update the image URL computation and loading logic**

Replace the `imageUrl` computed and the `loadImage`/`applyThreshold` functions:

```javascript
const BASE = (import.meta.env.VITE_BASE_PATH || "").replace(/\/$/, "");

function resolveImageUrl(path) {
  if (!path) return null;
  const relative = path.replace(/^data\/scans\//, "");
  return `${BASE}/scans/${relative}`;
}

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

Update `loadImage` to use `activeImageUrl` instead of `imageUrl`:

```javascript
function loadImage() {
  if (!activeImageUrl.value) return;
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
    // Only apply client-side threshold on original view
    if (props.viewMode === "original") {
      applyThreshold();
    }
  };
  img.src = activeImageUrl.value;
}
```

Update the watchers:

```javascript
watch(() => activeImageUrl.value, loadImage);
watch(() => props.adjustments.threshold, () => {
  if (props.viewMode === "original") applyThreshold();
});
onMounted(loadImage);
```

Remove the old `imageUrl` computed and the old `watch(() => props.imagePath, loadImage)` watcher.

- [ ] **Step 3: Add viewMode prop and segmented toggle to ScanEditorPage**

In `src/frontend/src/pages/ScanEditorPage.vue`, add state:

```javascript
const viewMode = ref("original"); // "original" | "corrected" | "binary"
```

In the `toolbar-extras` div, add the view toggle after the stave-count span:

```html
<div class="view-toggle">
  <button
    class="btn btn-sm"
    :class="{ 'btn-active': viewMode === 'original' }"
    @click="viewMode = 'original'"
  >
    Original
  </button>
  <button
    class="btn btn-sm"
    :class="{ 'btn-active': viewMode === 'corrected' }"
    :disabled="!scan?.corrected_image_path"
    @click="viewMode = 'corrected'"
  >
    Korrigiert
  </button>
  <button
    class="btn btn-sm"
    :class="{ 'btn-active': viewMode === 'binary' }"
    :disabled="!scan?.processed_image_path"
    @click="viewMode = 'binary'"
  >
    Binär
  </button>
</div>
```

Update the `ScanCanvas` usage to pass the new props:

```html
<ScanCanvas
  :image-path="scan?.image_path ?? null"
  :corrected-image-path="scan?.corrected_image_path ?? null"
  :processed-image-path="scan?.processed_image_path ?? null"
  :staves="staves"
  :symbols="symbols"
  :adjustments="adjustments"
  :selected-symbol-id="selectedSymbol?.id ?? null"
  :show-staves="showStaves"
  :show-symbols="showSymbols"
  :capture-mode="captureMode"
  :view-mode="viewMode"
  @select-symbol="onSelectSymbol"
  @capture-box="onCaptureBox"
/>
```

- [ ] **Step 4: Add CSS for the view toggle**

In `ScanEditorPage.vue` `<style scoped>`, add:

```css
.view-toggle {
  display: inline-flex;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  overflow: hidden;
  margin-left: 0.5rem;
}

.view-toggle .btn {
  border: none;
  border-radius: 0;
  border-right: 1px solid var(--color-border);
}

.view-toggle .btn:last-child {
  border-right: none;
}
```

- [ ] **Step 5: Verify the frontend builds and toggle renders**

Run: `frontend-logs` to confirm vite build succeeds. Open a scan editor page — the toolbar should show the 3 toggle buttons. "Korrigiert" and "Binär" should be disabled until an analysis has been run.

- [ ] **Step 6: Commit**

```bash
git add src/frontend/src/components/ScanCanvas.vue src/frontend/src/pages/ScanEditorPage.vue
git commit -m "feat(frontend): add original/corrected/binary view toggle in scan editor"
```

---

### Task 7: End-to-end verification

- [ ] **Step 1: Run all backend tests**

Run: `python -m pytest tests/backend/ -v`
Expected: All PASS

- [ ] **Step 2: Run frontend build**

Run: `frontend-logs`
Expected: vite build completes without errors

- [ ] **Step 3: Run pre-commit checks**

Run: `pre-commit run --all-files`
Expected: All PASS

- [ ] **Step 4: Manual E2E test**

1. Open the app, navigate to a scan project with a tilted scan
2. Open scanner config ("Konfig."), set deskew method to "Projektions-Optimierung (genau)"
3. Run analysis ("Analyse starten")
4. After completion, the "Korrigiert" and "Binär" buttons should become active
5. Click "Korrigiert" — the image should appear straightened with staff lines more horizontal
6. Click "Binär" — should show the black/white processed version
7. Toggle staff line overlay ("Linien einblenden") — overlay lines should align well with actual staff lines in corrected view
8. Switch deskew to "Hough-Linien (schnell)" and re-run analysis — should also produce a corrected result

- [ ] **Step 5: Final commit with any fixes from E2E testing**

```bash
git add -u
git commit -m "fix: address issues found during E2E verification"
```
