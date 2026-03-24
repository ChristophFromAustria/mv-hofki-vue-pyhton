# Notenscanner (Sheet Music Digitization) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a sheet music digitization feature that scans degraded printed music, detects musical symbols via a growing reference library, and exports to MusicXML.

**Architecture:** Hybrid — Python backend (OpenCV) handles image processing, stave detection, symbol segmentation, and library-based matching via a modular pipeline. Vue 3 frontend provides upload, image adjustment, interactive review/correction, and export. New database tables for projects, parts, scans, detected staves/symbols, and a two-level symbol library (template → variants).

**Tech Stack:** FastAPI, OpenCV (opencv-python-headless), NumPy, SQLAlchemy 2.0 async, Alembic, Vue 3 Composition API, Canvas API

**Spec:** `docs/superpowers/specs/2026-03-24-notenscanner-design.md`

---

## File Structure

| Action | File | Purpose |
|--------|------|---------|
| Modify | `pyproject.toml` | Add `opencv-python-headless`, `numpy` dependencies |
| Create | `src/backend/mv_hofki/models/scan_project.py` | ScanProject ORM model |
| Create | `src/backend/mv_hofki/models/scan_part.py` | ScanPart ORM model |
| Create | `src/backend/mv_hofki/models/sheet_music_scan.py` | SheetMusicScan ORM model |
| Create | `src/backend/mv_hofki/models/detected_staff.py` | DetectedStaff ORM model |
| Create | `src/backend/mv_hofki/models/detected_symbol.py` | DetectedSymbol ORM model |
| Create | `src/backend/mv_hofki/models/symbol_template.py` | SymbolTemplate ORM model |
| Create | `src/backend/mv_hofki/models/symbol_variant.py` | SymbolVariant ORM model |
| Modify | `src/backend/mv_hofki/models/__init__.py` | Register new models |
| Create | `src/backend/mv_hofki/schemas/scan_project.py` | ScanProject Pydantic schemas |
| Create | `src/backend/mv_hofki/schemas/scan_part.py` | ScanPart Pydantic schemas |
| Create | `src/backend/mv_hofki/schemas/sheet_music_scan.py` | SheetMusicScan Pydantic schemas |
| Create | `src/backend/mv_hofki/schemas/detected_staff.py` | DetectedStaff Pydantic schemas |
| Create | `src/backend/mv_hofki/schemas/detected_symbol.py` | DetectedSymbol Pydantic schemas |
| Create | `src/backend/mv_hofki/schemas/symbol_template.py` | SymbolTemplate Pydantic schemas |
| Create | `src/backend/mv_hofki/schemas/symbol_variant.py` | SymbolVariant Pydantic schemas |
| Create | `src/backend/mv_hofki/services/scan_project.py` | ScanProject CRUD service |
| Create | `src/backend/mv_hofki/services/scan_part.py` | ScanPart CRUD service |
| Create | `src/backend/mv_hofki/services/sheet_music_scan.py` | SheetMusicScan CRUD + upload service |
| Create | `src/backend/mv_hofki/services/symbol_library.py` | SymbolTemplate/Variant CRUD + feedback service |
| Create | `src/backend/mv_hofki/services/scanner/__init__.py` | Scanner package init |
| Create | `src/backend/mv_hofki/services/scanner/pipeline.py` | Pipeline runner, stage orchestration |
| Create | `src/backend/mv_hofki/services/scanner/stages/__init__.py` | Stages package init |
| Create | `src/backend/mv_hofki/services/scanner/stages/base.py` | ProcessingStage ABC |
| Create | `src/backend/mv_hofki/services/scanner/stages/preprocess.py` | Binarization, deskew, denoise |
| Create | `src/backend/mv_hofki/services/scanner/stages/stave_detection.py` | Find staff line groups |
| Create | `src/backend/mv_hofki/services/scanner/stages/staff_removal.py` | Optional staff line removal |
| Create | `src/backend/mv_hofki/services/scanner/stages/segmentation.py` | Symbol bounding box detection |
| Create | `src/backend/mv_hofki/services/scanner/stages/matching.py` | Symbol library matching |
| Create | `src/backend/mv_hofki/services/scanner/export/__init__.py` | Export package init |
| Create | `src/backend/mv_hofki/services/scanner/export/musicxml.py` | MusicXML generation |
| Create | `src/backend/mv_hofki/services/scanner/library/__init__.py` | Library package init |
| Create | `src/backend/mv_hofki/services/scanner/library/seed.py` | Pre-seed symbol templates + variant images |
| Create | `src/backend/mv_hofki/api/routes/scan_projects.py` | ScanProject API routes |
| Create | `src/backend/mv_hofki/api/routes/scan_parts.py` | ScanPart API routes |
| Create | `src/backend/mv_hofki/api/routes/scans.py` | SheetMusicScan API routes (upload, status) |
| Create | `src/backend/mv_hofki/api/routes/scan_processing.py` | Pipeline trigger/status routes |
| Create | `src/backend/mv_hofki/api/routes/symbol_library.py` | Symbol library browse/manage routes |
| Modify | `src/backend/mv_hofki/api/app.py` | Register scanner routers, mount scan uploads dir |
| Modify | `src/backend/mv_hofki/db/seed.py` | Add symbol template seeding |
| Create | `tests/backend/test_scan_projects.py` | ScanProject CRUD tests |
| Create | `tests/backend/test_scan_parts.py` | ScanPart CRUD tests |
| Create | `tests/backend/test_scans.py` | SheetMusicScan upload + CRUD tests |
| Create | `tests/backend/test_symbol_library.py` | Symbol library tests |
| Create | `tests/backend/test_pipeline_stages.py` | Pipeline stage unit tests |
| Create | `tests/backend/test_musicxml_export.py` | MusicXML generation tests |
| Create | `tests/backend/fixtures/` | Test fixture images (clean + degraded samples) |
| Create | `src/frontend/src/pages/ScanProjectListPage.vue` | Project list page |
| Create | `src/frontend/src/pages/ScanProjectDetailPage.vue` | Project detail with parts/scans |
| Create | `src/frontend/src/pages/ScanEditorPage.vue` | Main scan editor workspace |
| Create | `src/frontend/src/pages/SymbolLibraryPage.vue` | Symbol library browser |
| Create | `src/frontend/src/components/ScanCanvas.vue` | Image display with detection overlays |
| Create | `src/frontend/src/components/SymbolPanel.vue` | Symbol detail + correction UI |
| Create | `src/frontend/src/components/ImageAdjustBar.vue` | Brightness/contrast/rotation controls |
| Create | `src/frontend/src/components/SymbolCard.vue` | Symbol template card for library |
| Modify | `src/frontend/src/router.js` | Add notenscanner routes |
| Modify | `src/frontend/src/components/NavBar.vue` | Add "Notenscanner" menu entry |

---

### Task 1: Add Python dependencies (OpenCV, NumPy)

**Files:**
- Modify: `pyproject.toml:6-15`

- [ ] **Step 1: Add opencv-python-headless and numpy to dependencies**

In `pyproject.toml`, add to the `dependencies` list:

```toml
dependencies = [
    "fastapi>=0.115,<1",
    "uvicorn[standard]>=0.34,<1",
    "pydantic-settings>=2.0,<3",
    "sqlalchemy[asyncio]>=2.0,<3",
    "aiosqlite>=0.20,<1",
    "alembic>=1.13,<2",
    "python-multipart>=0.0.9,<1",
    "httpx>=0.27,<1",
    "opencv-python-headless>=4.9,<5",
    "numpy>=1.26,<3",
]
```

- [ ] **Step 2: Install dependencies**

Run: `cd /workspaces/mv_hofki && pip install -e ".[dev]"`
Expected: Successfully installed opencv-python-headless and numpy

- [ ] **Step 3: Verify imports work**

Run: `python -c "import cv2; import numpy; print(f'OpenCV {cv2.__version__}, NumPy {numpy.__version__}')"`
Expected: Prints version numbers without errors

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "feat(scanner): add opencv-python-headless and numpy dependencies"
```

---

### Task 2: Create scanner database models

**Files:**
- Create: `src/backend/mv_hofki/models/scan_project.py`
- Create: `src/backend/mv_hofki/models/scan_part.py`
- Create: `src/backend/mv_hofki/models/sheet_music_scan.py`
- Create: `src/backend/mv_hofki/models/detected_staff.py`
- Create: `src/backend/mv_hofki/models/detected_symbol.py`
- Create: `src/backend/mv_hofki/models/symbol_template.py`
- Create: `src/backend/mv_hofki/models/symbol_variant.py`
- Modify: `src/backend/mv_hofki/models/__init__.py`

- [ ] **Step 1: Create ScanProject model**

Create `src/backend/mv_hofki/models/scan_project.py`:

```python
"""ScanProject ORM model."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mv_hofki.db.base import Base


class ScanProject(Base):
    __tablename__ = "scan_projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    composer: Mapped[str | None] = mapped_column(String(200))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )

    parts: Mapped[list["ScanPart"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", lazy="selectin"
    )
```

- [ ] **Step 2: Create ScanPart model**

Create `src/backend/mv_hofki/models/scan_part.py`:

```python
"""ScanPart ORM model."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mv_hofki.db.base import Base


class ScanPart(Base):
    __tablename__ = "scan_parts"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("scan_projects.id", ondelete="CASCADE"), nullable=False
    )
    part_name: Mapped[str] = mapped_column(String(200), nullable=False)
    part_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    clef_hint: Mapped[str | None] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    project: Mapped["ScanProject"] = relationship(back_populates="parts")
    scans: Mapped[list["SheetMusicScan"]] = relationship(
        back_populates="part", cascade="all, delete-orphan", lazy="selectin"
    )
```

- [ ] **Step 3: Create SheetMusicScan model**

Create `src/backend/mv_hofki/models/sheet_music_scan.py`:

```python
"""SheetMusicScan ORM model."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mv_hofki.db.base import Base


class SheetMusicScan(Base):
    __tablename__ = "sheet_music_scans"

    id: Mapped[int] = mapped_column(primary_key=True)
    part_id: Mapped[int] = mapped_column(
        ForeignKey("scan_parts.id", ondelete="CASCADE"), nullable=False
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    image_path: Mapped[str] = mapped_column(String(500), nullable=False)
    processed_image_path: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="uploaded"
    )
    adjustments_json: Mapped[str | None] = mapped_column(Text)
    pipeline_config_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )

    part: Mapped["ScanPart"] = relationship(back_populates="scans")
    staves: Mapped[list["DetectedStaff"]] = relationship(
        back_populates="scan", cascade="all, delete-orphan", lazy="selectin"
    )
```

- [ ] **Step 4: Create DetectedStaff model**

Create `src/backend/mv_hofki/models/detected_staff.py`:

```python
"""DetectedStaff ORM model."""

from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mv_hofki.db.base import Base


class DetectedStaff(Base):
    __tablename__ = "detected_staves"

    id: Mapped[int] = mapped_column(primary_key=True)
    scan_id: Mapped[int] = mapped_column(
        ForeignKey("sheet_music_scans.id", ondelete="CASCADE"), nullable=False
    )
    staff_index: Mapped[int] = mapped_column(Integer, nullable=False)
    y_top: Mapped[int] = mapped_column(Integer, nullable=False)
    y_bottom: Mapped[int] = mapped_column(Integer, nullable=False)
    line_positions_json: Mapped[str] = mapped_column(Text, nullable=False)
    line_spacing: Mapped[float] = mapped_column(Float, nullable=False)
    clef: Mapped[str | None] = mapped_column(String(20))
    key_signature: Mapped[str | None] = mapped_column(String(50))
    time_signature: Mapped[str | None] = mapped_column(String(20))

    scan: Mapped["SheetMusicScan"] = relationship(back_populates="staves")
    symbols: Mapped[list["DetectedSymbol"]] = relationship(
        back_populates="staff", cascade="all, delete-orphan", lazy="selectin"
    )
```

- [ ] **Step 5: Create DetectedSymbol model**

Create `src/backend/mv_hofki/models/detected_symbol.py`:

```python
"""DetectedSymbol ORM model."""

from __future__ import annotations

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mv_hofki.db.base import Base


class DetectedSymbol(Base):
    __tablename__ = "detected_symbols"

    id: Mapped[int] = mapped_column(primary_key=True)
    staff_id: Mapped[int] = mapped_column(
        ForeignKey("detected_staves.id", ondelete="CASCADE"), nullable=False
    )
    x: Mapped[int] = mapped_column(Integer, nullable=False)
    y: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    snippet_path: Mapped[str | None] = mapped_column(String(500))
    position_on_staff: Mapped[int | None] = mapped_column(Integer)
    sequence_order: Mapped[int] = mapped_column(Integer, nullable=False)
    matched_symbol_id: Mapped[int | None] = mapped_column(
        ForeignKey("symbol_templates.id", ondelete="SET NULL")
    )
    confidence: Mapped[float | None] = mapped_column(Float)
    user_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    user_corrected_symbol_id: Mapped[int | None] = mapped_column(
        ForeignKey("symbol_templates.id", ondelete="SET NULL")
    )

    staff: Mapped["DetectedStaff"] = relationship(back_populates="symbols")
    matched_symbol: Mapped["SymbolTemplate | None"] = relationship(
        foreign_keys=[matched_symbol_id], lazy="joined"
    )
    corrected_symbol: Mapped["SymbolTemplate | None"] = relationship(
        foreign_keys=[user_corrected_symbol_id], lazy="joined"
    )
```

- [ ] **Step 6: Create SymbolTemplate model**

Create `src/backend/mv_hofki/models/symbol_template.py`:

```python
"""SymbolTemplate ORM model."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mv_hofki.db.base import Base


class SymbolTemplate(Base):
    __tablename__ = "symbol_templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    musicxml_element: Mapped[str | None] = mapped_column(Text)
    lilypond_token: Mapped[str | None] = mapped_column(String(50))
    is_seed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    variants: Mapped[list["SymbolVariant"]] = relationship(
        back_populates="template", cascade="all, delete-orphan", lazy="selectin"
    )
```

- [ ] **Step 7: Create SymbolVariant model**

Create `src/backend/mv_hofki/models/symbol_variant.py`:

```python
"""SymbolVariant ORM model."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mv_hofki.db.base import Base


class SymbolVariant(Base):
    __tablename__ = "symbol_variants"

    id: Mapped[int] = mapped_column(primary_key=True)
    template_id: Mapped[int] = mapped_column(
        ForeignKey("symbol_templates.id", ondelete="CASCADE"), nullable=False
    )
    image_path: Mapped[str] = mapped_column(String(500), nullable=False)
    source: Mapped[str] = mapped_column(String(30), nullable=False, default="seed")
    feature_vector_json: Mapped[str | None] = mapped_column(Text)
    usage_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    template: Mapped["SymbolTemplate"] = relationship(back_populates="variants")
```

- [ ] **Step 8: Register all new models in `__init__.py`**

Modify `src/backend/mv_hofki/models/__init__.py` to add imports and `__all__` entries for all 7 new models:

```python
"""ORM models."""

from mv_hofki.models.clothing_detail import ClothingDetail
from mv_hofki.models.clothing_type import ClothingType
from mv_hofki.models.currency import Currency
from mv_hofki.models.detected_staff import DetectedStaff
from mv_hofki.models.detected_symbol import DetectedSymbol
from mv_hofki.models.instrument_detail import InstrumentDetail
from mv_hofki.models.instrument_type import InstrumentType
from mv_hofki.models.inventory_item import InventoryItem
from mv_hofki.models.item_image import ItemImage
from mv_hofki.models.item_invoice import ItemInvoice
from mv_hofki.models.loan import Loan
from mv_hofki.models.musician import Musician
from mv_hofki.models.scan_part import ScanPart
from mv_hofki.models.scan_project import ScanProject
from mv_hofki.models.sheet_music_detail import SheetMusicDetail
from mv_hofki.models.sheet_music_genre import SheetMusicGenre
from mv_hofki.models.sheet_music_scan import SheetMusicScan
from mv_hofki.models.symbol_template import SymbolTemplate
from mv_hofki.models.symbol_variant import SymbolVariant

__all__ = [
    "ClothingDetail",
    "ClothingType",
    "Currency",
    "DetectedStaff",
    "DetectedSymbol",
    "InstrumentDetail",
    "InstrumentType",
    "InventoryItem",
    "ItemImage",
    "ItemInvoice",
    "Loan",
    "Musician",
    "ScanPart",
    "ScanProject",
    "SheetMusicDetail",
    "SheetMusicGenre",
    "SheetMusicScan",
    "SymbolTemplate",
    "SymbolVariant",
]
```

- [ ] **Step 9: Create Alembic migration**

Run: `cd /workspaces/mv_hofki && PYTHONPATH=src/backend alembic revision --autogenerate -m "add scanner tables"`
Expected: New migration file created in `alembic/versions/`

- [ ] **Step 10: Run migration**

Run: `cd /workspaces/mv_hofki && PYTHONPATH=src/backend alembic upgrade head`
Expected: Migration applied successfully

- [ ] **Step 11: Run existing tests to verify no regressions**

Run: `cd /workspaces/mv_hofki && python -m pytest tests/backend/ -v --tb=short`
Expected: All existing tests pass

- [ ] **Step 12: Commit**

```bash
git add src/backend/mv_hofki/models/ alembic/versions/
git commit -m "feat(scanner): add database models for scan projects, parts, scans, staves, symbols, and symbol library"
```

---

### Task 3: Create Pydantic schemas for scanner entities

**Files:**
- Create: `src/backend/mv_hofki/schemas/scan_project.py`
- Create: `src/backend/mv_hofki/schemas/scan_part.py`
- Create: `src/backend/mv_hofki/schemas/sheet_music_scan.py`
- Create: `src/backend/mv_hofki/schemas/detected_staff.py`
- Create: `src/backend/mv_hofki/schemas/detected_symbol.py`
- Create: `src/backend/mv_hofki/schemas/symbol_template.py`
- Create: `src/backend/mv_hofki/schemas/symbol_variant.py`

- [ ] **Step 1: Create ScanProject schemas**

Create `src/backend/mv_hofki/schemas/scan_project.py`:

```python
"""ScanProject Pydantic schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, field_validator


class ScanProjectCreate(BaseModel):
    name: str
    composer: str | None = None
    notes: str | None = None

    @field_validator("name")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Darf nicht leer sein")
        return v.strip()


class ScanProjectUpdate(BaseModel):
    name: str | None = None
    composer: str | None = None
    notes: str | None = None

    @field_validator("name")
    @classmethod
    def not_empty(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("Darf nicht leer sein")
        return v.strip() if v else v


class ScanProjectRead(BaseModel):
    id: int
    name: str
    composer: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
    part_count: int = 0
    scan_count: int = 0
    completed_count: int = 0

    model_config = {"from_attributes": True}
```

- [ ] **Step 2: Create ScanPart schemas**

Create `src/backend/mv_hofki/schemas/scan_part.py`:

```python
"""ScanPart Pydantic schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, field_validator


class ScanPartCreate(BaseModel):
    part_name: str
    part_order: int = 0
    clef_hint: str | None = None

    @field_validator("part_name")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Darf nicht leer sein")
        return v.strip()

    @field_validator("clef_hint")
    @classmethod
    def valid_clef(cls, v: str | None) -> str | None:
        if v is not None and v not in ("treble", "bass"):
            raise ValueError("Muss 'treble' oder 'bass' sein")
        return v


class ScanPartUpdate(BaseModel):
    part_name: str | None = None
    part_order: int | None = None
    clef_hint: str | None = None


class ScanPartRead(BaseModel):
    id: int
    project_id: int
    part_name: str
    part_order: int
    clef_hint: str | None
    created_at: datetime
    scan_count: int = 0
    completed_count: int = 0

    model_config = {"from_attributes": True}
```

- [ ] **Step 3: Create SheetMusicScan schemas**

Create `src/backend/mv_hofki/schemas/sheet_music_scan.py`:

```python
"""SheetMusicScan Pydantic schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class SheetMusicScanRead(BaseModel):
    id: int
    part_id: int
    page_number: int
    original_filename: str
    image_path: str
    processed_image_path: str | None
    status: str
    adjustments_json: str | None
    pipeline_config_json: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SheetMusicScanUpdate(BaseModel):
    page_number: int | None = None
    adjustments_json: str | None = None
    pipeline_config_json: str | None = None


class ScanStatusRead(BaseModel):
    status: str
    current_stage: str | None = None
    progress: float | None = None
```

- [ ] **Step 4: Create DetectedStaff schemas**

Create `src/backend/mv_hofki/schemas/detected_staff.py`:

```python
"""DetectedStaff Pydantic schemas."""

from __future__ import annotations

from pydantic import BaseModel


class DetectedStaffRead(BaseModel):
    id: int
    scan_id: int
    staff_index: int
    y_top: int
    y_bottom: int
    line_positions_json: str
    line_spacing: float
    clef: str | None
    key_signature: str | None
    time_signature: str | None
    symbol_count: int = 0
    verified_count: int = 0

    model_config = {"from_attributes": True}


class DetectedStaffUpdate(BaseModel):
    clef: str | None = None
    key_signature: str | None = None
    time_signature: str | None = None
```

- [ ] **Step 5: Create DetectedSymbol schemas**

Create `src/backend/mv_hofki/schemas/detected_symbol.py`:

```python
"""DetectedSymbol Pydantic schemas."""

from __future__ import annotations

from pydantic import BaseModel

from mv_hofki.schemas.symbol_template import SymbolTemplateRead


class DetectedSymbolRead(BaseModel):
    id: int
    staff_id: int
    x: int
    y: int
    width: int
    height: int
    snippet_path: str | None
    position_on_staff: int | None
    sequence_order: int
    matched_symbol_id: int | None
    confidence: float | None
    user_verified: bool
    user_corrected_symbol_id: int | None
    matched_symbol: SymbolTemplateRead | None = None
    corrected_symbol: SymbolTemplateRead | None = None

    model_config = {"from_attributes": True}


class SymbolCorrectionRequest(BaseModel):
    symbol_template_id: int
```

- [ ] **Step 6: Create SymbolTemplate schemas**

Create `src/backend/mv_hofki/schemas/symbol_template.py`:

```python
"""SymbolTemplate Pydantic schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class SymbolTemplateCreate(BaseModel):
    category: str
    name: str
    display_name: str
    musicxml_element: str | None = None
    lilypond_token: str | None = None


class SymbolTemplateRead(BaseModel):
    id: int
    category: str
    name: str
    display_name: str
    musicxml_element: str | None
    lilypond_token: str | None
    is_seed: bool
    created_at: datetime
    variant_count: int = 0

    model_config = {"from_attributes": True}
```

- [ ] **Step 7: Create SymbolVariant schemas**

Create `src/backend/mv_hofki/schemas/symbol_variant.py`:

```python
"""SymbolVariant Pydantic schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class SymbolVariantRead(BaseModel):
    id: int
    template_id: int
    image_path: str
    source: str
    usage_count: int
    created_at: datetime

    model_config = {"from_attributes": True}
```

- [ ] **Step 8: Commit**

```bash
git add src/backend/mv_hofki/schemas/scan_project.py src/backend/mv_hofki/schemas/scan_part.py src/backend/mv_hofki/schemas/sheet_music_scan.py src/backend/mv_hofki/schemas/detected_staff.py src/backend/mv_hofki/schemas/detected_symbol.py src/backend/mv_hofki/schemas/symbol_template.py src/backend/mv_hofki/schemas/symbol_variant.py
git commit -m "feat(scanner): add Pydantic schemas for all scanner entities"
```

---

### Task 4: Create ScanProject CRUD service and API routes with tests

**Files:**
- Create: `src/backend/mv_hofki/services/scan_project.py`
- Create: `src/backend/mv_hofki/api/routes/scan_projects.py`
- Modify: `src/backend/mv_hofki/api/app.py:12-60`
- Create: `tests/backend/test_scan_projects.py`

- [ ] **Step 1: Write failing tests for ScanProject CRUD**

Create `tests/backend/test_scan_projects.py`:

```python
"""Tests for scan project CRUD endpoints."""

import pytest


@pytest.mark.asyncio
async def test_create_scan_project(client):
    resp = await client.post(
        "/api/v1/scanner/projects",
        json={"name": "Böhmischer Traum", "composer": "J. Brunner"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Böhmischer Traum"
    assert data["composer"] == "J. Brunner"
    assert data["id"] is not None


@pytest.mark.asyncio
async def test_create_scan_project_empty_name_rejected(client):
    resp = await client.post(
        "/api/v1/scanner/projects", json={"name": "  "}
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_scan_projects(client):
    await client.post(
        "/api/v1/scanner/projects",
        json={"name": "Projekt A"},
    )
    await client.post(
        "/api/v1/scanner/projects",
        json={"name": "Projekt B"},
    )
    resp = await client.get("/api/v1/scanner/projects")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


@pytest.mark.asyncio
async def test_get_scan_project(client):
    create_resp = await client.post(
        "/api/v1/scanner/projects",
        json={"name": "Test Projekt"},
    )
    project_id = create_resp.json()["id"]
    resp = await client.get(f"/api/v1/scanner/projects/{project_id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Test Projekt"


@pytest.mark.asyncio
async def test_get_scan_project_not_found(client):
    resp = await client.get("/api/v1/scanner/projects/999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_scan_project(client):
    create_resp = await client.post(
        "/api/v1/scanner/projects",
        json={"name": "Original"},
    )
    project_id = create_resp.json()["id"]
    resp = await client.put(
        f"/api/v1/scanner/projects/{project_id}",
        json={"name": "Geändert"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Geändert"


@pytest.mark.asyncio
async def test_delete_scan_project(client):
    create_resp = await client.post(
        "/api/v1/scanner/projects",
        json={"name": "Zum Löschen"},
    )
    project_id = create_resp.json()["id"]
    resp = await client.delete(f"/api/v1/scanner/projects/{project_id}")
    assert resp.status_code == 204
    resp = await client.get(f"/api/v1/scanner/projects/{project_id}")
    assert resp.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /workspaces/mv_hofki && python -m pytest tests/backend/test_scan_projects.py -v`
Expected: FAIL — routes don't exist yet

- [ ] **Step 3: Create ScanProject service**

Create `src/backend/mv_hofki/services/scan_project.py`:

```python
"""ScanProject CRUD service."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.models.scan_project import ScanProject
from mv_hofki.schemas.scan_project import ScanProjectCreate, ScanProjectUpdate


async def get_list(
    session: AsyncSession,
    *,
    limit: int = 50,
    offset: int = 0,
    search: str | None = None,
) -> tuple[list[ScanProject], int]:
    query = select(ScanProject)
    count_query = select(func.count()).select_from(ScanProject)

    if search:
        pattern = f"%{search}%"
        search_filter = ScanProject.name.ilike(pattern)
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    total = (await session.execute(count_query)).scalar_one()
    query = query.order_by(ScanProject.updated_at.desc()).limit(limit).offset(offset)
    result = await session.execute(query)
    return list(result.scalars().all()), total


async def get_by_id(session: AsyncSession, project_id: int) -> ScanProject:
    project = await session.get(ScanProject, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Scan-Projekt nicht gefunden")
    return project


async def create(session: AsyncSession, data: ScanProjectCreate) -> ScanProject:
    project = ScanProject(**data.model_dump())
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project


async def update(
    session: AsyncSession, project_id: int, data: ScanProjectUpdate
) -> ScanProject:
    project = await get_by_id(session, project_id)
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(project, key, value)
    await session.commit()
    await session.refresh(project)
    return project


async def delete(session: AsyncSession, project_id: int) -> None:
    project = await get_by_id(session, project_id)
    await session.delete(project)
    await session.commit()
```

- [ ] **Step 4: Create ScanProject API routes**

Create `src/backend/mv_hofki/api/routes/scan_projects.py`:

```python
"""ScanProject API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.api.deps import get_db
from mv_hofki.schemas.pagination import PaginatedResponse
from mv_hofki.schemas.scan_project import (
    ScanProjectCreate,
    ScanProjectRead,
    ScanProjectUpdate,
)
from mv_hofki.services import scan_project as project_service

router = APIRouter(prefix="/api/v1/scanner/projects", tags=["scanner"])


@router.get("", response_model=PaginatedResponse[ScanProjectRead])
async def list_projects(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    items, total = await project_service.get_list(
        db, limit=limit, offset=offset, search=search
    )
    return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)


@router.post("", response_model=ScanProjectRead, status_code=201)
async def create_project(data: ScanProjectCreate, db: AsyncSession = Depends(get_db)):
    return await project_service.create(db, data)


@router.get("/{project_id}", response_model=ScanProjectRead)
async def get_project(project_id: int, db: AsyncSession = Depends(get_db)):
    return await project_service.get_by_id(db, project_id)


@router.put("/{project_id}", response_model=ScanProjectRead)
async def update_project(
    project_id: int, data: ScanProjectUpdate, db: AsyncSession = Depends(get_db)
):
    return await project_service.update(db, project_id, data)


@router.delete("/{project_id}", status_code=204)
async def delete_project(project_id: int, db: AsyncSession = Depends(get_db)):
    await project_service.delete(db, project_id)
    return Response(status_code=204)
```

- [ ] **Step 5: Register router in app.py**

In `src/backend/mv_hofki/api/app.py`, add the import and `include_router` call:

Add import:
```python
from mv_hofki.api.routes.scan_projects import router as scan_projects_router
```

Add after the `access_router` line:
```python
app.include_router(scan_projects_router)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd /workspaces/mv_hofki && python -m pytest tests/backend/test_scan_projects.py -v`
Expected: All 6 tests pass

- [ ] **Step 7: Run all tests to check for regressions**

Run: `cd /workspaces/mv_hofki && python -m pytest tests/backend/ -v --tb=short`
Expected: All tests pass

- [ ] **Step 8: Commit**

```bash
git add src/backend/mv_hofki/services/scan_project.py src/backend/mv_hofki/api/routes/scan_projects.py src/backend/mv_hofki/api/app.py tests/backend/test_scan_projects.py
git commit -m "feat(scanner): add ScanProject CRUD service, routes, and tests"
```

---

### Task 5: Create ScanPart CRUD service, API routes, and tests

**Files:**
- Create: `src/backend/mv_hofki/services/scan_part.py`
- Create: `src/backend/mv_hofki/api/routes/scan_parts.py`
- Modify: `src/backend/mv_hofki/api/app.py`
- Create: `tests/backend/test_scan_parts.py`

- [ ] **Step 1: Write failing tests for ScanPart CRUD**

Create `tests/backend/test_scan_parts.py`:

```python
"""Tests for scan part CRUD endpoints."""

import pytest


@pytest.fixture
async def project_id(client):
    resp = await client.post(
        "/api/v1/scanner/projects", json={"name": "Test Projekt"}
    )
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_create_scan_part(client, project_id):
    resp = await client.post(
        f"/api/v1/scanner/projects/{project_id}/parts",
        json={"part_name": "1. Flügelhorn", "part_order": 1, "clef_hint": "treble"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["part_name"] == "1. Flügelhorn"
    assert data["clef_hint"] == "treble"


@pytest.mark.asyncio
async def test_create_scan_part_invalid_clef(client, project_id):
    resp = await client.post(
        f"/api/v1/scanner/projects/{project_id}/parts",
        json={"part_name": "Test", "clef_hint": "alto"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_scan_parts(client, project_id):
    await client.post(
        f"/api/v1/scanner/projects/{project_id}/parts",
        json={"part_name": "1. Flügelhorn", "part_order": 1},
    )
    await client.post(
        f"/api/v1/scanner/projects/{project_id}/parts",
        json={"part_name": "Posaune", "part_order": 2},
    )
    resp = await client.get(f"/api/v1/scanner/projects/{project_id}/parts")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["part_name"] == "1. Flügelhorn"


@pytest.mark.asyncio
async def test_delete_scan_part(client, project_id):
    create_resp = await client.post(
        f"/api/v1/scanner/projects/{project_id}/parts",
        json={"part_name": "Zum Löschen"},
    )
    part_id = create_resp.json()["id"]
    resp = await client.delete(
        f"/api/v1/scanner/projects/{project_id}/parts/{part_id}"
    )
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_project_cascades_parts(client, project_id):
    await client.post(
        f"/api/v1/scanner/projects/{project_id}/parts",
        json={"part_name": "Stimme"},
    )
    await client.delete(f"/api/v1/scanner/projects/{project_id}")
    resp = await client.get(f"/api/v1/scanner/projects/{project_id}/parts")
    assert resp.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /workspaces/mv_hofki && python -m pytest tests/backend/test_scan_parts.py -v`
Expected: FAIL

- [ ] **Step 3: Create ScanPart service**

Create `src/backend/mv_hofki/services/scan_part.py`:

```python
"""ScanPart CRUD service."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.models.scan_part import ScanPart
from mv_hofki.schemas.scan_part import ScanPartCreate, ScanPartUpdate
from mv_hofki.services import scan_project as project_service


async def get_list(session: AsyncSession, project_id: int) -> list[ScanPart]:
    await project_service.get_by_id(session, project_id)
    query = (
        select(ScanPart)
        .where(ScanPart.project_id == project_id)
        .order_by(ScanPart.part_order)
    )
    result = await session.execute(query)
    return list(result.scalars().all())


async def get_by_id(
    session: AsyncSession, project_id: int, part_id: int
) -> ScanPart:
    part = await session.get(ScanPart, part_id)
    if not part or part.project_id != project_id:
        raise HTTPException(status_code=404, detail="Stimme nicht gefunden")
    return part


async def create(
    session: AsyncSession, project_id: int, data: ScanPartCreate
) -> ScanPart:
    await project_service.get_by_id(session, project_id)
    part = ScanPart(project_id=project_id, **data.model_dump())
    session.add(part)
    await session.commit()
    await session.refresh(part)
    return part


async def update(
    session: AsyncSession, project_id: int, part_id: int, data: ScanPartUpdate
) -> ScanPart:
    part = await get_by_id(session, project_id, part_id)
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(part, key, value)
    await session.commit()
    await session.refresh(part)
    return part


async def delete(session: AsyncSession, project_id: int, part_id: int) -> None:
    part = await get_by_id(session, project_id, part_id)
    await session.delete(part)
    await session.commit()
```

- [ ] **Step 4: Create ScanPart API routes**

Create `src/backend/mv_hofki/api/routes/scan_parts.py`:

```python
"""ScanPart API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.api.deps import get_db
from mv_hofki.schemas.scan_part import ScanPartCreate, ScanPartRead, ScanPartUpdate
from mv_hofki.services import scan_part as part_service

router = APIRouter(prefix="/api/v1/scanner/projects/{project_id}/parts", tags=["scanner"])


@router.get("", response_model=list[ScanPartRead])
async def list_parts(project_id: int, db: AsyncSession = Depends(get_db)):
    return await part_service.get_list(db, project_id)


@router.post("", response_model=ScanPartRead, status_code=201)
async def create_part(
    project_id: int, data: ScanPartCreate, db: AsyncSession = Depends(get_db)
):
    return await part_service.create(db, project_id, data)


@router.get("/{part_id}", response_model=ScanPartRead)
async def get_part(
    project_id: int, part_id: int, db: AsyncSession = Depends(get_db)
):
    return await part_service.get_by_id(db, project_id, part_id)


@router.put("/{part_id}", response_model=ScanPartRead)
async def update_part(
    project_id: int,
    part_id: int,
    data: ScanPartUpdate,
    db: AsyncSession = Depends(get_db),
):
    return await part_service.update(db, project_id, part_id, data)


@router.delete("/{part_id}", status_code=204)
async def delete_part(
    project_id: int, part_id: int, db: AsyncSession = Depends(get_db)
):
    await part_service.delete(db, project_id, part_id)
    return Response(status_code=204)
```

- [ ] **Step 5: Register router in app.py**

In `src/backend/mv_hofki/api/app.py`, add:

```python
from mv_hofki.api.routes.scan_parts import router as scan_parts_router
```

And:
```python
app.include_router(scan_parts_router)
```

- [ ] **Step 6: Run tests**

Run: `cd /workspaces/mv_hofki && python -m pytest tests/backend/test_scan_parts.py -v`
Expected: All tests pass

- [ ] **Step 7: Commit**

```bash
git add src/backend/mv_hofki/services/scan_part.py src/backend/mv_hofki/api/routes/scan_parts.py src/backend/mv_hofki/api/app.py tests/backend/test_scan_parts.py
git commit -m "feat(scanner): add ScanPart CRUD service, routes, and tests"
```

---

### Task 6: Create SheetMusicScan upload service, API routes, and tests

**Files:**
- Create: `src/backend/mv_hofki/services/sheet_music_scan.py`
- Create: `src/backend/mv_hofki/api/routes/scans.py`
- Modify: `src/backend/mv_hofki/api/app.py`
- Create: `tests/backend/test_scans.py`

- [ ] **Step 1: Write failing tests**

Create `tests/backend/test_scans.py`:

```python
"""Tests for sheet music scan endpoints."""

import io

import pytest


@pytest.fixture
async def part_id(client):
    resp = await client.post(
        "/api/v1/scanner/projects", json={"name": "Test"}
    )
    project_id = resp.json()["id"]
    resp = await client.post(
        f"/api/v1/scanner/projects/{project_id}/parts",
        json={"part_name": "1. Flügelhorn"},
    )
    return project_id, resp.json()["id"]


def _fake_png():
    """Minimal valid PNG (1x1 white pixel)."""
    import struct
    import zlib

    header = b"\x89PNG\r\n\x1a\n"
    ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    ihdr_crc = zlib.crc32(b"IHDR" + ihdr_data) & 0xFFFFFFFF
    ihdr = struct.pack(">I", 13) + b"IHDR" + ihdr_data + struct.pack(">I", ihdr_crc)
    raw = zlib.compress(b"\x00\xff\xff\xff")
    idat_crc = zlib.crc32(b"IDAT" + raw) & 0xFFFFFFFF
    idat = struct.pack(">I", len(raw)) + b"IDAT" + raw + struct.pack(">I", idat_crc)
    iend_crc = zlib.crc32(b"IEND") & 0xFFFFFFFF
    iend = struct.pack(">I", 0) + b"IEND" + struct.pack(">I", iend_crc)
    return header + ihdr + idat + iend


@pytest.mark.asyncio
async def test_upload_scan(client, part_id):
    project_id, p_id = part_id
    png_data = _fake_png()
    resp = await client.post(
        f"/api/v1/scanner/projects/{project_id}/parts/{p_id}/scans",
        files={"file": ("test.png", io.BytesIO(png_data), "image/png")},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["original_filename"] == "test.png"
    assert data["status"] == "uploaded"


@pytest.mark.asyncio
async def test_upload_scan_invalid_type(client, part_id):
    project_id, p_id = part_id
    resp = await client.post(
        f"/api/v1/scanner/projects/{project_id}/parts/{p_id}/scans",
        files={"file": ("test.txt", io.BytesIO(b"not an image"), "text/plain")},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_list_scans(client, part_id):
    project_id, p_id = part_id
    png_data = _fake_png()
    await client.post(
        f"/api/v1/scanner/projects/{project_id}/parts/{p_id}/scans",
        files={"file": ("page1.png", io.BytesIO(png_data), "image/png")},
    )
    resp = await client.get(
        f"/api/v1/scanner/projects/{project_id}/parts/{p_id}/scans"
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_delete_scan(client, part_id):
    project_id, p_id = part_id
    png_data = _fake_png()
    create_resp = await client.post(
        f"/api/v1/scanner/projects/{project_id}/parts/{p_id}/scans",
        files={"file": ("page1.png", io.BytesIO(png_data), "image/png")},
    )
    scan_id = create_resp.json()["id"]
    resp = await client.delete(
        f"/api/v1/scanner/projects/{project_id}/parts/{p_id}/scans/{scan_id}"
    )
    assert resp.status_code == 204
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /workspaces/mv_hofki && python -m pytest tests/backend/test_scans.py -v`
Expected: FAIL

- [ ] **Step 3: Create SheetMusicScan service**

Create `src/backend/mv_hofki/services/sheet_music_scan.py`:

```python
"""SheetMusicScan CRUD + upload service."""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.core.config import settings
from mv_hofki.models.sheet_music_scan import SheetMusicScan
from mv_hofki.schemas.sheet_music_scan import SheetMusicScanUpdate
from mv_hofki.services import scan_part as part_service

ALLOWED_MIME_TYPES = {"image/png", "image/jpeg", "image/tiff"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB

_SCANS_ROOT = settings.PROJECT_ROOT / "data" / "scans"


def _scan_dir(project_id: int, part_id: int, scan_id: int) -> Path:
    return _SCANS_ROOT / str(project_id) / str(part_id) / str(scan_id)


async def get_list(
    session: AsyncSession, project_id: int, part_id: int
) -> list[SheetMusicScan]:
    await part_service.get_by_id(session, project_id, part_id)
    query = (
        select(SheetMusicScan)
        .where(SheetMusicScan.part_id == part_id)
        .order_by(SheetMusicScan.page_number)
    )
    result = await session.execute(query)
    return list(result.scalars().all())


async def get_by_id(
    session: AsyncSession, project_id: int, part_id: int, scan_id: int
) -> SheetMusicScan:
    scan = await session.get(SheetMusicScan, scan_id)
    if not scan or scan.part_id != part_id:
        raise HTTPException(status_code=404, detail="Scan nicht gefunden")
    await part_service.get_by_id(session, project_id, part_id)
    return scan


async def upload(
    session: AsyncSession,
    project_id: int,
    part_id: int,
    file: UploadFile,
) -> SheetMusicScan:
    await part_service.get_by_id(session, project_id, part_id)

    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Ungültiger Dateityp: {file.content_type}. Erlaubt: PNG, JPEG, TIFF",
        )

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="Datei zu groß (max. 50 MB)")

    # Determine next page number
    count_result = await session.execute(
        select(func.count()).where(SheetMusicScan.part_id == part_id)
    )
    page_number = count_result.scalar_one() + 1

    # Create DB record first to get ID
    ext = Path(file.filename or "upload.png").suffix or ".png"
    scan = SheetMusicScan(
        part_id=part_id,
        page_number=page_number,
        original_filename=file.filename or "upload.png",
        image_path="",  # placeholder, updated after save
        status="uploaded",
    )
    session.add(scan)
    await session.flush()

    # Save file
    scan_directory = _scan_dir(project_id, part_id, scan.id)
    scan_directory.mkdir(parents=True, exist_ok=True)
    filename = f"original{ext}"
    file_path = scan_directory / filename
    file_path.write_bytes(content)

    scan.image_path = str(file_path.relative_to(settings.PROJECT_ROOT))
    await session.commit()
    await session.refresh(scan)
    return scan


async def update(
    session: AsyncSession,
    project_id: int,
    part_id: int,
    scan_id: int,
    data: SheetMusicScanUpdate,
) -> SheetMusicScan:
    scan = await get_by_id(session, project_id, part_id, scan_id)
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(scan, key, value)
    await session.commit()
    await session.refresh(scan)
    return scan


async def delete(
    session: AsyncSession, project_id: int, part_id: int, scan_id: int
) -> None:
    scan = await get_by_id(session, project_id, part_id, scan_id)
    scan_directory = _scan_dir(project_id, part_id, scan_id)
    if scan_directory.exists():
        shutil.rmtree(scan_directory)
    await session.delete(scan)
    await session.commit()
```

- [ ] **Step 4: Create SheetMusicScan API routes**

Create `src/backend/mv_hofki/api/routes/scans.py`:

```python
"""SheetMusicScan API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.api.deps import get_db
from mv_hofki.schemas.sheet_music_scan import SheetMusicScanRead, SheetMusicScanUpdate
from mv_hofki.services import sheet_music_scan as scan_service

router = APIRouter(
    prefix="/api/v1/scanner/projects/{project_id}/parts/{part_id}/scans",
    tags=["scanner"],
)


@router.get("", response_model=list[SheetMusicScanRead])
async def list_scans(
    project_id: int, part_id: int, db: AsyncSession = Depends(get_db)
):
    return await scan_service.get_list(db, project_id, part_id)


@router.post("", response_model=SheetMusicScanRead, status_code=201)
async def upload_scan(
    project_id: int,
    part_id: int,
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
):
    return await scan_service.upload(db, project_id, part_id, file)


@router.get("/{scan_id}", response_model=SheetMusicScanRead)
async def get_scan(
    project_id: int, part_id: int, scan_id: int, db: AsyncSession = Depends(get_db)
):
    return await scan_service.get_by_id(db, project_id, part_id, scan_id)


@router.put("/{scan_id}", response_model=SheetMusicScanRead)
async def update_scan(
    project_id: int,
    part_id: int,
    scan_id: int,
    data: SheetMusicScanUpdate,
    db: AsyncSession = Depends(get_db),
):
    return await scan_service.update(db, project_id, part_id, scan_id, data)


@router.delete("/{scan_id}", status_code=204)
async def delete_scan(
    project_id: int, part_id: int, scan_id: int, db: AsyncSession = Depends(get_db)
):
    await scan_service.delete(db, project_id, part_id, scan_id)
    return Response(status_code=204)
```

- [ ] **Step 5: Register router and mount scans directory in app.py**

In `src/backend/mv_hofki/api/app.py`, add:

```python
from mv_hofki.api.routes.scans import router as scans_router
```

Add the router:
```python
app.include_router(scans_router)
```

Mount the scans directory (after the existing uploads mount):
```python
_scans_dir = settings.PROJECT_ROOT / "data" / "scans"
_scans_dir.mkdir(parents=True, exist_ok=True)
app.mount("/scans", StaticFiles(directory=str(_scans_dir)), name="scans")
```

- [ ] **Step 6: Run tests**

Run: `cd /workspaces/mv_hofki && python -m pytest tests/backend/test_scans.py -v`
Expected: All tests pass

- [ ] **Step 7: Commit**

```bash
git add src/backend/mv_hofki/services/sheet_music_scan.py src/backend/mv_hofki/api/routes/scans.py src/backend/mv_hofki/api/app.py tests/backend/test_scans.py
git commit -m "feat(scanner): add SheetMusicScan upload, CRUD service, routes, and tests"
```

---

### Task 7: Create Symbol Library service, API routes, seed data, and tests

**Files:**
- Create: `src/backend/mv_hofki/services/symbol_library.py`
- Create: `src/backend/mv_hofki/api/routes/symbol_library.py`
- Create: `src/backend/mv_hofki/services/scanner/library/__init__.py`
- Create: `src/backend/mv_hofki/services/scanner/library/seed.py`
- Modify: `src/backend/mv_hofki/db/seed.py`
- Modify: `src/backend/mv_hofki/api/app.py`
- Create: `tests/backend/test_symbol_library.py`

- [ ] **Step 1: Write failing tests**

Create `tests/backend/test_symbol_library.py`:

```python
"""Tests for symbol library endpoints."""

import pytest

from mv_hofki.services.scanner.library.seed import SYMBOL_TEMPLATES


@pytest.mark.asyncio
async def test_list_symbol_templates_empty(client):
    resp = await client.get("/api/v1/scanner/library/templates")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_create_symbol_template(client):
    resp = await client.post(
        "/api/v1/scanner/library/templates",
        json={
            "category": "note",
            "name": "test_note",
            "display_name": "Testnote",
        },
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == "test_note"


@pytest.mark.asyncio
async def test_list_symbol_templates_by_category(client):
    await client.post(
        "/api/v1/scanner/library/templates",
        json={"category": "note", "name": "n1", "display_name": "Note 1"},
    )
    await client.post(
        "/api/v1/scanner/library/templates",
        json={"category": "rest", "name": "r1", "display_name": "Pause 1"},
    )
    resp = await client.get("/api/v1/scanner/library/templates?category=note")
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["category"] == "note"


@pytest.mark.asyncio
async def test_get_symbol_template(client):
    create_resp = await client.post(
        "/api/v1/scanner/library/templates",
        json={"category": "clef", "name": "treble_clef", "display_name": "Violinschlüssel"},
    )
    template_id = create_resp.json()["id"]
    resp = await client.get(f"/api/v1/scanner/library/templates/{template_id}")
    assert resp.status_code == 200
    assert resp.json()["display_name"] == "Violinschlüssel"


@pytest.mark.asyncio
async def test_seed_data_structure():
    """Verify seed data has required fields."""
    assert len(SYMBOL_TEMPLATES) > 30
    for t in SYMBOL_TEMPLATES:
        assert "category" in t
        assert "name" in t
        assert "display_name" in t
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /workspaces/mv_hofki && python -m pytest tests/backend/test_symbol_library.py -v`
Expected: FAIL

- [ ] **Step 3: Create seed data definitions**

Create `src/backend/mv_hofki/services/scanner/__init__.py` (empty), `src/backend/mv_hofki/services/scanner/library/__init__.py` (empty), then create `src/backend/mv_hofki/services/scanner/library/seed.py`:

```python
"""Pre-seed symbol template definitions for the symbol library."""

SYMBOL_TEMPLATES = [
    # Notes
    {"category": "note", "name": "whole_note", "display_name": "Ganze Note", "lilypond_token": "1"},
    {"category": "note", "name": "half_note", "display_name": "Halbe Note", "lilypond_token": "2"},
    {"category": "note", "name": "quarter_note", "display_name": "Viertelnote", "lilypond_token": "4"},
    {"category": "note", "name": "eighth_note", "display_name": "Achtelnote", "lilypond_token": "8"},
    {"category": "note", "name": "sixteenth_note", "display_name": "Sechzehntelnote", "lilypond_token": "16"},
    {"category": "note", "name": "dotted_half_note", "display_name": "Punktierte Halbe", "lilypond_token": "2."},
    {"category": "note", "name": "dotted_quarter_note", "display_name": "Punktierte Viertel", "lilypond_token": "4."},
    {"category": "note", "name": "dotted_eighth_note", "display_name": "Punktierte Achtel", "lilypond_token": "8."},
    # Rests
    {"category": "rest", "name": "whole_rest", "display_name": "Ganze Pause", "lilypond_token": "r1"},
    {"category": "rest", "name": "half_rest", "display_name": "Halbe Pause", "lilypond_token": "r2"},
    {"category": "rest", "name": "quarter_rest", "display_name": "Viertelpause", "lilypond_token": "r4"},
    {"category": "rest", "name": "eighth_rest", "display_name": "Achtelpause", "lilypond_token": "r8"},
    {"category": "rest", "name": "sixteenth_rest", "display_name": "Sechzehntelpause", "lilypond_token": "r16"},
    # Accidentals
    {"category": "accidental", "name": "sharp", "display_name": "Kreuz", "lilypond_token": "is"},
    {"category": "accidental", "name": "flat", "display_name": "Be", "lilypond_token": "es"},
    {"category": "accidental", "name": "natural", "display_name": "Auflösungszeichen", "lilypond_token": "!"},
    {"category": "accidental", "name": "double_sharp", "display_name": "Doppelkreuz", "lilypond_token": "isis"},
    {"category": "accidental", "name": "double_flat", "display_name": "Doppel-Be", "lilypond_token": "eses"},
    # Clefs
    {"category": "clef", "name": "treble_clef", "display_name": "Violinschlüssel", "lilypond_token": "\\clef treble"},
    {"category": "clef", "name": "bass_clef", "display_name": "Bassschlüssel", "lilypond_token": "\\clef bass"},
    # Time signatures
    {"category": "time_sig", "name": "time_4_4", "display_name": "4/4-Takt", "lilypond_token": "\\time 4/4"},
    {"category": "time_sig", "name": "time_3_4", "display_name": "3/4-Takt", "lilypond_token": "\\time 3/4"},
    {"category": "time_sig", "name": "time_2_4", "display_name": "2/4-Takt", "lilypond_token": "\\time 2/4"},
    {"category": "time_sig", "name": "time_6_8", "display_name": "6/8-Takt", "lilypond_token": "\\time 6/8"},
    {"category": "time_sig", "name": "time_common", "display_name": "Alla breve (C)", "lilypond_token": "\\time 4/4"},
    {"category": "time_sig", "name": "time_cut", "display_name": "Alla breve (₵)", "lilypond_token": "\\time 2/2"},
    # Barlines
    {"category": "barline", "name": "single_barline", "display_name": "Einfacher Taktstrich"},
    {"category": "barline", "name": "double_barline", "display_name": "Doppelter Taktstrich"},
    {"category": "barline", "name": "final_barline", "display_name": "Schlusstaktstrich"},
    {"category": "barline", "name": "repeat_start", "display_name": "Wiederholung Anfang"},
    {"category": "barline", "name": "repeat_end", "display_name": "Wiederholung Ende"},
    # Dynamics
    {"category": "dynamic", "name": "pp", "display_name": "Pianissimo"},
    {"category": "dynamic", "name": "p", "display_name": "Piano"},
    {"category": "dynamic", "name": "mp", "display_name": "Mezzopiano"},
    {"category": "dynamic", "name": "mf", "display_name": "Mezzoforte"},
    {"category": "dynamic", "name": "f", "display_name": "Forte"},
    {"category": "dynamic", "name": "ff", "display_name": "Fortissimo"},
    {"category": "dynamic", "name": "crescendo", "display_name": "Crescendo"},
    {"category": "dynamic", "name": "decrescendo", "display_name": "Decrescendo"},
    # Articulations
    {"category": "ornament", "name": "staccato", "display_name": "Staccato"},
    {"category": "ornament", "name": "accent", "display_name": "Akzent"},
    {"category": "ornament", "name": "tenuto", "display_name": "Tenuto"},
    {"category": "ornament", "name": "fermata", "display_name": "Fermate"},
    # Other
    {"category": "other", "name": "tie", "display_name": "Haltebogen"},
    {"category": "other", "name": "slur", "display_name": "Bindebogen"},
    {"category": "other", "name": "dot", "display_name": "Punkt (Verlängerung)"},
    {"category": "other", "name": "segno", "display_name": "Segno"},
    {"category": "other", "name": "coda", "display_name": "Coda"},
    {"category": "other", "name": "trill", "display_name": "Triller"},
]
```

- [ ] **Step 4: Create Symbol Library service**

Create `src/backend/mv_hofki/services/symbol_library.py`:

```python
"""SymbolTemplate and SymbolVariant CRUD service."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.models.symbol_template import SymbolTemplate
from mv_hofki.models.symbol_variant import SymbolVariant
from mv_hofki.schemas.symbol_template import SymbolTemplateCreate


async def get_templates(
    session: AsyncSession,
    *,
    limit: int = 50,
    offset: int = 0,
    category: str | None = None,
) -> tuple[list[SymbolTemplate], int]:
    query = select(SymbolTemplate)
    count_query = select(func.count()).select_from(SymbolTemplate)

    if category:
        query = query.where(SymbolTemplate.category == category)
        count_query = count_query.where(SymbolTemplate.category == category)

    total = (await session.execute(count_query)).scalar_one()
    query = (
        query.order_by(SymbolTemplate.category, SymbolTemplate.name)
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(query)
    return list(result.scalars().all()), total


async def get_template_by_id(
    session: AsyncSession, template_id: int
) -> SymbolTemplate:
    template = await session.get(SymbolTemplate, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Symbol-Vorlage nicht gefunden")
    return template


async def create_template(
    session: AsyncSession, data: SymbolTemplateCreate
) -> SymbolTemplate:
    template = SymbolTemplate(**data.model_dump())
    session.add(template)
    await session.commit()
    await session.refresh(template)
    return template


async def get_variants(
    session: AsyncSession, template_id: int
) -> list[SymbolVariant]:
    await get_template_by_id(session, template_id)
    query = (
        select(SymbolVariant)
        .where(SymbolVariant.template_id == template_id)
        .order_by(SymbolVariant.usage_count.desc())
    )
    result = await session.execute(query)
    return list(result.scalars().all())
```

- [ ] **Step 5: Create Symbol Library API routes**

Create `src/backend/mv_hofki/api/routes/symbol_library.py`:

```python
"""Symbol library API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.api.deps import get_db
from mv_hofki.schemas.pagination import PaginatedResponse
from mv_hofki.schemas.symbol_template import SymbolTemplateCreate, SymbolTemplateRead
from mv_hofki.schemas.symbol_variant import SymbolVariantRead
from mv_hofki.services import symbol_library as lib_service

router = APIRouter(prefix="/api/v1/scanner/library", tags=["scanner-library"])


@router.get("/templates", response_model=PaginatedResponse[SymbolTemplateRead])
async def list_templates(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    category: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    items, total = await lib_service.get_templates(
        db, limit=limit, offset=offset, category=category
    )
    return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)


@router.post("/templates", response_model=SymbolTemplateRead, status_code=201)
async def create_template(
    data: SymbolTemplateCreate, db: AsyncSession = Depends(get_db)
):
    return await lib_service.create_template(db, data)


@router.get("/templates/{template_id}", response_model=SymbolTemplateRead)
async def get_template(template_id: int, db: AsyncSession = Depends(get_db)):
    return await lib_service.get_template_by_id(db, template_id)


@router.get(
    "/templates/{template_id}/variants",
    response_model=list[SymbolVariantRead],
)
async def list_variants(template_id: int, db: AsyncSession = Depends(get_db)):
    return await lib_service.get_variants(db, template_id)
```

- [ ] **Step 6: Add symbol template seeding to seed.py**

In `src/backend/mv_hofki/db/seed.py`, add the import and seed logic:

Add imports:
```python
from mv_hofki.models.symbol_template import SymbolTemplate
from mv_hofki.services.scanner.library.seed import SYMBOL_TEMPLATES
```

Add at the end of `seed_data()`, before `await session.commit()`:
```python
    result = await session.execute(select(SymbolTemplate).limit(1))
    if result.scalar_one_or_none() is None:
        await session.execute(
            insert(SymbolTemplate),
            [{"is_seed": True, **t} for t in SYMBOL_TEMPLATES],
        )
```

- [ ] **Step 7: Register router in app.py**

In `src/backend/mv_hofki/api/app.py`, add:
```python
from mv_hofki.api.routes.symbol_library import router as symbol_library_router
```
And:
```python
app.include_router(symbol_library_router)
```

- [ ] **Step 8: Run tests**

Run: `cd /workspaces/mv_hofki && python -m pytest tests/backend/test_symbol_library.py -v`
Expected: All tests pass

- [ ] **Step 9: Commit**

```bash
git add src/backend/mv_hofki/services/scanner/ src/backend/mv_hofki/services/symbol_library.py src/backend/mv_hofki/api/routes/symbol_library.py src/backend/mv_hofki/db/seed.py tests/backend/test_symbol_library.py
git commit -m "feat(scanner): add symbol library service, routes, seed data, and tests"
```

---

### Task 8: Create processing pipeline framework and stage base class

**Files:**
- Create: `src/backend/mv_hofki/services/scanner/stages/__init__.py`
- Create: `src/backend/mv_hofki/services/scanner/stages/base.py`
- Create: `src/backend/mv_hofki/services/scanner/pipeline.py`
- Create: `tests/backend/test_pipeline_stages.py`

- [ ] **Step 1: Write failing tests for pipeline framework**

Create `tests/backend/test_pipeline_stages.py`:

```python
"""Tests for the processing pipeline framework."""

import numpy as np
import pytest

from mv_hofki.services.scanner.stages.base import PipelineContext, ProcessingStage


class DummyStage(ProcessingStage):
    name = "dummy"

    def process(self, ctx: PipelineContext) -> PipelineContext:
        ctx.metadata["dummy_ran"] = True
        return ctx

    def validate(self, ctx: PipelineContext) -> bool:
        return ctx.image is not None


class FailingValidationStage(ProcessingStage):
    name = "failing"

    def process(self, ctx: PipelineContext) -> PipelineContext:
        return ctx

    def validate(self, ctx: PipelineContext) -> bool:
        return False


def test_pipeline_context_creation():
    img = np.zeros((100, 100), dtype=np.uint8)
    ctx = PipelineContext(image=img)
    assert ctx.image is not None
    assert ctx.metadata == {}
    assert ctx.staves == []
    assert ctx.symbols == []


def test_stage_process():
    img = np.zeros((100, 100), dtype=np.uint8)
    ctx = PipelineContext(image=img)
    stage = DummyStage()
    result = stage.process(ctx)
    assert result.metadata["dummy_ran"] is True


def test_stage_validate():
    ctx = PipelineContext(image=np.zeros((10, 10), dtype=np.uint8))
    assert DummyStage().validate(ctx) is True

    ctx_no_image = PipelineContext(image=None)
    assert DummyStage().validate(ctx_no_image) is False


def test_pipeline_runs_stages_in_order():
    from mv_hofki.services.scanner.pipeline import Pipeline

    class StageA(ProcessingStage):
        name = "a"
        def process(self, ctx):
            ctx.metadata.setdefault("order", []).append("a")
            return ctx
        def validate(self, ctx):
            return True

    class StageB(ProcessingStage):
        name = "b"
        def process(self, ctx):
            ctx.metadata.setdefault("order", []).append("b")
            return ctx
        def validate(self, ctx):
            return True

    pipeline = Pipeline(stages=[StageA(), StageB()])
    ctx = PipelineContext(image=np.zeros((10, 10), dtype=np.uint8))
    result = pipeline.run(ctx)
    assert result.metadata["order"] == ["a", "b"]


def test_pipeline_skips_disabled_stages():
    from mv_hofki.services.scanner.pipeline import Pipeline

    class StageA(ProcessingStage):
        name = "a"
        def process(self, ctx):
            ctx.metadata["a_ran"] = True
            return ctx
        def validate(self, ctx):
            return True

    pipeline = Pipeline(stages=[StageA()])
    ctx = PipelineContext(
        image=np.zeros((10, 10), dtype=np.uint8),
        config={"disabled_stages": ["a"]},
    )
    result = pipeline.run(ctx)
    assert "a_ran" not in result.metadata


def test_pipeline_records_completed_stages():
    from mv_hofki.services.scanner.pipeline import Pipeline

    class StageA(ProcessingStage):
        name = "a"
        def process(self, ctx):
            return ctx
        def validate(self, ctx):
            return True

    pipeline = Pipeline(stages=[StageA()])
    ctx = PipelineContext(image=np.zeros((10, 10), dtype=np.uint8))
    result = pipeline.run(ctx)
    assert "a" in result.completed_stages
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /workspaces/mv_hofki && python -m pytest tests/backend/test_pipeline_stages.py -v`
Expected: FAIL

- [ ] **Step 3: Create pipeline context and stage base class**

Create `src/backend/mv_hofki/services/scanner/stages/__init__.py` (empty file).

Create `src/backend/mv_hofki/services/scanner/stages/base.py`:

```python
"""Processing stage base class and pipeline context."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass
class StaffData:
    """Data for a single detected staff."""

    staff_index: int
    y_top: int
    y_bottom: int
    line_positions: list[int]
    line_spacing: float
    clef: str | None = None
    key_signature: str | None = None
    time_signature: str | None = None


@dataclass
class SymbolData:
    """Data for a single detected symbol."""

    staff_index: int
    x: int
    y: int
    width: int
    height: int
    snippet: np.ndarray | None = None
    position_on_staff: int | None = None
    sequence_order: int = 0
    matched_template_id: int | None = None
    confidence: float | None = None
    alternatives: list[tuple[int, float]] = field(default_factory=list)


@dataclass
class PipelineContext:
    """Shared context passed between pipeline stages."""

    image: np.ndarray | None
    original_image: np.ndarray | None = None
    processed_image: np.ndarray | None = None
    staves: list[StaffData] = field(default_factory=list)
    symbols: list[SymbolData] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    config: dict[str, Any] = field(default_factory=dict)
    completed_stages: list[str] = field(default_factory=list)


class ProcessingStage(ABC):
    """Abstract base for all processing pipeline stages."""

    name: str

    @abstractmethod
    def process(self, ctx: PipelineContext) -> PipelineContext:
        """Run this stage's processing on the context."""

    @abstractmethod
    def validate(self, ctx: PipelineContext) -> bool:
        """Check if prerequisites for this stage are met."""
```

- [ ] **Step 4: Create Pipeline runner**

Create `src/backend/mv_hofki/services/scanner/pipeline.py`:

```python
"""Pipeline runner — executes processing stages in order."""

from __future__ import annotations

import logging

from mv_hofki.services.scanner.stages.base import PipelineContext, ProcessingStage

logger = logging.getLogger(__name__)


class Pipeline:
    """Runs a sequence of processing stages, respecting disabled stages."""

    def __init__(self, stages: list[ProcessingStage]) -> None:
        self.stages = stages

    def run(self, ctx: PipelineContext) -> PipelineContext:
        disabled = set(ctx.config.get("disabled_stages", []))

        for stage in self.stages:
            if stage.name in disabled:
                logger.info("Skipping disabled stage: %s", stage.name)
                continue

            if not stage.validate(ctx):
                logger.warning(
                    "Stage %s validation failed, skipping", stage.name
                )
                continue

            logger.info("Running stage: %s", stage.name)
            ctx = stage.process(ctx)
            ctx.completed_stages.append(stage.name)
            logger.info("Stage %s completed", stage.name)

        return ctx
```

- [ ] **Step 5: Run tests**

Run: `cd /workspaces/mv_hofki && python -m pytest tests/backend/test_pipeline_stages.py -v`
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add src/backend/mv_hofki/services/scanner/stages/ src/backend/mv_hofki/services/scanner/pipeline.py tests/backend/test_pipeline_stages.py
git commit -m "feat(scanner): add processing pipeline framework with stage base class"
```

---

### Task 9: Implement preprocessing stage (binarization, deskew, denoise)

**Files:**
- Create: `src/backend/mv_hofki/services/scanner/stages/preprocess.py`
- Create: `tests/backend/fixtures/` (test fixture directory)
- Modify: `tests/backend/test_pipeline_stages.py`

- [ ] **Step 1: Write failing tests for preprocessing**

Add to `tests/backend/test_pipeline_stages.py`:

```python
def test_preprocess_stage_binarizes():
    from mv_hofki.services.scanner.stages.preprocess import PreprocessStage

    # Create a grayscale image with some gray areas
    img = np.full((200, 200), 180, dtype=np.uint8)
    img[50:150, 50:150] = 40  # dark square

    ctx = PipelineContext(image=img)
    stage = PreprocessStage()
    result = stage.process(ctx)

    assert result.processed_image is not None
    # Should be binary — only 0 and 255
    unique = np.unique(result.processed_image)
    assert all(v in (0, 255) for v in unique)


def test_preprocess_stage_preserves_original():
    from mv_hofki.services.scanner.stages.preprocess import PreprocessStage

    img = np.full((100, 100), 128, dtype=np.uint8)
    ctx = PipelineContext(image=img)
    stage = PreprocessStage()
    result = stage.process(ctx)

    assert result.original_image is not None
    assert np.array_equal(result.original_image, img)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /workspaces/mv_hofki && python -m pytest tests/backend/test_pipeline_stages.py::test_preprocess_stage_binarizes -v`
Expected: FAIL

- [ ] **Step 3: Implement PreprocessStage**

Create `src/backend/mv_hofki/services/scanner/stages/preprocess.py`:

```python
"""Preprocessing stage: binarization, deskew, noise removal."""

from __future__ import annotations

import cv2
import numpy as np

from mv_hofki.services.scanner.stages.base import PipelineContext, ProcessingStage


class PreprocessStage(ProcessingStage):
    """Adaptive thresholding, deskew, and morphological noise removal."""

    name = "preprocess"

    def process(self, ctx: PipelineContext) -> PipelineContext:
        img = ctx.image
        ctx.original_image = img.copy()

        # Convert to grayscale if needed
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            gray = img.copy()

        # Apply brightness/contrast adjustments from config
        brightness = ctx.config.get("brightness", 0)
        contrast = ctx.config.get("contrast", 1.0)
        if brightness != 0 or contrast != 1.0:
            gray = cv2.convertScaleAbs(gray, alpha=contrast, beta=brightness)

        # Adaptive thresholding — handles uneven lighting from degraded copies
        binary = cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            blockSize=15,
            C=10,
        )

        # Deskew using Hough line detection
        binary = self._deskew(binary)

        # Morphological noise removal
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2, 2))
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)

        ctx.processed_image = binary
        ctx.image = binary
        return ctx

    def validate(self, ctx: PipelineContext) -> bool:
        return ctx.image is not None

    @staticmethod
    def _deskew(img: np.ndarray) -> np.ndarray:
        """Detect and correct skew angle using Hough transform."""
        edges = cv2.Canny(img, 50, 150, apertureSize=3)
        lines = cv2.HoughLinesP(
            edges, 1, np.pi / 180, threshold=100, minLineLength=100, maxLineGap=10
        )

        if lines is None:
            return img

        angles = []
        for line in lines:
            x1, y1, x2, y2 = line[0]
            angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))
            if abs(angle) < 5:  # only consider near-horizontal lines
                angles.append(angle)

        if not angles:
            return img

        median_angle = np.median(angles)
        if abs(median_angle) < 0.1:  # skip if nearly straight
            return img

        h, w = img.shape[:2]
        center = (w // 2, h // 2)
        matrix = cv2.getRotationMatrix2D(center, median_angle, 1.0)
        rotated = cv2.warpAffine(
            img, matrix, (w, h), flags=cv2.INTER_LINEAR, borderValue=255
        )
        return rotated
```

- [ ] **Step 4: Run tests**

Run: `cd /workspaces/mv_hofki && python -m pytest tests/backend/test_pipeline_stages.py -v`
Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add src/backend/mv_hofki/services/scanner/stages/preprocess.py tests/backend/test_pipeline_stages.py
git commit -m "feat(scanner): implement preprocessing stage (binarize, deskew, denoise)"
```

---

### Task 10: Implement stave detection stage

**Files:**
- Create: `src/backend/mv_hofki/services/scanner/stages/stave_detection.py`
- Modify: `tests/backend/test_pipeline_stages.py`

- [ ] **Step 1: Write failing tests for stave detection**

Add to `tests/backend/test_pipeline_stages.py`:

```python
def _create_staff_image(num_staves=3, staff_spacing=60, line_gap=10, width=800):
    """Create a test image with horizontal staff lines."""
    height = num_staves * staff_spacing * 2 + 100
    img = np.full((height, width), 255, dtype=np.uint8)
    y = 50
    for _ in range(num_staves):
        for line in range(5):
            line_y = y + line * line_gap
            img[line_y : line_y + 2, 20 : width - 20] = 0
        y += staff_spacing + 5 * line_gap
    return img


def test_stave_detection_finds_staves():
    from mv_hofki.services.scanner.stages.stave_detection import StaveDetectionStage

    img = _create_staff_image(num_staves=3)
    ctx = PipelineContext(image=img, processed_image=img)
    stage = StaveDetectionStage()
    result = stage.process(ctx)

    assert len(result.staves) == 3
    for staff in result.staves:
        assert len(staff.line_positions) == 5
        assert staff.line_spacing > 0


def test_stave_detection_single_staff():
    from mv_hofki.services.scanner.stages.stave_detection import StaveDetectionStage

    img = _create_staff_image(num_staves=1)
    ctx = PipelineContext(image=img, processed_image=img)
    stage = StaveDetectionStage()
    result = stage.process(ctx)

    assert len(result.staves) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /workspaces/mv_hofki && python -m pytest tests/backend/test_pipeline_stages.py::test_stave_detection_finds_staves -v`
Expected: FAIL

- [ ] **Step 3: Implement StaveDetectionStage**

Create `src/backend/mv_hofki/services/scanner/stages/stave_detection.py`:

```python
"""Stave detection stage: find staff line groups via horizontal projection."""

from __future__ import annotations

import numpy as np

from mv_hofki.services.scanner.stages.base import (
    PipelineContext,
    ProcessingStage,
    StaffData,
)


class StaveDetectionStage(ProcessingStage):
    """Detect groups of 5 horizontal lines that form musical staves."""

    name = "stave_detection"

    def process(self, ctx: PipelineContext) -> PipelineContext:
        img = ctx.processed_image if ctx.processed_image is not None else ctx.image

        # Horizontal projection: sum black pixels per row
        # (assuming binary image: 0=black, 255=white)
        binary = img if len(img.shape) == 2 else img[:, :, 0]
        projection = np.sum(binary == 0, axis=1).astype(float)

        # Find line candidates: rows with high density of black pixels
        threshold = projection.max() * 0.3
        line_rows = np.where(projection > threshold)[0]

        if len(line_rows) == 0:
            return ctx

        # Group consecutive rows into line centers
        line_centers = self._group_consecutive(line_rows)

        # Group line centers into staves (groups of 5 with consistent spacing)
        staves = self._group_into_staves(line_centers)

        for i, staff_lines in enumerate(staves):
            spacing = np.mean(np.diff(staff_lines))
            margin = int(spacing * 2)
            ctx.staves.append(
                StaffData(
                    staff_index=i,
                    y_top=max(0, staff_lines[0] - margin),
                    y_bottom=min(img.shape[0], staff_lines[-1] + margin),
                    line_positions=[int(y) for y in staff_lines],
                    line_spacing=float(spacing),
                )
            )

        return ctx

    def validate(self, ctx: PipelineContext) -> bool:
        return (ctx.processed_image is not None) or (ctx.image is not None)

    @staticmethod
    def _group_consecutive(rows: np.ndarray, max_gap: int = 3) -> list[int]:
        """Group consecutive row indices and return their centers."""
        groups: list[list[int]] = []
        current: list[int] = [rows[0]]

        for r in rows[1:]:
            if r - current[-1] <= max_gap:
                current.append(r)
            else:
                groups.append(current)
                current = [r]
        groups.append(current)

        return [int(np.mean(g)) for g in groups]

    @staticmethod
    def _group_into_staves(
        line_centers: list[int], tolerance: float = 0.3
    ) -> list[list[int]]:
        """Group line centers into staves of 5 with consistent spacing."""
        if len(line_centers) < 5:
            return []

        staves: list[list[int]] = []
        used = set()

        i = 0
        while i <= len(line_centers) - 5:
            if i in used:
                i += 1
                continue

            candidate = line_centers[i : i + 5]
            spacings = np.diff(candidate)
            mean_spacing = np.mean(spacings)

            if mean_spacing < 3:
                i += 1
                continue

            # Check spacing consistency
            deviations = np.abs(spacings - mean_spacing) / mean_spacing
            if np.all(deviations < tolerance):
                staves.append(candidate)
                for j in range(i, i + 5):
                    used.add(j)
                i += 5
            else:
                i += 1

        return staves
```

- [ ] **Step 4: Run tests**

Run: `cd /workspaces/mv_hofki && python -m pytest tests/backend/test_pipeline_stages.py -v`
Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add src/backend/mv_hofki/services/scanner/stages/stave_detection.py tests/backend/test_pipeline_stages.py
git commit -m "feat(scanner): implement stave detection stage via horizontal projection"
```

---

### Task 11: Implement staff removal stage (optional) and segmentation stage

**Files:**
- Create: `src/backend/mv_hofki/services/scanner/stages/staff_removal.py`
- Create: `src/backend/mv_hofki/services/scanner/stages/segmentation.py`
- Modify: `tests/backend/test_pipeline_stages.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/backend/test_pipeline_stages.py`:

```python
def test_staff_removal_removes_lines():
    from mv_hofki.services.scanner.stages.staff_removal import StaffRemovalStage

    img = _create_staff_image(num_staves=1, width=200)
    ctx = PipelineContext(
        image=img,
        processed_image=img,
        staves=[
            StaffData(
                staff_index=0,
                y_top=30,
                y_bottom=120,
                line_positions=[50, 60, 70, 80, 90],
                line_spacing=10.0,
            )
        ],
    )
    stage = StaffRemovalStage()
    result = stage.process(ctx)

    # Staff lines should be mostly removed
    for y in [50, 60, 70, 80, 90]:
        row_black = np.sum(result.image[y : y + 2, :] == 0)
        original_black = np.sum(img[y : y + 2, :] == 0)
        assert row_black < original_black


def test_segmentation_finds_symbols():
    from mv_hofki.services.scanner.stages.segmentation import SegmentationStage

    # Create image with staff lines and some "note" blobs
    img = np.full((200, 400), 255, dtype=np.uint8)
    # Add some black circles (fake notes)
    cv2.circle(img, (100, 80), 8, 0, -1)
    cv2.circle(img, (200, 90), 8, 0, -1)
    cv2.circle(img, (300, 75), 8, 0, -1)

    ctx = PipelineContext(
        image=img,
        processed_image=img,
        staves=[
            StaffData(
                staff_index=0,
                y_top=30,
                y_bottom=150,
                line_positions=[50, 65, 80, 95, 110],
                line_spacing=15.0,
            )
        ],
    )
    stage = SegmentationStage()
    result = stage.process(ctx)

    assert len(result.symbols) == 3
    # Should be ordered left to right
    xs = [s.x for s in result.symbols]
    assert xs == sorted(xs)
```

Add this import at the top of the test file:
```python
import cv2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /workspaces/mv_hofki && python -m pytest tests/backend/test_pipeline_stages.py::test_staff_removal_removes_lines -v`
Expected: FAIL

- [ ] **Step 3: Implement StaffRemovalStage**

Create `src/backend/mv_hofki/services/scanner/stages/staff_removal.py`:

```python
"""Staff line removal stage (optional)."""

from __future__ import annotations

import cv2
import numpy as np

from mv_hofki.services.scanner.stages.base import PipelineContext, ProcessingStage


class StaffRemovalStage(ProcessingStage):
    """Remove horizontal staff lines, preserving vertical components."""

    name = "staff_removal"

    def process(self, ctx: PipelineContext) -> PipelineContext:
        img = ctx.image.copy()

        for staff in ctx.staves:
            for line_y in staff.line_positions:
                self._remove_line(img, line_y, line_thickness=3)

        ctx.image = img
        return ctx

    def validate(self, ctx: PipelineContext) -> bool:
        return ctx.image is not None and len(ctx.staves) > 0

    @staticmethod
    def _remove_line(img: np.ndarray, y: int, line_thickness: int = 3) -> None:
        """Remove a horizontal line at y, preserving vertical crossings."""
        h, w = img.shape[:2]
        y_start = max(0, y - line_thickness // 2)
        y_end = min(h, y + line_thickness // 2 + 1)

        for x in range(w):
            # Check if this column has a vertical component crossing the line
            above_black = False
            below_black = False

            check_range = line_thickness + 2
            if y_start - check_range >= 0:
                above_black = np.any(img[y_start - check_range : y_start, x] == 0)
            if y_end + check_range < h:
                below_black = np.any(img[y_end : y_end + check_range, x] == 0)

            # Only remove if no vertical component crosses here
            if not (above_black and below_black):
                img[y_start:y_end, x] = 255
```

- [ ] **Step 4: Implement SegmentationStage**

Create `src/backend/mv_hofki/services/scanner/stages/segmentation.py`:

```python
"""Symbol segmentation stage: find bounding boxes via connected components."""

from __future__ import annotations

import cv2
import numpy as np

from mv_hofki.services.scanner.stages.base import (
    PipelineContext,
    ProcessingStage,
    SymbolData,
)


class SegmentationStage(ProcessingStage):
    """Detect symbol regions using connected component analysis."""

    name = "segmentation"

    def process(self, ctx: PipelineContext) -> PipelineContext:
        img = ctx.image
        if len(img.shape) == 3:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Invert so symbols are white (for connectedComponents)
        inverted = cv2.bitwise_not(img)

        for staff in ctx.staves:
            # Crop to staff region
            region = inverted[staff.y_top : staff.y_bottom, :]
            symbols = self._find_symbols_in_region(
                region, staff, ctx.image.shape[1]
            )
            ctx.symbols.extend(symbols)

        # Sort all symbols by staff index, then left to right
        ctx.symbols.sort(key=lambda s: (s.staff_index, s.x))

        # Assign sequence order
        for i, sym in enumerate(ctx.symbols):
            sym.sequence_order = i

        return ctx

    def validate(self, ctx: PipelineContext) -> bool:
        return ctx.image is not None and len(ctx.staves) > 0

    def _find_symbols_in_region(
        self,
        region: np.ndarray,
        staff,
        image_width: int,
    ) -> list[SymbolData]:
        """Find connected components in a staff region."""
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
            region, connectivity=8
        )

        min_area = int(staff.line_spacing * 2)
        max_area = int(staff.line_spacing * staff.line_spacing * 20)
        symbols = []

        for label_id in range(1, num_labels):  # skip background (0)
            x = stats[label_id, cv2.CC_STAT_LEFT]
            y = stats[label_id, cv2.CC_STAT_TOP]
            w = stats[label_id, cv2.CC_STAT_WIDTH]
            h = stats[label_id, cv2.CC_STAT_HEIGHT]
            area = stats[label_id, cv2.CC_STAT_AREA]

            if area < min_area or area > max_area:
                continue

            # Skip very wide components (likely line remnants)
            if w > image_width * 0.5:
                continue

            abs_y = staff.y_top + y
            center_y = abs_y + h // 2

            # Determine position on staff (line/space index)
            position = self._get_staff_position(center_y, staff.line_positions)

            # Extract snippet from original region
            snippet = region[y : y + h, x : x + w]

            symbols.append(
                SymbolData(
                    staff_index=staff.staff_index,
                    x=x,
                    y=abs_y,
                    width=w,
                    height=h,
                    snippet=snippet.copy(),
                    position_on_staff=position,
                )
            )

        return symbols

    @staticmethod
    def _get_staff_position(center_y: int, line_positions: list[int]) -> int:
        """Map a y-coordinate to a staff position index.

        Lines are even indices (0, 2, 4, 6, 8), spaces are odd (1, 3, 5, 7).
        Position 0 = top line, position 8 = bottom line.
        Negative = above staff, >8 = below staff.
        """
        if not line_positions:
            return 0

        spacing = (line_positions[-1] - line_positions[0]) / 4.0
        half_space = spacing / 2.0

        for i, line_y in enumerate(line_positions):
            if abs(center_y - line_y) < half_space:
                return i * 2  # on a line

        # Check spaces between lines
        for i in range(len(line_positions) - 1):
            mid = (line_positions[i] + line_positions[i + 1]) / 2.0
            if abs(center_y - mid) < half_space:
                return i * 2 + 1  # in a space

        # Above or below staff
        if center_y < line_positions[0]:
            return -1
        return 9
```

- [ ] **Step 5: Run tests**

Run: `cd /workspaces/mv_hofki && python -m pytest tests/backend/test_pipeline_stages.py -v`
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add src/backend/mv_hofki/services/scanner/stages/staff_removal.py src/backend/mv_hofki/services/scanner/stages/segmentation.py tests/backend/test_pipeline_stages.py
git commit -m "feat(scanner): implement staff removal and symbol segmentation stages"
```

---

### Task 12: Implement matching stage

**Files:**
- Create: `src/backend/mv_hofki/services/scanner/stages/matching.py`
- Modify: `tests/backend/test_pipeline_stages.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/backend/test_pipeline_stages.py`:

```python
def test_matching_computes_features():
    from mv_hofki.services.scanner.stages.matching import MatchingStage

    # Create a simple symbol snippet
    snippet = np.zeros((20, 15), dtype=np.uint8)
    cv2.circle(snippet, (7, 10), 5, 255, -1)

    stage = MatchingStage(variant_images=[], variant_template_ids=[])
    features = stage.compute_features(snippet)

    assert "hu_moments" in features
    assert "aspect_ratio" in features
    assert "fill_density" in features
    assert len(features["hu_moments"]) == 7


def test_matching_finds_best_match():
    from mv_hofki.services.scanner.stages.matching import MatchingStage

    # Create a "library" variant — a black circle
    variant = np.zeros((20, 15), dtype=np.uint8)
    cv2.circle(variant, (7, 10), 5, 255, -1)

    # Create a query snippet — same circle
    query = np.zeros((20, 15), dtype=np.uint8)
    cv2.circle(query, (7, 10), 5, 255, -1)

    stage = MatchingStage(
        variant_images=[variant],
        variant_template_ids=[42],
    )
    template_id, confidence, alternatives = stage.match_snippet(query)

    assert template_id == 42
    assert confidence > 0.8
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /workspaces/mv_hofki && python -m pytest tests/backend/test_pipeline_stages.py::test_matching_computes_features -v`
Expected: FAIL

- [ ] **Step 3: Implement MatchingStage**

Create `src/backend/mv_hofki/services/scanner/stages/matching.py`:

```python
"""Symbol matching stage: compare detected regions against library."""

from __future__ import annotations

import cv2
import numpy as np

from mv_hofki.services.scanner.stages.base import PipelineContext, ProcessingStage

# Confidence thresholds
HIGH_CONFIDENCE = 0.85
LOW_CONFIDENCE = 0.40


class MatchingStage(ProcessingStage):
    """Compare extracted symbol snippets against library variants."""

    name = "matching"

    def __init__(
        self,
        variant_images: list[np.ndarray],
        variant_template_ids: list[int],
    ) -> None:
        self._variant_images = variant_images
        self._variant_template_ids = variant_template_ids
        self._variant_features: list[dict] | None = None

    def process(self, ctx: PipelineContext) -> PipelineContext:
        self._ensure_features()

        for symbol in ctx.symbols:
            if symbol.snippet is None:
                continue
            template_id, confidence, alternatives = self.match_snippet(
                symbol.snippet
            )
            symbol.matched_template_id = template_id
            symbol.confidence = confidence
            symbol.alternatives = alternatives

        return ctx

    def validate(self, ctx: PipelineContext) -> bool:
        return len(ctx.symbols) > 0

    def match_snippet(
        self, snippet: np.ndarray
    ) -> tuple[int | None, float, list[tuple[int, float]]]:
        """Match a snippet against all library variants.

        Returns (best_template_id, confidence, [(template_id, score), ...]).
        """
        self._ensure_features()

        if not self._variant_features:
            return None, 0.0, []

        query_features = self.compute_features(snippet)
        scores: list[tuple[int, float]] = []

        for i, variant_feat in enumerate(self._variant_features):
            score = self._compare_features(query_features, variant_feat)
            template_id = self._variant_template_ids[i]
            scores.append((template_id, score))

        # Aggregate by template_id (take max score per template)
        template_scores: dict[int, float] = {}
        for tid, score in scores:
            if tid not in template_scores or score > template_scores[tid]:
                template_scores[tid] = score

        ranked = sorted(template_scores.items(), key=lambda x: x[1], reverse=True)

        if not ranked or ranked[0][1] < LOW_CONFIDENCE:
            return None, ranked[0][1] if ranked else 0.0, ranked[:5]

        return ranked[0][0], ranked[0][1], ranked[:5]

    @staticmethod
    def compute_features(snippet: np.ndarray) -> dict:
        """Compute feature vector for a symbol snippet."""
        if len(snippet.shape) == 3:
            snippet = cv2.cvtColor(snippet, cv2.COLOR_BGR2GRAY)

        h, w = snippet.shape
        aspect_ratio = w / max(h, 1)
        fill_density = np.sum(snippet > 128) / max(h * w, 1)

        # Hu moments — shape-based, scale/rotation invariant
        moments = cv2.moments(snippet)
        hu = cv2.HuMoments(moments).flatten()
        # Log-transform for better comparison
        hu_log = [-1 * np.sign(h) * np.log10(abs(h) + 1e-10) for h in hu]

        return {
            "hu_moments": hu_log,
            "aspect_ratio": float(aspect_ratio),
            "fill_density": float(fill_density),
        }

    def _ensure_features(self) -> None:
        """Compute features for library variants if not already done."""
        if self._variant_features is not None:
            return
        self._variant_features = [
            self.compute_features(img) for img in self._variant_images
        ]

    @staticmethod
    def _compare_features(a: dict, b: dict) -> float:
        """Compare two feature vectors, return similarity score 0-1."""
        # Hu moment distance (weighted heavily)
        hu_a = np.array(a["hu_moments"])
        hu_b = np.array(b["hu_moments"])
        hu_dist = np.sqrt(np.sum((hu_a - hu_b) ** 2))
        hu_score = max(0, 1 - hu_dist / 20.0)

        # Aspect ratio similarity
        ar_diff = abs(a["aspect_ratio"] - b["aspect_ratio"])
        ar_score = max(0, 1 - ar_diff / 2.0)

        # Fill density similarity
        fd_diff = abs(a["fill_density"] - b["fill_density"])
        fd_score = max(0, 1 - fd_diff)

        # Weighted combination
        return hu_score * 0.6 + ar_score * 0.2 + fd_score * 0.2
```

- [ ] **Step 4: Run tests**

Run: `cd /workspaces/mv_hofki && python -m pytest tests/backend/test_pipeline_stages.py -v`
Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add src/backend/mv_hofki/services/scanner/stages/matching.py tests/backend/test_pipeline_stages.py
git commit -m "feat(scanner): implement symbol matching stage with Hu moments"
```

---

### Task 13: Implement MusicXML export

**Files:**
- Create: `src/backend/mv_hofki/services/scanner/export/__init__.py`
- Create: `src/backend/mv_hofki/services/scanner/export/musicxml.py`
- Create: `tests/backend/test_musicxml_export.py`

- [ ] **Step 1: Write failing tests**

Create `tests/backend/test_musicxml_export.py`:

```python
"""Tests for MusicXML export."""

import xml.etree.ElementTree as ET

import pytest

from mv_hofki.services.scanner.export.musicxml import generate_musicxml


def test_generate_empty_part():
    xml_str = generate_musicxml(
        part_name="1. Flügelhorn",
        clef="treble",
        time_signature="4/4",
        key_signature="0",
        measures=[],
    )
    root = ET.fromstring(xml_str)
    assert root.tag == "score-partwise"
    part_name_el = root.find(".//part-name")
    assert part_name_el is not None
    assert part_name_el.text == "1. Flügelhorn"


def test_generate_single_measure():
    measures = [
        [
            {"type": "note", "pitch": "C", "octave": 4, "duration": "quarter"},
            {"type": "note", "pitch": "D", "octave": 4, "duration": "quarter"},
            {"type": "note", "pitch": "E", "octave": 4, "duration": "quarter"},
            {"type": "note", "pitch": "F", "octave": 4, "duration": "quarter"},
        ]
    ]
    xml_str = generate_musicxml(
        part_name="Test",
        clef="treble",
        time_signature="4/4",
        key_signature="0",
        measures=measures,
    )
    root = ET.fromstring(xml_str)
    notes = root.findall(".//note")
    assert len(notes) == 4

    # Check first note is C4
    pitch = notes[0].find("pitch")
    assert pitch.find("step").text == "C"
    assert pitch.find("octave").text == "4"


def test_generate_with_rests():
    measures = [
        [
            {"type": "note", "pitch": "C", "octave": 4, "duration": "quarter"},
            {"type": "rest", "duration": "quarter"},
            {"type": "note", "pitch": "E", "octave": 4, "duration": "half"},
        ]
    ]
    xml_str = generate_musicxml(
        part_name="Test",
        clef="treble",
        time_signature="4/4",
        key_signature="0",
        measures=measures,
    )
    root = ET.fromstring(xml_str)
    rests = root.findall(".//rest")
    assert len(rests) == 1


def test_generate_bass_clef():
    xml_str = generate_musicxml(
        part_name="Posaune",
        clef="bass",
        time_signature="4/4",
        key_signature="0",
        measures=[],
    )
    root = ET.fromstring(xml_str)
    sign = root.find(".//sign")
    assert sign.text == "F"
    line = root.find(".//clef/line")
    assert line.text == "4"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /workspaces/mv_hofki && python -m pytest tests/backend/test_musicxml_export.py -v`
Expected: FAIL

- [ ] **Step 3: Implement MusicXML generator**

Create `src/backend/mv_hofki/services/scanner/export/__init__.py` (empty file).

Create `src/backend/mv_hofki/services/scanner/export/musicxml.py`:

```python
"""MusicXML generation from detected and verified symbols."""

from __future__ import annotations

import xml.etree.ElementTree as ET

DURATION_MAP = {
    "whole": ("whole", 16),
    "half": ("half", 8),
    "quarter": ("quarter", 4),
    "eighth": ("eighth", 2),
    "sixteenth": ("16th", 1),
}

CLEF_MAP = {
    "treble": ("G", "2"),
    "bass": ("F", "4"),
}


def generate_musicxml(
    *,
    part_name: str,
    clef: str,
    time_signature: str,
    key_signature: str,
    measures: list[list[dict]],
) -> str:
    """Generate a MusicXML string from structured measure data.

    Each measure is a list of dicts with keys:
    - type: "note" | "rest"
    - pitch: str (e.g. "C", "D") — only for notes
    - octave: int — only for notes
    - duration: str (e.g. "quarter", "half")
    - alter: int (optional, -1=flat, 1=sharp)
    """
    root = ET.Element("score-partwise", version="4.0")

    # Part list
    part_list = ET.SubElement(root, "part-list")
    score_part = ET.SubElement(part_list, "score-part", id="P1")
    pn = ET.SubElement(score_part, "part-name")
    pn.text = part_name

    # Part
    part = ET.SubElement(root, "part", id="P1")

    # Parse time signature
    beats, beat_type = time_signature.split("/") if "/" in time_signature else ("4", "4")

    for measure_num, measure_data in enumerate(measures, start=1):
        measure = ET.SubElement(part, "measure", number=str(measure_num))

        # Attributes on first measure
        if measure_num == 1:
            attributes = ET.SubElement(measure, "attributes")
            div = ET.SubElement(attributes, "divisions")
            div.text = "4"

            key = ET.SubElement(attributes, "key")
            fifths = ET.SubElement(key, "fifths")
            fifths.text = str(key_signature)

            time_el = ET.SubElement(attributes, "time")
            beats_el = ET.SubElement(time_el, "beats")
            beats_el.text = beats
            beat_type_el = ET.SubElement(time_el, "beat-type")
            beat_type_el.text = beat_type

            clef_sign, clef_line = CLEF_MAP.get(clef, ("G", "2"))
            clef_el = ET.SubElement(attributes, "clef")
            sign_el = ET.SubElement(clef_el, "sign")
            sign_el.text = clef_sign
            line_el = ET.SubElement(clef_el, "line")
            line_el.text = clef_line

        # Notes and rests
        for item in measure_data:
            note_el = ET.SubElement(measure, "note")

            if item["type"] == "rest":
                ET.SubElement(note_el, "rest")
            else:
                pitch_el = ET.SubElement(note_el, "pitch")
                step = ET.SubElement(pitch_el, "step")
                step.text = item["pitch"]
                if "alter" in item and item["alter"] != 0:
                    alter = ET.SubElement(pitch_el, "alter")
                    alter.text = str(item["alter"])
                octave = ET.SubElement(pitch_el, "octave")
                octave.text = str(item["octave"])

            dur_name, dur_val = DURATION_MAP.get(
                item["duration"], ("quarter", 4)
            )
            duration = ET.SubElement(note_el, "duration")
            duration.text = str(dur_val)
            type_el = ET.SubElement(note_el, "type")
            type_el.text = dur_name

    # If no measures, add an empty first measure with attributes
    if not measures:
        measure = ET.SubElement(part, "measure", number="1")
        attributes = ET.SubElement(measure, "attributes")
        div = ET.SubElement(attributes, "divisions")
        div.text = "4"

        key = ET.SubElement(attributes, "key")
        fifths = ET.SubElement(key, "fifths")
        fifths.text = str(key_signature)

        time_el = ET.SubElement(attributes, "time")
        beats_el = ET.SubElement(time_el, "beats")
        beats_el.text = beats
        beat_type_el = ET.SubElement(time_el, "beat-type")
        beat_type_el.text = beat_type

        clef_sign, clef_line = CLEF_MAP.get(clef, ("G", "2"))
        clef_el = ET.SubElement(attributes, "clef")
        sign_el = ET.SubElement(clef_el, "sign")
        sign_el.text = clef_sign
        line_el = ET.SubElement(clef_el, "line")
        line_el.text = clef_line

    ET.indent(root)
    return ET.tostring(root, encoding="unicode", xml_declaration=True)
```

- [ ] **Step 4: Run tests**

Run: `cd /workspaces/mv_hofki && python -m pytest tests/backend/test_musicxml_export.py -v`
Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add src/backend/mv_hofki/services/scanner/export/ tests/backend/test_musicxml_export.py
git commit -m "feat(scanner): implement MusicXML export generator"
```

---

### Task 14: Create scan processing route (trigger pipeline, poll status)

**Files:**
- Create: `src/backend/mv_hofki/api/routes/scan_processing.py`
- Modify: `src/backend/mv_hofki/api/app.py`

- [ ] **Step 1: Create processing route**

Create `src/backend/mv_hofki/api/routes/scan_processing.py`:

```python
"""Scan processing API routes — trigger pipeline and poll status."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.api.deps import get_db
from mv_hofki.schemas.detected_staff import DetectedStaffRead
from mv_hofki.schemas.detected_symbol import DetectedSymbolRead, SymbolCorrectionRequest
from mv_hofki.schemas.sheet_music_scan import ScanStatusRead
from mv_hofki.services import sheet_music_scan as scan_service

router = APIRouter(prefix="/api/v1/scanner", tags=["scanner-processing"])

logger = logging.getLogger(__name__)


@router.post("/scans/{scan_id}/process", response_model=ScanStatusRead)
async def trigger_processing(scan_id: int, db: AsyncSession = Depends(get_db)):
    """Trigger the processing pipeline for a scan.

    This is a placeholder that sets the status to 'processing'.
    The actual pipeline integration will connect the stages to this endpoint.
    """
    from mv_hofki.models.sheet_music_scan import SheetMusicScan

    scan = await db.get(SheetMusicScan, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan nicht gefunden")

    if scan.status not in ("uploaded", "review", "completed"):
        raise HTTPException(status_code=409, detail="Scan wird bereits verarbeitet")

    scan.status = "processing"
    await db.commit()
    await db.refresh(scan)

    # TODO: actual pipeline execution will be added here
    # For now, just set status back to review as placeholder
    scan.status = "review"
    await db.commit()

    return ScanStatusRead(status=scan.status, current_stage=None, progress=1.0)


@router.get("/scans/{scan_id}/status", response_model=ScanStatusRead)
async def get_processing_status(scan_id: int, db: AsyncSession = Depends(get_db)):
    """Poll processing status."""
    from mv_hofki.models.sheet_music_scan import SheetMusicScan

    scan = await db.get(SheetMusicScan, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan nicht gefunden")

    return ScanStatusRead(status=scan.status)


@router.get("/scans/{scan_id}/staves", response_model=list[DetectedStaffRead])
async def get_detected_staves(scan_id: int, db: AsyncSession = Depends(get_db)):
    """Get all detected staves for a scan."""
    from sqlalchemy import select

    from mv_hofki.models.detected_staff import DetectedStaff
    from mv_hofki.models.sheet_music_scan import SheetMusicScan

    scan = await db.get(SheetMusicScan, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan nicht gefunden")

    result = await db.execute(
        select(DetectedStaff)
        .where(DetectedStaff.scan_id == scan_id)
        .order_by(DetectedStaff.staff_index)
    )
    return list(result.scalars().all())


@router.get("/scans/{scan_id}/symbols", response_model=list[DetectedSymbolRead])
async def get_detected_symbols(scan_id: int, db: AsyncSession = Depends(get_db)):
    """Get all detected symbols for a scan."""
    from sqlalchemy import select
    from sqlalchemy.orm import joinedload

    from mv_hofki.models.detected_staff import DetectedStaff
    from mv_hofki.models.detected_symbol import DetectedSymbol
    from mv_hofki.models.sheet_music_scan import SheetMusicScan

    scan = await db.get(SheetMusicScan, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan nicht gefunden")

    result = await db.execute(
        select(DetectedSymbol)
        .join(DetectedStaff)
        .where(DetectedStaff.scan_id == scan_id)
        .options(
            joinedload(DetectedSymbol.matched_symbol),
            joinedload(DetectedSymbol.corrected_symbol),
        )
        .order_by(DetectedSymbol.sequence_order)
    )
    return list(result.scalars().unique().all())


@router.put("/symbols/{symbol_id}/correct")
async def correct_symbol(
    symbol_id: int,
    data: SymbolCorrectionRequest,
    db: AsyncSession = Depends(get_db),
):
    """Correct a symbol's match — sets user_corrected_symbol_id and user_verified."""
    from mv_hofki.models.detected_symbol import DetectedSymbol

    symbol = await db.get(DetectedSymbol, symbol_id)
    if not symbol:
        raise HTTPException(status_code=404, detail="Symbol nicht gefunden")

    symbol.user_corrected_symbol_id = data.symbol_template_id
    symbol.user_verified = True
    await db.commit()
    await db.refresh(symbol)
    return {"status": "ok"}


@router.put("/symbols/{symbol_id}/verify")
async def verify_symbol(symbol_id: int, db: AsyncSession = Depends(get_db)):
    """Confirm a symbol's automatic match as correct."""
    from mv_hofki.models.detected_symbol import DetectedSymbol

    symbol = await db.get(DetectedSymbol, symbol_id)
    if not symbol:
        raise HTTPException(status_code=404, detail="Symbol nicht gefunden")

    symbol.user_verified = True
    await db.commit()
    return {"status": "ok"}
```

- [ ] **Step 2: Register router in app.py**

In `src/backend/mv_hofki/api/app.py`, add:
```python
from mv_hofki.api.routes.scan_processing import router as scan_processing_router
```
And:
```python
app.include_router(scan_processing_router)
```

- [ ] **Step 3: Run all backend tests**

Run: `cd /workspaces/mv_hofki && python -m pytest tests/backend/ -v --tb=short`
Expected: All tests pass

- [ ] **Step 4: Commit**

```bash
git add src/backend/mv_hofki/api/routes/scan_processing.py src/backend/mv_hofki/api/app.py
git commit -m "feat(scanner): add processing trigger, status polling, and symbol correction routes"
```

---

### Task 15: Wire pipeline stages into scan processing endpoint

**Files:**
- Modify: `src/backend/mv_hofki/api/routes/scan_processing.py`
- Modify: `src/backend/mv_hofki/services/sheet_music_scan.py`

- [ ] **Step 1: Create a pipeline integration service function**

Add to `src/backend/mv_hofki/services/sheet_music_scan.py` a function `run_pipeline` that:

1. Loads the scan image from disk using `cv2.imread()`
2. Loads all SymbolVariant images and their template_ids from the database
3. Builds a `Pipeline` with all stages: `PreprocessStage`, `StaveDetectionStage`, `StaffRemovalStage` (if enabled in `pipeline_config_json`), `SegmentationStage`, `MatchingStage`
4. Runs the pipeline
5. Persists results: creates `DetectedStaff` rows from `ctx.staves` and `DetectedSymbol` rows from `ctx.symbols`
6. Saves extracted snippets to disk under `data/scans/{project_id}/{part_id}/{scan_id}/snippets/`
7. Updates scan status to `"review"`

```python
async def run_pipeline(
    session: AsyncSession,
    project_id: int,
    part_id: int,
    scan_id: int,
) -> None:
    import json
    import cv2
    from mv_hofki.models.detected_staff import DetectedStaff
    from mv_hofki.models.detected_symbol import DetectedSymbol
    from mv_hofki.models.symbol_variant import SymbolVariant
    from mv_hofki.services.scanner.pipeline import Pipeline
    from mv_hofki.services.scanner.stages.base import PipelineContext
    from mv_hofki.services.scanner.stages.preprocess import PreprocessStage
    from mv_hofki.services.scanner.stages.stave_detection import StaveDetectionStage
    from mv_hofki.services.scanner.stages.staff_removal import StaffRemovalStage
    from mv_hofki.services.scanner.stages.segmentation import SegmentationStage
    from mv_hofki.services.scanner.stages.matching import MatchingStage

    scan = await get_by_id(session, project_id, part_id, scan_id)
    img_path = settings.PROJECT_ROOT / scan.image_path
    img = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise HTTPException(status_code=400, detail="Bild konnte nicht geladen werden")

    # Load symbol library variants
    from sqlalchemy import select as sa_select
    result = await session.execute(sa_select(SymbolVariant))
    variants = list(result.scalars().all())

    variant_images = []
    variant_template_ids = []
    for v in variants:
        v_path = settings.PROJECT_ROOT / v.image_path
        v_img = cv2.imread(str(v_path), cv2.IMREAD_GRAYSCALE)
        if v_img is not None:
            variant_images.append(v_img)
            variant_template_ids.append(v.template_id)

    # Build pipeline config
    config = json.loads(scan.pipeline_config_json) if scan.pipeline_config_json else {}

    stages = [
        PreprocessStage(),
        StaveDetectionStage(),
        StaffRemovalStage(),
        SegmentationStage(),
        MatchingStage(variant_images=variant_images, variant_template_ids=variant_template_ids),
    ]

    ctx = PipelineContext(image=img, config=config)
    pipeline = Pipeline(stages=stages)
    ctx = pipeline.run(ctx)

    # Clear previous detection results
    from sqlalchemy import delete as sa_delete
    staff_ids_q = sa_select(DetectedStaff.id).where(DetectedStaff.scan_id == scan_id)
    await session.execute(
        sa_delete(DetectedSymbol).where(
            DetectedSymbol.staff_id.in_(staff_ids_q)
        )
    )
    await session.execute(
        sa_delete(DetectedStaff).where(DetectedStaff.scan_id == scan_id)
    )

    # Persist detected staves
    snippet_dir = _scan_dir(project_id, part_id, scan_id) / "snippets"
    snippet_dir.mkdir(parents=True, exist_ok=True)

    for staff_data in ctx.staves:
        staff = DetectedStaff(
            scan_id=scan_id,
            staff_index=staff_data.staff_index,
            y_top=staff_data.y_top,
            y_bottom=staff_data.y_bottom,
            line_positions_json=json.dumps(staff_data.line_positions),
            line_spacing=staff_data.line_spacing,
            clef=staff_data.clef,
            key_signature=staff_data.key_signature,
            time_signature=staff_data.time_signature,
        )
        session.add(staff)
        await session.flush()

        # Persist symbols for this staff
        for sym_data in ctx.symbols:
            if sym_data.staff_index != staff_data.staff_index:
                continue

            snippet_path = None
            if sym_data.snippet is not None:
                snippet_filename = f"{sym_data.sequence_order}.png"
                snippet_file = snippet_dir / snippet_filename
                cv2.imwrite(str(snippet_file), sym_data.snippet)
                snippet_path = str(snippet_file.relative_to(settings.PROJECT_ROOT))

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
                confidence=sym_data.confidence,
                user_verified=sym_data.confidence is not None and sym_data.confidence >= 0.85,
            )
            session.add(symbol)

    # Save processed image
    if ctx.processed_image is not None:
        processed_path = _scan_dir(project_id, part_id, scan_id) / "processed.png"
        cv2.imwrite(str(processed_path), ctx.processed_image)
        scan.processed_image_path = str(processed_path.relative_to(settings.PROJECT_ROOT))

    scan.status = "review"
    await session.commit()
```

- [ ] **Step 2: Update the trigger_processing route to call run_pipeline**

In `src/backend/mv_hofki/api/routes/scan_processing.py`, replace the placeholder in `trigger_processing` with:

```python
@router.post("/scans/{scan_id}/process", response_model=ScanStatusRead)
async def trigger_processing(
    scan_id: int,
    project_id: int | None = None,
    part_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    from mv_hofki.models.sheet_music_scan import SheetMusicScan
    from mv_hofki.models.scan_part import ScanPart

    scan = await db.get(SheetMusicScan, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan nicht gefunden")

    if scan.status == "processing":
        raise HTTPException(status_code=409, detail="Scan wird bereits verarbeitet")

    # Resolve project_id and part_id from scan
    part = await db.get(ScanPart, scan.part_id)
    actual_project_id = part.project_id
    actual_part_id = part.id

    scan.status = "processing"
    await db.commit()

    try:
        await scan_service.run_pipeline(db, actual_project_id, actual_part_id, scan_id)
    except Exception:
        scan.status = "uploaded"
        await db.commit()
        raise

    await db.refresh(scan)
    return ScanStatusRead(status=scan.status, current_stage=None, progress=1.0)
```

Add the import at the top:
```python
from mv_hofki.services import sheet_music_scan as scan_service
```

- [ ] **Step 3: Add symbol correction feedback loop**

In `scan_processing.py`, update the `correct_symbol` endpoint to also create a new SymbolVariant:

```python
@router.put("/symbols/{symbol_id}/correct")
async def correct_symbol(
    symbol_id: int,
    data: SymbolCorrectionRequest,
    db: AsyncSession = Depends(get_db),
):
    from mv_hofki.models.detected_symbol import DetectedSymbol
    from mv_hofki.models.symbol_variant import SymbolVariant

    symbol = await db.get(DetectedSymbol, symbol_id)
    if not symbol:
        raise HTTPException(status_code=404, detail="Symbol nicht gefunden")

    symbol.user_corrected_symbol_id = data.symbol_template_id
    symbol.user_verified = True

    # Feedback loop: add snippet as new variant of the corrected template
    if symbol.snippet_path:
        variant = SymbolVariant(
            template_id=data.symbol_template_id,
            image_path=symbol.snippet_path,
            source="user_correction",
        )
        db.add(variant)

    await db.commit()
    return {"status": "ok"}
```

- [ ] **Step 4: Run all backend tests**

Run: `cd /workspaces/mv_hofki && python -m pytest tests/backend/ -v --tb=short`
Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add src/backend/mv_hofki/services/sheet_music_scan.py src/backend/mv_hofki/api/routes/scan_processing.py
git commit -m "feat(scanner): wire pipeline stages into processing endpoint with feedback loop"
```

---

### Task 16: Add frontend routes and NavBar entry
**Files:**
- Modify: `src/frontend/src/router.js`
- Modify: `src/frontend/src/components/NavBar.vue`

- [ ] **Step 1: Add scanner routes to router.js**

In `src/frontend/src/router.js`, add the scanner routes after the invoice route (before the settings routes):

```javascript
  {
    path: "/notenscanner",
    name: "scanner-projects",
    component: () => import("./pages/ScanProjectListPage.vue"),
  },
  {
    path: "/notenscanner/bibliothek",
    name: "symbol-library",
    component: () => import("./pages/SymbolLibraryPage.vue"),
  },
  {
    path: "/notenscanner/:id",
    name: "scanner-project-detail",
    component: () => import("./pages/ScanProjectDetailPage.vue"),
    props: (route) => ({ id: route.params.id }),
  },
  {
    path: "/notenscanner/:id/scan/:scanId",
    name: "scan-editor",
    component: () => import("./pages/ScanEditorPage.vue"),
    props: (route) => ({ projectId: route.params.id, scanId: route.params.scanId }),
  },
```

Note: `/notenscanner/bibliothek` must come before `/notenscanner/:id` to avoid being caught by the dynamic route.

- [ ] **Step 2: Add NavBar entry**

In `src/frontend/src/components/NavBar.vue`, add the "Notenscanner" link after "Rechnungen" and before the dropdown:

```html
        <RouterLink to="/notenscanner" @click="closeMenu">Notenscanner</RouterLink>
```

- [ ] **Step 3: Commit**

```bash
git add src/frontend/src/router.js src/frontend/src/components/NavBar.vue
git commit -m "feat(scanner): add frontend routes and NavBar menu entry"
```

---

### Task 17: Create ScanProjectListPage

**Files:**
- Create: `src/frontend/src/pages/ScanProjectListPage.vue`

- [ ] **Step 1: Create the project list page**

Create `src/frontend/src/pages/ScanProjectListPage.vue`:

```vue
<script setup>
import { ref, onMounted } from "vue";
import { RouterLink, useRouter } from "vue-router";
import { get, post, del } from "../lib/api.js";
import LoadingSpinner from "../components/LoadingSpinner.vue";
import ConfirmDialog from "../components/ConfirmDialog.vue";

const router = useRouter();
const projects = ref([]);
const loading = ref(true);
const showCreate = ref(false);
const newName = ref("");
const newComposer = ref("");
const confirmRef = ref(null);
const deleteTarget = ref(null);

async function fetchProjects() {
  loading.value = true;
  try {
    const data = await get("/scanner/projects");
    projects.value = data.items;
  } finally {
    loading.value = false;
  }
}

async function createProject() {
  if (!newName.value.trim()) return;
  const project = await post("/scanner/projects", {
    name: newName.value.trim(),
    composer: newComposer.value.trim() || null,
  });
  showCreate.value = false;
  newName.value = "";
  newComposer.value = "";
  router.push({ name: "scanner-project-detail", params: { id: project.id } });
}

function confirmDelete(project) {
  deleteTarget.value = project;
  confirmRef.value.open();
}

async function deleteProject() {
  if (!deleteTarget.value) return;
  await del(`/scanner/projects/${deleteTarget.value.id}`);
  deleteTarget.value = null;
  await fetchProjects();
}

onMounted(fetchProjects);
</script>

<template>
  <div>
    <div class="page-header">
      <h1>Scan-Projekte</h1>
      <button class="btn btn-primary" @click="showCreate = true">+ Neues Projekt</button>
    </div>

    <LoadingSpinner v-if="loading" />

    <div v-else-if="projects.length === 0" class="empty-state">
      <p>Noch keine Scan-Projekte vorhanden.</p>
      <button class="btn btn-primary" @click="showCreate = true">Erstes Projekt erstellen</button>
    </div>

    <div v-else class="project-list">
      <RouterLink
        v-for="p in projects"
        :key="p.id"
        :to="{ name: 'scanner-project-detail', params: { id: p.id } }"
        class="project-card"
      >
        <div class="project-info">
          <strong>{{ p.name }}</strong>
          <span v-if="p.composer" class="composer">{{ p.composer }}</span>
        </div>
        <button
          class="btn btn-danger btn-sm"
          @click.prevent="confirmDelete(p)"
        >
          Löschen
        </button>
      </RouterLink>
    </div>

    <!-- Create dialog -->
    <div v-if="showCreate" class="modal-backdrop" @click.self="showCreate = false">
      <div class="modal">
        <h2>Neues Scan-Projekt</h2>
        <label>
          Name des Stücks
          <input v-model="newName" type="text" placeholder="z.B. Böhmischer Traum" />
        </label>
        <label>
          Komponist (optional)
          <input v-model="newComposer" type="text" placeholder="z.B. J. Brunner" />
        </label>
        <div class="modal-actions">
          <button class="btn" @click="showCreate = false">Abbrechen</button>
          <button class="btn btn-primary" @click="createProject" :disabled="!newName.trim()">
            Erstellen
          </button>
        </div>
      </div>
    </div>

    <ConfirmDialog
      ref="confirmRef"
      title="Projekt löschen"
      :message="`'${deleteTarget?.name}' und alle zugehörigen Scans wirklich löschen?`"
      @confirm="deleteProject"
    />
  </div>
</template>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
}

.project-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.project-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 1.25rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  transition: background var(--transition);
}

.project-card:hover {
  background: var(--color-bg-soft);
}

.project-info {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.composer {
  color: var(--color-muted);
  font-size: 0.9rem;
}

.empty-state {
  text-align: center;
  padding: 3rem 1rem;
  color: var(--color-muted);
}

.empty-state .btn {
  margin-top: 1rem;
}

.modal-backdrop {
  position: fixed;
  inset: 0;
  background: var(--color-overlay);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 500;
}

.modal {
  background: var(--color-bg);
  border-radius: var(--radius);
  padding: 1.5rem;
  width: 100%;
  max-width: 400px;
}

.modal h2 {
  margin-bottom: 1rem;
}

.modal label {
  display: block;
  margin-bottom: 1rem;
  font-size: 0.9rem;
  color: var(--color-muted);
}

.modal input {
  display: block;
  width: 100%;
  margin-top: 0.25rem;
  padding: 0.5rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  background: var(--color-bg);
  color: var(--color-text);
}

.modal-actions {
  display: flex;
  gap: 0.5rem;
  justify-content: flex-end;
}
</style>
```

- [ ] **Step 2: Verify frontend builds**

Run: `cd /workspaces/mv_hofki/src/frontend && npx vite build`
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
git add src/frontend/src/pages/ScanProjectListPage.vue
git commit -m "feat(scanner): add ScanProjectListPage with create/delete"
```

---

### Task 18: Create ScanProjectDetailPage

**Files:**
- Create: `src/frontend/src/pages/ScanProjectDetailPage.vue`

- [ ] **Step 1: Create the project detail page**

Create `src/frontend/src/pages/ScanProjectDetailPage.vue` — this page shows parts and their scans. It should support:
- Displaying the project name and composer
- Adding/removing parts (with part_name and optional clef_hint)
- Uploading scans to each part via file input
- Showing scan thumbnails per part with status indicators
- Navigating to the scan editor when clicking a scan
- Export button (MusicXML) — placeholder for now

This is a larger component (~300 lines). Key sections:
- Part list with inline add form
- Per-part scan thumbnails (use the stored image_path served via `/scans/`)
- File upload per part
- Status badges: uploaded (gray), processing (blue), review (orange), completed (green)
- Click scan thumbnail → navigate to scan editor

- [ ] **Step 2: Verify frontend builds**

Run: `cd /workspaces/mv_hofki/src/frontend && npx vite build`
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
git add src/frontend/src/pages/ScanProjectDetailPage.vue
git commit -m "feat(scanner): add ScanProjectDetailPage with parts and scan management"
```

---

### Task 19: Create ScanEditorPage (main workspace)

**Files:**
- Create: `src/frontend/src/pages/ScanEditorPage.vue`
- Create: `src/frontend/src/components/ScanCanvas.vue`
- Create: `src/frontend/src/components/SymbolPanel.vue`
- Create: `src/frontend/src/components/ImageAdjustBar.vue`

- [ ] **Step 1: Create ImageAdjustBar component**

Create `src/frontend/src/components/ImageAdjustBar.vue` — toolbar with:
- Brightness slider (-50 to +50, default 0)
- Contrast slider (0.5 to 2.0, default 1.0)
- Rotation buttons (±90 degrees)
- "Analyse starten" button (emits `analyze` event)
- Emits `adjust` with {brightness, contrast, rotation}

- [ ] **Step 2: Create ScanCanvas component**

Create `src/frontend/src/components/ScanCanvas.vue` — the main image display with:
- Loads scan image onto a canvas element
- Applies brightness/contrast adjustments client-side via Canvas filters
- Draws detection overlays (staff outlines, symbol bounding boxes)
- Color codes symbols: green (≥0.85), orange (0.40-0.84), red (<0.40)
- Clicking a symbol emits `select-symbol` with the symbol data
- Props: `imagePath`, `staves`, `symbols`, `adjustments`, `selectedSymbolId`

- [ ] **Step 3: Create SymbolPanel component**

Create `src/frontend/src/components/SymbolPanel.vue` — right sidebar with:
- Selected symbol's extracted snippet image
- Matched template name and confidence
- Top-N alternatives list with confidence scores
- "Bestätigen" button (verify current match)
- "Korrigieren" button (pick alternative or browse library)
- Props: `symbol`, emits: `verify`, `correct`

- [ ] **Step 4: Create ScanEditorPage**

Create `src/frontend/src/pages/ScanEditorPage.vue` — main workspace that:
- Props: `projectId`, `scanId`
- Fetches scan data, staves, and symbols from API
- Layout: toolbar top, canvas left (~75%), symbol panel right (~25%)
- Status bar at bottom showing progress
- "Analyse starten" triggers `POST /api/v1/scanner/scans/{scanId}/process`
- Polls status during processing
- Symbol selection/correction calls verify/correct endpoints
- "Bestätigen & Exportieren" button when all symbols verified

- [ ] **Step 5: Verify frontend builds**

Run: `cd /workspaces/mv_hofki/src/frontend && npx vite build`
Expected: Build succeeds

- [ ] **Step 6: Commit**

```bash
git add src/frontend/src/pages/ScanEditorPage.vue src/frontend/src/components/ScanCanvas.vue src/frontend/src/components/SymbolPanel.vue src/frontend/src/components/ImageAdjustBar.vue
git commit -m "feat(scanner): add ScanEditorPage with canvas, symbol panel, and adjust toolbar"
```

---

### Task 20: Create SymbolLibraryPage

**Files:**
- Create: `src/frontend/src/pages/SymbolLibraryPage.vue`
- Create: `src/frontend/src/components/SymbolCard.vue`

- [ ] **Step 1: Create SymbolCard component**

Create `src/frontend/src/components/SymbolCard.vue` — card showing:
- Symbol display_name
- Category badge
- Variant count
- Click to expand/view variants
- Props: `template`

- [ ] **Step 2: Create SymbolLibraryPage**

Create `src/frontend/src/pages/SymbolLibraryPage.vue` — browse all templates:
- Category filter tabs (Alle, Noten, Pausen, Vorzeichen, Schlüssel, Taktarten, Taktstriche, Dynamik, Verzierungen, Sonstige)
- Grid of SymbolCard components
- Pagination
- Fetches from `GET /api/v1/scanner/library/templates?category=...`

- [ ] **Step 3: Verify frontend builds**

Run: `cd /workspaces/mv_hofki/src/frontend && npx vite build`
Expected: Build succeeds

- [ ] **Step 4: Commit**

```bash
git add src/frontend/src/pages/SymbolLibraryPage.vue src/frontend/src/components/SymbolCard.vue
git commit -m "feat(scanner): add SymbolLibraryPage with category filter and grid"
```

---

### Task 21: Run all tests and lint, final verification

**Files:** None (verification only)

- [ ] **Step 1: Run backend tests**

Run: `cd /workspaces/mv_hofki && python -m pytest tests/backend/ -v`
Expected: All tests pass

- [ ] **Step 2: Run frontend build**

Run: `cd /workspaces/mv_hofki/src/frontend && npx vite build`
Expected: Build succeeds

- [ ] **Step 3: Run linters**

Run: `cd /workspaces/mv_hofki && pre-commit run --all-files`
Expected: All checks pass

- [ ] **Step 4: Run frontend tests if any exist**

Run: `cd /workspaces/mv_hofki/src/frontend && npx vitest run`
Expected: Tests pass (or no tests yet for new components)

- [ ] **Step 5: Final commit if lint fixes needed**

```bash
git add -A
git commit -m "chore: lint fixes for scanner feature"
```
