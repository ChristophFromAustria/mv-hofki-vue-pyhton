# Staff-Bounds-Scan und Mindestbreite-Filter — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the `has_symbol`-based staff x_start/x_end detection with a 5-line scan that finds where all staff lines begin/end, and add a minimum-width filter to MeasureDetectionStage so narrow segments (closing barline area) don't get measure numbers.

**Architecture:** StaffRemovalStage gets a new `_find_staff_x_bounds` method that scans inward from both edges checking if all 5 staff lines have black pixels at each column. This replaces the `has_symbol`-based bounds. MeasureDetectionStage filters out segments narrower than `line_spacing` before assigning measure numbers.

**Tech Stack:** Python, numpy, pytest

---

### Task 1: Replace x_start/x_end with 5-line scan in StaffRemovalStage

**Files:**
- Modify: `src/backend/mv_hofki/services/scanner/stages/staff_removal.py`
- Test: `tests/backend/test_template_matching_features.py`

- [ ] **Step 1: Write test for the 5-line scan**

Replace the existing `test_staff_removal_sets_x_bounds` test in `tests/backend/test_template_matching_features.py` (lines 236-266) with a new test that specifically validates the 5-line scan behavior — staff lines that don't span the full width should define tighter bounds, and text/symbols outside the staff lines should be ignored:

```python
def test_staff_removal_sets_x_bounds_from_line_scan():
    """x_start/x_end should be where all 5 staff lines begin/end, not where symbols are."""
    from mv_hofki.services.scanner.stages.staff_removal import StaffRemovalStage

    img = np.full((200, 400), 255, dtype=np.uint8)
    # Draw staff lines from x=50 to x=350 (all 5 lines)
    for i in range(5):
        y = 30 + i * 20
        img[y : y + 2, 50:350] = 0
    # Draw "text" before staff lines (only near top line, not all 5)
    # This simulates an instrument name that should NOT push x_start left
    img[28:32, 10:45] = 0  # black pixels near line 1 only

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
    # x_start should be 50 (where all 5 lines begin), not 10 (where text is)
    assert result.staves[0].x_start == 50
    # x_end should be 349 (last column where all 5 lines have pixels)
    assert result.staves[0].x_end == 349
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/backend/test_template_matching_features.py::test_staff_removal_sets_x_bounds_from_line_scan -v`
Expected: FAIL — current implementation uses `has_symbol` which would include the text area

- [ ] **Step 3: Add `_find_staff_x_bounds` method and update `process`**

In `src/backend/mv_hofki/services/scanner/stages/staff_removal.py`, add a new static method before `_remove_empty_staff_segments`:

```python
    @staticmethod
    def _find_staff_x_bounds(
        img: np.ndarray,
        line_positions: list[int],
        line_thickness: int,
    ) -> tuple[int | None, int | None]:
        """Find where all 5 staff lines begin and end by scanning inward.

        Scans from the left edge rightward until a column is found where
        all 5 lines have at least one black pixel within their thickness
        range.  Then scans from the right edge leftward for the end.

        Returns ``(x_start, x_end)`` (inclusive), or ``(None, None)``
        if no column has all 5 lines present.
        """
        h, w = img.shape[:2]
        half_t = line_thickness // 2 + 1

        def _all_lines_present(x: int) -> bool:
            for ly in line_positions:
                y_lo = max(0, ly - half_t)
                y_hi = min(h, ly + half_t + 1)
                if not np.any(img[y_lo:y_hi, x] == 0):
                    return False
            return True

        # Scan from left
        x_start = None
        for x in range(w):
            if _all_lines_present(x):
                x_start = x
                break

        if x_start is None:
            return None, None

        # Scan from right
        x_end = None
        for x in range(w - 1, x_start - 1, -1):
            if _all_lines_present(x):
                x_end = x
                break

        return x_start, x_end
```

Then update the `process` method. Change lines 38-46 from:

```python
            x_start, x_end = self._remove_empty_staff_segments(
                img,
                staff.line_positions,
                line_spacing=staff.line_spacing,
                line_thickness=effective,
                symbol_padding=symbol_padding,
            )
            staff.x_start = x_start
            staff.x_end = x_end
```

to:

```python
            x_start, x_end = self._find_staff_x_bounds(
                img, staff.line_positions, effective
            )
            staff.x_start = x_start
            staff.x_end = x_end
            self._remove_empty_staff_segments(
                img,
                staff.line_positions,
                line_spacing=staff.line_spacing,
                line_thickness=effective,
                symbol_padding=symbol_padding,
            )
```

And revert `_remove_empty_staff_segments` to return `None` instead of the tuple. Change its signature back:

```python
    @staticmethod
    def _remove_empty_staff_segments(
        img: np.ndarray,
        line_positions: list[int],
        line_spacing: float,
        line_thickness: int,
        symbol_padding: int = 0,
    ) -> None:
```

Remove the x_start/x_end computation block (lines 157-164) and the `return x_start, x_end` at the end (line 191). The method should end with the empty-run erasure loop and have no return statement.

- [ ] **Step 4: Delete the old test**

Remove the `test_staff_removal_sets_x_bounds` function from `tests/backend/test_template_matching_features.py` (the one that used `has_symbol`-based assertions with `<= 50` and `>= 319`).

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/backend/test_template_matching_features.py -v`
Expected: All PASS (including the new line-scan test)

- [ ] **Step 6: Commit**

```bash
git add src/backend/mv_hofki/services/scanner/stages/staff_removal.py tests/backend/test_template_matching_features.py
git commit -m "feat: replace has_symbol x-bounds with 5-line scan in StaffRemovalStage"
```

---

### Task 2: Add minimum-width filter to MeasureDetectionStage

**Files:**
- Modify: `src/backend/mv_hofki/services/scanner/stages/measure_detection.py`
- Modify: `tests/backend/test_measure_detection.py`

- [ ] **Step 1: Write test for narrow segment filtering**

Add the following tests to `tests/backend/test_measure_detection.py` after the existing tests:

```python
def test_narrow_trailing_segment_not_counted():
    """A narrow segment after the last barline (< line_spacing) should not become a measure."""
    staff = _make_staff(x_start=10, x_end=508)  # 8px after last barline, line_spacing=10
    symbols = [
        SymbolData(
            staff_index=0,
            x=100,
            y=50,
            width=5,
            height=50,
            staff_x_start=100,
            staff_x_end=105,
            matched_template_id=10,
        ),
        SymbolData(
            staff_index=0,
            x=500,
            y=50,
            width=5,
            height=50,
            staff_x_start=500,
            staff_x_end=505,
            matched_template_id=10,
        ),
    ]
    categories = {10: "barline"}
    ctx = _ctx_with_symbols([staff], symbols, categories)
    result = MeasureDetectionStage().process(ctx)

    # Segment from 10-100 (90px, ok), 100-500 (400px, ok), 500-508 (8px < 10 line_spacing → filtered)
    assert len(result.measures) == 2
    assert result.measures[0].x_start == 10
    assert result.measures[0].x_end == 100
    assert result.measures[1].x_start == 100
    assert result.measures[1].x_end == 500


def test_narrow_leading_segment_not_counted():
    """A narrow segment before the first barline (< line_spacing) should not become a measure."""
    staff = _make_staff(x_start=95, x_end=600)  # 5px before first barline, line_spacing=10
    symbols = [
        SymbolData(
            staff_index=0,
            x=100,
            y=50,
            width=5,
            height=50,
            staff_x_start=100,
            staff_x_end=105,
            matched_template_id=10,
        ),
    ]
    categories = {10: "barline"}
    ctx = _ctx_with_symbols([staff], symbols, categories)
    result = MeasureDetectionStage().process(ctx)

    # Segment from 95-100 (5px < 10 → filtered), 100-600 (500px, ok)
    assert len(result.measures) == 1
    assert result.measures[0].x_start == 100
    assert result.measures[0].x_end == 600


def test_wide_trailing_segment_is_counted():
    """A segment after the last barline wider than line_spacing SHOULD be a measure."""
    staff = _make_staff(x_start=10, x_end=520)  # 20px after last barline, line_spacing=10
    symbols = [
        SymbolData(
            staff_index=0,
            x=500,
            y=50,
            width=5,
            height=50,
            staff_x_start=500,
            staff_x_end=505,
            matched_template_id=10,
        ),
    ]
    categories = {10: "barline"}
    ctx = _ctx_with_symbols([staff], symbols, categories)
    result = MeasureDetectionStage().process(ctx)

    # Segment from 10-500 (490px, ok), 500-520 (20px >= 10 → counted)
    assert len(result.measures) == 2
```

- [ ] **Step 2: Run new tests to verify they fail**

Run: `python -m pytest tests/backend/test_measure_detection.py::test_narrow_trailing_segment_not_counted tests/backend/test_measure_detection.py::test_narrow_leading_segment_not_counted -v`
Expected: FAIL — current implementation does not filter narrow segments

- [ ] **Step 3: Add minimum-width filter to MeasureDetectionStage**

In `src/backend/mv_hofki/services/scanner/stages/measure_detection.py`, replace the measure-building loop (lines 86-99):

```python
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
```

with:

```python
            local_num = 1
            min_width = staff.line_spacing
            for x_start, x_end, end_barline in boundary_list:
                if (x_end - x_start) < min_width:
                    continue
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
```

- [ ] **Step 4: Update existing tests that are affected**

The existing `test_barline_start_is_measure_boundary` test creates a staff with `x_start=0, x_end=700` and a single barline at x=100. This produces segments `0-100` (100px) and `100-700` (600px) — both wider than `line_spacing=10`, so this test still passes unchanged.

The existing `test_single_staff_three_barlines_four_measures` test produces a last segment from `500-620` (120px) — still passes.

Run all measure detection tests to verify:

Run: `python -m pytest tests/backend/test_measure_detection.py -v`
Expected: All PASS (10 tests: 7 existing + 3 new)

- [ ] **Step 5: Commit**

```bash
git add src/backend/mv_hofki/services/scanner/stages/measure_detection.py tests/backend/test_measure_detection.py
git commit -m "feat: filter out narrow segments (< line_spacing) from measure detection"
```
