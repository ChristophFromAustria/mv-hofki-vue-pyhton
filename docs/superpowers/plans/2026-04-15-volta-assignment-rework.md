# Volta-Zuweisung Rework Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the naive "all overlapping measures get the same volta_number" logic with a walk-based algorithm that starts at the repeat barline and walks outward, using a configurable overlap threshold.

**Architecture:** New function `_assign_volta_numbers()` replaces inline assignment. Called once per repeat-pair after all hitboxes are collected. Helper `_measure_hitbox_overlap()` checks if a measure has sufficient X-overlap with any hitbox. Config parameter `volta_min_overlap_pct` controls the threshold.

**Tech Stack:** Python, numpy, existing scanner pipeline + config registry

**Spec:** `docs/superpowers/specs/2026-04-15-volta-assignment-rework-design.md`

---

### Task 1: Add `volta_min_overlap_pct` config registry entry

**Files:**
- Modify: `src/backend/mv_hofki/services/scanner_config_registry.py:344` (insert after hairpin section)

- [ ] **Step 1: Add the registry entry**

In `scanner_config_registry.py`, insert after line 344 (the closing `},` of `hairpin_min_confidence`), before the `# LilyPond Layout` comment:

```python
    #  ── Nachbearbeitung \ Volta-Erkennung ───────────────────────────
    {
        "key": "volta_min_overlap_pct",
        "default_value": "0.3",
        "type": "number",
        "label": "Min. \u00dcberlappung Takt/Klammer (%)",
        "group_path": "Nachbearbeitung\\Volta-Erkennung",
        "min": 0.0,
        "max": 1.0,
        "step": 0.05,
        "sort_order": 10,
    },
```

- [ ] **Step 2: Verify linter passes**

Run: `pre-commit run --files src/backend/mv_hofki/services/scanner_config_registry.py`
Expected: all checks pass

- [ ] **Step 3: Commit**

```bash
git add src/backend/mv_hofki/services/scanner_config_registry.py
git commit -m "feat(volta): add volta_min_overlap_pct config parameter"
```

---

### Task 2: Write and test `_measure_hitbox_overlap` helper

**Files:**
- Modify: `src/backend/mv_hofki/services/scanner/stages/volta_detection.py` (add function before `VoltaDetectionStage`)
- Modify: `tests/backend/test_volta_detection.py` (add unit tests)

- [ ] **Step 1: Write the failing tests**

Append to `tests/backend/test_volta_detection.py`:

```python
def test_measure_hitbox_overlap_sufficient():
    """Measure with 50% coverage passes 30% threshold."""
    from mv_hofki.services.scanner.stages.volta_detection import (
        _measure_hitbox_overlap,
    )

    m = MeasureData(0, 1, 1, x_start=100, x_end=300)
    hitboxes = [(200, 0, 400, 10, 0)]  # covers x=200-300 = 50%
    assert _measure_hitbox_overlap(m, hitboxes, 0.3) is True


def test_measure_hitbox_overlap_insufficient():
    """Measure with 10% coverage fails 30% threshold."""
    from mv_hofki.services.scanner.stages.volta_detection import (
        _measure_hitbox_overlap,
    )

    m = MeasureData(0, 1, 1, x_start=100, x_end=300)
    hitboxes = [(280, 0, 400, 10, 0)]  # covers x=280-300 = 10%
    assert _measure_hitbox_overlap(m, hitboxes, 0.3) is False


def test_measure_hitbox_overlap_wrong_staff():
    """Hitbox on different staff is ignored."""
    from mv_hofki.services.scanner.stages.volta_detection import (
        _measure_hitbox_overlap,
    )

    m = MeasureData(0, 1, 1, x_start=100, x_end=300)
    hitboxes = [(100, 0, 300, 10, 1)]  # staff 1, not staff 0
    assert _measure_hitbox_overlap(m, hitboxes, 0.3) is False


def test_measure_hitbox_overlap_multiple_hitboxes():
    """Passes if ANY hitbox on the same staff has enough overlap."""
    from mv_hofki.services.scanner.stages.volta_detection import (
        _measure_hitbox_overlap,
    )

    m = MeasureData(0, 1, 1, x_start=100, x_end=300)
    hitboxes = [
        (280, 0, 400, 10, 0),  # 10% — insufficient
        (150, 0, 350, 10, 0),  # 75% — sufficient
    ]
    assert _measure_hitbox_overlap(m, hitboxes, 0.3) is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/backend/test_volta_detection.py::test_measure_hitbox_overlap_sufficient -v`
Expected: ImportError — `_measure_hitbox_overlap` not found

- [ ] **Step 3: Implement the function**

In `volta_detection.py`, add before the `class VoltaDetectionStage` line (after `_bridge_bracket_gap`):

```python
def _measure_hitbox_overlap(
    measure: MeasureData,
    hitboxes: list[tuple[int, int, int, int, int]],
    min_overlap: float,
) -> bool:
    """Check if a measure has sufficient X overlap with any hitbox on its staff.

    Parameters
    ----------
    measure : the measure to check
    hitboxes : list of (x1, y1, x2, y2, staff_index) bounding boxes
    min_overlap : minimum overlap ratio (0.0–1.0) relative to measure width
    """
    m_width = measure.x_end - measure.x_start
    if m_width <= 0:
        return False
    for bx1, _by1, bx2, _by2, si in hitboxes:
        if si != measure.staff_index:
            continue
        overlap = max(0, min(measure.x_end, bx2) - max(measure.x_start, bx1))
        if overlap / m_width >= min_overlap:
            return True
    return False
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/backend/test_volta_detection.py -k "hitbox_overlap" -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/backend/mv_hofki/services/scanner/stages/volta_detection.py tests/backend/test_volta_detection.py
git commit -m "feat(volta): add _measure_hitbox_overlap helper with tests"
```

---

### Task 3: Write and test `_assign_volta_numbers` function

**Files:**
- Modify: `src/backend/mv_hofki/services/scanner/stages/volta_detection.py` (add function before `VoltaDetectionStage`)
- Modify: `tests/backend/test_volta_detection.py` (add unit tests)

- [ ] **Step 1: Write the failing tests**

Append to `tests/backend/test_volta_detection.py`:

```python
def test_assign_volta_spanning_bracket():
    """One bracket spanning across repeat assigns volta 1 left, volta 2 right."""
    from mv_hofki.services.scanner.stages.volta_detection import (
        _assign_volta_numbers,
    )

    measures = [
        MeasureData(0, 1, 1, x_start=100, x_end=300),
        MeasureData(0, 2, 2, x_start=300, x_end=500, end_barline="Wiederholung Ende"),
        MeasureData(0, 3, 3, x_start=500, x_end=700),
    ]
    # One hitbox spanning 150–650 on staff 0
    hitboxes = [(150, 0, 650, 10, 0)]

    _assign_volta_numbers(measures, hitboxes, measures[1], measures[2], 1, 0.3)

    assert measures[0].volta_number == 1
    assert measures[0].volta_group_id == 1
    assert measures[1].volta_number == 1
    assert measures[1].volta_group_id == 1
    assert measures[2].volta_number == 2
    assert measures[2].volta_group_id == 1


def test_assign_volta_separate_brackets():
    """Two separate hitboxes assign volta 1 and 2 correctly."""
    from mv_hofki.services.scanner.stages.volta_detection import (
        _assign_volta_numbers,
    )

    measures = [
        MeasureData(0, 1, 1, x_start=100, x_end=300),
        MeasureData(0, 2, 2, x_start=300, x_end=500, end_barline="Wiederholung Ende"),
        MeasureData(0, 3, 3, x_start=500, x_end=700),
    ]
    hitboxes = [
        (280, 0, 510, 10, 0),  # overlaps m2 (100%) and m3 (tiny)
        (490, 0, 710, 10, 0),  # overlaps m3 (100%)
    ]

    _assign_volta_numbers(measures, hitboxes, measures[1], measures[2], 1, 0.3)

    assert measures[0].volta_number is None  # no overlap
    assert measures[1].volta_number == 1
    assert measures[2].volta_number == 2


def test_assign_volta_walk_stops_at_gap():
    """Walk stops when a measure has insufficient overlap."""
    from mv_hofki.services.scanner.stages.volta_detection import (
        _assign_volta_numbers,
    )

    measures = [
        MeasureData(0, 1, 1, x_start=100, x_end=300),  # no overlap
        MeasureData(0, 2, 2, x_start=300, x_end=500),  # no overlap
        MeasureData(0, 3, 3, x_start=500, x_end=700, end_barline="Wiederholung Ende"),
        MeasureData(0, 4, 4, x_start=700, x_end=900),
    ]
    # Hitbox only over measures 3 and 4
    hitboxes = [(480, 0, 920, 10, 0)]

    _assign_volta_numbers(measures, hitboxes, measures[2], measures[3], 1, 0.3)

    assert measures[0].volta_number is None
    assert measures[1].volta_number is None  # walk stopped here
    assert measures[2].volta_number == 1
    assert measures[3].volta_number == 2


def test_assign_volta_cross_staff():
    """Volta 2 assigned on different staff via forward walk."""
    from mv_hofki.services.scanner.stages.volta_detection import (
        _assign_volta_numbers,
    )

    measures = [
        MeasureData(0, 1, 1, x_start=100, x_end=400),
        MeasureData(0, 2, 2, x_start=400, x_end=700, end_barline="Wiederholung Ende"),
        MeasureData(1, 1, 3, x_start=50, x_end=300),
        MeasureData(1, 2, 4, x_start=300, x_end=600),
    ]
    hitboxes = [
        (350, 0, 700, 10, 0),  # staff 0
        (50, 0, 300, 10, 1),   # staff 1
    ]

    _assign_volta_numbers(measures, hitboxes, measures[1], measures[2], 1, 0.3)

    assert measures[0].volta_number is None  # insufficient overlap
    assert measures[1].volta_number == 1
    assert measures[2].volta_number == 2
    assert measures[3].volta_number is None  # no overlap on staff 1


def test_assign_volta_no_hitboxes():
    """No hitboxes means no assignment."""
    from mv_hofki.services.scanner.stages.volta_detection import (
        _assign_volta_numbers,
    )

    measures = [
        MeasureData(0, 1, 1, x_start=100, x_end=300, end_barline="Wiederholung Ende"),
        MeasureData(0, 2, 2, x_start=300, x_end=500),
    ]

    _assign_volta_numbers(measures, [], measures[0], measures[1], 1, 0.3)

    assert measures[0].volta_number is None
    assert measures[1].volta_number is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/backend/test_volta_detection.py::test_assign_volta_spanning_bracket -v`
Expected: ImportError — `_assign_volta_numbers` not found

- [ ] **Step 3: Implement the function**

In `volta_detection.py`, add after `_measure_hitbox_overlap` and before `class VoltaDetectionStage`:

```python
def _assign_volta_numbers(
    measures: list[MeasureData],
    hitboxes: list[tuple[int, int, int, int, int]],
    pair_before: MeasureData,
    pair_after: MeasureData | None,
    group_id: int,
    min_overlap: float,
) -> None:
    """Assign volta numbers by walking outward from the repeat barline.

    Starting at the repeat measure, walks backwards assigning volta 1,
    then forwards assigning volta 2.  Stops in each direction when a
    measure has insufficient overlap with the collected hitboxes.
    """
    if not hitboxes:
        return

    # --- Volta 1: walk backwards on pair_before's staff ---
    staff_measures = sorted(
        [m for m in measures if m.staff_index == pair_before.staff_index],
        key=lambda m: m.x_start,
    )
    repeat_idx: int | None = None
    for i, m in enumerate(staff_measures):
        if m is pair_before:
            repeat_idx = i
            break

    if repeat_idx is not None:
        for i in range(repeat_idx, -1, -1):
            m = staff_measures[i]
            if _measure_hitbox_overlap(m, hitboxes, min_overlap):
                m.volta_number = 1
                m.volta_group_id = group_id
            else:
                break

    # --- Volta 2: walk forwards ---
    if pair_after is None:
        return

    if pair_after.staff_index == pair_before.staff_index:
        # Same staff — continue from repeat_idx + 1
        if repeat_idx is not None:
            for i in range(repeat_idx + 1, len(staff_measures)):
                m = staff_measures[i]
                if _measure_hitbox_overlap(m, hitboxes, min_overlap):
                    m.volta_number = 2
                    m.volta_group_id = group_id
                else:
                    break
    else:
        # Cross-staff — walk forwards on pair_after's staff
        after_staff_measures = sorted(
            [m for m in measures if m.staff_index == pair_after.staff_index],
            key=lambda m: m.x_start,
        )
        after_idx: int | None = None
        for i, m in enumerate(after_staff_measures):
            if m is pair_after:
                after_idx = i
                break
        if after_idx is not None:
            for i in range(after_idx, len(after_staff_measures)):
                m = after_staff_measures[i]
                if _measure_hitbox_overlap(m, hitboxes, min_overlap):
                    m.volta_number = 2
                    m.volta_group_id = group_id
                else:
                    break
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/backend/test_volta_detection.py -k "assign_volta" -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add src/backend/mv_hofki/services/scanner/stages/volta_detection.py tests/backend/test_volta_detection.py
git commit -m "feat(volta): add _assign_volta_numbers walk algorithm with tests"
```

---

### Task 4: Refactor `process()` to use `_assign_volta_numbers`

**Files:**
- Modify: `src/backend/mv_hofki/services/scanner/stages/volta_detection.py:257-411` (VoltaDetectionStage.process)

- [ ] **Step 1: Read config value at start of `process()`**

After line 263 (`staff_by_index = ...`), add:

```python
        min_overlap = float(ctx.config.get("volta_min_overlap_pct", 0.3))
```

- [ ] **Step 2: Add hitbox collection list inside repeat_pairs loop**

After line 297 (`for volta_num, measure in candidates:`), but **before** the candidates loop — i.e. after the `candidates = [...]` definition on line 294-297, add:

```python
            hitboxes: list[tuple[int, int, int, int, int]] = []
```

- [ ] **Step 3: Replace inline assignment with hitbox collection**

Replace the current assignment block (lines 386-392):

```python
                    # Assign volta number to all overlapping measures
                    for m in ctx.measures:
                        if m.staff_index != staff.staff_index:
                            continue
                        if m.x_start < bx2 and m.x_end > bx1:
                            m.volta_number = volta_num
                            m.volta_group_id = group_id
```

With:

```python
                    hitboxes.append((bx1, by1, bx2, by2, staff.staff_index))
```

- [ ] **Step 4: Call `_assign_volta_numbers` after candidates loop**

After the `for volta_num, measure in candidates:` loop ends (after line 399's `break`), add at the same indentation level as the `for volta_num` line:

```python
            _assign_volta_numbers(
                ctx.measures,
                hitboxes,
                pair_before,
                pair_after,
                group_id,
                min_overlap,
            )
```

- [ ] **Step 5: Run all volta tests**

Run: `python -m pytest tests/backend/test_volta_detection.py -v`
Expected: all tests pass (existing integration tests + new unit tests)

- [ ] **Step 6: Run linter**

Run: `pre-commit run --files src/backend/mv_hofki/services/scanner/stages/volta_detection.py`
Expected: all checks pass

- [ ] **Step 7: Commit**

```bash
git add src/backend/mv_hofki/services/scanner/stages/volta_detection.py
git commit -m "refactor(volta): replace inline assignment with walk-based _assign_volta_numbers"
```

---

### Task 5: Final verification

- [ ] **Step 1: Run full backend test suite**

Run: `python -m pytest tests/backend/ -v`
Expected: all tests pass (except the 2 pre-existing failures in test_scanner_config and test_item_invoices)

- [ ] **Step 2: Run linter on all changed files**

Run: `pre-commit run --all-files`
Expected: all checks pass
