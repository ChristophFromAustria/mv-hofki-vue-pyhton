# Post-Matching Refactoring & Taktgrenzen-Verfeinerung — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract barline filter into its own module, compute staff X-bounds in StaffRemovalStage, and use barline start (not end) as measure boundary.

**Architecture:** StaffData gains `x_start`/`x_end` fields populated by StaffRemovalStage from its existing `has_symbol` column analysis. PostMatching becomes a package with the orchestrator in `__init__.py` and BarlineFilter in its own module. MeasureDetectionStage uses `bl_start` as boundary and staff X-bounds instead of symbol min/max. StaffRemoval becomes mandatory (config guard removed).

**Tech Stack:** Python, numpy, pytest

---

### Task 1: Add x_start/x_end to StaffData

**Files:**
- Modify: `src/backend/mv_hofki/services/scanner/stages/base.py:14-25`
- Test: `tests/backend/test_post_matching.py` (existing helper uses StaffData)

- [ ] **Step 1: Add fields to StaffData**

In `src/backend/mv_hofki/services/scanner/stages/base.py`, add two fields after `line_thickness`:

```python
@dataclass
class StaffData:
    """Data for a single detected staff."""

    staff_index: int
    y_top: int
    y_bottom: int
    line_positions: list[int]
    line_spacing: float
    line_thickness: int | None = None
    x_start: int | None = None
    x_end: int | None = None
    clef: str | None = None
    key_signature: str | None = None
    time_signature: str | None = None
```

- [ ] **Step 2: Run existing tests to verify nothing breaks**

Run: `python -m pytest tests/backend/test_post_matching.py tests/backend/test_measure_detection.py tests/backend/test_template_matching_features.py -v`
Expected: All PASS (new fields have defaults, no existing code affected)

- [ ] **Step 3: Commit**

```bash
git add src/backend/mv_hofki/services/scanner/stages/base.py
git commit -m "feat: add x_start/x_end fields to StaffData"
```

---

### Task 2: Compute staff X-bounds in StaffRemovalStage

**Files:**
- Modify: `src/backend/mv_hofki/services/scanner/stages/staff_removal.py:22-48`
- Test: `tests/backend/test_template_matching_features.py` (existing staff removal test)

- [ ] **Step 1: Write a test for x_start/x_end computation**

Add to `tests/backend/test_template_matching_features.py` after the existing `test_staff_removal_before_matching_config` test (line ~234):

```python
def test_staff_removal_sets_x_bounds():
    """StaffRemovalStage should set x_start/x_end on each staff."""
    from mv_hofki.services.scanner.stages.staff_removal import StaffRemovalStage

    img = np.full((200, 400), 255, dtype=np.uint8)
    # Draw staff lines from x=20 to x=380
    for i in range(5):
        y = 30 + i * 20
        img[y : y + 2, 20:380] = 0
    # Draw a symbol (black block) at x=50..70
    img[25:55, 50:70] = 0
    # Draw another symbol at x=300..320
    img[25:55, 300:320] = 0

    staff = StaffData(
        staff_index=0,
        y_top=0,
        y_bottom=180,
        line_positions=[30, 50, 70, 90, 110],
        line_spacing=20.0,
    )
    ctx = PipelineContext(image=img.copy(), staves=[staff])
    stage = StaffRemovalStage()
    result = stage.process(ctx)

    assert result.staves[0].x_start is not None
    assert result.staves[0].x_end is not None
    # The symbol regions are at x=50..70 and x=300..320
    # x_start should be <= 50, x_end should be >= 320
    assert result.staves[0].x_start <= 50
    assert result.staves[0].x_end >= 319
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/backend/test_template_matching_features.py::test_staff_removal_sets_x_bounds -v`
Expected: FAIL — `x_start` is still `None`

- [ ] **Step 3: Implement X-bounds computation in StaffRemovalStage**

In `src/backend/mv_hofki/services/scanner/stages/staff_removal.py`, modify the `process` method. After the existing `_remove_empty_staff_segments` call (line 43), add a call to a new method that computes x_start/x_end. The `_remove_empty_staff_segments` method already computes `has_symbol` — extract the bounds from it.

Replace the `_remove_empty_staff_segments` static method signature and the `process` method:

```python
def process(self, ctx: PipelineContext) -> PipelineContext:
    assert ctx.image is not None
    img = ctx.image.copy()

    thickness_pct = ctx.config.get("staff_removal_thickness_pct", 100)
    symbol_padding = ctx.config.get("staff_removal_symbol_padding", 0)

    for staff in ctx.staves:
        measured = self._measure_thickness(img, staff.line_positions)
        effective = max(1, int(measured * thickness_pct / 100))
        staff.line_thickness = int(measured)
        ctx.log(
            f"  System {staff.staff_index}: Liniendicke={measured}px, "
            f"effektiv={effective}px ({thickness_pct}%), "
            f"Abstand={staff.line_spacing:.0f}px"
        )
        x_start, x_end = self._remove_empty_staff_segments(
            img,
            staff.line_positions,
            line_spacing=staff.line_spacing,
            line_thickness=effective,
            symbol_padding=symbol_padding,
        )
        staff.x_start = x_start
        staff.x_end = x_end

    ctx.image = img
    ctx.processed_image = img.copy()
    return ctx
```

Update `_remove_empty_staff_segments` to return `(x_start, x_end)`:

```python
@staticmethod
def _remove_empty_staff_segments(
    img: np.ndarray,
    line_positions: list[int],
    line_spacing: float,
    line_thickness: int,
    symbol_padding: int = 0,
) -> tuple[int | None, int | None]:
    """Erase columns of the staff region where only line pixels exist.

    *symbol_padding* keeps that many extra pixels of staff lines intact
    on each side of a symbol, so lines don't end abruptly at the symbol
    edge.

    Returns ``(x_start, x_end)`` — the first and last column indices
    that contain symbol pixels, or ``(None, None)`` if no symbols found.
    """
    h, w = img.shape[:2]
    half_t = line_thickness // 2 + 1

    margin = int(line_spacing * 0.5)
    region_top = max(0, line_positions[0] - margin)
    region_bot = min(h, line_positions[-1] + margin)

    region_h = region_bot - region_top
    line_mask = np.zeros(region_h, dtype=bool)
    for ly in line_positions:
        local_top = max(0, ly - half_t - region_top)
        local_bot = min(region_h, ly + half_t + 1 - region_top)
        line_mask[local_top:local_bot] = True

    region = img[region_top:region_bot, :]
    is_black = region == 0

    symbol_pixels = is_black & ~line_mask[:, np.newaxis]
    symbol_count = np.count_nonzero(symbol_pixels, axis=0)

    has_symbol = symbol_count > 0  # shape (w,)

    # Compute staff X-bounds from symbol positions
    symbol_indices = np.where(has_symbol)[0]
    if len(symbol_indices) > 0:
        x_start = int(symbol_indices[0])
        x_end = int(symbol_indices[-1])
    else:
        x_start = None
        x_end = None

    # Expand symbol columns by *symbol_padding* pixels in each direction
    if symbol_padding > 0:
        protected = has_symbol.copy()
        for shift in range(1, symbol_padding + 1):
            if shift < w:
                protected[shift:] |= has_symbol[:-shift]  # pad right
                protected[:-shift] |= has_symbol[shift:]  # pad left
        is_empty = ~protected
    else:
        is_empty = ~has_symbol

    # Erase contiguous empty runs
    run_start: int | None = None
    for x in range(w):
        if not is_empty[x]:
            if run_start is not None:
                img[region_top:region_bot, run_start:x] = 255
            run_start = None
        else:
            if run_start is None:
                run_start = x

    if run_start is not None:
        img[region_top:region_bot, run_start:w] = 255

    return x_start, x_end
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/backend/test_template_matching_features.py::test_staff_removal_sets_x_bounds tests/backend/test_template_matching_features.py::test_staff_removal_before_matching_config -v`
Expected: Both PASS

- [ ] **Step 5: Commit**

```bash
git add src/backend/mv_hofki/services/scanner/stages/staff_removal.py tests/backend/test_template_matching_features.py
git commit -m "feat: compute staff x_start/x_end in StaffRemovalStage"
```

---

### Task 3: Extract post_matching to a package

**Files:**
- Delete: `src/backend/mv_hofki/services/scanner/stages/post_matching.py`
- Create: `src/backend/mv_hofki/services/scanner/stages/post_matching/__init__.py`
- Create: `src/backend/mv_hofki/services/scanner/stages/post_matching/barline_filter.py`
- Test: `tests/backend/test_post_matching.py` (existing — imports must still work)

- [ ] **Step 1: Create `barline_filter.py` with the BarlineFilter class**

Create `src/backend/mv_hofki/services/scanner/stages/post_matching/barline_filter.py`:

```python
"""Barline filter: removes false-positive single barline detections."""

from __future__ import annotations

from mv_hofki.services.scanner.stages.base import PipelineContext, SymbolData

# Display-name substrings that take priority over single barlines.
_BARLINE_PRIORITY_NAMES = [
    "Wiederholung",
    "Schlusstaktstrich",
    "Achtel",
    "Viertel",
    "Sechzehntel",
    "Halbe",
    "Doppelter Taktstrich",
]

_SINGLE_BARLINE_DISPLAY_NAME = "Einfacher Taktstrich"


class BarlineFilter:
    """Filter false-positive single barline detections."""

    name = "barline_filter"

    def apply(self, ctx: PipelineContext) -> None:
        display_names: dict[int, str] = ctx.metadata.get("template_display_names", {})
        staff_map = {s.staff_index: s for s in ctx.staves}

        # Step 1: Position filter
        for sym in ctx.symbols:
            if sym.filtered:
                continue
            dn = display_names.get(
                sym.matched_template_id if sym.matched_template_id is not None else -1,
                "",
            )
            if dn != _SINGLE_BARLINE_DISPLAY_NAME:
                continue
            staff = staff_map.get(sym.staff_index)
            if staff is None:
                continue
            center_y = sym.y + sym.height / 2
            allowed_top = staff.y_top - staff.line_spacing
            allowed_bottom = staff.y_bottom + staff.line_spacing
            if center_y < allowed_top or center_y > allowed_bottom:
                sym.filtered = True
                sym.filter_reason = "barline_position_outside_staff"

        # Step 2: Overlap filter
        self._apply_overlap_filter(ctx.symbols, display_names)

    def _apply_overlap_filter(
        self,
        symbols: list[SymbolData],
        display_names: dict[int, str],
    ) -> None:
        for i, sym_a in enumerate(symbols):
            if sym_a.filtered:
                continue
            for j, sym_b in enumerate(symbols):
                if i == j or sym_b.filtered:
                    continue
                if not self._boxes_overlap(sym_a, sym_b):
                    continue

                dn_a = display_names.get(
                    sym_a.matched_template_id
                    if sym_a.matched_template_id is not None
                    else -1,
                    "",
                )
                dn_b = display_names.get(
                    sym_b.matched_template_id
                    if sym_b.matched_template_id is not None
                    else -1,
                    "",
                )

                a_is_single = dn_a == _SINGLE_BARLINE_DISPLAY_NAME
                b_is_single = dn_b == _SINGLE_BARLINE_DISPLAY_NAME

                # Case: single barline overlaps with a priority symbol
                if a_is_single and self._is_priority(dn_b):
                    sym_a.filtered = True
                    sym_a.filter_reason = f"barline_overlap_with_{dn_b}"
                    break
                if b_is_single and self._is_priority(dn_a):
                    sym_b.filtered = True
                    sym_b.filter_reason = f"barline_overlap_with_{dn_a}"
                    continue

                # Case: single barline overlaps with non-priority symbol
                if a_is_single or b_is_single:
                    if (sym_a.confidence or 0) <= (sym_b.confidence or 0):
                        sym_a.filtered = True
                        sym_a.filter_reason = "overlap_lower_confidence"
                        break
                    else:
                        sym_b.filtered = True
                        sym_b.filter_reason = "overlap_lower_confidence"

    @staticmethod
    def _is_priority(display_name: str) -> bool:
        return any(p in display_name for p in _BARLINE_PRIORITY_NAMES)

    @staticmethod
    def _boxes_overlap(a: SymbolData, b: SymbolData) -> bool:
        return (
            a.x < b.x + b.width
            and a.x + a.width > b.x
            and a.y < b.y + b.height
            and a.y + a.height > b.y
        )
```

- [ ] **Step 2: Create `__init__.py` as the orchestrator**

Create `src/backend/mv_hofki/services/scanner/stages/post_matching/__init__.py`:

```python
"""Post-matching stage: filters and cleans up template matching results."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from mv_hofki.services.scanner.stages.base import PipelineContext, ProcessingStage
from mv_hofki.services.scanner.stages.post_matching.barline_filter import BarlineFilter

logger = logging.getLogger(__name__)


class PostMatchingOperation(ABC):
    """Base class for post-matching sub-operations."""

    name: str

    @abstractmethod
    def apply(self, ctx: PipelineContext) -> None:
        """Modify ctx.symbols in-place (set filtered/filter_reason)."""


class PostMatchingStage(ProcessingStage):
    """Runs post-matching sub-operations on detected symbols."""

    name = "post_matching"

    def __init__(self) -> None:
        self._operations = [
            BarlineFilter(),
        ]

    def process(self, ctx: PipelineContext) -> PipelineContext:
        for op in self._operations:
            ctx.log(f"  Post-Matching: {op.name}...")
            op.apply(ctx)
            filtered_count = sum(1 for s in ctx.symbols if s.filtered)
            ctx.log(
                f"  Post-Matching: {op.name} abgeschlossen ({filtered_count} gefiltert)"
            )
        return ctx

    def validate(self, ctx: PipelineContext) -> bool:
        return len(ctx.symbols) > 0
```

- [ ] **Step 3: Delete the old single-file module**

```bash
rm src/backend/mv_hofki/services/scanner/stages/post_matching.py
```

- [ ] **Step 4: Run existing tests to verify imports still work**

Run: `python -m pytest tests/backend/test_post_matching.py -v`
Expected: All PASS (imports `from ...post_matching import PostMatchingStage` still resolve)

- [ ] **Step 5: Commit**

```bash
git add src/backend/mv_hofki/services/scanner/stages/post_matching/
git rm src/backend/mv_hofki/services/scanner/stages/post_matching.py
git commit -m "refactor: extract post_matching into package with barline_filter module"
```

Note: `git rm` on the old `.py` file may already be staged if git detected the delete. If `git rm` fails because the file is already gone, use `git add -A src/backend/mv_hofki/services/scanner/stages/post_matching*` instead.

---

### Task 4: Update MeasureDetectionStage to use barline start and staff X-bounds

**Files:**
- Modify: `src/backend/mv_hofki/services/scanner/stages/measure_detection.py`
- Test: `tests/backend/test_measure_detection.py`

- [ ] **Step 1: Write tests for new boundary logic**

Replace the entire contents of `tests/backend/test_measure_detection.py`:

```python
"""Tests for MeasureDetectionStage."""

import numpy as np

from mv_hofki.services.scanner.stages.base import (
    PipelineContext,
    StaffData,
    SymbolData,
)
from mv_hofki.services.scanner.stages.measure_detection import MeasureDetectionStage


def _make_staff(staff_index=0, x_start=0, x_end=800):
    return StaffData(
        staff_index=staff_index,
        y_top=50,
        y_bottom=100,
        line_positions=[50, 60, 70, 80, 90],
        line_spacing=10.0,
        x_start=x_start,
        x_end=x_end,
    )


def _ctx_with_symbols(staves, symbols, template_categories=None):
    ctx = PipelineContext(image=np.zeros((100, 800), dtype=np.uint8))
    ctx.staves = staves
    ctx.symbols = symbols
    ctx.metadata["template_categories"] = template_categories or {}
    return ctx


def test_barline_start_is_measure_boundary():
    """Measure boundary should be at barline start (x), not barline end (x+width)."""
    staff = _make_staff(x_start=0, x_end=700)
    symbols = [
        SymbolData(
            staff_index=0, x=100, y=50, width=10, height=50,
            staff_x_start=100, staff_x_end=110, matched_template_id=10,
        ),
    ]
    categories = {10: "barline"}
    ctx = _ctx_with_symbols([staff], symbols, categories)
    result = MeasureDetectionStage().process(ctx)

    assert len(result.measures) == 2
    # First measure: staff x_start to barline start
    assert result.measures[0].x_start == 0
    assert result.measures[0].x_end == 100
    # Second measure: barline start to staff x_end
    assert result.measures[1].x_start == 100
    assert result.measures[1].x_end == 700


def test_staff_x_bounds_used_instead_of_symbol_minmax():
    """Measures should use staff.x_start/x_end, not symbol min/max."""
    staff = _make_staff(x_start=5, x_end=795)
    symbols = [
        # Note at x=50 — should NOT define measure start
        SymbolData(
            staff_index=0, x=50, y=60, width=20, height=30,
            staff_x_start=50, staff_x_end=70, matched_template_id=1,
        ),
        # Note at x=600 — should NOT define measure end
        SymbolData(
            staff_index=0, x=600, y=60, width=20, height=30,
            staff_x_start=600, staff_x_end=620, matched_template_id=1,
        ),
    ]
    categories = {1: "note"}
    ctx = _ctx_with_symbols([staff], symbols, categories)
    result = MeasureDetectionStage().process(ctx)

    assert len(result.measures) == 1
    assert result.measures[0].x_start == 5
    assert result.measures[0].x_end == 795


def test_single_staff_three_barlines_four_measures():
    staff = _make_staff(x_start=10, x_end=620)
    symbols = [
        SymbolData(
            staff_index=0, x=10, y=60, width=20, height=30,
            staff_x_start=10, staff_x_end=30, matched_template_id=1,
        ),
        SymbolData(
            staff_index=0, x=100, y=50, width=5, height=50,
            staff_x_start=100, staff_x_end=105, matched_template_id=10,
        ),
        SymbolData(
            staff_index=0, x=300, y=50, width=5, height=50,
            staff_x_start=300, staff_x_end=305, matched_template_id=10,
        ),
        SymbolData(
            staff_index=0, x=500, y=50, width=5, height=50,
            staff_x_start=500, staff_x_end=505, matched_template_id=10,
        ),
        SymbolData(
            staff_index=0, x=600, y=60, width=20, height=30,
            staff_x_start=600, staff_x_end=620, matched_template_id=1,
        ),
    ]
    categories = {1: "note", 10: "barline"}
    ctx = _ctx_with_symbols([staff], symbols, categories)
    result = MeasureDetectionStage().process(ctx)

    assert len(result.measures) == 4
    assert result.measures[0].measure_number_in_staff == 1
    assert result.measures[0].x_start == 10
    assert result.measures[0].x_end == 100
    assert result.measures[1].measure_number_in_staff == 2
    assert result.measures[1].x_start == 100
    assert result.measures[1].x_end == 300
    assert result.measures[2].x_start == 300
    assert result.measures[2].x_end == 500
    assert result.measures[3].measure_number_in_staff == 4
    assert result.measures[3].x_start == 500
    assert result.measures[3].x_end == 620


def test_two_staffs_global_numbering():
    staff0 = _make_staff(staff_index=0, x_start=10, x_end=370)
    staff1 = StaffData(
        staff_index=1, y_top=150, y_bottom=200,
        line_positions=[150, 160, 170, 180, 190], line_spacing=10.0,
        x_start=10, x_end=370,
    )
    symbols = [
        SymbolData(
            staff_index=0, x=10, y=60, width=20, height=30,
            staff_x_start=10, staff_x_end=30, matched_template_id=1,
        ),
        SymbolData(
            staff_index=0, x=200, y=50, width=5, height=50,
            staff_x_start=200, staff_x_end=205, matched_template_id=10,
        ),
        SymbolData(
            staff_index=0, x=350, y=60, width=20, height=30,
            staff_x_start=350, staff_x_end=370, matched_template_id=1,
        ),
        SymbolData(
            staff_index=1, x=10, y=160, width=20, height=30,
            staff_x_start=10, staff_x_end=30, matched_template_id=1,
        ),
        SymbolData(
            staff_index=1, x=200, y=150, width=5, height=50,
            staff_x_start=200, staff_x_end=205, matched_template_id=10,
        ),
        SymbolData(
            staff_index=1, x=350, y=160, width=20, height=30,
            staff_x_start=350, staff_x_end=370, matched_template_id=1,
        ),
    ]
    categories = {1: "note", 10: "barline"}
    ctx = _ctx_with_symbols([staff0, staff1], symbols, categories)
    result = MeasureDetectionStage().process(ctx)

    assert len(result.measures) == 4
    assert result.measures[0].global_measure_number == 1
    assert result.measures[1].global_measure_number == 2
    assert result.measures[2].global_measure_number == 3
    assert result.measures[3].global_measure_number == 4


def test_no_barlines_single_measure():
    staff = _make_staff(x_start=10, x_end=220)
    symbols = [
        SymbolData(
            staff_index=0, x=10, y=60, width=20, height=30,
            staff_x_start=10, staff_x_end=30, matched_template_id=1,
        ),
        SymbolData(
            staff_index=0, x=200, y=60, width=20, height=30,
            staff_x_start=200, staff_x_end=220, matched_template_id=1,
        ),
    ]
    categories = {1: "note"}
    ctx = _ctx_with_symbols([staff], symbols, categories)
    result = MeasureDetectionStage().process(ctx)

    assert len(result.measures) == 1
    assert result.measures[0].x_start == 10
    assert result.measures[0].x_end == 220


def test_filtered_barlines_ignored():
    staff = _make_staff(x_start=10, x_end=420)
    symbols = [
        SymbolData(
            staff_index=0, x=10, y=60, width=20, height=30,
            staff_x_start=10, staff_x_end=30, matched_template_id=1,
        ),
        SymbolData(
            staff_index=0, x=200, y=50, width=5, height=50,
            staff_x_start=200, staff_x_end=205, matched_template_id=10,
            filtered=True, filter_reason="barline_position_outside_staff",
        ),
        SymbolData(
            staff_index=0, x=400, y=60, width=20, height=30,
            staff_x_start=400, staff_x_end=420, matched_template_id=1,
        ),
    ]
    categories = {1: "note", 10: "barline"}
    ctx = _ctx_with_symbols([staff], symbols, categories)
    result = MeasureDetectionStage().process(ctx)

    assert len(result.measures) == 1


def test_staff_without_x_bounds_skipped():
    """A staff without x_start/x_end should be skipped gracefully."""
    staff = StaffData(
        staff_index=0, y_top=50, y_bottom=100,
        line_positions=[50, 60, 70, 80, 90], line_spacing=10.0,
    )
    symbols = [
        SymbolData(
            staff_index=0, x=10, y=60, width=20, height=30,
            staff_x_start=10, staff_x_end=30, matched_template_id=1,
        ),
    ]
    categories = {1: "note"}
    ctx = _ctx_with_symbols([staff], symbols, categories)
    result = MeasureDetectionStage().process(ctx)

    assert len(result.measures) == 0
```

- [ ] **Step 2: Run new tests to verify they fail**

Run: `python -m pytest tests/backend/test_measure_detection.py -v`
Expected: Several FAIL — old implementation uses `bl_end` and symbol min/max

- [ ] **Step 3: Rewrite MeasureDetectionStage**

Replace the contents of `src/backend/mv_hofki/services/scanner/stages/measure_detection.py`:

```python
"""Measure detection stage: builds measure boundaries from barline positions."""

from __future__ import annotations

from mv_hofki.services.scanner.stages.base import (
    MeasureData,
    PipelineContext,
    ProcessingStage,
)


class MeasureDetectionStage(ProcessingStage):
    """Detect measures by splitting staves at barline symbol positions."""

    name = "measure_detection"

    def process(self, ctx: PipelineContext) -> PipelineContext:
        template_categories: dict[int, str] = ctx.metadata.get(
            "template_categories", {}
        )
        template_display_names: dict[int, str] = ctx.metadata.get(
            "template_display_names", {}
        )
        staff_map = {s.staff_index: s for s in ctx.staves}

        barlines_by_staff: dict[int, list] = {}

        for sym in ctx.symbols:
            if sym.filtered:
                continue
            tid = sym.matched_template_id if sym.matched_template_id is not None else -1
            cat = template_categories.get(tid, "")
            if cat == "barline":
                if sym.staff_index not in barlines_by_staff:
                    barlines_by_staff[sym.staff_index] = []
                barlines_by_staff[sym.staff_index].append(sym)

        measures: list[MeasureData] = []
        global_num = 1

        for staff_index in sorted(staff_map.keys()):
            staff = staff_map[staff_index]

            # Skip staves without X-bounds
            if staff.x_start is None or staff.x_end is None:
                continue

            min_x = staff.x_start
            max_x = staff.x_end

            barlines = barlines_by_staff.get(staff_index, [])
            barlines.sort(key=lambda s: s.staff_x_start or s.x)

            # Deduplicate overlapping barlines — keep the one with higher confidence
            deduped: list = []
            for bl in barlines:
                bl_start = bl.staff_x_start or bl.x
                if deduped:
                    prev = deduped[-1]
                    prev_end = prev.staff_x_end or (prev.x + prev.width)
                    if bl_start < prev_end:
                        if (bl.confidence or 0) > (prev.confidence or 0):
                            deduped[-1] = bl
                        continue
                deduped.append(bl)
            barlines = deduped

            # Build boundaries: barline START is the boundary point
            boundary_list: list[tuple[int, int, str | None]] = []
            prev_end = min_x

            for bl in barlines:
                bl_start = bl.staff_x_start or bl.x
                if bl_start > prev_end:
                    tid = bl.matched_template_id or -1
                    bl_name = template_display_names.get(tid)
                    boundary_list.append((prev_end, bl_start, bl_name))
                prev_end = bl_start

            if prev_end < max_x:
                boundary_list.append((prev_end, max_x, None))

            if not boundary_list:
                boundary_list = [(min_x, max_x, None)]

            local_num = 1
            for x_start, x_end, end_barline in boundary_list:
                measures.append(
                    MeasureData(
                        staff_index=staff_index,
                        measure_number_in_staff=local_num,
                        global_measure_number=global_num,
                        x_start=x_start,
                        x_end=x_end,
                        end_barline=end_barline,
                    )
                )
                local_num += 1
                global_num += 1

        ctx.measures = measures
        ctx.log(f"Taktstruktur erkannt: {len(measures)} Takte")
        return ctx

    def validate(self, ctx: PipelineContext) -> bool:
        return len(ctx.symbols) > 0
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/backend/test_measure_detection.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/backend/mv_hofki/services/scanner/stages/measure_detection.py tests/backend/test_measure_detection.py
git commit -m "feat: use barline start as measure boundary, use staff x_start/x_end"
```

---

### Task 5: Make StaffRemovalStage mandatory and clean up config

**Files:**
- Modify: `src/backend/mv_hofki/services/sheet_music_scan.py:238-239`
- Modify: `src/frontend/src/lib/scanner-config.js:93-99`
- Modify: `src/backend/mv_hofki/schemas/scanner_config.py:19,64`
- Modify: `src/backend/mv_hofki/models/scanner_config.py:41-43`

- [ ] **Step 1: Remove the config guard in sheet_music_scan.py**

In `src/backend/mv_hofki/services/sheet_music_scan.py`, replace lines 238-239:

```python
    if config.get("staff_removal_before_matching", False):
        stages.append(StaffRemovalStage())
```

with:

```python
    stages.append(StaffRemovalStage())
```

- [ ] **Step 2: Remove the toggle from the frontend config**

In `src/frontend/src/lib/scanner-config.js`, remove the toggle entry (lines 94-99):

```javascript
  {
    key: "staff_removal_before_matching",
    label: "Notenlinien vor Matching entfernen",
    group: "Notenlinien-Entfernung",
    type: "toggle",
  },
```

- [ ] **Step 3: Run all tests to verify nothing breaks**

Run: `python -m pytest tests/backend/ -v`
Expected: All PASS

- [ ] **Step 4: Run pre-commit**

Run: `pre-commit run --all-files`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add src/backend/mv_hofki/services/sheet_music_scan.py src/frontend/src/lib/scanner-config.js
git commit -m "feat: make StaffRemovalStage mandatory, remove toggle from config UI"
```

Note: The `staff_removal_before_matching` column in the DB model and schemas is left in place — removing it would require an Alembic migration which is out of scope. The column is simply ignored now.
