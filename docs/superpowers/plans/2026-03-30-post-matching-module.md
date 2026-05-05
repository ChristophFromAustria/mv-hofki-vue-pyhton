# Post-Matching Module Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a PostMatchingStage to the scanner pipeline that filters false-positive barline detections based on staff position and bounding-box overlap with priority symbols.

**Architecture:** A new `PostMatchingStage` (extending `ProcessingStage`) runs after `TemplateMatchingStage`. It orchestrates a list of `PostMatchingOperation` sub-operations. The first sub-operation is `BarlineFilter`, which marks false-positive single barlines via two rules: position validation and overlap priority. Filtered symbols stay in the results but are marked with `filtered=True` and a `filter_reason`.

**Tech Stack:** Python, SQLAlchemy, Alembic, OpenCV (existing), pytest

---

## File Structure

| File | Role |
|------|------|
| `src/backend/mv_hofki/services/scanner/stages/post_matching.py` | `PostMatchingOperation` ABC, `PostMatchingStage`, `BarlineFilter` |
| `src/backend/mv_hofki/services/scanner/stages/base.py` | Add `filtered` and `filter_reason` to `SymbolData` |
| `src/backend/mv_hofki/models/detected_symbol.py` | Add `filtered` and `filter_reason` DB columns |
| `src/backend/mv_hofki/services/sheet_music_scan.py` | Wire `PostMatchingStage` into pipeline, persist new fields |
| `src/backend/mv_hofki/services/scanner/stages/template_matching.py` | Expose template display-name mapping in `ctx.metadata` |
| `alembic/versions/*_add_filtered_fields_to_detected_symbols.py` | Migration |
| `tests/backend/test_post_matching.py` | All tests for the new module |

---

### Task 1: Extend SymbolData with filter fields

**Files:**
- Modify: `src/backend/mv_hofki/services/scanner/stages/base.py:29-42`

- [ ] **Step 1: Write the failing test**

Create `tests/backend/test_post_matching.py`:

```python
"""Tests for the post-matching stage."""

from mv_hofki.services.scanner.stages.base import SymbolData


def test_symbol_data_has_filter_fields():
    """SymbolData should have filtered and filter_reason fields."""
    sym = SymbolData(staff_index=0, x=10, y=20, width=5, height=40)
    assert sym.filtered is False
    assert sym.filter_reason is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /workspaces/mv_hofki && python -m pytest tests/backend/test_post_matching.py::test_symbol_data_has_filter_fields -v`
Expected: FAIL — `AttributeError: 'SymbolData' object has no attribute 'filtered'`

- [ ] **Step 3: Add fields to SymbolData**

In `src/backend/mv_hofki/services/scanner/stages/base.py`, add two fields to the `SymbolData` dataclass after line 42 (`alternatives`):

```python
    filtered: bool = False
    filter_reason: str | None = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /workspaces/mv_hofki && python -m pytest tests/backend/test_post_matching.py::test_symbol_data_has_filter_fields -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/backend/mv_hofki/services/scanner/stages/base.py tests/backend/test_post_matching.py
git commit -m "feat(scanner): add filtered/filter_reason fields to SymbolData"
```

---

### Task 2: Add DB columns and migration

**Files:**
- Modify: `src/backend/mv_hofki/models/detected_symbol.py`
- Create: `alembic/versions/*_add_filtered_fields_to_detected_symbols.py`

- [ ] **Step 1: Add columns to DetectedSymbol model**

In `src/backend/mv_hofki/models/detected_symbol.py`, add after line 39 (`alternatives_json`):

```python
    filtered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    filter_reason: Mapped[str | None] = mapped_column(String(200))
```

- [ ] **Step 2: Generate Alembic migration**

Run: `cd /workspaces/mv_hofki && PYTHONPATH=src/backend alembic revision --autogenerate -m "add filtered fields to detected symbols"`

Verify the generated migration adds two columns: `filtered` (Boolean, NOT NULL, default False) and `filter_reason` (String(200), nullable).

- [ ] **Step 3: Run migration**

Run: `cd /workspaces/mv_hofki && PYTHONPATH=src/backend alembic upgrade head`
Expected: Successfully applies migration.

- [ ] **Step 4: Commit**

```bash
git add src/backend/mv_hofki/models/detected_symbol.py alembic/versions/*_add_filtered_fields_to_detected_symbols.py
git commit -m "feat(scanner): add filtered/filter_reason columns to detected_symbols"
```

---

### Task 3: Expose template display-name mapping in TemplateMatchingStage

**Files:**
- Modify: `src/backend/mv_hofki/services/scanner/stages/template_matching.py`
- Modify: `src/backend/mv_hofki/services/sheet_music_scan.py`

The `BarlineFilter` needs to know each symbol's `display_name`. The `TemplateMatchingStage` only receives `variant_template_ids` (which are `SymbolTemplate.id` values). We add a `template_display_names` dict to the stage constructor and write it to `ctx.metadata`.

- [ ] **Step 1: Write the failing test**

Append to `tests/backend/test_post_matching.py`:

```python
import numpy as np

from mv_hofki.services.scanner.stages.base import PipelineContext, StaffData
from mv_hofki.services.scanner.stages.template_matching import TemplateMatchingStage


def test_template_matching_exposes_display_names():
    """TemplateMatchingStage should store display names in ctx.metadata."""
    staff = StaffData(
        staff_index=0, y_top=10, y_bottom=170,
        line_positions=[10, 30, 50, 70, 90], line_spacing=20.0,
    )
    img = np.full((200, 400), 255, dtype=np.uint8)
    display_names = {42: "Einfacher Taktstrich"}

    stage = TemplateMatchingStage(
        variant_images=[], variant_template_ids=[],
        variant_heights=[], variant_line_spacings=[],
        template_display_names=display_names,
    )

    ctx = PipelineContext(image=img, staves=[staff], config={})
    result = stage.process(ctx)
    assert result.metadata["template_display_names"] == {42: "Einfacher Taktstrich"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /workspaces/mv_hofki && python -m pytest tests/backend/test_post_matching.py::test_template_matching_exposes_display_names -v`
Expected: FAIL — `TypeError: TemplateMatchingStage.__init__() got an unexpected keyword argument 'template_display_names'`

- [ ] **Step 3: Add template_display_names parameter to TemplateMatchingStage**

In `src/backend/mv_hofki/services/scanner/stages/template_matching.py`, modify `__init__`:

```python
    def __init__(
        self,
        variant_images: list[np.ndarray],
        variant_template_ids: list[int],
        variant_heights: list[float],
        variant_line_spacings: list[float] | None = None,
        template_display_names: dict[int, str] | None = None,
    ) -> None:
        self._variant_images = variant_images
        self._variant_template_ids = variant_template_ids
        self._variant_heights = variant_heights
        self._variant_line_spacings = variant_line_spacings or [0.0] * len(
            variant_images
        )
        self._template_display_names = template_display_names or {}
```

At the **start** of the `process` method (after `assert ctx.image is not None`), add:

```python
        ctx.metadata["template_display_names"] = self._template_display_names
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /workspaces/mv_hofki && python -m pytest tests/backend/test_post_matching.py::test_template_matching_exposes_display_names -v`
Expected: PASS

- [ ] **Step 5: Run existing template matching tests to verify no regression**

Run: `cd /workspaces/mv_hofki && python -m pytest tests/backend/test_template_matching.py -v`
Expected: All PASS (existing tests don't pass `template_display_names`, the default `{}` keeps them working)

- [ ] **Step 6: Wire display names in run_pipeline**

In `src/backend/mv_hofki/services/sheet_music_scan.py`, after loading variants (after line 183), add a query to build the display-name mapping:

```python
    from mv_hofki.models.symbol_template import SymbolTemplate

    # Build template_id → display_name mapping for post-matching filters
    tmpl_result = await session.execute(sa_select(SymbolTemplate))
    all_templates = list(tmpl_result.scalars().all())
    template_display_names = {t.id: t.display_name for t in all_templates}
```

Then update the `TemplateMatchingStage` instantiation (around line 207) to pass the mapping:

```python
    stages.append(
        TemplateMatchingStage(
            variant_images=variant_images,
            variant_template_ids=variant_template_ids,
            variant_heights=variant_heights,
            variant_line_spacings=variant_line_spacings,
            template_display_names=template_display_names,
        ),
    )
```

- [ ] **Step 7: Commit**

```bash
git add src/backend/mv_hofki/services/scanner/stages/template_matching.py src/backend/mv_hofki/services/sheet_music_scan.py tests/backend/test_post_matching.py
git commit -m "feat(scanner): expose template display names via pipeline metadata"
```

---

### Task 4: Implement PostMatchingStage and BarlineFilter

**Files:**
- Create: `src/backend/mv_hofki/services/scanner/stages/post_matching.py`
- Test: `tests/backend/test_post_matching.py`

- [ ] **Step 1: Write failing tests for the position filter**

Append to `tests/backend/test_post_matching.py`:

```python
from mv_hofki.services.scanner.stages.post_matching import (
    BarlineFilter,
    PostMatchingStage,
)


def _make_ctx(symbols, staves=None, display_names=None):
    """Helper to create a PipelineContext for post-matching tests."""
    if staves is None:
        staves = [
            StaffData(
                staff_index=0, y_top=100, y_bottom=200,
                line_positions=[100, 125, 150, 175, 200], line_spacing=25.0,
            )
        ]
    ctx = PipelineContext(
        image=np.full((400, 600), 255, dtype=np.uint8),
        staves=staves,
        symbols=symbols,
        metadata={"template_display_names": display_names or {}},
        config={},
    )
    return ctx


def test_barline_position_filter_marks_outside_staff():
    """A barline far outside the staff region should be filtered."""
    sym = SymbolData(
        staff_index=0, x=50, y=10, width=5, height=40,
        matched_template_id=1, confidence=0.8,
    )
    ctx = _make_ctx(
        symbols=[sym],
        display_names={1: "Einfacher Taktstrich"},
    )
    stage = PostMatchingStage()
    result = stage.process(ctx)
    assert result.symbols[0].filtered is True
    assert result.symbols[0].filter_reason == "barline_position_outside_staff"


def test_barline_position_filter_keeps_inside_staff():
    """A barline within the staff region should not be filtered."""
    sym = SymbolData(
        staff_index=0, x=50, y=120, width=5, height=60,
        matched_template_id=1, confidence=0.8,
    )
    ctx = _make_ctx(
        symbols=[sym],
        display_names={1: "Einfacher Taktstrich"},
    )
    stage = PostMatchingStage()
    result = stage.process(ctx)
    assert result.symbols[0].filtered is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /workspaces/mv_hofki && python -m pytest tests/backend/test_post_matching.py::test_barline_position_filter_marks_outside_staff tests/backend/test_post_matching.py::test_barline_position_filter_keeps_inside_staff -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'mv_hofki.services.scanner.stages.post_matching'`

- [ ] **Step 3: Implement PostMatchingStage and BarlineFilter position logic**

Create `src/backend/mv_hofki/services/scanner/stages/post_matching.py`:

```python
"""Post-matching stage: filters and cleans up template matching results."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from mv_hofki.services.scanner.stages.base import PipelineContext, ProcessingStage

logger = logging.getLogger(__name__)

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


class PostMatchingOperation(ABC):
    """Base class for post-matching sub-operations."""

    name: str

    @abstractmethod
    def apply(self, ctx: PipelineContext) -> None:
        """Modify ctx.symbols in-place (set filtered/filter_reason)."""


class BarlineFilter(PostMatchingOperation):
    """Filter false-positive single barline detections."""

    name = "barline_filter"

    def apply(self, ctx: PipelineContext) -> None:
        display_names: dict[int, str] = ctx.metadata.get(
            "template_display_names", {}
        )
        staff_map = {s.staff_index: s for s in ctx.staves}

        # Step 1: Position filter
        for sym in ctx.symbols:
            if sym.filtered:
                continue
            dn = display_names.get(sym.matched_template_id or -1, "")
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
        symbols: list,
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

                dn_a = display_names.get(sym_a.matched_template_id or -1, "")
                dn_b = display_names.get(sym_b.matched_template_id or -1, "")

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
    def _boxes_overlap(a, b) -> bool:
        return (
            a.x < b.x + b.width
            and a.x + a.width > b.x
            and a.y < b.y + b.height
            and a.y + a.height > b.y
        )


class PostMatchingStage(ProcessingStage):
    """Runs post-matching sub-operations on detected symbols."""

    name = "post_matching"

    def __init__(self) -> None:
        self._operations: list[PostMatchingOperation] = [
            BarlineFilter(),
        ]

    def process(self, ctx: PipelineContext) -> PipelineContext:
        for op in self._operations:
            ctx.log(f"  Post-Matching: {op.name}...")
            op.apply(ctx)
            filtered_count = sum(1 for s in ctx.symbols if s.filtered)
            ctx.log(f"  Post-Matching: {op.name} abgeschlossen ({filtered_count} gefiltert)")
        return ctx

    def validate(self, ctx: PipelineContext) -> bool:
        return len(ctx.symbols) > 0
```

- [ ] **Step 4: Run position filter tests**

Run: `cd /workspaces/mv_hofki && python -m pytest tests/backend/test_post_matching.py::test_barline_position_filter_marks_outside_staff tests/backend/test_post_matching.py::test_barline_position_filter_keeps_inside_staff -v`
Expected: PASS

- [ ] **Step 5: Write failing tests for the overlap filter**

Append to `tests/backend/test_post_matching.py`:

```python
def test_barline_overlap_with_priority_symbol():
    """A barline overlapping a priority symbol should be filtered."""
    barline = SymbolData(
        staff_index=0, x=100, y=100, width=5, height=100,
        matched_template_id=1, confidence=0.9,
    )
    note = SymbolData(
        staff_index=0, x=98, y=110, width=20, height=50,
        matched_template_id=2, confidence=0.7,
    )
    ctx = _make_ctx(
        symbols=[barline, note],
        display_names={1: "Einfacher Taktstrich", 2: "Viertelnote"},
    )
    stage = PostMatchingStage()
    result = stage.process(ctx)
    assert result.symbols[0].filtered is True  # barline filtered
    assert "Viertelnote" in result.symbols[0].filter_reason
    assert result.symbols[1].filtered is False  # note kept


def test_barline_overlap_with_repeat_symbol():
    """A barline overlapping a repeat sign should be filtered."""
    barline = SymbolData(
        staff_index=0, x=100, y=100, width=5, height=100,
        matched_template_id=1, confidence=0.95,
    )
    repeat = SymbolData(
        staff_index=0, x=98, y=100, width=15, height=100,
        matched_template_id=3, confidence=0.6,
    )
    ctx = _make_ctx(
        symbols=[barline, repeat],
        display_names={1: "Einfacher Taktstrich", 3: "Wiederholung Ende"},
    )
    stage = PostMatchingStage()
    result = stage.process(ctx)
    assert result.symbols[0].filtered is True  # barline filtered even with higher confidence
    assert result.symbols[1].filtered is False


def test_barline_overlap_non_priority_lower_confidence_filtered():
    """When overlapping a non-priority symbol, the lower confidence is filtered."""
    barline = SymbolData(
        staff_index=0, x=100, y=100, width=5, height=100,
        matched_template_id=1, confidence=0.6,
    )
    other = SymbolData(
        staff_index=0, x=102, y=110, width=10, height=30,
        matched_template_id=4, confidence=0.8,
    )
    ctx = _make_ctx(
        symbols=[barline, other],
        display_names={1: "Einfacher Taktstrich", 4: "Staccato"},
    )
    stage = PostMatchingStage()
    result = stage.process(ctx)
    assert result.symbols[0].filtered is True  # barline has lower confidence
    assert result.symbols[0].filter_reason == "overlap_lower_confidence"
    assert result.symbols[1].filtered is False


def test_no_overlap_no_filter():
    """Non-overlapping symbols should not be filtered."""
    barline = SymbolData(
        staff_index=0, x=100, y=100, width=5, height=100,
        matched_template_id=1, confidence=0.8,
    )
    note = SymbolData(
        staff_index=0, x=200, y=110, width=20, height=50,
        matched_template_id=2, confidence=0.7,
    )
    ctx = _make_ctx(
        symbols=[barline, note],
        display_names={1: "Einfacher Taktstrich", 2: "Viertelnote"},
    )
    stage = PostMatchingStage()
    result = stage.process(ctx)
    assert result.symbols[0].filtered is False
    assert result.symbols[1].filtered is False
```

- [ ] **Step 6: Run overlap tests**

Run: `cd /workspaces/mv_hofki && python -m pytest tests/backend/test_post_matching.py -v`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add src/backend/mv_hofki/services/scanner/stages/post_matching.py tests/backend/test_post_matching.py
git commit -m "feat(scanner): add PostMatchingStage with BarlineFilter"
```

---

### Task 5: Wire PostMatchingStage into the pipeline and persist filter fields

**Files:**
- Modify: `src/backend/mv_hofki/services/sheet_music_scan.py`

- [ ] **Step 1: Add PostMatchingStage import and stage insertion**

In `src/backend/mv_hofki/services/sheet_music_scan.py`, add the import alongside the other stage imports (inside `run_pipeline`, around line 154):

```python
    from mv_hofki.services.scanner.stages.post_matching import PostMatchingStage
```

After the `stages.append(TemplateMatchingStage(...))` block (after line 213), add:

```python
    stages.append(PostMatchingStage())
```

- [ ] **Step 2: Persist filtered/filter_reason when saving symbols**

In the symbol persistence loop (around line 278), add the two new fields to the `DetectedSymbol` constructor. After `alternatives_json=alternatives_json,` add:

```python
                filtered=sym_data.filtered,
                filter_reason=sym_data.filter_reason,
```

- [ ] **Step 3: Verify the full pipeline still works**

Run: `cd /workspaces/mv_hofki && python -m pytest tests/backend/ -v`
Expected: All tests PASS

- [ ] **Step 4: Run pre-commit checks**

Run: `cd /workspaces/mv_hofki && pre-commit run --all-files`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/backend/mv_hofki/services/sheet_music_scan.py
git commit -m "feat(scanner): wire PostMatchingStage into pipeline and persist filter fields"
```

---

### Task 6: Edge case tests and validate method

**Files:**
- Modify: `tests/backend/test_post_matching.py`

- [ ] **Step 1: Write edge case tests**

Append to `tests/backend/test_post_matching.py`:

```python
def test_post_matching_validate_with_no_symbols():
    """PostMatchingStage.validate should return False with no symbols."""
    ctx = PipelineContext(
        image=np.full((200, 400), 255, dtype=np.uint8),
        staves=[], symbols=[], metadata={}, config={},
    )
    stage = PostMatchingStage()
    assert stage.validate(ctx) is False


def test_post_matching_validate_with_symbols():
    """PostMatchingStage.validate should return True with symbols."""
    ctx = _make_ctx(
        symbols=[SymbolData(staff_index=0, x=10, y=100, width=5, height=40)],
        display_names={},
    )
    stage = PostMatchingStage()
    assert stage.validate(ctx) is True


def test_barline_filter_ignores_non_barline_symbols():
    """Non-barline symbols should not be affected by the barline filter."""
    note = SymbolData(
        staff_index=0, x=50, y=10, width=20, height=40,
        matched_template_id=2, confidence=0.8,
    )
    ctx = _make_ctx(
        symbols=[note],
        display_names={2: "Viertelnote"},
    )
    stage = PostMatchingStage()
    result = stage.process(ctx)
    assert result.symbols[0].filtered is False


def test_barline_position_at_boundary():
    """A barline right at the line_spacing boundary should NOT be filtered."""
    # Staff y_top=100, y_bottom=200, line_spacing=25
    # Allowed range: 75 to 225
    # Symbol center at y=75 (exactly at boundary)
    sym = SymbolData(
        staff_index=0, x=50, y=55, width=5, height=40,
        matched_template_id=1, confidence=0.8,
    )
    ctx = _make_ctx(
        symbols=[sym],
        display_names={1: "Einfacher Taktstrich"},
    )
    stage = PostMatchingStage()
    result = stage.process(ctx)
    # center_y = 55 + 20 = 75 which equals allowed_top → NOT filtered
    assert result.symbols[0].filtered is False


def test_multiple_staves():
    """Filter should work correctly across multiple staves."""
    staves = [
        StaffData(
            staff_index=0, y_top=50, y_bottom=150,
            line_positions=[50, 75, 100, 125, 150], line_spacing=25.0,
        ),
        StaffData(
            staff_index=1, y_top=250, y_bottom=350,
            line_positions=[250, 275, 300, 325, 350], line_spacing=25.0,
        ),
    ]
    # Barline on staff 0 — valid position
    b0 = SymbolData(
        staff_index=0, x=100, y=70, width=5, height=60,
        matched_template_id=1, confidence=0.8,
    )
    # Barline on staff 1 — way outside
    b1 = SymbolData(
        staff_index=1, x=100, y=10, width=5, height=40,
        matched_template_id=1, confidence=0.8,
    )
    ctx = _make_ctx(
        symbols=[b0, b1],
        staves=staves,
        display_names={1: "Einfacher Taktstrich"},
    )
    stage = PostMatchingStage()
    result = stage.process(ctx)
    assert result.symbols[0].filtered is False  # valid on staff 0
    assert result.symbols[1].filtered is True   # outside staff 1
```

- [ ] **Step 2: Run all tests**

Run: `cd /workspaces/mv_hofki && python -m pytest tests/backend/test_post_matching.py -v`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add tests/backend/test_post_matching.py
git commit -m "test(scanner): add edge case tests for PostMatchingStage"
```
