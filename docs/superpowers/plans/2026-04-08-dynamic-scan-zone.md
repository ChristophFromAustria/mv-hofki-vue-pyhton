# Dynamic Scan Zone Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dynamic templates (pp, ff, mf, etc.) scan the inter-staff region instead of the regular staff region, eliminating false positives from oversized staff margins.

**Architecture:** The `TemplateMatchingStage` gains a `template_categories` dict. Before matching, templates are split into "staff" vs "below_staff" groups by category. Per staff, two matching passes run on different image regions. A helper method is extracted to avoid duplicating the matching loop.

**Tech Stack:** Python, OpenCV, NumPy, pytest

**Spec:** `docs/superpowers/specs/2026-04-08-dynamic-scan-zone-design.md`

---

### Task 1: Extract matching loop into reusable method

The inner matching loop (lines 104-239 in `template_matching.py`) must become a callable method so both zones can use it without duplication. This is a pure refactor — no behavior change.

**Files:**
- Modify: `src/backend/mv_hofki/services/scanner/stages/template_matching.py:104-239`
- Test: `tests/backend/test_template_matching.py` (existing, must still pass)
- Test: `tests/backend/test_template_matching_features.py` (existing, must still pass)

- [ ] **Step 1: Write a regression test that captures current behavior**

Add to `tests/backend/test_template_matching.py`:

```python
def test_template_matching_returns_staff_positions():
    """Detections include correct staff_y_top and staff_y_bottom."""
    spacing = 20
    staff = _make_staff(spacing)

    img = np.full((200, 400), 255, dtype=np.uint8)
    symbol = np.full((40, 20), 255, dtype=np.uint8)
    cv2.circle(symbol, (10, 20), 8, 0, -1)
    img[30:70, 100:120] = symbol

    stage = TemplateMatchingStage(
        variant_images=[symbol.copy()],
        variant_template_ids=[42],
        variant_heights=[2.0],
    )
    ctx = PipelineContext(
        image=img, staves=[staff], config={"confidence_threshold": 0.5}
    )
    result = stage.process(ctx)

    assert len(result.symbols) > 0
    sym = result.symbols[0]
    assert sym.staff_y_top is not None
    assert sym.staff_y_bottom is not None
    # Bottom line is at y=90 (line_positions[4]=10+20*4=90)
    # Symbol y ≈ 30, so staff_y_top ≈ (90-30)/20 = 3.0
    assert 2.0 <= sym.staff_y_top <= 4.0
```

- [ ] **Step 2: Run all existing template matching tests**

Run: `python -m pytest tests/backend/test_template_matching.py tests/backend/test_template_matching_features.py -v`
Expected: All PASS (including the new test)

- [ ] **Step 3: Extract `_match_templates_in_region` method**

In `template_matching.py`, extract lines 104-239 into a new method. The `process` method calls it once per staff. The method signature:

```python
def _match_templates_in_region(
    self,
    *,
    region: np.ndarray,
    edge_region: np.ndarray | None,
    staff: StaffData,
    template_indices: list[int],
    region_y_offset: int,
    confidence_threshold: float,
    cv_method: int,
    is_sqdiff: bool,
    multi_scale_enabled: bool,
    multi_scale_range: float,
    multi_scale_steps: int,
    edge_matching_enabled: bool,
    canny_low: int,
    canny_high: int,
    masked_matching_enabled: bool,
    mask_threshold: int,
) -> list[SymbolData]:
```

Replace lines 96-239 in `process()` with:

```python
        raw_detections: list[SymbolData] = []

        for staff in ctx.staves:
            region = img[staff.y_top : staff.y_bottom, :]
            edge_region: np.ndarray | None = None
            if edge_img is not None:
                edge_region = edge_img[staff.y_top : staff.y_bottom, :]

            all_indices = list(range(len(self._variant_images)))
            raw_detections.extend(
                self._match_templates_in_region(
                    region=region,
                    edge_region=edge_region,
                    staff=staff,
                    template_indices=all_indices,
                    region_y_offset=staff.y_top,
                    confidence_threshold=confidence_threshold,
                    cv_method=cv_method,
                    is_sqdiff=is_sqdiff,
                    multi_scale_enabled=multi_scale_enabled,
                    multi_scale_range=multi_scale_range,
                    multi_scale_steps=multi_scale_steps,
                    edge_matching_enabled=edge_matching_enabled,
                    canny_low=canny_low,
                    canny_high=canny_high,
                    masked_matching_enabled=masked_matching_enabled,
                    mask_threshold=mask_threshold,
                )
            )
```

The body of `_match_templates_in_region` is the old lines 104-239 with these changes:
- Loop over `template_indices` instead of `enumerate(self._variant_images)` — use each index to look up `self._variant_images[i]`, `self._variant_template_ids[i]`, etc.
- Replace `staff.y_top + pt_y` with `region_y_offset + pt_y` for `abs_y` calculation (line 215)
- Return the list of `SymbolData` instead of appending to `raw_detections`

- [ ] **Step 4: Run all template matching tests**

Run: `python -m pytest tests/backend/test_template_matching.py tests/backend/test_template_matching_features.py -v`
Expected: All PASS — behavior unchanged

- [ ] **Step 5: Commit**

```bash
git add src/backend/mv_hofki/services/scanner/stages/template_matching.py tests/backend/test_template_matching.py
git commit -m "refactor: extract _match_templates_in_region method for zone support"
```

---

### Task 2: Add template_categories parameter and zone splitting

The stage learns about template categories and splits templates into staff vs below_staff groups.

**Files:**
- Modify: `src/backend/mv_hofki/services/scanner/stages/template_matching.py`
- Test: `tests/backend/test_template_matching.py`

- [ ] **Step 1: Write test for zone splitting**

Add to `tests/backend/test_template_matching.py`:

```python
def test_template_categories_splits_into_zones():
    """Templates are split by category: dynamics → below_staff, others → staff."""
    stage = TemplateMatchingStage(
        variant_images=[],
        variant_template_ids=[1, 2, 3],
        variant_heights=[],
        template_categories={1: "note", 2: "dynamic", 3: "barline"},
    )
    staff_indices, below_staff_indices = stage._split_by_zone()
    assert staff_indices == [0, 2]
    assert below_staff_indices == [1]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/backend/test_template_matching.py::test_template_categories_splits_into_zones -v`
Expected: FAIL — `template_categories` parameter not accepted yet

- [ ] **Step 3: Add `template_categories` parameter and `_split_by_zone` method**

In `template_matching.py`, update `__init__`:

```python
def __init__(
    self,
    variant_images: list[np.ndarray],
    variant_template_ids: list[int],
    variant_heights: list[float],
    variant_line_spacings: list[float] | None = None,
    template_display_names: dict[int, str] | None = None,
    template_categories: dict[int, str] | None = None,
) -> None:
    self._variant_images = variant_images
    self._variant_template_ids = variant_template_ids
    self._variant_heights = variant_heights
    self._variant_line_spacings = variant_line_spacings or [0.0] * len(
        variant_images
    )
    self._template_display_names = template_display_names or {}
    self._template_categories = template_categories or {}
```

Add the splitting method:

```python
_BELOW_STAFF_CATEGORY = "dynamic"

def _split_by_zone(self) -> tuple[list[int], list[int]]:
    """Split variant indices into staff and below_staff groups."""
    staff_indices: list[int] = []
    below_staff_indices: list[int] = []
    for i, tid in enumerate(self._variant_template_ids):
        cat = self._template_categories.get(tid, "")
        if cat == self._BELOW_STAFF_CATEGORY:
            below_staff_indices.append(i)
        else:
            staff_indices.append(i)
    return staff_indices, below_staff_indices
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/backend/test_template_matching.py::test_template_categories_splits_into_zones -v`
Expected: PASS

- [ ] **Step 5: Run all template matching tests to check nothing broke**

Run: `python -m pytest tests/backend/test_template_matching.py tests/backend/test_template_matching_features.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add src/backend/mv_hofki/services/scanner/stages/template_matching.py tests/backend/test_template_matching.py
git commit -m "feat: add template_categories param and zone splitting to TemplateMatchingStage"
```

---

### Task 3: Implement below_staff region calculation

Add the method that computes the below_staff scan region for a given staff.

**Files:**
- Modify: `src/backend/mv_hofki/services/scanner/stages/template_matching.py`
- Test: `tests/backend/test_template_matching.py`

- [ ] **Step 1: Write tests for below_staff region calculation**

Add to `tests/backend/test_template_matching.py`:

```python
def test_below_staff_region_with_next_staff():
    """below_staff region goes from bottom_line - 1*ls to next staff's top line."""
    staff = StaffData(
        staff_index=0,
        y_top=10,
        y_bottom=170,
        line_positions=[50, 70, 90, 110, 130],
        line_spacing=20.0,
    )
    next_staff = StaffData(
        staff_index=1,
        y_top=210,
        y_bottom=370,
        line_positions=[250, 270, 290, 310, 330],
        line_spacing=20.0,
    )
    y_start, y_end = TemplateMatchingStage._compute_below_staff_region(
        staff, next_staff, img_height=500
    )
    # y_start = max(line_positions) - 1 * line_spacing = 130 - 20 = 110
    assert y_start == 110
    # y_end = min(next_staff.line_positions) = 250
    assert y_end == 250


def test_below_staff_region_last_staff():
    """For the last staff, below_staff region extends to page bottom."""
    staff = StaffData(
        staff_index=0,
        y_top=10,
        y_bottom=170,
        line_positions=[50, 70, 90, 110, 130],
        line_spacing=20.0,
    )
    y_start, y_end = TemplateMatchingStage._compute_below_staff_region(
        staff, None, img_height=500
    )
    assert y_start == 110
    assert y_end == 500


def test_below_staff_region_clamps_to_zero():
    """y_start should not go below 0 for staves near the top."""
    staff = StaffData(
        staff_index=0,
        y_top=0,
        y_bottom=100,
        line_positions=[5, 15, 25, 35, 45],
        line_spacing=10.0,
    )
    y_start, y_end = TemplateMatchingStage._compute_below_staff_region(
        staff, None, img_height=200
    )
    # y_start = max(5,15,25,35,45) - 10 = 35, no clamping needed here
    assert y_start == 35
    assert y_end == 200
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/backend/test_template_matching.py::test_below_staff_region_with_next_staff tests/backend/test_template_matching.py::test_below_staff_region_last_staff tests/backend/test_template_matching.py::test_below_staff_region_clamps_to_zero -v`
Expected: FAIL — method not defined

- [ ] **Step 3: Implement `_compute_below_staff_region`**

Add to `TemplateMatchingStage`:

```python
@staticmethod
def _compute_below_staff_region(
    staff: StaffData,
    next_staff: StaffData | None,
    img_height: int,
) -> tuple[int, int]:
    """Compute the vertical region for below-staff matching (dynamics).

    Returns (y_start, y_end) where:
    - y_start = bottom staff line minus 1 × line_spacing
    - y_end = top line of next staff, or image height if last staff
    """
    bottom_line = max(staff.line_positions)
    y_start = max(0, int(bottom_line - staff.line_spacing))
    if next_staff is not None:
        y_end = min(next_staff.line_positions)
    else:
        y_end = img_height
    return y_start, y_end
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/backend/test_template_matching.py::test_below_staff_region_with_next_staff tests/backend/test_template_matching.py::test_below_staff_region_last_staff tests/backend/test_template_matching.py::test_below_staff_region_clamps_to_zero -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/backend/mv_hofki/services/scanner/stages/template_matching.py tests/backend/test_template_matching.py
git commit -m "feat: add _compute_below_staff_region for inter-staff dynamic scanning"
```

---

### Task 4: Wire zone-based matching into the process loop

Connect all pieces: `process()` splits templates by zone, runs staff-zone matching, then below_staff-zone matching per staff.

**Files:**
- Modify: `src/backend/mv_hofki/services/scanner/stages/template_matching.py`
- Test: `tests/backend/test_template_matching.py`

- [ ] **Step 1: Write integration test for zone-based matching**

Add to `tests/backend/test_template_matching.py`:

```python
def test_dynamic_template_scans_below_staff_region():
    """A dynamic symbol placed between two staves is found via below_staff zone."""
    spacing = 20
    # Two staves: staff 0 lines at y=50..130, staff 1 lines at y=250..330
    staff0 = StaffData(
        staff_index=0,
        y_top=10,
        y_bottom=170,
        line_positions=[50, 70, 90, 110, 130],
        line_spacing=float(spacing),
    )
    staff1 = StaffData(
        staff_index=1,
        y_top=210,
        y_bottom=370,
        line_positions=[250, 270, 290, 310, 330],
        line_spacing=float(spacing),
    )

    img = np.full((500, 400), 255, dtype=np.uint8)

    # Place a dynamic symbol at y=180 (below staff0, above staff1)
    # This is OUTSIDE staff0.y_bottom=170 so it would NOT be found
    # without the below_staff zone.
    symbol = np.full((30, 40), 255, dtype=np.uint8)
    cv2.rectangle(symbol, (5, 5), (35, 25), 0, -1)
    img[180:210, 100:140] = symbol

    stage = TemplateMatchingStage(
        variant_images=[symbol.copy()],
        variant_template_ids=[50],
        variant_heights=[1.5],
        template_categories={50: "dynamic"},
    )
    ctx = PipelineContext(
        image=img,
        staves=[staff0, staff1],
        config={"confidence_threshold": 0.5},
        metadata={"template_categories": {50: "dynamic"}},
    )
    result = stage.process(ctx)

    # Should find the dynamic between the staves
    assert len(result.symbols) > 0
    dynamic_hits = [s for s in result.symbols if s.matched_template_id == 50]
    assert len(dynamic_hits) > 0
    # Should be assigned to staff 0
    assert dynamic_hits[0].staff_index == 0
    # y should be near 180
    assert any(170 <= s.y <= 215 for s in dynamic_hits)


def test_non_dynamic_not_scanned_in_below_staff_region():
    """Non-dynamic templates only scan the staff region, not below_staff."""
    spacing = 20
    staff0 = StaffData(
        staff_index=0,
        y_top=10,
        y_bottom=170,
        line_positions=[50, 70, 90, 110, 130],
        line_spacing=float(spacing),
    )

    img = np.full((500, 400), 255, dtype=np.uint8)

    # Place a note-like symbol at y=180 — outside staff region
    symbol = np.full((30, 40), 255, dtype=np.uint8)
    cv2.rectangle(symbol, (5, 5), (35, 25), 0, -1)
    img[180:210, 100:140] = symbol

    stage = TemplateMatchingStage(
        variant_images=[symbol.copy()],
        variant_template_ids=[1],
        variant_heights=[1.5],
        template_categories={1: "note"},
    )
    ctx = PipelineContext(
        image=img,
        staves=[staff0],
        config={"confidence_threshold": 0.5},
        metadata={"template_categories": {1: "note"}},
    )
    result = stage.process(ctx)

    # Should NOT find anything — symbol is outside staff region
    note_hits = [s for s in result.symbols if 170 <= s.y <= 215]
    assert len(note_hits) == 0
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `python -m pytest tests/backend/test_template_matching.py::test_dynamic_template_scans_below_staff_region tests/backend/test_template_matching.py::test_non_dynamic_not_scanned_in_below_staff_region -v`
Expected: First test FAILS (dynamic not found outside staff region), second test may pass already

- [ ] **Step 3: Update `process()` to use zone-based matching**

Replace the staff loop in `process()` with:

```python
        raw_detections: list[SymbolData] = []
        staff_indices, below_staff_indices = self._split_by_zone()

        for si, staff in enumerate(ctx.staves):
            next_staff = ctx.staves[si + 1] if si + 1 < len(ctx.staves) else None

            # --- Zone 1: staff region (all non-dynamic templates) ---
            if staff_indices:
                region = img[staff.y_top : staff.y_bottom, :]
                edge_region: np.ndarray | None = None
                if edge_img is not None:
                    edge_region = edge_img[staff.y_top : staff.y_bottom, :]

                raw_detections.extend(
                    self._match_templates_in_region(
                        region=region,
                        edge_region=edge_region,
                        staff=staff,
                        template_indices=staff_indices,
                        region_y_offset=staff.y_top,
                        confidence_threshold=confidence_threshold,
                        cv_method=cv_method,
                        is_sqdiff=is_sqdiff,
                        multi_scale_enabled=multi_scale_enabled,
                        multi_scale_range=multi_scale_range,
                        multi_scale_steps=multi_scale_steps,
                        edge_matching_enabled=edge_matching_enabled,
                        canny_low=canny_low,
                        canny_high=canny_high,
                        masked_matching_enabled=masked_matching_enabled,
                        mask_threshold=mask_threshold,
                    )
                )

            # --- Zone 2: below_staff region (dynamic templates only) ---
            if below_staff_indices:
                bs_start, bs_end = self._compute_below_staff_region(
                    staff, next_staff, img.shape[0]
                )
                if bs_end > bs_start:
                    bs_region = img[bs_start:bs_end, :]
                    bs_edge_region: np.ndarray | None = None
                    if edge_img is not None:
                        bs_edge_region = edge_img[bs_start:bs_end, :]

                    raw_detections.extend(
                        self._match_templates_in_region(
                            region=bs_region,
                            edge_region=bs_edge_region,
                            staff=staff,
                            template_indices=below_staff_indices,
                            region_y_offset=bs_start,
                            confidence_threshold=confidence_threshold,
                            cv_method=cv_method,
                            is_sqdiff=is_sqdiff,
                            multi_scale_enabled=multi_scale_enabled,
                            multi_scale_range=multi_scale_range,
                            multi_scale_steps=multi_scale_steps,
                            edge_matching_enabled=edge_matching_enabled,
                            canny_low=canny_low,
                            canny_high=canny_high,
                            masked_matching_enabled=masked_matching_enabled,
                            mask_threshold=mask_threshold,
                        )
                    )
```

- [ ] **Step 4: Run all template matching tests**

Run: `python -m pytest tests/backend/test_template_matching.py tests/backend/test_template_matching_features.py -v`
Expected: All PASS

- [ ] **Step 5: Run the full backend test suite**

Run: `python -m pytest tests/backend/ -v`
Expected: All PASS (including dynamic filter tests — they still work because DynamicFilter is downstream)

- [ ] **Step 6: Commit**

```bash
git add src/backend/mv_hofki/services/scanner/stages/template_matching.py tests/backend/test_template_matching.py
git commit -m "feat: wire zone-based matching — dynamics scan below_staff region"
```

---

### Task 5: Pass template_categories from pipeline entry point

The `sheet_music_scan.py` already builds `template_categories` but doesn't pass it to `TemplateMatchingStage`. Wire it through.

**Files:**
- Modify: `src/backend/mv_hofki/services/sheet_music_scan.py:240-248`

- [ ] **Step 1: Update TemplateMatchingStage construction**

In `sheet_music_scan.py`, change the `TemplateMatchingStage(...)` call (around line 240) from:

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

to:

```python
    stages.append(
        TemplateMatchingStage(
            variant_images=variant_images,
            variant_template_ids=variant_template_ids,
            variant_heights=variant_heights,
            variant_line_spacings=variant_line_spacings,
            template_display_names=template_display_names,
            template_categories=template_categories,
        ),
    )
```

- [ ] **Step 2: Run backend tests**

Run: `python -m pytest tests/backend/ -v`
Expected: All PASS

- [ ] **Step 3: Run pre-commit checks**

Run: `pre-commit run --all-files`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add src/backend/mv_hofki/services/sheet_music_scan.py
git commit -m "feat: pass template_categories to TemplateMatchingStage for zone-based scanning"
```
