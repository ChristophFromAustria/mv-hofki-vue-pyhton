# Volta Bracket Detection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite VoltaDetectionStage to detect repeat brackets above staves by seeding from repeat barlines, finding horizontal Hough lines, expanding via connected components, and storing results as SymbolData with volta metadata on measures.

**Architecture:** Extract `_expand_to_connected` into a shared utility, then rewrite `volta_detection.py` to: find repeat barlines in `ctx.measures`, scan the region above the staff for horizontal Hough lines near those barlines, CC-expand to get the full bracket bounds, create `SymbolData` entries with the "Wiederholungs Klammer" template ID (60), and assign `volta_number`/`volta_group_id` on affected measures.

**Tech Stack:** Python, OpenCV (Hough, connected components), NumPy

---

### Task 1: Extract `_expand_to_connected` into shared utility

**Files:**
- Create: `src/backend/mv_hofki/services/scanner/stages/utils.py`
- Modify: `src/backend/mv_hofki/services/scanner/stages/hairpin_detection.py`

- [ ] **Step 1: Create utils.py with the function**

Create `src/backend/mv_hofki/services/scanner/stages/utils.py`:

```python
"""Shared utilities for scanner pipeline stages."""

from __future__ import annotations

import cv2
import numpy as np


def expand_to_connected(
    binary: np.ndarray,
    x_min: int,
    y_min: int,
    x_max: int,
    y_max: int,
    region_top: int,
    region_bottom: int,
) -> tuple[int, int, int, int]:
    """Expand a bounding box to cover all connected black pixels.

    Uses the specified region for connected component analysis
    so the expansion can reach the full extent of connected symbols.

    Parameters
    ----------
    binary : grayscale image (0=black, 255=white)
    x_min, y_min, x_max, y_max : seed bounding box (absolute coords)
    region_top, region_bottom : Y limits for CC analysis (absolute coords)

    Returns (x_min, y_min, x_max, y_max) of expanded box.
    """
    h, w = binary.shape[:2]
    roi_y1 = max(0, region_top)
    roi_y2 = min(h, region_bottom)

    roi = binary[roi_y1:roi_y2, :]
    inverted = cv2.bitwise_not(roi)

    _, labels = cv2.connectedComponents(inverted)

    # Find which labels touch the seed box (relative to ROI)
    seed_y1 = max(0, y_min - roi_y1)
    seed_y2 = min(roi_y2 - roi_y1, y_max - roi_y1)
    seed_x1 = max(0, x_min)
    seed_x2 = min(w, x_max)

    if seed_y1 >= seed_y2 or seed_x1 >= seed_x2:
        return x_min, y_min, x_max, y_max

    seed_region = labels[seed_y1:seed_y2, seed_x1:seed_x2]
    touching_labels = set(np.unique(seed_region)) - {0}

    if not touching_labels:
        return x_min, y_min, x_max, y_max

    # Find the bounding box of all pixels with those labels
    mask = np.isin(labels, list(touching_labels))
    coords = cv2.findNonZero(mask.astype(np.uint8))
    if coords is None:
        return x_min, y_min, x_max, y_max

    rx, ry, rw, rh = cv2.boundingRect(coords)
    return rx, roi_y1 + ry, rx + rw, roi_y1 + ry + rh
```

- [ ] **Step 2: Update hairpin_detection.py to import from utils**

In `src/backend/mv_hofki/services/scanner/stages/hairpin_detection.py`:

Add import at the top (after existing imports):
```python
from mv_hofki.services.scanner.stages.utils import expand_to_connected
```

Find the call to `_expand_to_connected` (around line 102) and change it to:
```python
                ex = expand_to_connected(
```

Then delete the entire `_expand_to_connected` function (starts around line 358, ~35 lines).

- [ ] **Step 3: Run linter and tests**

Run: `pre-commit run --files src/backend/mv_hofki/services/scanner/stages/utils.py src/backend/mv_hofki/services/scanner/stages/hairpin_detection.py && python -m pytest tests/backend/ -v -x`

- [ ] **Step 4: Commit**

```bash
git add src/backend/mv_hofki/services/scanner/stages/utils.py src/backend/mv_hofki/services/scanner/stages/hairpin_detection.py
git commit -m "refactor: extract expand_to_connected into shared utils module"
```

---

### Task 2: Rewrite VoltaDetectionStage

**Files:**
- Rewrite: `src/backend/mv_hofki/services/scanner/stages/volta_detection.py`
- Create: `tests/backend/test_volta_detection.py`

- [ ] **Step 1: Write tests**

Create `tests/backend/test_volta_detection.py`:

```python
"""Tests for the volta bracket detection stage."""

import cv2
import numpy as np

from mv_hofki.services.scanner.stages.base import (
    MeasureData,
    PipelineContext,
    StaffData,
)


def _make_image_with_bracket():
    """Create a binary image with staff lines and a volta bracket above."""
    img = np.full((400, 800), 255, dtype=np.uint8)

    # Staff lines at y=200..240
    for y in [200, 210, 220, 230, 240]:
        img[y : y + 2, 20:780] = 0

    # Volta bracket above staff: horizontal line at y=170 from x=400 to x=600
    cv2.line(img, (400, 170), (600, 170), 0, 2)
    # Vertical hook at left end
    cv2.line(img, (400, 170), (400, 185), 0, 2)

    staff = StaffData(
        staff_index=0,
        y_top=140,
        y_bottom=300,
        line_positions=[200, 210, 220, 230, 240],
        line_spacing=10.0,
    )
    return img, staff


def test_volta_detects_bracket_above_repeat_barline():
    from mv_hofki.services.scanner.stages.volta_detection import VoltaDetectionStage

    img, staff = _make_image_with_bracket()
    measures = [
        MeasureData(
            staff_index=0,
            measure_number_in_staff=1,
            global_measure_number=1,
            x_start=200,
            x_end=400,
            end_barline="Wiederholung Ende",
        ),
        MeasureData(
            staff_index=0,
            measure_number_in_staff=2,
            global_measure_number=2,
            x_start=400,
            x_end=600,
            end_barline="Einfacher Taktstrich",
        ),
    ]

    ctx = PipelineContext(
        image=img,
        processed_image=img.copy(),
        staves=[staff],
        measures=measures,
        metadata={
            "template_display_names": {60: "Wiederholungs Klammer"},
        },
    )

    stage = VoltaDetectionStage()
    result = stage.process(ctx)

    # Should find a symbol for the bracket
    bracket_syms = [
        s for s in result.symbols if s.matched_template_id == 60
    ]
    assert len(bracket_syms) >= 1
    bracket = bracket_syms[0]
    assert bracket.staff_index == 0
    assert bracket.staff_x_start is not None
    assert bracket.staff_x_start <= 410
    assert bracket.staff_x_end is not None
    assert bracket.staff_x_end >= 590


def test_volta_assigns_volta_numbers_to_measures():
    from mv_hofki.services.scanner.stages.volta_detection import VoltaDetectionStage

    img, staff = _make_image_with_bracket()

    # Add a second bracket at x=600-780
    cv2.line(img, (600, 170), (780, 170), 0, 2)
    cv2.line(img, (600, 170), (600, 185), 0, 2)

    measures = [
        MeasureData(
            staff_index=0,
            measure_number_in_staff=1,
            global_measure_number=1,
            x_start=200,
            x_end=400,
            end_barline="Wiederholung Ende",
        ),
        MeasureData(
            staff_index=0,
            measure_number_in_staff=2,
            global_measure_number=2,
            x_start=400,
            x_end=600,
            end_barline=None,
        ),
        MeasureData(
            staff_index=0,
            measure_number_in_staff=3,
            global_measure_number=3,
            x_start=600,
            x_end=780,
            end_barline=None,
        ),
    ]

    ctx = PipelineContext(
        image=img,
        processed_image=img.copy(),
        staves=[staff],
        measures=measures,
        metadata={
            "template_display_names": {60: "Wiederholungs Klammer"},
        },
    )

    stage = VoltaDetectionStage()
    result = stage.process(ctx)

    # Measures under brackets should have volta_number set
    volta_measures = [m for m in result.measures if m.volta_number is not None]
    assert len(volta_measures) >= 2

    # First bracket → volta 1, second → volta 2
    nums = sorted(set(m.volta_number for m in volta_measures))
    assert 1 in nums
    assert 2 in nums


def test_volta_no_detection_without_repeat_barlines():
    from mv_hofki.services.scanner.stages.volta_detection import VoltaDetectionStage

    img, staff = _make_image_with_bracket()
    measures = [
        MeasureData(
            staff_index=0,
            measure_number_in_staff=1,
            global_measure_number=1,
            x_start=200,
            x_end=600,
            end_barline="Einfacher Taktstrich",
        ),
    ]

    ctx = PipelineContext(
        image=img,
        processed_image=img.copy(),
        staves=[staff],
        measures=measures,
        metadata={
            "template_display_names": {60: "Wiederholungs Klammer"},
        },
    )

    stage = VoltaDetectionStage()
    result = stage.process(ctx)

    bracket_syms = [
        s for s in result.symbols if s.matched_template_id == 60
    ]
    assert len(bracket_syms) == 0


def test_volta_validate():
    from mv_hofki.services.scanner.stages.volta_detection import VoltaDetectionStage

    stage = VoltaDetectionStage()

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

Run: `python -m pytest tests/backend/test_volta_detection.py -v`
Expected: FAIL (the old VoltaDetectionStage doesn't produce symbols)

- [ ] **Step 3: Rewrite volta_detection.py**

Replace the entire content of `src/backend/mv_hofki/services/scanner/stages/volta_detection.py`:

```python
"""Volta bracket detection: find repeat brackets above staves."""

from __future__ import annotations

import cv2
import numpy as np

from mv_hofki.services.scanner.stages.base import (
    PipelineContext,
    ProcessingStage,
    SymbolData,
)
from mv_hofki.services.scanner.stages.utils import expand_to_connected

# Barline names that indicate a repeat boundary
_REPEAT_BARLINES = {
    "Wiederholung Ende",
    "Wiederholung Anfang",
    "Wiederholung Beidseitig",
}


class VoltaDetectionStage(ProcessingStage):
    """Detect volta brackets above staves by seeding from repeat barlines."""

    name = "volta_detection"

    def process(self, ctx: PipelineContext) -> PipelineContext:
        binary = ctx.processed_image
        if binary is None:
            return ctx

        staves = sorted(ctx.staves, key=lambda s: s.staff_index)
        staff_map = {s.staff_index: s for s in staves}

        # Look up template ID for "Wiederholungs Klammer"
        display_names: dict[int, str] = ctx.metadata.get(
            "template_display_names", {}
        )
        bracket_id: int | None = None
        for tid, name in display_names.items():
            if name == "Wiederholungs Klammer":
                bracket_id = tid
                break

        # Group repeat barlines by staff
        repeat_measures_by_staff: dict[int, list] = {}
        for m in ctx.measures:
            if m.end_barline in _REPEAT_BARLINES:
                repeat_measures_by_staff.setdefault(m.staff_index, []).append(m)

        debug_lines: list[dict] = []
        brackets: list[SymbolData] = []
        volta_group_id = 0

        for staff_index, repeat_measures in repeat_measures_by_staff.items():
            staff = staff_map.get(staff_index)
            if staff is None:
                continue

            top_line = min(staff.line_positions)
            region_top = staff.y_top
            region_bottom = top_line

            if region_top >= region_bottom:
                continue

            # Find horizontal Hough lines in the region above the staff
            region = binary[region_top:region_bottom, :]
            inverted = cv2.bitwise_not(region)
            edges = cv2.Canny(inverted, 50, 150, apertureSize=3)

            min_line_len = int(staff.line_spacing * 2)
            lines = cv2.HoughLinesP(
                edges,
                rho=1,
                theta=np.pi / 180,
                threshold=15,
                minLineLength=min_line_len,
                maxLineGap=10,
            )

            if lines is None:
                continue

            # Collect near-horizontal lines (≤5°)
            h_lines: list[tuple[int, int, int, int]] = []
            for line in lines:
                x1, y1, x2, y2 = line[0]
                angle = abs(np.degrees(np.arctan2(y2 - y1, x2 - x1)))

                debug_lines.append(
                    {
                        "x1": int(x1),
                        "y1": int(region_top + y1),
                        "x2": int(x2),
                        "y2": int(region_top + y2),
                        "staff_index": staff_index,
                    }
                )

                if angle <= 5:
                    if x1 > x2:
                        x1, y1, x2, y2 = x2, y2, x1, y1
                    h_lines.append((
                        int(x1),
                        int(region_top + y1),
                        int(x2),
                        int(region_top + y2),
                    ))

            # For each repeat barline, find horizontal lines near it
            for measure in repeat_measures:
                bar_x = measure.x_end
                matched = _find_bracket_line(h_lines, bar_x, staff.line_spacing)
                if matched is None:
                    continue

                lx1, ly1, lx2, ly2 = matched

                # Expand via connected components
                ex_x1, ex_y1, ex_x2, ex_y2 = expand_to_connected(
                    binary, lx1, ly1, lx2, ly2, region_top, region_bottom
                )

                bottom_line_y = max(staff.line_positions)
                ls = staff.line_spacing

                brackets.append(
                    SymbolData(
                        staff_index=staff_index,
                        x=ex_x1,
                        y=ex_y1,
                        width=ex_x2 - ex_x1,
                        height=max(ex_y2 - ex_y1, int(ls // 2)),
                        staff_y_top=round((bottom_line_y - ex_y1) / ls, 2),
                        staff_y_bottom=round(
                            (bottom_line_y - ex_y2) / ls, 2
                        ),
                        staff_x_start=ex_x1,
                        staff_x_end=ex_x2,
                        matched_template_id=bracket_id,
                        confidence=0.8,
                    )
                )

                ctx.log(
                    f"  Volta-Klammer erkannt: System {staff_index}, "
                    f"x={ex_x1}-{ex_x2}"
                )

            # Assign volta numbers to measures under brackets
            staff_brackets = [
                b for b in brackets if b.staff_index == staff_index
            ]
            staff_brackets.sort(key=lambda b: b.staff_x_start or b.x)

            if staff_brackets:
                volta_group_id += 1
                for volta_num, bracket in enumerate(staff_brackets, start=1):
                    bx1 = bracket.staff_x_start or bracket.x
                    bx2 = bracket.staff_x_end or (bracket.x + bracket.width)
                    for m in ctx.measures:
                        if m.staff_index != staff_index:
                            continue
                        # Measure overlaps with bracket X range
                        if m.x_start < bx2 and m.x_end > bx1:
                            m.volta_number = volta_num
                            m.volta_group_id = volta_group_id

        # Add brackets to symbols list
        for b in brackets:
            b.sequence_order = len(ctx.symbols)
            ctx.symbols.append(b)

        ctx.metadata["volta_debug_lines"] = debug_lines
        ctx.log(
            f"Volta-Erkennung: {len(brackets)} Klammern, "
            f"{len(debug_lines)} Hough-Linien"
        )
        return ctx

    def validate(self, ctx: PipelineContext) -> bool:
        return ctx.processed_image is not None and len(ctx.staves) > 0


def _find_bracket_line(
    h_lines: list[tuple[int, int, int, int]],
    bar_x: int,
    line_spacing: float,
) -> tuple[int, int, int, int] | None:
    """Find the horizontal line closest to a barline X position.

    The line must touch or be near the barline X coordinate (within
    1× line_spacing). Returns the longest matching line, or None.
    """
    tolerance = int(line_spacing * 1.0)
    best: tuple[int, int, int, int] | None = None
    best_len = 0

    for x1, y1, x2, y2 in h_lines:
        # Line must touch the barline X position (within tolerance)
        if x1 - tolerance <= bar_x <= x2 + tolerance:
            length = x2 - x1
            if length > best_len:
                best = (x1, y1, x2, y2)
                best_len = length

    return best
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/backend/test_volta_detection.py -v`
Expected: all 4 tests PASS

- [ ] **Step 5: Run linter**

Run: `pre-commit run --files src/backend/mv_hofki/services/scanner/stages/volta_detection.py tests/backend/test_volta_detection.py`

- [ ] **Step 6: Commit**

```bash
git add src/backend/mv_hofki/services/scanner/stages/volta_detection.py tests/backend/test_volta_detection.py
git commit -m "feat: rewrite VoltaDetectionStage with repeat barline seeding and CC expansion"
```

---

### Task 3: Manual verification

**Files:** none (manual test via UI)

- [ ] **Step 1: Restart server if needed**

- [ ] **Step 2: Run scan on a march with repeat brackets**

- [ ] **Step 3: Verify results**

1. "Wiederholungs Klammer" symbols appear with hitboxes in the symbol overlay
2. Clicking a bracket shows details in SymbolPanel
3. Volta numbers appear on the affected measures (L-shaped overlay)
4. Debug lines visible when Volta toggle is on
