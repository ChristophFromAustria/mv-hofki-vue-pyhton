# Volta Detection Rewrite: Run-Length Scanning

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Hough-based volta bracket detection with a run-length scanning approach that seeds from repeat barline positions and uses flood fill to determine bracket extents.

**Architecture:** For each "Wiederholung Ende" / "Wiederholung Beidseitig" barline, scan the measure region before and after for horizontal pixel runs in the above-staff area. Group runs into line candidates, expand via connected components to get the full bracket hitbox, then assign volta numbers (before=1, after=2) and map brackets to measures by X-overlap.

**Tech Stack:** Python, NumPy, OpenCV (cv2.connectedComponents via existing `expand_to_connected`), pytest

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `src/backend/mv_hofki/services/scanner/stages/volta_detection.py` | Rewrite | Complete new implementation with run-length scanning |
| `tests/backend/test_volta_detection.py` | Rewrite | Tests for new algorithm |

---

### Task 1: Write helper — find horizontal runs in a pixel row

**Files:**
- Modify: `src/backend/mv_hofki/services/scanner/stages/volta_detection.py`
- Test: `tests/backend/test_volta_detection.py`

- [ ] **Step 1: Write the failing test for `_find_runs`**

```python
"""Tests for the volta bracket detection stage."""

import numpy as np
import pytest


def test_find_runs_single_run():
    """A single black segment in a white row returns one run."""
    from mv_hofki.services.scanner.stages.volta_detection import _find_runs

    # Row: 10 white, 20 black, 10 white (40 px total)
    row = np.full(40, 255, dtype=np.uint8)
    row[10:30] = 0
    runs = _find_runs(row, min_length=10)
    assert len(runs) == 1
    assert runs[0] == (10, 29)  # (start_x, end_x) inclusive


def test_find_runs_filters_short():
    """Runs shorter than min_length are discarded."""
    from mv_hofki.services.scanner.stages.volta_detection import _find_runs

    row = np.full(40, 255, dtype=np.uint8)
    row[5:10] = 0  # 5 px run
    row[20:35] = 0  # 15 px run
    runs = _find_runs(row, min_length=10)
    assert len(runs) == 1
    assert runs[0] == (20, 34)


def test_find_runs_empty_row():
    """An all-white row returns no runs."""
    from mv_hofki.services.scanner.stages.volta_detection import _find_runs

    row = np.full(40, 255, dtype=np.uint8)
    runs = _find_runs(row, min_length=5)
    assert runs == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/backend/test_volta_detection.py::test_find_runs_single_run tests/backend/test_volta_detection.py::test_find_runs_filters_short tests/backend/test_volta_detection.py::test_find_runs_empty_row -v`
Expected: FAIL with `ImportError` (function does not exist yet)

- [ ] **Step 3: Write `_find_runs` implementation**

Replace the entire content of `volta_detection.py` with the new module skeleton containing `_find_runs`:

```python
"""Volta bracket detection: find repeat brackets above staves via run-length scanning."""

from __future__ import annotations

import math

import cv2
import numpy as np

from mv_hofki.services.scanner.stages.base import (
    MeasureData,
    PipelineContext,
    ProcessingStage,
    SymbolData,
)
from mv_hofki.services.scanner.stages.utils import expand_to_connected

# Barline names that indicate a repeat boundary
_REPEAT_BARLINES = {
    "Wiederholung Ende",
    "Wiederholung Beidseitig",
}

_BLACK_THRESHOLD = 128


def _find_runs(
    row: np.ndarray, min_length: int
) -> list[tuple[int, int]]:
    """Find contiguous black pixel runs in a single row.

    Parameters
    ----------
    row : 1-D uint8 array (one row of a grayscale image)
    min_length : minimum run length in pixels

    Returns list of (start_x, end_x) inclusive.
    """
    black = row < _BLACK_THRESHOLD
    runs: list[tuple[int, int]] = []
    n = len(black)
    i = 0
    while i < n:
        if black[i]:
            start = i
            while i < n and black[i]:
                i += 1
            end = i - 1
            if (end - start + 1) >= min_length:
                runs.append((start, end))
        else:
            i += 1
    return runs
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/backend/test_volta_detection.py::test_find_runs_single_run tests/backend/test_volta_detection.py::test_find_runs_filters_short tests/backend/test_volta_detection.py::test_find_runs_empty_row -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/backend/mv_hofki/services/scanner/stages/volta_detection.py tests/backend/test_volta_detection.py
git commit -m "feat(volta): add _find_runs helper for run-length scanning"
```

---

### Task 2: Write helper — group runs into line candidates

**Files:**
- Modify: `src/backend/mv_hofki/services/scanner/stages/volta_detection.py`
- Test: `tests/backend/test_volta_detection.py`

- [ ] **Step 1: Write the failing test for `_group_runs_into_lines`**

Append to test file:

```python
def test_group_runs_simple_horizontal_line():
    """Runs on adjacent rows with strong X-overlap form one line group."""
    from mv_hofki.services.scanner.stages.volta_detection import (
        _group_runs_into_lines,
    )

    # 3 rows of runs at roughly the same X position
    runs_by_row = {
        10: [(50, 150)],
        11: [(51, 151)],
        12: [(50, 150)],
    }
    lines = _group_runs_into_lines(runs_by_row, min_height=2)
    assert len(lines) == 1
    line = lines[0]
    # Line bounding box: x_start, y_start, x_end, y_end
    assert line[0] <= 51  # x_start
    assert line[1] == 10  # y_start
    assert line[2] >= 150  # x_end
    assert line[3] == 12  # y_end


def test_group_runs_rejects_non_horizontal():
    """Runs that drift too much in X are rejected (>2 degree drift)."""
    from mv_hofki.services.scanner.stages.volta_detection import (
        _group_runs_into_lines,
    )

    # 20 rows where the midpoint drifts 20px — that's atan(20/20)=45 degrees
    runs_by_row = {}
    for i in range(20):
        start = 50 + i
        runs_by_row[i] = [(start, start + 100)]
    lines = _group_runs_into_lines(runs_by_row, min_height=2)
    assert len(lines) == 0


def test_group_runs_two_separate_lines():
    """Runs at different X positions on the same rows form separate groups."""
    from mv_hofki.services.scanner.stages.volta_detection import (
        _group_runs_into_lines,
    )

    runs_by_row = {
        10: [(50, 150), (300, 400)],
        11: [(50, 150), (300, 400)],
        12: [(50, 150), (300, 400)],
    }
    lines = _group_runs_into_lines(runs_by_row, min_height=2)
    assert len(lines) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/backend/test_volta_detection.py::test_group_runs_simple_horizontal_line tests/backend/test_volta_detection.py::test_group_runs_rejects_non_horizontal tests/backend/test_volta_detection.py::test_group_runs_two_separate_lines -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Write `_group_runs_into_lines` implementation**

Add to `volta_detection.py`:

```python
# Maximum angle deviation from horizontal (degrees)
_MAX_ANGLE_DEG = 2.0


def _group_runs_into_lines(
    runs_by_row: dict[int, list[tuple[int, int]]],
    min_height: int,
) -> list[tuple[int, int, int, int]]:
    """Group runs on adjacent rows into horizontal line candidates.

    Parameters
    ----------
    runs_by_row : mapping of absolute Y -> list of (start_x, end_x) runs
    min_height : minimum number of rows a group must span

    Returns list of (x_start, y_start, x_end, y_end) bounding boxes
    for line candidates that pass the horizontality check.
    """
    if not runs_by_row:
        return []

    sorted_rows = sorted(runs_by_row.keys())

    # Each active group tracks: list of (y, start_x, end_x) per row
    active_groups: list[list[tuple[int, int, int]]] = []
    result: list[tuple[int, int, int, int]] = []

    for y in sorted_rows:
        row_runs = runs_by_row[y]
        next_active: list[list[tuple[int, int, int]]] = []
        used_runs: set[int] = set()

        for group in active_groups:
            last_y, last_sx, last_ex = group[-1]
            if y - last_y > 1:
                # Gap — finalize this group
                _finalize_group(group, min_height, result)
                continue

            # Find a matching run in this row (>=80% X overlap)
            best_idx = _best_overlap_run(last_sx, last_ex, row_runs, used_runs)
            if best_idx is not None:
                sx, ex = row_runs[best_idx]
                group.append((y, sx, ex))
                used_runs.add(best_idx)
                next_active.append(group)
            else:
                _finalize_group(group, min_height, result)

        # Start new groups from unmatched runs
        for idx, (sx, ex) in enumerate(row_runs):
            if idx not in used_runs:
                next_active.append([(y, sx, ex)])

        active_groups = next_active

    # Finalize remaining groups
    for group in active_groups:
        _finalize_group(group, min_height, result)

    return result


def _best_overlap_run(
    last_sx: int,
    last_ex: int,
    row_runs: list[tuple[int, int]],
    used: set[int],
) -> int | None:
    """Find the run in row_runs with >=80% X overlap to (last_sx, last_ex)."""
    last_len = last_ex - last_sx + 1
    best_idx = None
    best_overlap = 0
    for idx, (sx, ex) in enumerate(row_runs):
        if idx in used:
            continue
        overlap = max(0, min(last_ex, ex) - max(last_sx, sx) + 1)
        run_len = ex - sx + 1
        min_len = min(last_len, run_len)
        if min_len > 0 and overlap >= min_len * 0.8 and overlap > best_overlap:
            best_overlap = overlap
            best_idx = idx
    return best_idx


def _finalize_group(
    group: list[tuple[int, int, int]],
    min_height: int,
    result: list[tuple[int, int, int, int]],
) -> None:
    """Check a completed group for height and horizontality, append to result."""
    if len(group) < min_height:
        return

    y_start = group[0][0]
    y_end = group[-1][0]
    height = y_end - y_start + 1

    if height < min_height:
        return

    # Check horizontality: midpoint drift vs height
    first_mid = (group[0][1] + group[0][2]) / 2
    last_mid = (group[-1][1] + group[-1][2]) / 2
    drift = abs(last_mid - first_mid)
    max_drift = math.tan(math.radians(_MAX_ANGLE_DEG)) * height
    if drift > max_drift:
        return

    x_start = min(sx for _, sx, _ in group)
    x_end = max(ex for _, _, ex in group)
    result.append((x_start, y_start, x_end, y_end))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/backend/test_volta_detection.py::test_group_runs_simple_horizontal_line tests/backend/test_volta_detection.py::test_group_runs_rejects_non_horizontal tests/backend/test_volta_detection.py::test_group_runs_two_separate_lines -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/backend/mv_hofki/services/scanner/stages/volta_detection.py tests/backend/test_volta_detection.py
git commit -m "feat(volta): add _group_runs_into_lines helper with horizontality check"
```

---

### Task 3: Write helper — scan a region for horizontal line candidates

**Files:**
- Modify: `src/backend/mv_hofki/services/scanner/stages/volta_detection.py`
- Test: `tests/backend/test_volta_detection.py`

- [ ] **Step 1: Write the failing test for `_scan_for_horizontal_lines`**

Append to test file:

```python
def test_scan_for_horizontal_lines_finds_bracket():
    """A drawn horizontal line in a binary image region is detected."""
    from mv_hofki.services.scanner.stages.volta_detection import (
        _scan_for_horizontal_lines,
    )

    img = np.full((100, 400), 255, dtype=np.uint8)
    # Draw a horizontal line at y=20, x=50..250 (2px thick)
    img[20:22, 50:250] = 0

    lines = _scan_for_horizontal_lines(
        binary=img,
        y_start=10,
        y_end=40,
        x_start=0,
        x_end=400,
        min_run_length=50,
        min_height=2,
    )
    assert len(lines) == 1
    x1, y1, x2, y2 = lines[0]
    assert x1 <= 50
    assert x2 >= 249
    assert y1 >= 20
    assert y2 <= 22


def test_scan_for_horizontal_lines_ignores_short():
    """Lines shorter than min_run_length are not returned."""
    from mv_hofki.services.scanner.stages.volta_detection import (
        _scan_for_horizontal_lines,
    )

    img = np.full((100, 400), 255, dtype=np.uint8)
    img[20:22, 50:80] = 0  # 30px, below threshold

    lines = _scan_for_horizontal_lines(
        binary=img,
        y_start=10,
        y_end=40,
        x_start=0,
        x_end=400,
        min_run_length=50,
        min_height=2,
    )
    assert len(lines) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/backend/test_volta_detection.py::test_scan_for_horizontal_lines_finds_bracket tests/backend/test_volta_detection.py::test_scan_for_horizontal_lines_ignores_short -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Write `_scan_for_horizontal_lines` implementation**

Add to `volta_detection.py`:

```python
def _scan_for_horizontal_lines(
    binary: np.ndarray,
    y_start: int,
    y_end: int,
    x_start: int,
    x_end: int,
    min_run_length: int,
    min_height: int,
) -> list[tuple[int, int, int, int]]:
    """Scan a region for horizontal line candidates via run-length analysis.

    Parameters
    ----------
    binary : grayscale image (0=black, 255=white)
    y_start, y_end : Y range to scan (absolute pixel coords, exclusive end)
    x_start, x_end : X range to scan (absolute pixel coords, exclusive end)
    min_run_length : minimum horizontal run length in pixels
    min_height : minimum number of rows a line must span

    Returns list of (x_start, y_start, x_end, y_end) bounding boxes.
    """
    h, w = binary.shape[:2]
    y_start = max(0, y_start)
    y_end = min(h, y_end)
    x_start = max(0, x_start)
    x_end = min(w, x_end)

    if y_start >= y_end or x_start >= x_end:
        return []

    runs_by_row: dict[int, list[tuple[int, int]]] = {}
    for y in range(y_start, y_end):
        row_slice = binary[y, x_start:x_end]
        runs = _find_runs(row_slice, min_run_length)
        if runs:
            # Shift X coordinates back to absolute
            runs_by_row[y] = [(sx + x_start, ex + x_start) for sx, ex in runs]

    return _group_runs_into_lines(runs_by_row, min_height)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/backend/test_volta_detection.py::test_scan_for_horizontal_lines_finds_bracket tests/backend/test_volta_detection.py::test_scan_for_horizontal_lines_ignores_short -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/backend/mv_hofki/services/scanner/stages/volta_detection.py tests/backend/test_volta_detection.py
git commit -m "feat(volta): add _scan_for_horizontal_lines region scanner"
```

---

### Task 4: Write the main VoltaDetectionStage.process method

**Files:**
- Modify: `src/backend/mv_hofki/services/scanner/stages/volta_detection.py`
- Test: `tests/backend/test_volta_detection.py`

- [ ] **Step 1: Write the failing integration test**

Append to test file:

```python
import cv2

from mv_hofki.services.scanner.stages.base import (
    MeasureData,
    PipelineContext,
    StaffData,
)


def _make_staff_image():
    """Create a binary image with staff lines."""
    img = np.full((400, 800), 255, dtype=np.uint8)
    # Staff lines at y=200..240 (5 lines, spacing=10)
    for y_pos in [200, 210, 220, 230, 240]:
        img[y_pos : y_pos + 2, 20:780] = 0
    staff = StaffData(
        staff_index=0,
        y_top=140,
        y_bottom=300,
        line_positions=[200, 210, 220, 230, 240],
        line_spacing=10.0,
        line_thickness=2,
        x_start=20,
        x_end=780,
    )
    return img, staff


def test_volta_detects_bracket_before_repeat():
    """A horizontal bracket above the measure before a repeat end is detected as volta 1."""
    from mv_hofki.services.scanner.stages.volta_detection import VoltaDetectionStage

    img, staff = _make_staff_image()

    # Draw volta bracket above measure 2 (x=300..500): horizontal at y=170, hook at x=300
    cv2.line(img, (300, 170), (500, 170), 0, 2)
    cv2.line(img, (300, 170), (300, 185), 0, 2)

    measures = [
        MeasureData(0, 1, 1, x_start=100, x_end=300, end_barline="Einfacher Taktstrich"),
        MeasureData(0, 2, 2, x_start=300, x_end=500, end_barline="Wiederholung Ende"),
        MeasureData(0, 3, 3, x_start=500, x_end=700, end_barline="Einfacher Taktstrich"),
    ]

    ctx = PipelineContext(
        image=img,
        processed_image=img.copy(),
        staves=[staff],
        measures=measures,
        metadata={"template_display_names": {60: "Wiederholungs Klammer"}},
    )

    stage = VoltaDetectionStage()
    result = stage.process(ctx)

    bracket_syms = [s for s in result.symbols if s.matched_template_id == 60]
    assert len(bracket_syms) >= 1

    # Measure 2 should be volta 1
    m2 = [m for m in result.measures if m.global_measure_number == 2][0]
    assert m2.volta_number == 1
    assert m2.volta_group_id is not None


def test_volta_detects_bracket_after_repeat():
    """A bracket above the measure after a repeat end is detected as volta 2."""
    from mv_hofki.services.scanner.stages.volta_detection import VoltaDetectionStage

    img, staff = _make_staff_image()

    # Volta 1 bracket above measure 2
    cv2.line(img, (300, 170), (500, 170), 0, 2)
    cv2.line(img, (300, 170), (300, 185), 0, 2)

    # Volta 2 bracket above measure 3
    cv2.line(img, (510, 170), (700, 170), 0, 2)
    cv2.line(img, (510, 170), (510, 185), 0, 2)

    measures = [
        MeasureData(0, 1, 1, x_start=100, x_end=300, end_barline="Einfacher Taktstrich"),
        MeasureData(0, 2, 2, x_start=300, x_end=500, end_barline="Wiederholung Ende"),
        MeasureData(0, 3, 3, x_start=500, x_end=700, end_barline="Einfacher Taktstrich"),
    ]

    ctx = PipelineContext(
        image=img,
        processed_image=img.copy(),
        staves=[staff],
        measures=measures,
        metadata={"template_display_names": {60: "Wiederholungs Klammer"}},
    )

    stage = VoltaDetectionStage()
    result = stage.process(ctx)

    bracket_syms = [s for s in result.symbols if s.matched_template_id == 60]
    assert len(bracket_syms) == 2

    m2 = [m for m in result.measures if m.global_measure_number == 2][0]
    m3 = [m for m in result.measures if m.global_measure_number == 3][0]
    assert m2.volta_number == 1
    assert m3.volta_number == 2
    assert m2.volta_group_id == m3.volta_group_id


def test_volta_no_detection_without_repeat():
    """No brackets are detected when there are no repeat barlines."""
    from mv_hofki.services.scanner.stages.volta_detection import VoltaDetectionStage

    img, staff = _make_staff_image()
    cv2.line(img, (300, 170), (500, 170), 0, 2)

    measures = [
        MeasureData(0, 1, 1, x_start=100, x_end=500, end_barline="Einfacher Taktstrich"),
    ]

    ctx = PipelineContext(
        image=img,
        processed_image=img.copy(),
        staves=[staff],
        measures=measures,
        metadata={"template_display_names": {60: "Wiederholungs Klammer"}},
    )

    stage = VoltaDetectionStage()
    result = stage.process(ctx)

    bracket_syms = [s for s in result.symbols if s.matched_template_id == 60]
    assert len(bracket_syms) == 0


def test_volta_cross_staff():
    """When repeat is at end of staff, volta 2 is found above next staff."""
    from mv_hofki.services.scanner.stages.volta_detection import VoltaDetectionStage

    img = np.full((600, 800), 255, dtype=np.uint8)

    # Staff 0: lines at y=100..140
    for y_pos in [100, 110, 120, 130, 140]:
        img[y_pos : y_pos + 2, 20:780] = 0
    staff0 = StaffData(
        staff_index=0, y_top=50, y_bottom=200,
        line_positions=[100, 110, 120, 130, 140],
        line_spacing=10.0, line_thickness=2, x_start=20, x_end=780,
    )

    # Staff 1: lines at y=350..390
    for y_pos in [350, 360, 370, 380, 390]:
        img[y_pos : y_pos + 2, 20:780] = 0
    staff1 = StaffData(
        staff_index=1, y_top=300, y_bottom=450,
        line_positions=[350, 360, 370, 380, 390],
        line_spacing=10.0, line_thickness=2, x_start=20, x_end=780,
    )

    # Volta 1 bracket above staff 0, measure at end
    cv2.line(img, (600, 70), (770, 70), 0, 2)
    cv2.line(img, (600, 70), (600, 85), 0, 2)

    # Volta 2 bracket above staff 1, measure at start
    cv2.line(img, (30, 320), (200, 320), 0, 2)
    cv2.line(img, (30, 320), (30, 335), 0, 2)

    measures = [
        MeasureData(0, 1, 1, x_start=20, x_end=400, end_barline="Einfacher Taktstrich"),
        MeasureData(0, 2, 2, x_start=400, x_end=600, end_barline="Einfacher Taktstrich"),
        MeasureData(0, 3, 3, x_start=600, x_end=780, end_barline="Wiederholung Ende"),
        MeasureData(1, 1, 4, x_start=20, x_end=200, end_barline="Einfacher Taktstrich"),
        MeasureData(1, 2, 5, x_start=200, x_end=500, end_barline="Einfacher Taktstrich"),
    ]

    ctx = PipelineContext(
        image=img,
        processed_image=img.copy(),
        staves=[staff0, staff1],
        measures=measures,
        metadata={"template_display_names": {60: "Wiederholungs Klammer"}},
    )

    stage = VoltaDetectionStage()
    result = stage.process(ctx)

    m3 = [m for m in result.measures if m.global_measure_number == 3][0]
    m4 = [m for m in result.measures if m.global_measure_number == 4][0]

    assert m3.volta_number == 1
    assert m4.volta_number == 2
    assert m3.volta_group_id == m4.volta_group_id


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

Run: `python -m pytest tests/backend/test_volta_detection.py::test_volta_detects_bracket_before_repeat tests/backend/test_volta_detection.py::test_volta_detects_bracket_after_repeat tests/backend/test_volta_detection.py::test_volta_no_detection_without_repeat tests/backend/test_volta_detection.py::test_volta_cross_staff tests/backend/test_volta_detection.py::test_volta_validate -v`
Expected: FAIL (class exists but `process` method is not yet reimplemented)

- [ ] **Step 3: Write VoltaDetectionStage.process implementation**

Add the `VoltaDetectionStage` class to `volta_detection.py`:

```python
class VoltaDetectionStage(ProcessingStage):
    """Detect volta brackets above staves via run-length scanning,
    seeded from repeat barline positions."""

    name = "volta_detection"

    def process(self, ctx: PipelineContext) -> PipelineContext:
        binary = ctx.processed_image
        if binary is None:
            return ctx

        staves = sorted(ctx.staves, key=lambda s: s.staff_index)
        staff_by_index = {s.staff_index: s for s in staves}

        # Look up template ID for "Wiederholungs Klammer"
        display_names: dict[int, str] = ctx.metadata.get("template_display_names", {})
        bracket_id: int | None = None
        for tid, name in display_names.items():
            if name == "Wiederholungs Klammer":
                bracket_id = tid
                break

        # Build ordered list of all measures
        all_measures = sorted(ctx.measures, key=lambda m: (m.staff_index, m.x_start))

        # Find repeat-end measures and their neighbours
        repeat_pairs: list[tuple[MeasureData | None, MeasureData | None, int]] = []
        volta_group_id = 0

        for idx, m in enumerate(all_measures):
            if m.end_barline not in _REPEAT_BARLINES:
                continue
            volta_group_id += 1
            # Measure before (the repeat measure itself) -> volta 1 candidate
            before_m = m
            # Measure after -> volta 2 candidate (may be on next staff)
            after_m = all_measures[idx + 1] if idx + 1 < len(all_measures) else None
            repeat_pairs.append((before_m, after_m, volta_group_id))

        brackets: list[SymbolData] = []
        debug_lines: list[dict] = []

        for before_m, after_m, group_id in repeat_pairs:
            for volta_num, measure in [(1, before_m), (2, after_m)]:
                if measure is None:
                    continue

                staff = staff_by_index.get(measure.staff_index)
                if staff is None:
                    continue

                ls = staff.line_spacing
                top_line = min(staff.line_positions)
                min_thickness = staff.line_thickness or 2

                y_start = staff.y_top
                y_end = top_line - int(ls)
                if y_start >= y_end:
                    continue

                min_run_length = int(ls * 2)

                line_candidates = _scan_for_horizontal_lines(
                    binary,
                    y_start=y_start,
                    y_end=y_end,
                    x_start=measure.x_start,
                    x_end=measure.x_end,
                    min_run_length=min_run_length,
                    min_height=min_thickness,
                )

                for lx1, ly1, lx2, ly2 in line_candidates:
                    debug_lines.append({
                        "x1": lx1, "y1": ly1, "x2": lx2, "y2": ly2,
                        "staff_index": staff.staff_index,
                    })

                    # Expand to full connected component
                    bx1, by1, bx2, by2 = expand_to_connected(
                        binary, lx1, ly1, lx2, ly2, y_start, y_end,
                    )

                    # Filter: must be wider than tall (factor 2)
                    box_w = bx2 - bx1
                    box_h = by2 - by1
                    if box_h > 0 and box_w < box_h * 2:
                        continue

                    bottom_line_y = max(staff.line_positions)

                    brackets.append(SymbolData(
                        staff_index=staff.staff_index,
                        x=bx1,
                        y=by1,
                        width=box_w,
                        height=max(box_h, int(ls // 2)),
                        staff_y_top=round((bottom_line_y - by1) / ls, 2),
                        staff_y_bottom=round((bottom_line_y - by2) / ls, 2),
                        staff_x_start=bx1,
                        staff_x_end=bx2,
                        matched_template_id=bracket_id,
                        confidence=0.8,
                    ))

                    # Assign volta number to all overlapping measures
                    for m in ctx.measures:
                        if m.staff_index != staff.staff_index:
                            continue
                        if m.x_start < bx2 and m.x_end > bx1:
                            m.volta_number = volta_num
                            m.volta_group_id = group_id

                    ctx.log(
                        f"  Volta-Klammer {volta_num} erkannt: "
                        f"System {staff.staff_index}, x={bx1}-{bx2}"
                    )
                    # Only use the first (longest) line candidate per measure
                    break

        # Add brackets to symbols list
        for b in brackets:
            b.sequence_order = len(ctx.symbols)
            ctx.symbols.append(b)

        ctx.metadata["volta_debug_lines"] = debug_lines
        ctx.log(
            f"Volta-Erkennung: {len(brackets)} Klammern, "
            f"{len(debug_lines)} Linienkandidaten"
        )
        return ctx

    def validate(self, ctx: PipelineContext) -> bool:
        return ctx.processed_image is not None and len(ctx.staves) > 0
```

- [ ] **Step 4: Run all tests to verify they pass**

Run: `python -m pytest tests/backend/test_volta_detection.py -v`
Expected: ALL PASS

- [ ] **Step 5: Run pre-commit checks**

Run: `cd /workspaces/mv_hofki && pre-commit run --all-files`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/backend/mv_hofki/services/scanner/stages/volta_detection.py tests/backend/test_volta_detection.py
git commit -m "feat(volta): rewrite VoltaDetectionStage with run-length scanning

Replace Hough-based detection with zeilenweises run-length scanning.
Seeds from repeat barline positions, uses expand_to_connected for
full bracket hitbox, supports cross-staff detection."
```

---

### Task 5: Verify full test suite and clean up

**Files:**
- No new files

- [ ] **Step 1: Run full backend test suite**

Run: `python -m pytest tests/backend/ -v`
Expected: ALL PASS (no regressions)

- [ ] **Step 2: Run pre-commit**

Run: `cd /workspaces/mv_hofki && pre-commit run --all-files`
Expected: PASS

- [ ] **Step 3: Final commit if any formatting changes**

Only if pre-commit made changes:
```bash
git add -u
git commit -m "style: apply formatting fixes"
```
