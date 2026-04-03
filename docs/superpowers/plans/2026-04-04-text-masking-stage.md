# Text Masking Stage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract text masking into a standalone pipeline stage that detects and removes text regions from the binary image before Hough-based stages run.

**Architecture:** New `TextMaskingStage` in its own module, with a `TextRegionData` dataclass on `PipelineContext`. The stage scans above and below each staff, clusters character-sized connected components into text regions, stores them as data, and whites them out in `processed_image`. The existing inline masking in `HairpinDetectionStage` is removed.

**Tech Stack:** Python, OpenCV (`connectedComponentsWithStats`), NumPy, pytest

---

### Task 1: Add `TextRegionData` to base module

**Files:**
- Modify: `src/backend/mv_hofki/services/scanner/stages/base.py:50-77`
- Test: `tests/backend/test_pipeline_stages.py`

- [ ] **Step 1: Write failing test for TextRegionData**

Add to `tests/backend/test_pipeline_stages.py`:

```python
def test_text_region_data_creation():
    from mv_hofki.services.scanner.stages.base import TextRegionData

    region = TextRegionData(staff_index=0, x=10, y=20, width=50, height=15)
    assert region.staff_index == 0
    assert region.x == 10
    assert region.y == 20
    assert region.width == 50
    assert region.height == 15
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/backend/test_pipeline_stages.py::test_text_region_data_creation -v`
Expected: FAIL with `ImportError: cannot import name 'TextRegionData'`

- [ ] **Step 3: Add TextRegionData dataclass**

In `src/backend/mv_hofki/services/scanner/stages/base.py`, add after the `MeasureData` class (after line 61):

```python
@dataclass
class TextRegionData:
    """Data for a detected text region."""

    staff_index: int
    x: int
    y: int
    width: int
    height: int
```

- [ ] **Step 4: Write failing test for text_regions on PipelineContext**

Add to `tests/backend/test_pipeline_stages.py`:

```python
def test_pipeline_context_has_text_regions():
    from mv_hofki.services.scanner.stages.base import PipelineContext

    ctx = PipelineContext(image=None)
    assert ctx.text_regions == []
```

- [ ] **Step 5: Run test to verify it fails**

Run: `python -m pytest tests/backend/test_pipeline_stages.py::test_pipeline_context_has_text_regions -v`
Expected: FAIL with `AttributeError: 'PipelineContext' has no attribute 'text_regions'`

- [ ] **Step 6: Add text_regions field to PipelineContext**

In `src/backend/mv_hofki/services/scanner/stages/base.py`, in the `PipelineContext` class, add after the `measures` field:

```python
    text_regions: list[TextRegionData] = field(default_factory=list)
```

- [ ] **Step 7: Run tests to verify both pass**

Run: `python -m pytest tests/backend/test_pipeline_stages.py::test_text_region_data_creation tests/backend/test_pipeline_stages.py::test_pipeline_context_has_text_regions -v`
Expected: both PASS

- [ ] **Step 8: Commit**

```bash
git add src/backend/mv_hofki/services/scanner/stages/base.py tests/backend/test_pipeline_stages.py
git commit -m "feat: add TextRegionData and text_regions to PipelineContext"
```

---

### Task 2: Create `TextMaskingStage`

**Files:**
- Create: `src/backend/mv_hofki/services/scanner/stages/text_masking.py`
- Create: `tests/backend/test_text_masking.py`

- [ ] **Step 1: Write failing test — stage detects text below staff**

Create `tests/backend/test_text_masking.py`:

```python
"""Tests for the text masking pipeline stage."""

import cv2
import numpy as np

from mv_hofki.services.scanner.stages.base import PipelineContext, StaffData


def _make_staff_with_text_below():
    """Create a binary image with staff lines and text characters below."""
    img = np.full((300, 800), 255, dtype=np.uint8)

    # Draw 5 staff lines at y=50,60,70,80,90
    for y in [50, 60, 70, 80, 90]:
        img[y : y + 2, 20:780] = 0

    # Draw text-like characters below the staff (y=120..135)
    # Simulate "cresc." — 6 small rectangles spaced horizontally
    for i, x in enumerate([100, 115, 130, 145, 160, 175]):
        cv2.rectangle(img, (x, 120), (x + 8, 135), 0, -1)

    staff = StaffData(
        staff_index=0,
        y_top=20,
        y_bottom=200,
        line_positions=[50, 60, 70, 80, 90],
        line_spacing=10.0,
    )
    return img, staff


def test_text_masking_detects_text_regions():
    from mv_hofki.services.scanner.stages.text_masking import TextMaskingStage

    img, staff = _make_staff_with_text_below()
    ctx = PipelineContext(image=img, processed_image=img.copy(), staves=[staff])

    stage = TextMaskingStage()
    result = stage.process(ctx)

    assert len(result.text_regions) >= 1
    region = result.text_regions[0]
    assert region.staff_index == 0
    assert region.x >= 90
    assert region.x <= 110
    assert region.width > 50
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/backend/test_text_masking.py::test_text_masking_detects_text_regions -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'mv_hofki.services.scanner.stages.text_masking'`

- [ ] **Step 3: Write TextMaskingStage implementation**

Create `src/backend/mv_hofki/services/scanner/stages/text_masking.py`:

```python
"""Text masking: detect and remove text regions before Hough-based stages."""

from __future__ import annotations

import cv2
import numpy as np

from mv_hofki.services.scanner.stages.base import (
    PipelineContext,
    ProcessingStage,
    StaffData,
    TextRegionData,
)


class TextMaskingStage(ProcessingStage):
    """Detect text-like regions around staves and mask them in the binary image."""

    name = "text_masking"

    def process(self, ctx: PipelineContext) -> PipelineContext:
        binary = ctx.processed_image
        if binary is None:
            return ctx

        staves = sorted(ctx.staves, key=lambda s: s.staff_index)

        for staff in staves:
            regions = _scan_staff_regions(binary, staff)
            ctx.text_regions.extend(regions)

        # Mask detected text regions in the binary image
        for region in ctx.text_regions:
            y1 = region.y
            y2 = region.y + region.height
            x1 = region.x
            x2 = region.x + region.width
            binary[y1:y2, x1:x2] = 255

        ctx.log(
            f"Text-Maskierung: {len(ctx.text_regions)} Textregionen "
            f"in {len(staves)} Systemen erkannt"
        )
        return ctx

    def validate(self, ctx: PipelineContext) -> bool:
        return ctx.processed_image is not None and len(ctx.staves) > 0


def _scan_staff_regions(
    binary: np.ndarray,
    staff: StaffData,
) -> list[TextRegionData]:
    """Scan above and below a staff for text-like regions."""
    results: list[TextRegionData] = []

    top_line = min(staff.line_positions)
    bottom_line = max(staff.line_positions)

    # Region above: y_top to top staff line
    if staff.y_top < top_line:
        above = _detect_text_regions(
            binary,
            staff.y_top,
            top_line,
            staff.line_spacing,
            staff.staff_index,
        )
        results.extend(above)

    # Region below: bottom staff line to y_bottom
    if bottom_line < staff.y_bottom:
        below = _detect_text_regions(
            binary,
            bottom_line,
            staff.y_bottom,
            staff.line_spacing,
            staff.staff_index,
        )
        results.extend(below)

    return results


def _detect_text_regions(
    binary: np.ndarray,
    region_top: int,
    region_bottom: int,
    line_spacing: float,
    staff_index: int,
) -> list[TextRegionData]:
    """Find text-like clusters in a horizontal strip of the binary image.

    Text characters are small connected components clustered horizontally.
    We identify them by size relative to line_spacing and group adjacent ones.
    """
    h, w = binary.shape[:2]
    region_top = max(0, region_top)
    region_bottom = min(h, region_bottom)

    if region_top >= region_bottom:
        return []

    region = binary[region_top:region_bottom, :]
    inverted = cv2.bitwise_not(region)

    rh, rw = inverted.shape[:2]
    if rh == 0 or rw == 0:
        return []

    num_labels, _labels, stats, _ = cv2.connectedComponentsWithStats(
        inverted, connectivity=8
    )

    # Thresholds derived from staff line spacing
    max_char_size = line_spacing * 1.5
    min_char_size = max(2, line_spacing * 0.15)

    # Collect bounding boxes of character-sized components
    char_boxes: list[tuple[int, int, int, int]] = []
    for label_idx in range(1, num_labels):  # skip background
        bx = stats[label_idx, cv2.CC_STAT_LEFT]
        by = stats[label_idx, cv2.CC_STAT_TOP]
        bw = stats[label_idx, cv2.CC_STAT_WIDTH]
        bh = stats[label_idx, cv2.CC_STAT_HEIGHT]

        if min_char_size <= bw <= max_char_size and min_char_size <= bh <= max_char_size:
            # Reject very elongated components (likely line fragments)
            aspect = max(bw, bh) / max(min(bw, bh), 1)
            if aspect < 5:
                char_boxes.append((bx, by, bx + bw, by + bh))

    if len(char_boxes) < 3:
        return []

    # Sort by x and cluster horizontally adjacent characters
    char_boxes.sort(key=lambda b: b[0])
    merge_gap = line_spacing * 1.0
    clusters: list[list[tuple[int, int, int, int]]] = [[char_boxes[0]]]

    for box in char_boxes[1:]:
        prev = clusters[-1][-1]
        h_gap = box[0] - prev[2]
        v_overlap = min(box[3], prev[3]) - max(box[1], prev[1])
        if h_gap <= merge_gap and v_overlap > 0:
            clusters[-1].append(box)
        else:
            clusters.append([box])

    # Convert clusters with >= 3 characters to TextRegionData
    padding = int(line_spacing * 0.3)
    results: list[TextRegionData] = []

    for cluster in clusters:
        if len(cluster) < 3:
            continue
        cx1 = max(0, min(b[0] for b in cluster) - padding)
        cy1 = max(0, min(b[1] for b in cluster) - padding)
        cx2 = min(rw, max(b[2] for b in cluster) + padding)
        cy2 = min(rh, max(b[3] for b in cluster) + padding)

        results.append(
            TextRegionData(
                staff_index=staff_index,
                x=cx1,
                y=region_top + cy1,
                width=cx2 - cx1,
                height=cy2 - cy1,
            )
        )

    return results
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/backend/test_text_masking.py::test_text_masking_detects_text_regions -v`
Expected: PASS

- [ ] **Step 5: Write test — stage masks pixels in processed_image**

Add to `tests/backend/test_text_masking.py`:

```python
def test_text_masking_whites_out_text_pixels():
    from mv_hofki.services.scanner.stages.text_masking import TextMaskingStage

    img, staff = _make_staff_with_text_below()
    original_black = np.sum(img[110:145, 90:200] == 0)

    ctx = PipelineContext(image=img, processed_image=img.copy(), staves=[staff])
    stage = TextMaskingStage()
    result = stage.process(ctx)

    masked_black = np.sum(result.processed_image[110:145, 90:200] == 0)
    assert masked_black < original_black
```

- [ ] **Step 6: Run test to verify it passes**

Run: `python -m pytest tests/backend/test_text_masking.py::test_text_masking_whites_out_text_pixels -v`
Expected: PASS

- [ ] **Step 7: Write test — stage detects text above staff**

Add to `tests/backend/test_text_masking.py`:

```python
def test_text_masking_detects_text_above_staff():
    from mv_hofki.services.scanner.stages.text_masking import TextMaskingStage

    img = np.full((300, 800), 255, dtype=np.uint8)

    # Staff lines at y=100..140
    for y in [100, 110, 120, 130, 140]:
        img[y : y + 2, 20:780] = 0

    # Text above staff (e.g. "1.") at y=60..75
    for x in [200, 215, 230, 245]:
        cv2.rectangle(img, (x, 60), (x + 8, 75), 0, -1)

    staff = StaffData(
        staff_index=0,
        y_top=30,
        y_bottom=250,
        line_positions=[100, 110, 120, 130, 140],
        line_spacing=10.0,
    )
    ctx = PipelineContext(image=img, processed_image=img.copy(), staves=[staff])

    stage = TextMaskingStage()
    result = stage.process(ctx)

    above_regions = [r for r in result.text_regions if r.y < 100]
    assert len(above_regions) >= 1
```

- [ ] **Step 8: Run test to verify it passes**

Run: `python -m pytest tests/backend/test_text_masking.py::test_text_masking_detects_text_above_staff -v`
Expected: PASS

- [ ] **Step 9: Write test — no false positives on clean staff**

Add to `tests/backend/test_text_masking.py`:

```python
def test_text_masking_no_false_positives_on_clean_staff():
    from mv_hofki.services.scanner.stages.text_masking import TextMaskingStage

    img = np.full((300, 800), 255, dtype=np.uint8)

    # Only staff lines, no text
    for y in [50, 60, 70, 80, 90]:
        img[y : y + 2, 20:780] = 0

    staff = StaffData(
        staff_index=0,
        y_top=20,
        y_bottom=200,
        line_positions=[50, 60, 70, 80, 90],
        line_spacing=10.0,
    )
    ctx = PipelineContext(image=img, processed_image=img.copy(), staves=[staff])

    stage = TextMaskingStage()
    result = stage.process(ctx)

    assert len(result.text_regions) == 0
```

- [ ] **Step 10: Run test to verify it passes**

Run: `python -m pytest tests/backend/test_text_masking.py::test_text_masking_no_false_positives_on_clean_staff -v`
Expected: PASS

- [ ] **Step 11: Write test — validate returns False without prerequisites**

Add to `tests/backend/test_text_masking.py`:

```python
def test_text_masking_validate():
    from mv_hofki.services.scanner.stages.text_masking import TextMaskingStage

    stage = TextMaskingStage()

    # No image → False
    ctx = PipelineContext(image=None, processed_image=None)
    assert stage.validate(ctx) is False

    # Image but no staves → False
    img = np.zeros((100, 100), dtype=np.uint8)
    ctx = PipelineContext(image=img, processed_image=img)
    assert stage.validate(ctx) is False

    # Image + staves → True
    staff = StaffData(
        staff_index=0, y_top=0, y_bottom=100,
        line_positions=[20, 30, 40, 50, 60], line_spacing=10.0,
    )
    ctx = PipelineContext(image=img, processed_image=img, staves=[staff])
    assert stage.validate(ctx) is True
```

- [ ] **Step 12: Run all text masking tests**

Run: `python -m pytest tests/backend/test_text_masking.py -v`
Expected: all 5 tests PASS

- [ ] **Step 13: Commit**

```bash
git add src/backend/mv_hofki/services/scanner/stages/text_masking.py tests/backend/test_text_masking.py
git commit -m "feat: add TextMaskingStage for text region detection and masking"
```

---

### Task 3: Remove inline text masking from HairpinDetectionStage

**Files:**
- Modify: `src/backend/mv_hofki/services/scanner/stages/hairpin_detection.py:50-53,153-227`

- [ ] **Step 1: Run existing tests as baseline**

Run: `python -m pytest tests/backend/test_pipeline_stages.py -v`
Expected: all PASS

- [ ] **Step 2: Remove inline masking call from process method**

In `src/backend/mv_hofki/services/scanner/stages/hairpin_detection.py`, remove lines 50-53:

```python
            # Mask out text-like regions to avoid false positives
            text_mask = _detect_text_mask(inverted, staff.line_spacing)
            if text_mask is not None:
                inverted = cv2.bitwise_and(inverted, cv2.bitwise_not(text_mask))
```

- [ ] **Step 3: Remove the `_detect_text_mask` function**

In `src/backend/mv_hofki/services/scanner/stages/hairpin_detection.py`, remove the entire `_detect_text_mask` function (lines 153-227).

- [ ] **Step 4: Run linter and tests**

Run: `pre-commit run --files src/backend/mv_hofki/services/scanner/stages/hairpin_detection.py && python -m pytest tests/backend/test_pipeline_stages.py -v`
Expected: linter passes, all tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/backend/mv_hofki/services/scanner/stages/hairpin_detection.py
git commit -m "refactor: remove inline text masking from HairpinDetectionStage"
```

---

### Task 4: Wire TextMaskingStage into the pipeline

**Files:**
- Modify: `src/backend/mv_hofki/services/sheet_music_scan.py:251-255`

- [ ] **Step 1: Add TextMaskingStage import and insertion**

In `src/backend/mv_hofki/services/sheet_music_scan.py`, after line 251 (`stages.append(PostMatchingStage())`), add:

```python
    from mv_hofki.services.scanner.stages.text_masking import TextMaskingStage

    stages.append(TextMaskingStage())
```

The resulting order will be:
```
PostMatchingStage → TextMaskingStage → HairpinDetectionStage
```

- [ ] **Step 2: Run linter**

Run: `pre-commit run --files src/backend/mv_hofki/services/sheet_music_scan.py`
Expected: all checks pass

- [ ] **Step 3: Run full test suite**

Run: `python -m pytest tests/backend/ -v`
Expected: all PASS

- [ ] **Step 4: Commit**

```bash
git add src/backend/mv_hofki/services/sheet_music_scan.py
git commit -m "feat: wire TextMaskingStage into scanner pipeline after PostMatching"
```

---

### Task 5: Manual verification with "47er Regimentsmarsch - Tuba 1"

**Files:** none (manual test via UI)

- [ ] **Step 1: Restart the backend server**

Run: `server-restart`

- [ ] **Step 2: Run a scan on "47er Regimentsmarsch - Tuba 1" via the UI**

Open the application, navigate to the scan, and trigger a re-scan.

- [ ] **Step 3: Verify results**

Check in the UI:
1. `processed.png` shows white-masked areas where text was (visual confirmation)
2. Hairpin detection reports exactly 4 Crescendo/Decrescendo (no false positives from text)
3. Text regions are stored (check scan debug output for the log line `Text-Maskierung: N Textregionen...`)
