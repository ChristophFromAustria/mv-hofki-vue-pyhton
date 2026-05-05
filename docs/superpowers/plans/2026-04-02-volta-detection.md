# Volta Detection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Detect volta brackets (1st/2nd endings) from the binary image, assign volta numbers based on proximity to repeat barlines, persist the data, render volta overlay in the UI, and generate correct Lilypond `\repeat volta` / `\alternative` structures.

**Architecture:** New `VoltaDetectionStage` uses morphological horizontal opening on the region above each staff to find bracket lines, then maps them to measures and assigns volta numbers. Two new nullable fields on `MeasureData`/`DetectedMeasure`. Lilypond generator is extended to emit `\repeat volta 2 { } \alternative { }` blocks.

**Tech Stack:** OpenCV (morphological ops), SQLAlchemy/Alembic, Vue 3 (SVG overlay)

---

### Task 1: Alembic migration — add volta fields to DetectedMeasure

**Files:**
- Create: `alembic/versions/XXXX_add_volta_fields_to_detected_measures.py`
- Modify: `src/backend/mv_hofki/models/detected_measure.py`
- Modify: `src/backend/mv_hofki/schemas/detected_measure.py`
- Modify: `src/backend/mv_hofki/services/scanner/stages/base.py:50-59`

- [ ] **Step 1: Add fields to MeasureData dataclass**

In `src/backend/mv_hofki/services/scanner/stages/base.py`, update `MeasureData`:

```python
@dataclass
class MeasureData:
    """Data for a single detected measure (Takt)."""

    staff_index: int
    measure_number_in_staff: int
    global_measure_number: int
    x_start: int
    x_end: int
    end_barline: str | None = None
    volta_number: int | None = None
    volta_group_id: int | None = None
```

- [ ] **Step 2: Add fields to DetectedMeasure model**

In `src/backend/mv_hofki/models/detected_measure.py`, add after `end_barline`:

```python
    volta_number: Mapped[int | None] = mapped_column(Integer)
    volta_group_id: Mapped[int | None] = mapped_column(Integer)
```

- [ ] **Step 3: Add fields to schema**

In `src/backend/mv_hofki/schemas/detected_measure.py`, add after `end_barline`:

```python
    volta_number: int | None
    volta_group_id: int | None
```

- [ ] **Step 4: Generate and write migration**

```bash
cd /workspaces/mv_hofki
PYTHONPATH=src/backend alembic revision -m "add_volta_fields_to_detected_measures"
```

In the generated file:

```python
def upgrade() -> None:
    with op.batch_alter_table("detected_measures") as batch_op:
        batch_op.add_column(sa.Column("volta_number", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("volta_group_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("detected_measures") as batch_op:
        batch_op.drop_column("volta_group_id")
        batch_op.drop_column("volta_number")
```

Run: `PYTHONPATH=src/backend alembic upgrade head`

- [ ] **Step 5: Update persistence in run_pipeline**

In `src/backend/mv_hofki/services/sheet_music_scan.py`, find the `DetectedMeasure(` creation (around line 359). Add the volta fields:

```python
    for m in ctx.measures:
        measure = DetectedMeasure(
            scan_id=scan_id,
            staff_id=staff_id_map.get(m.staff_index, 0),
            staff_index=m.staff_index,
            measure_number_in_staff=m.measure_number_in_staff,
            global_measure_number=m.global_measure_number,
            x_start=m.x_start,
            x_end=m.x_end,
            end_barline=m.end_barline,
            volta_number=m.volta_number,
            volta_group_id=m.volta_group_id,
        )
```

- [ ] **Step 6: Update API endpoint measure dict**

In `src/backend/mv_hofki/api/routes/scan_processing.py`, find the measures list comprehension in `generate_lilypond_endpoint`. Add:

```python
            "volta_number": m.volta_number,
            "volta_group_id": m.volta_group_id,
```

- [ ] **Step 7: Run tests and commit**

```bash
python -m pytest tests/backend/ -v -k "scan or measure" --tb=short
git add -A
git commit -m "feat: add volta_number and volta_group_id fields to DetectedMeasure"
```

---

### Task 2: Implement VoltaDetectionStage

**Files:**
- Create: `src/backend/mv_hofki/services/scanner/stages/volta_detection.py`
- Create: `tests/backend/test_volta_detection.py`

- [ ] **Step 1: Write the tests**

Create `tests/backend/test_volta_detection.py`:

```python
"""Tests for VoltaDetectionStage."""

import numpy as np

from mv_hofki.services.scanner.stages.base import (
    MeasureData,
    PipelineContext,
    StaffData,
)
from mv_hofki.services.scanner.stages.volta_detection import VoltaDetectionStage


def _make_binary_image_with_volta(
    width: int,
    height: int,
    staff_y_top: int,
    line_spacing: float,
    volta_x_start: int,
    volta_x_end: int,
) -> np.ndarray:
    """Create a white binary image with a horizontal volta line above the staff."""
    img = np.full((height, width), 255, dtype=np.uint8)
    # Draw a horizontal black line above the staff (volta bracket)
    volta_y = int(staff_y_top - line_spacing * 1.5)
    img[volta_y, volta_x_start:volta_x_end] = 0
    # Also draw a small vertical hook at the start
    img[volta_y : volta_y + int(line_spacing), volta_x_start] = 0
    return img


def test_single_volta_bracket_detected():
    """A horizontal line above the staff should be detected as a volta bracket."""
    staff = StaffData(
        staff_index=0,
        y_top=200,
        y_bottom=400,
        line_positions=[200, 250, 300, 350, 400],
        line_spacing=50.0,
    )
    measures = [
        MeasureData(
            staff_index=0, measure_number_in_staff=1,
            global_measure_number=1, x_start=50, x_end=200,
            end_barline="Einfacher Taktstrich",
        ),
        MeasureData(
            staff_index=0, measure_number_in_staff=2,
            global_measure_number=2, x_start=210, x_end=400,
            end_barline="Wiederholung Ende",
        ),
        MeasureData(
            staff_index=0, measure_number_in_staff=3,
            global_measure_number=3, x_start=410, x_end=600,
            end_barline=None,
        ),
    ]

    img = _make_binary_image_with_volta(
        width=700, height=500, staff_y_top=200, line_spacing=50.0,
        volta_x_start=210, volta_x_end=400,
    )

    ctx = PipelineContext(image=img, processed_image=img)
    ctx.staves = [staff]
    ctx.measures = measures

    result = VoltaDetectionStage().process(ctx)

    # The measure at x=210-400 should be marked as volta 1
    volta_measures = [m for m in result.measures if m.volta_number is not None]
    assert len(volta_measures) >= 1
    assert volta_measures[0].volta_number == 1


def test_no_volta_without_horizontal_line():
    """An image with no horizontal line above the staff should produce no voltas."""
    staff = StaffData(
        staff_index=0,
        y_top=200,
        y_bottom=400,
        line_positions=[200, 250, 300, 350, 400],
        line_spacing=50.0,
    )
    measures = [
        MeasureData(
            staff_index=0, measure_number_in_staff=1,
            global_measure_number=1, x_start=50, x_end=400,
            end_barline="Wiederholung Ende",
        ),
    ]

    img = np.full((500, 700), 255, dtype=np.uint8)

    ctx = PipelineContext(image=img, processed_image=img)
    ctx.staves = [staff]
    ctx.measures = measures

    result = VoltaDetectionStage().process(ctx)

    volta_measures = [m for m in result.measures if m.volta_number is not None]
    assert len(volta_measures) == 0


def test_two_brackets_get_different_numbers():
    """Two brackets near a repeat-end should be assigned volta 1 and volta 2."""
    staff = StaffData(
        staff_index=0,
        y_top=200,
        y_bottom=400,
        line_positions=[200, 250, 300, 350, 400],
        line_spacing=50.0,
    )
    measures = [
        MeasureData(
            staff_index=0, measure_number_in_staff=1,
            global_measure_number=1, x_start=50, x_end=200,
            end_barline="Einfacher Taktstrich",
        ),
        MeasureData(
            staff_index=0, measure_number_in_staff=2,
            global_measure_number=2, x_start=210, x_end=400,
            end_barline="Wiederholung Ende",
        ),
        MeasureData(
            staff_index=0, measure_number_in_staff=3,
            global_measure_number=3, x_start=410, x_end=600,
            end_barline=None,
        ),
    ]

    img = np.full((500, 700), 255, dtype=np.uint8)
    volta_y = int(200 - 50 * 1.5)
    # Volta 1: over measure 2
    img[volta_y, 210:400] = 0
    img[volta_y : volta_y + 50, 210] = 0
    # Volta 2: over measure 3
    img[volta_y, 410:600] = 0
    img[volta_y : volta_y + 50, 410] = 0

    ctx = PipelineContext(image=img, processed_image=img)
    ctx.staves = [staff]
    ctx.measures = measures

    result = VoltaDetectionStage().process(ctx)

    volta_measures = [m for m in result.measures if m.volta_number is not None]
    assert len(volta_measures) == 2
    volta_measures.sort(key=lambda m: m.x_start)
    assert volta_measures[0].volta_number == 1
    assert volta_measures[1].volta_number == 2
    assert volta_measures[0].volta_group_id == volta_measures[1].volta_group_id
```

- [ ] **Step 2: Run tests — expect ImportError**

```bash
python -m pytest tests/backend/test_volta_detection.py -v
```

- [ ] **Step 3: Implement VoltaDetectionStage**

Create `src/backend/mv_hofki/services/scanner/stages/volta_detection.py`:

```python
"""Volta bracket detection: find 1st/2nd ending brackets above staves."""

from __future__ import annotations

import cv2
import numpy as np

from mv_hofki.services.scanner.stages.base import (
    MeasureData,
    PipelineContext,
    ProcessingStage,
    StaffData,
)

_REPEAT_END_NAMES = {"Wiederholung Ende", "Wiederholung Beidseitig"}


class VoltaDetectionStage(ProcessingStage):
    """Detect volta brackets by finding horizontal lines above staves."""

    name = "volta_detection"

    def process(self, ctx: PipelineContext) -> PipelineContext:
        binary = ctx.processed_image
        if binary is None:
            return ctx

        staff_map = {s.staff_index: s for s in ctx.staves}
        measures_by_staff: dict[int, list[MeasureData]] = {}
        for m in ctx.measures:
            measures_by_staff.setdefault(m.staff_index, []).append(m)

        group_id = 1

        for staff_index in sorted(staff_map.keys()):
            staff = staff_map[staff_index]
            staff_measures = measures_by_staff.get(staff_index, [])
            if not staff_measures:
                continue

            # Find horizontal volta lines above this staff
            brackets = self._find_brackets(binary, staff, staff_measures)
            if not brackets:
                continue

            # Assign volta numbers based on proximity to repeat barlines
            self._assign_volta_numbers(
                brackets, staff_measures, group_id
            )
            group_id += len(brackets)

        ctx.log(
            f"Volta-Erkennung: "
            f"{sum(1 for m in ctx.measures if m.volta_number is not None)} "
            f"Takte mit Volta-Klammern"
        )
        return ctx

    def _find_brackets(
        self,
        binary: np.ndarray,
        staff: StaffData,
        measures: list[MeasureData],
    ) -> list[tuple[int, int]]:
        """Find horizontal line segments in the volta region above the staff.

        Returns list of (x_start, x_end) for each detected bracket.
        """
        ls = staff.line_spacing
        # Volta region: from 3*line_spacing above y_top to y_top
        region_top = max(0, int(staff.y_top - 3 * ls))
        region_bottom = staff.y_top
        if region_top >= region_bottom:
            return []

        # Extract and invert the region (make foreground white for morphology)
        region = binary[region_top:region_bottom, :]
        inverted = cv2.bitwise_not(region)

        # Average measure width for kernel sizing
        avg_measure_width = int(
            sum(m.x_end - m.x_start for m in measures) / max(len(measures), 1)
        )
        kernel_width = max(avg_measure_width // 2, 20)

        # Horizontal morphological opening to isolate horizontal lines
        kernel = cv2.getStructuringElement(
            cv2.MORPH_RECT, (kernel_width, 1)
        )
        horizontal = cv2.morphologyEx(inverted, cv2.MORPH_OPEN, kernel)

        # Find contours
        contours, _ = cv2.findContours(
            horizontal, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        min_width = avg_measure_width // 2
        brackets: list[tuple[int, int]] = []
        for cnt in contours:
            x, _, w, _ = cv2.boundingRect(cnt)
            if w >= min_width:
                brackets.append((x, x + w))

        brackets.sort(key=lambda b: b[0])
        return brackets

    def _assign_volta_numbers(
        self,
        brackets: list[tuple[int, int]],
        measures: list[MeasureData],
        start_group_id: int,
    ) -> None:
        """Assign volta_number and volta_group_id to measures under brackets.

        Brackets before/at a repeat-end barline get volta_number=1,
        brackets after get volta_number=2.
        """
        # Find repeat-end measure positions
        repeat_end_positions: list[int] = []
        for m in measures:
            if m.end_barline in _REPEAT_END_NAMES:
                repeat_end_positions.append(m.x_end)

        current_group = start_group_id

        for bx_start, bx_end in brackets:
            # Determine volta number: check if bracket is before or after a repeat-end
            volta_num = 1  # default
            for rep_x in repeat_end_positions:
                if bx_start >= rep_x:
                    volta_num = 2
                    break

            # Find measures under this bracket
            for m in measures:
                # Measure overlaps with bracket if there's horizontal intersection
                overlap = min(m.x_end, bx_end) - max(m.x_start, bx_start)
                measure_width = m.x_end - m.x_start
                if overlap > measure_width * 0.3:
                    m.volta_number = volta_num
                    m.volta_group_id = current_group

            current_group += 1

        # Pair up volta 1 and volta 2 with the same group_id
        # Find volta 1 brackets and the next volta 2 bracket
        volta1_groups = set()
        volta2_groups = set()
        for m in measures:
            if m.volta_number == 1 and m.volta_group_id is not None:
                volta1_groups.add(m.volta_group_id)
            elif m.volta_number == 2 and m.volta_group_id is not None:
                volta2_groups.add(m.volta_group_id)

        # Merge adjacent volta 1/2 into the same group
        if volta1_groups and volta2_groups:
            v1_id = min(volta1_groups)
            for m in measures:
                if m.volta_number == 2 and m.volta_group_id in volta2_groups:
                    m.volta_group_id = v1_id

    def validate(self, ctx: PipelineContext) -> bool:
        return ctx.processed_image is not None and len(ctx.measures) > 0
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/backend/test_volta_detection.py -v
```

Expected: all 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/backend/mv_hofki/services/scanner/stages/volta_detection.py tests/backend/test_volta_detection.py
git commit -m "feat: add VoltaDetectionStage with image-based bracket detection"
```

---

### Task 3: Wire VoltaDetectionStage into pipeline

**Files:**
- Modify: `src/backend/mv_hofki/services/sheet_music_scan.py`

- [ ] **Step 1: Add the stage after MeasureDetectionStage**

In `src/backend/mv_hofki/services/sheet_music_scan.py`, find where `MeasureDetectionStage()` is appended (around line 255). Add after it:

```python
    from mv_hofki.services.scanner.stages.volta_detection import VoltaDetectionStage

    stages.append(VoltaDetectionStage())
```

- [ ] **Step 2: Run tests**

```bash
python -m pytest tests/backend/ -v -k "scan or measure or volta" --tb=short
```

- [ ] **Step 3: Commit**

```bash
git add src/backend/mv_hofki/services/sheet_music_scan.py
git commit -m "feat: wire VoltaDetectionStage into pipeline after MeasureDetection"
```

---

### Task 4: Update Lilypond generator for volta/repeat structures

**Files:**
- Modify: `src/backend/mv_hofki/services/lilypond_generator.py:56-69`
- Modify: `tests/backend/test_lilypond_generator.py`

- [ ] **Step 1: Write the test**

Add to `tests/backend/test_lilypond_generator.py`:

```python
def test_volta_brackets_generate_repeat_alternative():
    """Measures with volta numbers should produce \\repeat volta / \\alternative."""
    measures = [
        {"staff_index": 0, "measure_number_in_staff": 1,
         "global_measure_number": 1, "x_start": 0, "x_end": 100,
         "end_barline": "Einfacher Taktstrich"},
        {"staff_index": 0, "measure_number_in_staff": 2,
         "global_measure_number": 2, "x_start": 100, "x_end": 200,
         "end_barline": "Einfacher Taktstrich"},
        {"staff_index": 0, "measure_number_in_staff": 3,
         "global_measure_number": 3, "x_start": 200, "x_end": 300,
         "end_barline": "Wiederholung Ende",
         "volta_number": 1, "volta_group_id": 1},
        {"staff_index": 0, "measure_number_in_staff": 4,
         "global_measure_number": 4, "x_start": 300, "x_end": 400,
         "end_barline": None,
         "volta_number": 2, "volta_group_id": 1},
    ]
    code = generate_lilypond(measures, "Test")
    assert "\\repeat volta 2 {" in code
    assert "\\alternative {" in code
    assert "\\volta 1 {" in code
    assert "\\volta 2 {" in code


def test_no_volta_no_repeat_structure():
    """Measures without volta numbers should not produce repeat structures."""
    measures = [
        {"staff_index": 0, "measure_number_in_staff": 1,
         "global_measure_number": 1, "x_start": 0, "x_end": 100,
         "end_barline": "Wiederholung Ende"},
    ]
    code = generate_lilypond(measures, "Test")
    assert "\\repeat volta" not in code
```

- [ ] **Step 2: Run test — expect failure**

```bash
python -m pytest tests/backend/test_lilypond_generator.py -v -k "volta"
```

- [ ] **Step 3: Rewrite the content generation in generate_lilypond**

In `src/backend/mv_hofki/services/lilypond_generator.py`, replace the content generation block (the section starting with `# Build note content` through `content = "\n".join(content_lines)`):

```python
    # Build note content with volta/repeat structures
    staff_indices = sorted(systems.keys())
    content_lines: list[str] = []

    for i, staff_idx in enumerate(staff_indices):
        staff_measures = systems[staff_idx]
        lines = _build_staff_content(staff_measures)
        content_lines.extend(f"    {line}" for line in lines)
        if i < len(staff_indices) - 1:
            content_lines.append("    \\break")

    content = "\n".join(content_lines)
```

And add this helper function BEFORE `generate_lilypond`:

```python
def _measure_to_ly(m: dict) -> str:
    """Convert a single measure dict to a LilyPond note string."""
    bar_cmd = _BARLINE_MAP.get(m.get("end_barline") or "", "")
    if bar_cmd:
        return f"c1 {bar_cmd}"
    return "c1"


def _build_staff_content(measures: list[dict]) -> list[str]:
    """Build LilyPond lines for a single staff, handling volta/repeat structures.

    Returns a list of LilyPond code lines (without indentation prefix).
    """
    lines: list[str] = []

    # Group measures by volta_group_id
    volta_groups: dict[int, list[dict]] = {}
    for m in measures:
        gid = m.get("volta_group_id")
        if gid is not None:
            volta_groups.setdefault(gid, []).append(m)

    i = 0
    while i < len(measures):
        m = measures[i]
        gid = m.get("volta_group_id")

        if gid is not None and m.get("volta_number") == 1:
            # Start of a volta group — find the repeat body before it
            # Look backwards for measures that are in the repeat body
            # (between the previous repeat-start barline and here)
            group = volta_groups[gid]
            volta1 = [g for g in group if g.get("volta_number") == 1]
            volta2 = [g for g in group if g.get("volta_number") == 2]

            # Find where the repeat body starts (scan backwards for .|: barline)
            repeat_start_idx = 0
            for j in range(i - 1, -1, -1):
                bl = measures[j].get("end_barline") or ""
                if "Wiederholung Anfang" in bl or "Wiederholung Beidseitig" in bl:
                    repeat_start_idx = j + 1
                    break

            # Collect repeat body measures (already emitted ones need to be
            # wrapped, but since we emit linearly, we need to handle this
            # by NOT emitting them earlier. For simplicity, we emit them
            # inline here and skip duplicates.)
            # Actually, the simpler approach: we already emitted measures
            # before the volta. We can't un-emit them. So we wrap just the
            # volta alternatives.

            lines.append("\\repeat volta 2 {")
            # Re-emit the repeat body (measures from repeat_start to first volta)
            # But we may have already emitted them. To avoid this, let's track.
            # Simpler: detect volta groups at the start, split the measures.

            # For now, emit the volta alternatives only
            lines.append("} \\alternative {")
            if volta1:
                volta1.sort(key=lambda m: m["measure_number_in_staff"])
                v1_notes = " ".join(_measure_to_ly(vm) for vm in volta1)
                lines.append(f"  \\volta 1 {{ {v1_notes} }}")
            if volta2:
                volta2.sort(key=lambda m: m["measure_number_in_staff"])
                v2_notes = " ".join(_measure_to_ly(vm) for vm in volta2)
                lines.append(f"  \\volta 2 {{ {v2_notes} }}")
            lines.append("}")

            # Skip all measures in this volta group
            group_indices = {
                m2["global_measure_number"] for m2 in group
            }
            while i < len(measures) and measures[i].get("global_measure_number") in group_indices:
                i += 1
        else:
            lines.append(_measure_to_ly(m))
            i += 1

    return lines
```

Wait — this approach has a problem: the repeat body (measures before the volta) needs to be wrapped in `\repeat volta 2 { }` but we've already emitted them as plain notes. Let me redesign.

Better approach — do a two-pass:

```python
def _measure_to_ly(m: dict) -> str:
    """Convert a single measure dict to a LilyPond note with optional barline."""
    bar_cmd = _BARLINE_MAP.get(m.get("end_barline") or "", "")
    return f"c1 {bar_cmd}" if bar_cmd else "c1"


def _build_staff_content(measures: list[dict]) -> list[str]:
    """Build LilyPond lines for one staff, handling volta/repeat structures."""
    lines: list[str] = []

    # Index volta groups
    volta_groups: dict[int, list[dict]] = {}
    for m in measures:
        gid = m.get("volta_group_id")
        if gid is not None:
            volta_groups.setdefault(gid, []).append(m)

    # Track which measures are in volta groups
    volta_measure_nums: set[int] = set()
    for group in volta_groups.values():
        for m in group:
            volta_measure_nums.add(m["global_measure_number"])

    # Find repeat body start positions for each volta group
    # A repeat body starts at the barline "Wiederholung Anfang" or "Wiederholung Beidseitig"
    # before the volta group, or at the beginning of the staff.
    repeat_body_starts: dict[int, int] = {}  # volta_group_id -> measure index
    for gid, group in volta_groups.items():
        first_volta_idx = min(
            i for i, m in enumerate(measures)
            if m.get("volta_group_id") == gid
        )
        # Scan backwards for repeat-start barline
        start_idx = 0
        for j in range(first_volta_idx - 1, -1, -1):
            bl = measures[j].get("end_barline") or ""
            if "Wiederholung Anfang" in bl or "Wiederholung Beidseitig" in bl:
                start_idx = j + 1
                break
        repeat_body_starts[gid] = start_idx

    # Track which measures are in repeat bodies
    repeat_body_nums: dict[int, set[int]] = {}  # gid -> set of global_measure_numbers
    for gid, start_idx in repeat_body_starts.items():
        first_volta_idx = min(
            i for i, m in enumerate(measures)
            if m.get("volta_group_id") == gid
        )
        repeat_body_nums[gid] = {
            measures[j]["global_measure_number"]
            for j in range(start_idx, first_volta_idx)
        }

    emitted: set[int] = set()
    i = 0
    while i < len(measures):
        m = measures[i]
        gnum = m["global_measure_number"]

        if gnum in emitted:
            i += 1
            continue

        # Check if this measure starts a repeat body for a volta group
        started_group = None
        for gid, start_idx in repeat_body_starts.items():
            if i == start_idx:
                started_group = gid
                break

        if started_group is not None:
            gid = started_group
            body_nums = repeat_body_nums[gid]
            group = volta_groups[gid]
            volta1 = sorted(
                [g for g in group if g.get("volta_number") == 1],
                key=lambda m: m["measure_number_in_staff"],
            )
            volta2 = sorted(
                [g for g in group if g.get("volta_number") == 2],
                key=lambda m: m["measure_number_in_staff"],
            )

            # Emit repeat body
            body_notes = []
            for j in range(i, len(measures)):
                if measures[j]["global_measure_number"] in body_nums:
                    body_notes.append(_measure_to_ly(measures[j]))
                    emitted.add(measures[j]["global_measure_number"])
                else:
                    break

            lines.append(
                "\\repeat volta 2 { "
                + " ".join(body_notes)
                + " }"
            )

            # Emit alternatives
            lines.append("\\alternative {")
            if volta1:
                v1 = " ".join(_measure_to_ly(vm) for vm in volta1)
                lines.append(f"  \\volta 1 {{ {v1} }}")
                for vm in volta1:
                    emitted.add(vm["global_measure_number"])
            if volta2:
                v2 = " ".join(_measure_to_ly(vm) for vm in volta2)
                lines.append(f"  \\volta 2 {{ {v2} }}")
                for vm in volta2:
                    emitted.add(vm["global_measure_number"])
            lines.append("}")

            # Advance past all emitted measures
            while i < len(measures) and measures[i]["global_measure_number"] in emitted:
                i += 1
        else:
            lines.append(_measure_to_ly(m))
            emitted.add(gnum)
            i += 1

    return lines
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/backend/test_lilypond_generator.py -v
```

Expected: all tests PASS (including the 2 new volta tests).

- [ ] **Step 5: Commit**

```bash
git add src/backend/mv_hofki/services/lilypond_generator.py tests/backend/test_lilypond_generator.py
git commit -m "feat: generate Lilypond repeat volta / alternative from volta data"
```

---

### Task 5: Frontend — volta overlay

**Files:**
- Modify: `src/frontend/src/components/ScanCanvas.vue`
- Modify: `src/frontend/src/components/FilterDropdown.vue`
- Modify: `src/frontend/src/pages/ScanEditorPage.vue`

- [ ] **Step 1: Add showVoltas to ScanEditorPage**

In `src/frontend/src/pages/ScanEditorPage.vue`, add ref near the other display refs:
```js
const showVoltas = ref(true);
```

Pass to ScanCanvas:
```html
            :show-voltas="showVoltas"
```

Pass to FilterDropdown:
```html
              :show-voltas="showVoltas"
              @update:show-voltas="showVoltas = $event"
```

- [ ] **Step 2: Add to FilterDropdown**

In `src/frontend/src/components/FilterDropdown.vue`:

Add prop:
```js
  showVoltas: { type: Boolean, default: true },
```

Add emit:
```js
"update:showVoltas"
```

Add checkbox after "Takte anzeigen":
```html
          <label class="filter-check">
            <input
              type="checkbox"
              :checked="showVoltas"
              @change="emit('update:showVoltas', $event.target.checked)"
            />
            Volta-Klammern anzeigen
          </label>
```

- [ ] **Step 3: Add volta rendering to ScanCanvas**

In `src/frontend/src/components/ScanCanvas.vue`:

Add prop:
```js
  showVoltas: { type: Boolean, default: true },
```

Add helper function:
```js
function voltaBrackets() {
  // Group measures by volta_group_id, return bracket info
  const groups = {};
  for (const m of props.measures) {
    if (m.volta_number && m.volta_group_id != null) {
      if (!groups[m.volta_group_id]) groups[m.volta_group_id] = {};
      if (!groups[m.volta_group_id][m.volta_number]) {
        groups[m.volta_group_id][m.volta_number] = [];
      }
      groups[m.volta_group_id][m.volta_number].push(m);
    }
  }
  const brackets = [];
  for (const [groupId, voltas] of Object.entries(groups)) {
    for (const [num, measures] of Object.entries(voltas)) {
      const xStart = Math.min(...measures.map((m) => m.x_start));
      const xEnd = Math.max(...measures.map((m) => m.x_end));
      const staffIdx = measures[0].staff_index;
      brackets.push({ groupId, num: parseInt(num), xStart, xEnd, staffIdx });
    }
  }
  return brackets;
}
```

Add SVG overlay after the measure boundaries block and before the symbol bounding boxes:
```html
        <!-- Volta brackets -->
        <template v-if="showVoltas">
          <g v-for="(vb, idx) in voltaBrackets()" :key="`volta-${idx}`">
            <!-- Horizontal line -->
            <line
              :x1="vb.xStart"
              :y1="(staffBounds(vb.staffIdx)?.y_top ?? 0) - 25"
              :x2="vb.xEnd"
              :y2="(staffBounds(vb.staffIdx)?.y_top ?? 0) - 25"
              stroke="#d946ef"
              stroke-width="2"
              opacity="0.8"
            />
            <!-- Vertical hook at start -->
            <line
              :x1="vb.xStart"
              :y1="(staffBounds(vb.staffIdx)?.y_top ?? 0) - 25"
              :x2="vb.xStart"
              :y2="(staffBounds(vb.staffIdx)?.y_top ?? 0) - 10"
              stroke="#d946ef"
              stroke-width="2"
              opacity="0.8"
            />
            <!-- Volta number label -->
            <text
              :x="vb.xStart + 6"
              :y="(staffBounds(vb.staffIdx)?.y_top ?? 0) - 28"
              fill="#d946ef"
              font-size="11"
              font-weight="700"
              opacity="0.9"
            >
              {{ vb.num }}.
            </text>
          </g>
        </template>
```

- [ ] **Step 4: Verify build**

```bash
cd /workspaces/mv_hofki/src/frontend && npx vite build
```

- [ ] **Step 5: Commit**

```bash
cd /workspaces/mv_hofki
git add src/frontend/src/components/ScanCanvas.vue src/frontend/src/components/FilterDropdown.vue src/frontend/src/pages/ScanEditorPage.vue
git commit -m "feat: render volta bracket overlay with toggle in scan editor"
```

---

### Task 6: Full verification

- [ ] **Step 1: Run all backend tests**

```bash
python -m pytest tests/backend/ -v --tb=short
```

- [ ] **Step 2: Run pre-commit**

```bash
pre-commit run --all-files
```

- [ ] **Step 3: Manual E2E test**

1. Run analysis on a scan that has repeat barlines with volta brackets visible in the original image (e.g. Scan 5 or Scan 9)
2. Check API: `curl .../scanner/scans/{id}/measures | python -m json.tool` — verify `volta_number` and `volta_group_id` are set on some measures
3. In the UI: magenta volta bracket lines above staves with "1." and "2." labels
4. Toggle "Volta-Klammern anzeigen" in FilterDropdown
5. Click "LilyPond" — verify the code contains `\repeat volta 2 { }` and `\alternative { \volta 1 { } \volta 2 { } }`
6. Open the generated PDF — verify the volta brackets render correctly in the score
