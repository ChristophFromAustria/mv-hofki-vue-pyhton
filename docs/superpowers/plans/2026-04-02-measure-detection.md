# Measure Detection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Detect measure (Takt) boundaries from barline matches, persist them, and visualize them as vertical lines with labels in the scan editor.

**Architecture:** New `MeasureData` dataclass and `MeasureDetectionStage` pipeline stage builds measures from barline symbols grouped by staff. New `DetectedMeasure` DB model stores the results. Frontend renders vertical lines at measure boundaries with global measure numbers as labels.

**Tech Stack:** SQLAlchemy/Alembic, FastAPI, Vue 3 (SVG overlay)

---

### Task 1: Add `MeasureData` to PipelineContext

**Files:**
- Modify: `src/backend/mv_hofki/services/scanner/stages/base.py`

- [ ] **Step 1: Add MeasureData dataclass**

In `src/backend/mv_hofki/services/scanner/stages/base.py`, add after the `SymbolData` class (around line 45) and before `PipelineContext`:

```python
@dataclass
class MeasureData:
    """Data for a single detected measure (Takt)."""

    staff_index: int
    measure_number_in_staff: int
    global_measure_number: int
    x_start: int
    x_end: int
```

- [ ] **Step 2: Add measures field to PipelineContext**

In the `PipelineContext` dataclass, add after `symbols`:

```python
    measures: list[MeasureData] = field(default_factory=list)
```

Update the import if `MeasureData` isn't auto-visible (it's in the same file, so no import needed).

- [ ] **Step 3: Commit**

```bash
git add src/backend/mv_hofki/services/scanner/stages/base.py
git commit -m "feat: add MeasureData dataclass and measures field to PipelineContext"
```

---

### Task 2: Implement MeasureDetectionStage

**Files:**
- Create: `src/backend/mv_hofki/services/scanner/stages/measure_detection.py`
- Create: `tests/backend/test_measure_detection.py`

- [ ] **Step 1: Write the tests**

Create `tests/backend/test_measure_detection.py`:

```python
"""Tests for MeasureDetectionStage."""

from mv_hofki.services.scanner.stages.base import (
    MeasureData,
    PipelineContext,
    StaffData,
    SymbolData,
)
from mv_hofki.services.scanner.stages.measure_detection import MeasureDetectionStage

import numpy as np


def _ctx_with_symbols(staves, symbols, template_categories=None):
    """Build a PipelineContext with staves, symbols, and template metadata."""
    ctx = PipelineContext(image=np.zeros((100, 800), dtype=np.uint8))
    ctx.staves = staves
    ctx.symbols = symbols
    ctx.metadata["template_categories"] = template_categories or {}
    return ctx


def test_single_staff_three_barlines_four_measures():
    """Three barlines split a single staff into four measures."""
    staff = StaffData(
        staff_index=0, y_top=50, y_bottom=100,
        line_positions=[50, 60, 70, 80, 90], line_spacing=10.0,
    )
    symbols = [
        # Some note symbols
        SymbolData(staff_index=0, x=10, y=60, width=20, height=30,
                   staff_x_start=10, staff_x_end=30, matched_template_id=1),
        # Barlines at x=100, x=300, x=500
        SymbolData(staff_index=0, x=100, y=50, width=5, height=50,
                   staff_x_start=100, staff_x_end=105, matched_template_id=10),
        SymbolData(staff_index=0, x=300, y=50, width=5, height=50,
                   staff_x_start=300, staff_x_end=305, matched_template_id=10),
        SymbolData(staff_index=0, x=500, y=50, width=5, height=50,
                   staff_x_start=500, staff_x_end=505, matched_template_id=10),
        # Note after last barline
        SymbolData(staff_index=0, x=600, y=60, width=20, height=30,
                   staff_x_start=600, staff_x_end=620, matched_template_id=1),
    ]
    categories = {1: "note", 10: "barline"}

    ctx = _ctx_with_symbols([staff], symbols, categories)
    result = MeasureDetectionStage().process(ctx)

    assert len(result.measures) == 4
    assert result.measures[0].measure_number_in_staff == 1
    assert result.measures[0].x_start == 10  # first symbol x
    assert result.measures[0].x_end == 100  # first barline x_start
    assert result.measures[1].measure_number_in_staff == 2
    assert result.measures[1].x_start == 105  # first barline x_end
    assert result.measures[1].x_end == 300
    assert result.measures[3].measure_number_in_staff == 4
    assert result.measures[3].x_end == 620  # last symbol x_end


def test_two_staffs_global_numbering():
    """Global measure numbers continue across staves."""
    staff0 = StaffData(
        staff_index=0, y_top=50, y_bottom=100,
        line_positions=[50, 60, 70, 80, 90], line_spacing=10.0,
    )
    staff1 = StaffData(
        staff_index=1, y_top=150, y_bottom=200,
        line_positions=[150, 160, 170, 180, 190], line_spacing=10.0,
    )
    symbols = [
        # Staff 0: one barline -> 2 measures
        SymbolData(staff_index=0, x=10, y=60, width=20, height=30,
                   staff_x_start=10, staff_x_end=30, matched_template_id=1),
        SymbolData(staff_index=0, x=200, y=50, width=5, height=50,
                   staff_x_start=200, staff_x_end=205, matched_template_id=10),
        SymbolData(staff_index=0, x=350, y=60, width=20, height=30,
                   staff_x_start=350, staff_x_end=370, matched_template_id=1),
        # Staff 1: one barline -> 2 measures
        SymbolData(staff_index=1, x=10, y=160, width=20, height=30,
                   staff_x_start=10, staff_x_end=30, matched_template_id=1),
        SymbolData(staff_index=1, x=200, y=150, width=5, height=50,
                   staff_x_start=200, staff_x_end=205, matched_template_id=10),
        SymbolData(staff_index=1, x=350, y=160, width=20, height=30,
                   staff_x_start=350, staff_x_end=370, matched_template_id=1),
    ]
    categories = {1: "note", 10: "barline"}

    ctx = _ctx_with_symbols([staff0, staff1], symbols, categories)
    result = MeasureDetectionStage().process(ctx)

    assert len(result.measures) == 4
    # Staff 0: global 1, 2
    assert result.measures[0].global_measure_number == 1
    assert result.measures[1].global_measure_number == 2
    # Staff 1: global 3, 4
    assert result.measures[2].global_measure_number == 3
    assert result.measures[3].global_measure_number == 4


def test_no_barlines_single_measure():
    """A staff with no barlines produces a single measure spanning all symbols."""
    staff = StaffData(
        staff_index=0, y_top=50, y_bottom=100,
        line_positions=[50, 60, 70, 80, 90], line_spacing=10.0,
    )
    symbols = [
        SymbolData(staff_index=0, x=10, y=60, width=20, height=30,
                   staff_x_start=10, staff_x_end=30, matched_template_id=1),
        SymbolData(staff_index=0, x=200, y=60, width=20, height=30,
                   staff_x_start=200, staff_x_end=220, matched_template_id=1),
    ]
    categories = {1: "note"}

    ctx = _ctx_with_symbols([staff], symbols, categories)
    result = MeasureDetectionStage().process(ctx)

    assert len(result.measures) == 1
    assert result.measures[0].x_start == 10
    assert result.measures[0].x_end == 220


def test_filtered_barlines_ignored():
    """Filtered barlines should not create measure boundaries."""
    staff = StaffData(
        staff_index=0, y_top=50, y_bottom=100,
        line_positions=[50, 60, 70, 80, 90], line_spacing=10.0,
    )
    symbols = [
        SymbolData(staff_index=0, x=10, y=60, width=20, height=30,
                   staff_x_start=10, staff_x_end=30, matched_template_id=1),
        SymbolData(staff_index=0, x=200, y=50, width=5, height=50,
                   staff_x_start=200, staff_x_end=205, matched_template_id=10,
                   filtered=True, filter_reason="barline_position_outside_staff"),
        SymbolData(staff_index=0, x=400, y=60, width=20, height=30,
                   staff_x_start=400, staff_x_end=420, matched_template_id=1),
    ]
    categories = {1: "note", 10: "barline"}

    ctx = _ctx_with_symbols([staff], symbols, categories)
    result = MeasureDetectionStage().process(ctx)

    assert len(result.measures) == 1  # no barline split
```

- [ ] **Step 2: Run tests — expect ImportError**

```bash
python -m pytest tests/backend/test_measure_detection.py -v
```

Expected: FAIL — `MeasureDetectionStage` does not exist.

- [ ] **Step 3: Implement MeasureDetectionStage**

Create `src/backend/mv_hofki/services/scanner/stages/measure_detection.py`:

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
        staff_map = {s.staff_index: s for s in ctx.staves}

        # Group non-filtered barline symbols and all symbols by staff
        barlines_by_staff: dict[int, list] = {}
        all_symbols_by_staff: dict[int, list] = {}

        for sym in ctx.symbols:
            if sym.staff_index not in all_symbols_by_staff:
                all_symbols_by_staff[sym.staff_index] = []
            all_symbols_by_staff[sym.staff_index].append(sym)

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
            barlines = barlines_by_staff.get(staff_index, [])
            barlines.sort(key=lambda s: s.staff_x_start or s.x)

            staff_symbols = all_symbols_by_staff.get(staff_index, [])
            if not staff_symbols:
                continue

            # Determine staff extent from symbol positions
            min_x = min(s.staff_x_start or s.x for s in staff_symbols)
            max_x = max(s.staff_x_end or (s.x + s.width) for s in staff_symbols)

            # Build measure boundaries
            boundaries: list[tuple[int, int]] = []
            prev_end = min_x

            for bl in barlines:
                bl_start = bl.staff_x_start or bl.x
                bl_end = bl.staff_x_end or (bl.x + bl.width)
                if bl_start > prev_end:
                    boundaries.append((prev_end, bl_start))
                prev_end = bl_end

            # Last measure: from last barline end to the staff extent
            if prev_end < max_x:
                boundaries.append((prev_end, max_x))

            # If no barlines at all, single measure
            if not boundaries:
                boundaries = [(min_x, max_x)]

            local_num = 1
            for x_start, x_end in boundaries:
                measures.append(
                    MeasureData(
                        staff_index=staff_index,
                        measure_number_in_staff=local_num,
                        global_measure_number=global_num,
                        x_start=x_start,
                        x_end=x_end,
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

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/backend/test_measure_detection.py -v
```

Expected: all 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/backend/mv_hofki/services/scanner/stages/measure_detection.py tests/backend/test_measure_detection.py
git commit -m "feat: add MeasureDetectionStage with tests"
```

---

### Task 3: Alembic migration + DetectedMeasure model + schema + API

**Files:**
- Create: `alembic/versions/XXXX_add_detected_measures.py`
- Create: `src/backend/mv_hofki/models/detected_measure.py`
- Modify: `src/backend/mv_hofki/models/__init__.py`
- Create: `src/backend/mv_hofki/schemas/detected_measure.py`
- Modify: `src/backend/mv_hofki/api/routes/scan_processing.py`

- [ ] **Step 1: Create the ORM model**

Create `src/backend/mv_hofki/models/detected_measure.py`:

```python
"""DetectedMeasure ORM model."""

from __future__ import annotations

from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from mv_hofki.db.base import Base


class DetectedMeasure(Base):
    __tablename__ = "detected_measures"

    id: Mapped[int] = mapped_column(primary_key=True)
    scan_id: Mapped[int] = mapped_column(
        ForeignKey("sheet_music_scans.id", ondelete="CASCADE"), nullable=False
    )
    staff_id: Mapped[int] = mapped_column(
        ForeignKey("detected_staves.id", ondelete="CASCADE"), nullable=False
    )
    staff_index: Mapped[int] = mapped_column(Integer, nullable=False)
    measure_number_in_staff: Mapped[int] = mapped_column(Integer, nullable=False)
    global_measure_number: Mapped[int] = mapped_column(Integer, nullable=False)
    x_start: Mapped[int] = mapped_column(Integer, nullable=False)
    x_end: Mapped[int] = mapped_column(Integer, nullable=False)
```

- [ ] **Step 2: Register model in `__init__.py`**

In `src/backend/mv_hofki/models/__init__.py`, add the import (follow existing pattern):

```python
from mv_hofki.models.detected_measure import DetectedMeasure
```

- [ ] **Step 3: Create the Pydantic schema**

Create `src/backend/mv_hofki/schemas/detected_measure.py`:

```python
"""DetectedMeasure Pydantic schemas."""

from __future__ import annotations

from pydantic import BaseModel


class DetectedMeasureRead(BaseModel):
    id: int
    scan_id: int
    staff_id: int
    staff_index: int
    measure_number_in_staff: int
    global_measure_number: int
    x_start: int
    x_end: int

    model_config = {"from_attributes": True}
```

- [ ] **Step 4: Generate and write migration**

```bash
cd /workspaces/mv_hofki
PYTHONPATH=src/backend alembic revision -m "add_detected_measures_table"
```

In the generated file:

```python
"""add detected_measures table"""

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.create_table(
        "detected_measures",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("scan_id", sa.Integer(), sa.ForeignKey("sheet_music_scans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("staff_id", sa.Integer(), sa.ForeignKey("detected_staves.id", ondelete="CASCADE"), nullable=False),
        sa.Column("staff_index", sa.Integer(), nullable=False),
        sa.Column("measure_number_in_staff", sa.Integer(), nullable=False),
        sa.Column("global_measure_number", sa.Integer(), nullable=False),
        sa.Column("x_start", sa.Integer(), nullable=False),
        sa.Column("x_end", sa.Integer(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("detected_measures")
```

Run:
```bash
PYTHONPATH=src/backend alembic upgrade head
```

- [ ] **Step 5: Add API endpoint**

In `src/backend/mv_hofki/api/routes/scan_processing.py`, add after the existing `/scans/{scan_id}/staves` endpoint:

```python
@router.get("/scans/{scan_id}/measures", response_model=list[DetectedMeasureRead])
async def get_detected_measures(scan_id: int, db: AsyncSession = Depends(get_db)):
    """Get all detected measures for a scan."""
    from sqlalchemy import select

    from mv_hofki.models.detected_measure import DetectedMeasure
    from mv_hofki.models.sheet_music_scan import SheetMusicScan

    scan = await db.get(SheetMusicScan, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan nicht gefunden")

    result = await db.execute(
        select(DetectedMeasure)
        .where(DetectedMeasure.scan_id == scan_id)
        .order_by(DetectedMeasure.global_measure_number)
    )
    return list(result.scalars().all())
```

Add the schema import at the top of the file:

```python
from mv_hofki.schemas.detected_measure import DetectedMeasureRead
```

- [ ] **Step 6: Run tests and linter**

```bash
python -m pytest tests/backend/ -v -k "scan" --tb=short
pre-commit run --all-files
```

- [ ] **Step 7: Commit**

```bash
git add src/backend/mv_hofki/models/detected_measure.py src/backend/mv_hofki/models/__init__.py src/backend/mv_hofki/schemas/detected_measure.py src/backend/mv_hofki/api/routes/scan_processing.py alembic/versions/*add_detected_measures*
git commit -m "feat: add DetectedMeasure model, schema, migration, and API endpoint"
```

---

### Task 4: Wire MeasureDetectionStage into pipeline and persist results

**Files:**
- Modify: `src/backend/mv_hofki/services/sheet_music_scan.py`

- [ ] **Step 1: Add template_categories to metadata and add stage**

In `src/backend/mv_hofki/services/sheet_music_scan.py`, find where `template_display_names` is built (around line 208-210). Add after it:

```python
    template_categories = {t.id: t.category for t in all_templates}
```

Find where `PostMatchingStage()` is appended (around line 250). Add after it:

```python
    from mv_hofki.services.scanner.stages.measure_detection import MeasureDetectionStage

    stages.append(MeasureDetectionStage())
```

Find where the `PipelineContext` is created (around line 258). The metadata dict needs the categories. Add after the context creation:

```python
    ctx.metadata["template_categories"] = template_categories
```

Note: `template_display_names` is already passed via `TemplateMatchingStage` constructor and set in metadata. Check if it's set on `ctx.metadata` — if not, the `template_categories` must also be set. Look for where `template_display_names` is placed on ctx.metadata and add `template_categories` alongside it.

- [ ] **Step 2: Persist measures after pipeline run**

In the persistence section (after the staves/symbols loop, around line 335), add before `scan.status = "review"`:

```python
    # Clear previous measures and persist new ones
    from mv_hofki.models.detected_measure import DetectedMeasure

    await session.execute(
        sa_delete(DetectedMeasure).where(DetectedMeasure.scan_id == scan_id)
    )

    # Build staff_index → staff.id lookup from just-persisted staves
    staff_id_map: dict[int, int] = {}
    from sqlalchemy import select as sa_sel
    result = await session.execute(
        sa_sel(DetectedStaff).where(DetectedStaff.scan_id == scan_id)
    )
    for s in result.scalars().all():
        staff_id_map[s.staff_index] = s.id

    for m in ctx.measures:
        measure = DetectedMeasure(
            scan_id=scan_id,
            staff_id=staff_id_map.get(m.staff_index, 0),
            staff_index=m.staff_index,
            measure_number_in_staff=m.measure_number_in_staff,
            global_measure_number=m.global_measure_number,
            x_start=m.x_start,
            x_end=m.x_end,
        )
        session.add(measure)
```

- [ ] **Step 3: Run tests**

```bash
python -m pytest tests/backend/ -v -k "scan" --tb=short
```

- [ ] **Step 4: Commit**

```bash
git add src/backend/mv_hofki/services/sheet_music_scan.py
git commit -m "feat: wire MeasureDetectionStage into pipeline and persist measures"
```

---

### Task 5: Frontend — Load measures and render overlay

**Files:**
- Modify: `src/frontend/src/pages/ScanEditorPage.vue`
- Modify: `src/frontend/src/components/ScanCanvas.vue`
- Modify: `src/frontend/src/components/FilterDropdown.vue`

- [ ] **Step 1: Add measures state and loading in ScanEditorPage**

In `src/frontend/src/pages/ScanEditorPage.vue`:

Add ref (near other refs around line 35):
```js
const measures = ref([]);
const showMeasures = ref(true);
```

In `fetchScanData()`, find where staves and symbols are loaded (around line 74-78). Add measures:
```js
    const [, stavesData, symbolsData, measuresData] = await Promise.all([
      get(`/scanner/scans/${props.scanId}/status`).catch(() => null),
      get(`/scanner/scans/${props.scanId}/staves`),
      get(`/scanner/scans/${props.scanId}/symbols`),
      get(`/scanner/scans/${props.scanId}/measures`).catch(() => []),
    ]);
```

Set the data (after `symbols.value`):
```js
    measures.value = measuresData || [];
```

In `onAnalysisDone()`, add measures loading alongside staves/symbols (find the existing `Promise.all`):
```js
      const [, stavesData, symbolsData, measuresData] = await Promise.all([
        get(`/scanner/scans/${props.scanId}/status`).catch(() => null),
        get(`/scanner/scans/${props.scanId}/staves`),
        get(`/scanner/scans/${props.scanId}/symbols`),
        get(`/scanner/scans/${props.scanId}/measures`).catch(() => []),
      ]);
```

And set:
```js
    measures.value = measuresData || [];
```

- [ ] **Step 2: Pass measures to ScanCanvas**

Find the `<ScanCanvas` tag and add:
```html
            :measures="measures"
            :show-measures="showMeasures"
```

- [ ] **Step 3: Add showMeasures to FilterDropdown**

In the `<FilterDropdown` tag, add:
```html
              :show-measures="showMeasures"
              @update:show-measures="showMeasures = $event"
```

In `src/frontend/src/components/FilterDropdown.vue`:

Add to props:
```js
  showMeasures: { type: Boolean, default: true },
```

Add to emits:
```js
"update:showMeasures"
```

In the template, find the "Systeme anzeigen" checkbox and add after it:
```html
          <label class="filter-check">
            <input
              type="checkbox"
              :checked="showMeasures"
              @change="emit('update:showMeasures', $event.target.checked)"
            />
            Takte anzeigen
          </label>
```

- [ ] **Step 4: Add measure overlay rendering to ScanCanvas**

In `src/frontend/src/components/ScanCanvas.vue`:

Add props:
```js
  measures: { type: Array, default: () => [] },
  showMeasures: { type: Boolean, default: true },
```

In the SVG template, add after the stave overlay block (after `</template>` that closes the staves `v-if`, around line 421) and before the symbol bounding boxes:

```html
        <!-- Measure boundaries -->
        <template v-if="showMeasures">
          <g v-for="measure in measures" :key="`m-${measure.id}`">
            <line
              :x1="measure.x_start"
              :y1="staffBounds(measure.staff_index)?.y_top - 10"
              :x2="measure.x_start"
              :y2="staffBounds(measure.staff_index)?.y_bottom + 10"
              stroke="#06b6d4"
              stroke-width="1.5"
              stroke-dasharray="4 3"
              opacity="0.6"
            />
            <text
              :x="measure.x_start + 4"
              :y="(staffBounds(measure.staff_index)?.y_top ?? 0) - 14"
              fill="#06b6d4"
              font-size="12"
              font-weight="600"
              opacity="0.8"
            >
              {{ measure.global_measure_number }}
            </text>
          </g>
        </template>
```

Add the helper function in `<script setup>`:

```js
function staffBounds(staffIndex) {
  return props.staves.find((s) => s.staff_index === staffIndex) ?? null;
}
```

- [ ] **Step 5: Verify build**

```bash
cd /workspaces/mv_hofki/src/frontend && npx vite build
```

- [ ] **Step 6: Commit**

```bash
cd /workspaces/mv_hofki
git add src/frontend/src/pages/ScanEditorPage.vue src/frontend/src/components/ScanCanvas.vue src/frontend/src/components/FilterDropdown.vue
git commit -m "feat: load and render measure overlay with toggle in scan editor"
```

---

### Task 6: Full verification

- [ ] **Step 1: Run all backend tests**

```bash
python -m pytest tests/backend/ -v --tb=short
```

Expected: all pass (except pre-existing `test_create_invoice_on_sheet_music_rejected`).

- [ ] **Step 2: Run pre-commit**

```bash
pre-commit run --all-files
```

- [ ] **Step 3: Manual E2E test**

1. Run analysis on a scan with visible barlines
2. Check API: `curl http://localhost:8000/api/v1/scanner/scans/{id}/measures | python -m json.tool`
3. Verify measure boundaries make sense (x_start/x_end align with barline positions)
4. Verify global_measure_number is continuous across systems
5. In the UI: vertical cyan dashed lines at measure boundaries with numbers
6. Toggle "Takte anzeigen" in FilterDropdown — overlay appears/disappears
