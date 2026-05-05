# Symbol Position Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Store symbol hitbox positions relative to the staff (Y in line-spacing units from bottom line, X in absolute pixels) and display them in the UI.

**Architecture:** Replace `position_on_staff` with 4 new fields on SymbolData/DetectedSymbol. Compute staff-relative Y in template matching stage where staff line positions are available. Display in SymbolPanel.

**Tech Stack:** SQLAlchemy/Alembic, OpenCV, Vue 3

---

### Task 1: Alembic migration — replace `position_on_staff` with new fields

**Files:**
- Create: `alembic/versions/XXXX_replace_position_on_staff_with_staff_coords.py`

- [ ] **Step 1: Generate migration**

```bash
cd /workspaces/mv_hofki
PYTHONPATH=src/backend alembic revision -m "replace_position_on_staff_with_staff_coords"
```

- [ ] **Step 2: Write the migration**

In the generated file, replace `upgrade()` and `downgrade()`:

```python
"""replace position_on_staff with staff coordinate fields"""

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    with op.batch_alter_table("detected_symbols") as batch_op:
        batch_op.drop_column("position_on_staff")
        batch_op.add_column(sa.Column("staff_y_top", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("staff_y_bottom", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("staff_x_start", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("staff_x_end", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("detected_symbols") as batch_op:
        batch_op.drop_column("staff_x_end")
        batch_op.drop_column("staff_x_start")
        batch_op.drop_column("staff_y_bottom")
        batch_op.drop_column("staff_y_top")
        batch_op.add_column(sa.Column("position_on_staff", sa.Integer(), nullable=True))
```

- [ ] **Step 3: Run migration**

```bash
PYTHONPATH=src/backend alembic upgrade head
```

- [ ] **Step 4: Commit**

```bash
git add alembic/versions/*replace_position_on_staff*
git commit -m "migrate: replace position_on_staff with staff_y_top/bottom staff_x_start/end"
```

---

### Task 2: Update SymbolData dataclass and DetectedSymbol model/schema

**Files:**
- Modify: `src/backend/mv_hofki/services/scanner/stages/base.py:28-44`
- Modify: `src/backend/mv_hofki/models/detected_symbol.py:29`
- Modify: `src/backend/mv_hofki/schemas/detected_symbol.py:24`

- [ ] **Step 1: Update SymbolData dataclass**

In `src/backend/mv_hofki/services/scanner/stages/base.py`, replace the `SymbolData` class (lines 28-44):

```python
@dataclass
class SymbolData:
    """Data for a single detected symbol."""

    staff_index: int
    x: int
    y: int
    width: int
    height: int
    snippet: np.ndarray | None = None
    staff_y_top: float | None = None
    staff_y_bottom: float | None = None
    staff_x_start: int | None = None
    staff_x_end: int | None = None
    sequence_order: int = 0
    matched_template_id: int | None = None
    confidence: float | None = None
    alternatives: list[tuple[int, float]] = field(default_factory=list)
    filtered: bool = False
    filter_reason: str | None = None
```

- [ ] **Step 2: Update DetectedSymbol ORM model**

In `src/backend/mv_hofki/models/detected_symbol.py`, replace line 29:

```python
    position_on_staff: Mapped[int | None] = mapped_column(Integer)
```

With:

```python
    staff_y_top: Mapped[float | None] = mapped_column(Float)
    staff_y_bottom: Mapped[float | None] = mapped_column(Float)
    staff_x_start: Mapped[int | None] = mapped_column(Integer)
    staff_x_end: Mapped[int | None] = mapped_column(Integer)
```

- [ ] **Step 3: Update DetectedSymbolRead schema**

In `src/backend/mv_hofki/schemas/detected_symbol.py`, replace line 24:

```python
    position_on_staff: int | None
```

With:

```python
    staff_y_top: float | None
    staff_y_bottom: float | None
    staff_x_start: int | None
    staff_x_end: int | None
```

- [ ] **Step 4: Run linter**

```bash
pre-commit run --all-files
```

- [ ] **Step 5: Commit**

```bash
git add src/backend/mv_hofki/services/scanner/stages/base.py src/backend/mv_hofki/models/detected_symbol.py src/backend/mv_hofki/schemas/detected_symbol.py
git commit -m "feat: replace position_on_staff with staff coordinate fields in model/schema/dataclass"
```

---

### Task 3: Compute staff-relative positions in template matching

**Files:**
- Modify: `src/backend/mv_hofki/services/scanner/stages/template_matching.py:211-225,236-239`
- Create: `tests/backend/test_staff_position.py`

- [ ] **Step 1: Write the test**

Create `tests/backend/test_staff_position.py`:

```python
"""Tests for staff-relative position computation in template matching."""

from mv_hofki.services.scanner.stages.base import StaffData, SymbolData


def _compute_staff_coords(sym: SymbolData, staff: StaffData) -> SymbolData:
    """Mirror the computation from template matching for testability."""
    bottom_line_y = max(staff.line_positions)
    sym.staff_y_top = round((bottom_line_y - sym.y) / staff.line_spacing, 2)
    sym.staff_y_bottom = round(
        (bottom_line_y - (sym.y + sym.height)) / staff.line_spacing, 2
    )
    sym.staff_x_start = sym.x
    sym.staff_x_end = sym.x + sym.width
    return sym


def test_symbol_on_bottom_line():
    """Symbol whose top edge sits on the bottom staff line."""
    staff = StaffData(
        staff_index=0,
        y_top=100,
        y_bottom=180,
        line_positions=[100, 120, 140, 160, 180],
        line_spacing=20.0,
    )
    sym = SymbolData(staff_index=0, x=50, y=180, width=30, height=40)
    result = _compute_staff_coords(sym, staff)
    assert result.staff_y_top == 0.0
    assert result.staff_y_bottom == -2.0
    assert result.staff_x_start == 50
    assert result.staff_x_end == 80


def test_symbol_one_line_above_bottom():
    """Symbol whose top edge is one line-spacing above the bottom line."""
    staff = StaffData(
        staff_index=0,
        y_top=100,
        y_bottom=180,
        line_positions=[100, 120, 140, 160, 180],
        line_spacing=20.0,
    )
    sym = SymbolData(staff_index=0, x=100, y=160, width=20, height=30)
    result = _compute_staff_coords(sym, staff)
    assert result.staff_y_top == 1.0
    assert result.staff_y_bottom == -0.5
    assert result.staff_x_start == 100
    assert result.staff_x_end == 120


def test_symbol_between_lines():
    """Symbol whose top edge is between two lines (half step)."""
    staff = StaffData(
        staff_index=0,
        y_top=100,
        y_bottom=180,
        line_positions=[100, 120, 140, 160, 180],
        line_spacing=20.0,
    )
    sym = SymbolData(staff_index=0, x=200, y=170, width=15, height=25)
    result = _compute_staff_coords(sym, staff)
    assert result.staff_y_top == 0.5
    assert result.staff_y_bottom == -0.75
    assert result.staff_x_start == 200
    assert result.staff_x_end == 215


def test_symbol_above_top_line():
    """Symbol above the top line gets positive staff_y > 4."""
    staff = StaffData(
        staff_index=0,
        y_top=100,
        y_bottom=180,
        line_positions=[100, 120, 140, 160, 180],
        line_spacing=20.0,
    )
    sym = SymbolData(staff_index=0, x=10, y=80, width=20, height=30)
    result = _compute_staff_coords(sym, staff)
    assert result.staff_y_top == 5.0
    assert result.staff_y_bottom == 3.5
```

- [ ] **Step 2: Run tests — expect PASS (pure data computation)**

```bash
python -m pytest tests/backend/test_staff_position.py -v
```

Expected: all 4 tests PASS.

- [ ] **Step 3: Add position computation to template matching**

In `src/backend/mv_hofki/services/scanner/stages/template_matching.py`, find the block where SymbolData is created (lines 214-225). Replace:

```python
                    for pt_y, pt_x in zip(locations[0], locations[1]):
                        score = float(result[pt_y, pt_x])
                        confidence = (1.0 - score) if iter_sqdiff else score
                        raw_detections.append(
                            SymbolData(
                                staff_index=staff.staff_index,
                                x=int(pt_x),
                                y=int(staff.y_top + pt_y),
                                width=int(scaled.shape[1]),
                                height=int(scaled.shape[0]),
                                position_on_staff=None,
                                matched_template_id=template_id,
                                confidence=confidence,
                            )
                        )
```

With:

```python
                    bottom_line_y = max(staff.line_positions)
                    for pt_y, pt_x in zip(locations[0], locations[1]):
                        score = float(result[pt_y, pt_x])
                        confidence = (1.0 - score) if iter_sqdiff else score
                        abs_y = int(staff.y_top + pt_y)
                        sym_h = int(scaled.shape[0])
                        sym_w = int(scaled.shape[1])
                        sym_x = int(pt_x)
                        raw_detections.append(
                            SymbolData(
                                staff_index=staff.staff_index,
                                x=sym_x,
                                y=abs_y,
                                width=sym_w,
                                height=sym_h,
                                staff_y_top=round(
                                    (bottom_line_y - abs_y) / staff.line_spacing, 2
                                ),
                                staff_y_bottom=round(
                                    (bottom_line_y - (abs_y + sym_h))
                                    / staff.line_spacing,
                                    2,
                                ),
                                staff_x_start=sym_x,
                                staff_x_end=sym_x + sym_w,
                                matched_template_id=template_id,
                                confidence=confidence,
                            )
                        )
```

- [ ] **Step 4: Run existing template matching tests**

```bash
python -m pytest tests/backend/ -v -k "template_matching" --tb=short
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/backend/mv_hofki/services/scanner/stages/template_matching.py tests/backend/test_staff_position.py
git commit -m "feat: compute staff-relative Y position in template matching"
```

---

### Task 4: Update persistence in run_pipeline

**Files:**
- Modify: `src/backend/mv_hofki/services/sheet_music_scan.py:315-324`

- [ ] **Step 1: Update the symbol creation in run_pipeline**

In `src/backend/mv_hofki/services/sheet_music_scan.py`, find the `DetectedSymbol(` creation block (around line 315). Replace:

```python
            symbol = DetectedSymbol(
                staff_id=staff.id,
                x=sym_data.x,
                y=sym_data.y,
                width=sym_data.width,
                height=sym_data.height,
                snippet_path=snippet_path,
                position_on_staff=sym_data.position_on_staff,
                sequence_order=sym_data.sequence_order,
                matched_symbol_id=sym_data.matched_template_id,
```

With:

```python
            symbol = DetectedSymbol(
                staff_id=staff.id,
                x=sym_data.x,
                y=sym_data.y,
                width=sym_data.width,
                height=sym_data.height,
                snippet_path=snippet_path,
                staff_y_top=sym_data.staff_y_top,
                staff_y_bottom=sym_data.staff_y_bottom,
                staff_x_start=sym_data.staff_x_start,
                staff_x_end=sym_data.staff_x_end,
                sequence_order=sym_data.sequence_order,
                matched_symbol_id=sym_data.matched_template_id,
```

- [ ] **Step 2: Run scan tests**

```bash
python -m pytest tests/backend/ -v -k "scan" --tb=short
```

Expected: all pass.

- [ ] **Step 3: Commit**

```bash
git add src/backend/mv_hofki/services/sheet_music_scan.py
git commit -m "feat: persist staff coordinate fields in run_pipeline"
```

---

### Task 5: Display position in SymbolPanel

**Files:**
- Modify: `src/frontend/src/components/SymbolPanel.vue:58-78`

- [ ] **Step 1: Add position info rows to the template**

In `src/frontend/src/components/SymbolPanel.vue`, find the `<!-- Match info -->` block (line 58). Add the position rows after the existing `info-row` elements (after the "Verifiziert" row, before the "Korrigiert zu" row, around line 73):

```html
        <div v-if="symbol.staff_x_start != null" class="info-row">
          <span class="info-label">X</span>
          <span class="info-value">{{ symbol.staff_x_start }} – {{ symbol.staff_x_end }} px</span>
        </div>
        <div v-if="symbol.staff_y_top != null" class="info-row">
          <span class="info-label">Y (Staff)</span>
          <span class="info-value">
            {{ symbol.staff_y_top.toFixed(1) }} – {{ symbol.staff_y_bottom.toFixed(1) }} Linien
          </span>
        </div>
```

- [ ] **Step 2: Verify build**

```bash
cd /workspaces/mv_hofki/src/frontend && npx vite build
```

Expected: builds without errors.

- [ ] **Step 3: Commit**

```bash
cd /workspaces/mv_hofki
git add src/frontend/src/components/SymbolPanel.vue
git commit -m "feat: display staff-relative position in SymbolPanel"
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

Expected: all pass (except pre-existing mypy pypdf issue).

- [ ] **Step 3: Manual verification**

Run an analysis on a scan and verify:
1. API response for symbols contains `staff_y_top`, `staff_y_bottom`, `staff_x_start`, `staff_x_end`
2. SymbolPanel shows "X: ... px" and "Y (Staff): ... Linien"
3. Values make sense: symbols on the bottom line have `staff_y_top` near 0, symbols higher have larger values
