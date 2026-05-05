# Phase 2: Multi-Category Inventory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend inventory from instruments-only to four categories (Instruments, Clothing, Sheet Music, General Items) with shared base table and category-specific detail tables.

**Architecture:** Shared `inventory_item` base table with 1:1 detail tables per category. Existing images, invoices, and loans reference `inventory_item` instead of `instrument`. Per-category inventory number sequences with prefixes (I-001, K-001, N-001, A-001).

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async, Alembic, Vue 3, Pydantic v2

**Spec:** `docs/superpowers/specs/2026-03-19-inventar-phase2-kategorien-design.md`

**E2E tests:** Out of scope for this plan. Will be addressed separately.

---

## File Structure

### New backend files
- `src/backend/mv_hofki/models/inventory_item.py` — InventoryItem base model
- `src/backend/mv_hofki/models/instrument_detail.py` — InstrumentDetail 1:1 model
- `src/backend/mv_hofki/models/clothing_detail.py` — ClothingDetail 1:1 model
- `src/backend/mv_hofki/models/clothing_type.py` — ClothingType lookup model
- `src/backend/mv_hofki/models/sheet_music_detail.py` — SheetMusicDetail 1:1 model
- `src/backend/mv_hofki/models/sheet_music_genre.py` — SheetMusicGenre lookup model
- `src/backend/mv_hofki/models/general_item_detail.py` — GeneralItemDetail 1:1 model
- `src/backend/mv_hofki/models/general_item_type.py` — GeneralItemType lookup model
- `src/backend/mv_hofki/models/item_image.py` — ItemImage (replaces InstrumentImage)
- `src/backend/mv_hofki/models/item_invoice.py` — ItemInvoice (replaces InstrumentInvoice)
- `src/backend/mv_hofki/schemas/inventory_item.py` — All item schemas (create/update/read per category)
- `src/backend/mv_hofki/schemas/clothing_type.py` — ClothingType schemas
- `src/backend/mv_hofki/schemas/sheet_music_genre.py` — SheetMusicGenre schemas
- `src/backend/mv_hofki/schemas/general_item_type.py` — GeneralItemType schemas
- `src/backend/mv_hofki/schemas/item_image.py` — ItemImage schemas
- `src/backend/mv_hofki/schemas/item_invoice.py` — ItemInvoice schemas
- `src/backend/mv_hofki/services/inventory_item.py` — Generic item CRUD service
- `src/backend/mv_hofki/services/item_image.py` — Image service (replaces instrument_image)
- `src/backend/mv_hofki/services/item_invoice.py` — Invoice service (replaces instrument_invoice)
- `src/backend/mv_hofki/services/clothing_type.py` — ClothingType CRUD service
- `src/backend/mv_hofki/services/sheet_music_genre.py` — SheetMusicGenre CRUD service
- `src/backend/mv_hofki/services/general_item_type.py` — GeneralItemType CRUD service
- `src/backend/mv_hofki/api/routes/items.py` — Item CRUD routes
- `src/backend/mv_hofki/api/routes/item_images.py` — Item image routes
- `src/backend/mv_hofki/api/routes/item_invoices.py` — Item invoice routes
- `src/backend/mv_hofki/api/routes/clothing_types.py` — ClothingType CRUD routes
- `src/backend/mv_hofki/api/routes/sheet_music_genres.py` — SheetMusicGenre CRUD routes
- `src/backend/mv_hofki/api/routes/general_item_types.py` — GeneralItemType CRUD routes
- `tests/backend/test_items.py` — Item CRUD tests (all categories)
- `tests/backend/test_item_images.py` — Item image tests
- `tests/backend/test_item_invoices.py` — Item invoice tests
- `tests/backend/test_clothing_types.py` — ClothingType CRUD tests
- `tests/backend/test_sheet_music_genres.py` — SheetMusicGenre CRUD tests
- `tests/backend/test_general_item_types.py` — GeneralItemType CRUD tests

### Modified backend files
- `src/backend/mv_hofki/models/__init__.py` — Update exports
- `src/backend/mv_hofki/db/seed.py` — Add new lookup seed data
- `src/backend/mv_hofki/api/app.py` — Register new routers, remove old ones
- `src/backend/mv_hofki/models/loan.py` — FK → inventory_item, `item` relationship replaces `instrument`
- `src/backend/mv_hofki/schemas/loan.py` — `instrument_id` → `item_id`, `instrument` → `item` in LoanRead
- `src/backend/mv_hofki/services/loan.py` — Use `item_id`, `joinedload(Loan.item)`, category validation
- `src/backend/mv_hofki/api/routes/loans.py` — Update param names
- `src/backend/mv_hofki/services/dashboard.py` — Multi-category stats
- `src/backend/mv_hofki/schemas/dashboard.py` — Updated stats schema
- `tests/backend/test_loans.py` — Update to use item_id
- `tests/backend/test_dashboard.py` — Update for multi-category

### Deleted backend files
- `src/backend/mv_hofki/models/instrument.py`
- `src/backend/mv_hofki/models/instrument_image.py`
- `src/backend/mv_hofki/models/instrument_invoice.py`
- `src/backend/mv_hofki/schemas/instrument.py`
- `src/backend/mv_hofki/schemas/instrument_image.py`
- `src/backend/mv_hofki/schemas/instrument_invoice.py`
- `src/backend/mv_hofki/services/instrument.py`
- `src/backend/mv_hofki/services/instrument_image.py`
- `src/backend/mv_hofki/services/instrument_invoice.py`
- `src/backend/mv_hofki/api/routes/instruments.py`
- `src/backend/mv_hofki/api/routes/instrument_images.py`
- `src/backend/mv_hofki/api/routes/instrument_invoices.py`
- `tests/backend/test_instruments.py`
- `tests/backend/test_instrument_images.py`

### New frontend files
- `src/frontend/src/pages/ItemListPage.vue` — Generic list page (replaces InstrumentListPage)
- `src/frontend/src/pages/ItemFormPage.vue` — Generic create/edit form (replaces InstrumentFormPage)
- `src/frontend/src/pages/ItemDetailPage.vue` — Generic detail page (replaces InstrumentDetailPage)
- `src/frontend/src/pages/ClothingTypeListPage.vue` — Settings page
- `src/frontend/src/pages/SheetMusicGenreListPage.vue` — Settings page
- `src/frontend/src/pages/GeneralItemTypeListPage.vue` — Settings page
- `src/frontend/src/lib/categories.js` — Category config (prefixes, labels, fields, routes)

### Modified frontend files
- `src/frontend/src/router.js` — New routes for all categories
- `src/frontend/src/components/NavBar.vue` — Add category navigation
- `src/frontend/src/components/InvoiceModal.vue` — item_id instead of instrument_id
- `src/frontend/src/components/ImageGallery.vue` — Updated upload paths
- `src/frontend/src/pages/LoanListPage.vue` — item_id, category filter
- `src/frontend/src/pages/DashboardPage.vue` — Multi-category stats

### Deleted frontend files
- `src/frontend/src/pages/InstrumentListPage.vue`
- `src/frontend/src/pages/InstrumentFormPage.vue`
- `src/frontend/src/pages/InstrumentDetailPage.vue`
- `src/frontend/src/components/InstrumentIcon.vue`

### Alembic
- New migration in `alembic/versions/` — Drop old tables, create all new tables

---

## Task 1: Clean Slate — Drop Old DB + Migrations

**Files:**
- Delete: `data/mv_hofki.db`
- Delete: `alembic/versions/*.py`

- [ ] **Step 1: Delete the SQLite database and old migration files**

```bash
rm -f data/mv_hofki.db
rm -f alembic/versions/*.py
```

This gives us a clean slate. We'll generate a fresh initial migration after all models are defined.

- [ ] **Step 2: Commit**

```bash
git add -A
git commit -m "chore: clean slate for Phase 2 — remove old DB and migrations"
```

---

## Task 2: New Models — Base + Detail + Lookup Tables

**Files:**
- Create: `src/backend/mv_hofki/models/inventory_item.py`
- Create: `src/backend/mv_hofki/models/instrument_detail.py`
- Create: `src/backend/mv_hofki/models/clothing_detail.py`
- Create: `src/backend/mv_hofki/models/clothing_type.py`
- Create: `src/backend/mv_hofki/models/sheet_music_detail.py`
- Create: `src/backend/mv_hofki/models/sheet_music_genre.py`
- Create: `src/backend/mv_hofki/models/general_item_detail.py`
- Create: `src/backend/mv_hofki/models/general_item_type.py`
- Create: `src/backend/mv_hofki/models/item_image.py`
- Create: `src/backend/mv_hofki/models/item_invoice.py`
- Modify: `src/backend/mv_hofki/models/loan.py`
- Delete: `src/backend/mv_hofki/models/instrument.py`
- Delete: `src/backend/mv_hofki/models/instrument_image.py`
- Delete: `src/backend/mv_hofki/models/instrument_invoice.py`
- Modify: `src/backend/mv_hofki/models/__init__.py`

- [ ] **Step 1: Create `inventory_item.py` model**

```python
"""InventoryItem base ORM model."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, Float, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mv_hofki.db.base import Base

if TYPE_CHECKING:
    from mv_hofki.models.currency import Currency


class InventoryItem(Base):
    __tablename__ = "inventory_items"
    __table_args__ = (UniqueConstraint("category", "inventory_nr"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    inventory_nr: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    manufacturer: Mapped[str | None] = mapped_column(String(100))
    acquisition_date: Mapped[date | None] = mapped_column(Date)
    acquisition_cost: Mapped[float | None] = mapped_column(Float)
    currency_id: Mapped[int | None] = mapped_column(
        ForeignKey("currencies.id"), nullable=True
    )
    owner: Mapped[str] = mapped_column(String(100), nullable=False, default="MV Hofkirchen")
    notes: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )

    currency: Mapped[Currency | None] = relationship(lazy="joined")
```

- [ ] **Step 2: Create `instrument_detail.py` model**

**Note:** `construction_year` is `Integer` (not `Date` as in old model — type change per spec).

```python
"""InstrumentDetail ORM model."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mv_hofki.db.base import Base

if TYPE_CHECKING:
    from mv_hofki.models.instrument_type import InstrumentType


class InstrumentDetail(Base):
    __tablename__ = "instrument_details"

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(
        ForeignKey("inventory_items.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    instrument_type_id: Mapped[int] = mapped_column(
        ForeignKey("instrument_types.id"), nullable=False
    )
    label_addition: Mapped[str | None] = mapped_column(String(100))
    serial_nr: Mapped[str | None] = mapped_column(String(100))
    construction_year: Mapped[int | None] = mapped_column(Integer)
    distributor: Mapped[str | None] = mapped_column(String(100))
    container: Mapped[str | None] = mapped_column(String(100))
    particularities: Mapped[str | None] = mapped_column(String(500))

    instrument_type: Mapped[InstrumentType] = relationship(lazy="joined")
```

- [ ] **Step 3: Create `clothing_type.py` model**

```python
"""ClothingType lookup ORM model."""

from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from mv_hofki.db.base import Base


class ClothingType(Base):
    __tablename__ = "clothing_types"

    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
```

- [ ] **Step 4: Create `clothing_detail.py` model**

```python
"""ClothingDetail ORM model."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mv_hofki.db.base import Base

if TYPE_CHECKING:
    from mv_hofki.models.clothing_type import ClothingType


class ClothingDetail(Base):
    __tablename__ = "clothing_details"

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(
        ForeignKey("inventory_items.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    clothing_type_id: Mapped[int] = mapped_column(
        ForeignKey("clothing_types.id"), nullable=False
    )
    size: Mapped[str | None] = mapped_column(String(20))
    gender: Mapped[str | None] = mapped_column(String(10))

    clothing_type: Mapped[ClothingType] = relationship(lazy="joined")
```

- [ ] **Step 5: Create `sheet_music_genre.py` model**

```python
"""SheetMusicGenre lookup ORM model."""

from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from mv_hofki.db.base import Base


class SheetMusicGenre(Base):
    __tablename__ = "sheet_music_genres"

    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
```

- [ ] **Step 6: Create `sheet_music_detail.py` model**

```python
"""SheetMusicDetail ORM model."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mv_hofki.db.base import Base

if TYPE_CHECKING:
    from mv_hofki.models.sheet_music_genre import SheetMusicGenre


class SheetMusicDetail(Base):
    __tablename__ = "sheet_music_details"

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(
        ForeignKey("inventory_items.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    composer: Mapped[str | None] = mapped_column(String(100))
    arranger: Mapped[str | None] = mapped_column(String(100))
    difficulty: Mapped[str | None] = mapped_column(String(50))
    genre_id: Mapped[int | None] = mapped_column(
        ForeignKey("sheet_music_genres.id"), nullable=True
    )

    genre: Mapped[SheetMusicGenre | None] = relationship(lazy="joined")
```

- [ ] **Step 7: Create `general_item_type.py` model**

```python
"""GeneralItemType lookup ORM model."""

from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from mv_hofki.db.base import Base


class GeneralItemType(Base):
    __tablename__ = "general_item_types"

    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
```

- [ ] **Step 8: Create `general_item_detail.py` model**

```python
"""GeneralItemDetail ORM model."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mv_hofki.db.base import Base

if TYPE_CHECKING:
    from mv_hofki.models.general_item_type import GeneralItemType


class GeneralItemDetail(Base):
    __tablename__ = "general_item_details"

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(
        ForeignKey("inventory_items.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    general_item_type_id: Mapped[int] = mapped_column(
        ForeignKey("general_item_types.id"), nullable=False
    )

    general_item_type: Mapped[GeneralItemType] = relationship(lazy="joined")
```

- [ ] **Step 9: Create `item_image.py` model** (replaces `instrument_image.py`)

```python
"""ItemImage ORM model."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from mv_hofki.db.base import Base


class ItemImage(Base):
    __tablename__ = "item_images"

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(
        ForeignKey("inventory_items.id", ondelete="CASCADE"), nullable=False
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    is_profile: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
```

- [ ] **Step 10: Create `item_invoice.py` model** (replaces `instrument_invoice.py`)

**Note:** `invoice_nr` is scoped per item (auto-assigned as `MAX(invoice_nr) WHERE item_id = :item_id + 1`).

```python
"""ItemInvoice ORM model."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mv_hofki.db.base import Base

if TYPE_CHECKING:
    from mv_hofki.models.currency import Currency


class ItemInvoice(Base):
    __tablename__ = "item_invoices"

    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_nr: Mapped[int] = mapped_column(Integer, nullable=False)
    item_id: Mapped[int] = mapped_column(
        ForeignKey("inventory_items.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency_id: Mapped[int] = mapped_column(
        ForeignKey("currencies.id"), nullable=False
    )
    date_issued: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str | None] = mapped_column(String(500))
    invoice_issuer: Mapped[str | None] = mapped_column(String(100))
    issuer_address: Mapped[str | None] = mapped_column(String(200))
    filename: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    currency: Mapped[Currency] = relationship(lazy="joined")
```

- [ ] **Step 11: Update `loan.py` model** — change `instrument_id` to `item_id`

Replace the `instrument_id` column and `instrument` relationship:

```python
# OLD:
instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id"), nullable=False)
instrument: Mapped[Instrument] = relationship(lazy="joined")

# NEW:
item_id: Mapped[int] = mapped_column(
    ForeignKey("inventory_items.id", ondelete="CASCADE"), nullable=False
)
item: Mapped[InventoryItem] = relationship(lazy="joined")
```

Add `InventoryItem` to TYPE_CHECKING imports, remove `Instrument` import.

- [ ] **Step 12: Delete old model files**

```bash
rm src/backend/mv_hofki/models/instrument.py
rm src/backend/mv_hofki/models/instrument_image.py
rm src/backend/mv_hofki/models/instrument_invoice.py
```

- [ ] **Step 13: Update `models/__init__.py`**

```python
"""ORM models."""

from mv_hofki.models.clothing_detail import ClothingDetail
from mv_hofki.models.clothing_type import ClothingType
from mv_hofki.models.currency import Currency
from mv_hofki.models.general_item_detail import GeneralItemDetail
from mv_hofki.models.general_item_type import GeneralItemType
from mv_hofki.models.instrument_detail import InstrumentDetail
from mv_hofki.models.instrument_type import InstrumentType
from mv_hofki.models.inventory_item import InventoryItem
from mv_hofki.models.item_image import ItemImage
from mv_hofki.models.item_invoice import ItemInvoice
from mv_hofki.models.loan import Loan
from mv_hofki.models.musician import Musician
from mv_hofki.models.sheet_music_detail import SheetMusicDetail
from mv_hofki.models.sheet_music_genre import SheetMusicGenre

__all__ = [
    "ClothingDetail",
    "ClothingType",
    "Currency",
    "GeneralItemDetail",
    "GeneralItemType",
    "InstrumentDetail",
    "InstrumentType",
    "InventoryItem",
    "ItemImage",
    "ItemInvoice",
    "Loan",
    "Musician",
    "SheetMusicDetail",
    "SheetMusicGenre",
]
```

- [ ] **Step 14: Commit**

```bash
git add -A
git commit -m "feat: add Phase 2 models — inventory_item base + detail + lookup tables"
```

---

## Task 3: Update Seed Data

**Files:**
- Modify: `src/backend/mv_hofki/db/seed.py`

- [ ] **Step 1: Add new lookup seed data**

Add to `seed.py`:

```python
from mv_hofki.models.clothing_type import ClothingType
from mv_hofki.models.general_item_type import GeneralItemType
from mv_hofki.models.sheet_music_genre import SheetMusicGenre

CLOTHING_TYPES = [
    {"label": "Hut"},
    {"label": "Jacke"},
    {"label": "Hose"},
    {"label": "Weste"},
    {"label": "Schuhe"},
    {"label": "Bluse"},
    {"label": "Rock"},
    {"label": "Strümpfe"},
]

SHEET_MUSIC_GENRES = [
    {"label": "Marsch"},
    {"label": "Polka"},
    {"label": "Walzer"},
    {"label": "Konzertwerk"},
    {"label": "Kirchenmusik"},
]

GENERAL_ITEM_TYPES = [
    {"label": "Lautsprecher"},
    {"label": "Kabel"},
    {"label": "Notenständer"},
    {"label": "Mischpult"},
    {"label": "Mikrofon"},
    {"label": "Verstärker"},
]
```

Add seed blocks in `seed_data()` for each new lookup table, same pattern as existing (check if empty, then insert).

- [ ] **Step 2: Commit**

```bash
git add src/backend/mv_hofki/db/seed.py
git commit -m "feat: add seed data for clothing types, sheet music genres, general item types"
```

---

## Task 4: Generate Alembic Migration

**Files:**
- Create: `alembic/versions/<auto>_phase2_initial.py`

- [ ] **Step 1: Generate fresh initial migration**

```bash
PYTHONPATH=src/backend alembic revision --autogenerate -m "phase2 initial schema"
```

- [ ] **Step 2: Review the generated migration**

Verify it creates all new tables and doesn't reference old ones.

- [ ] **Step 3: Run the migration**

```bash
PYTHONPATH=src/backend alembic upgrade head
```

- [ ] **Step 4: Commit**

```bash
git add alembic/
git commit -m "feat: add Phase 2 alembic migration"
```

---

## Task 5: Schemas + Services + Routes — All Backend (combined to avoid dependency issues)

This task combines schemas, services, and routes into one task because tests call HTTP endpoints which require all three layers to be in place.

**Files:**
- Create: `src/backend/mv_hofki/schemas/inventory_item.py`
- Create: `src/backend/mv_hofki/schemas/clothing_type.py`
- Create: `src/backend/mv_hofki/schemas/sheet_music_genre.py`
- Create: `src/backend/mv_hofki/schemas/general_item_type.py`
- Create: `src/backend/mv_hofki/schemas/item_image.py`
- Create: `src/backend/mv_hofki/schemas/item_invoice.py`
- Create: `src/backend/mv_hofki/services/inventory_item.py`
- Create: `src/backend/mv_hofki/services/item_image.py`
- Create: `src/backend/mv_hofki/services/item_invoice.py`
- Create: `src/backend/mv_hofki/services/clothing_type.py`
- Create: `src/backend/mv_hofki/services/sheet_music_genre.py`
- Create: `src/backend/mv_hofki/services/general_item_type.py`
- Create: `src/backend/mv_hofki/api/routes/items.py`
- Create: `src/backend/mv_hofki/api/routes/item_images.py`
- Create: `src/backend/mv_hofki/api/routes/item_invoices.py`
- Create: `src/backend/mv_hofki/api/routes/clothing_types.py`
- Create: `src/backend/mv_hofki/api/routes/sheet_music_genres.py`
- Create: `src/backend/mv_hofki/api/routes/general_item_types.py`
- Delete: `src/backend/mv_hofki/schemas/instrument.py`
- Delete: `src/backend/mv_hofki/schemas/instrument_image.py`
- Delete: `src/backend/mv_hofki/schemas/instrument_invoice.py`
- Delete: `src/backend/mv_hofki/services/instrument.py`
- Delete: `src/backend/mv_hofki/services/instrument_image.py`
- Delete: `src/backend/mv_hofki/services/instrument_invoice.py`
- Delete: `src/backend/mv_hofki/api/routes/instruments.py`
- Delete: `src/backend/mv_hofki/api/routes/instrument_images.py`
- Delete: `src/backend/mv_hofki/api/routes/instrument_invoices.py`
- Modify: `src/backend/mv_hofki/schemas/loan.py`
- Modify: `src/backend/mv_hofki/schemas/dashboard.py`
- Modify: `src/backend/mv_hofki/services/loan.py`
- Modify: `src/backend/mv_hofki/services/dashboard.py`
- Modify: `src/backend/mv_hofki/api/routes/loans.py`
- Modify: `src/backend/mv_hofki/api/app.py`

### Step 5a: Schemas

- [ ] **Step 1: Create `schemas/inventory_item.py`**

Key schemas needed:
- `ItemCreateBase` — base fields: `label` (required), `manufacturer`, `acquisition_date`, `acquisition_cost`, `currency_id`, `owner` (default "MV Hofkirchen"), `notes`
- `InstrumentItemCreate(ItemCreateBase)` — adds `instrument_type_id` (required), `label_addition`, `serial_nr`, `construction_year: int | None` (**Note: was `date` in old schema, now `int`**), `distributor`, `container`, `particularities`. Literal `category = "instrument"`.
- `ClothingItemCreate(ItemCreateBase)` — adds `clothing_type_id` (required), `size`, `gender`. Literal `category = "clothing"`.
- `SheetMusicItemCreate(ItemCreateBase)` — adds `composer`, `arranger`, `difficulty`, `genre_id`. Literal `category = "sheet_music"`.
- `GeneralItemItemCreate(ItemCreateBase)` — adds `general_item_type_id` (required). Literal `category = "general_item"`.
- Corresponding `*Update` schemas (all fields optional)
- `ItemRead` — base read fields + `category`, `inventory_nr`, `display_nr` (computed: e.g. "I-001"), `active_loan: ActiveLoanInfo | None`, `profile_image_url: str | None`, `updated_at`
- `InstrumentItemRead(ItemRead)` — adds instrument detail fields + `instrument_type: InstrumentTypeRead`
- `ClothingItemRead(ItemRead)` — adds clothing detail fields + `clothing_type: ClothingTypeRead`
- `SheetMusicItemRead(ItemRead)` — adds sheet music detail fields + `genre: SheetMusicGenreRead | None`
- `GeneralItemItemRead(ItemRead)` — adds general item detail fields + `general_item_type: GeneralItemTypeRead`
- `ActiveLoanInfo` — same as before: `loan_id`, `musician_id`, `musician_name`, `is_extern`, `start_date`
- **Validator on base create/update:** if `acquisition_cost` is set, `currency_id` must also be set

- [ ] **Step 2: Create lookup type schemas** (`clothing_type.py`, `sheet_music_genre.py`, `general_item_type.py`)

Same pattern as existing `instrument_type.py` schemas: `*Create` (label required), `*Update` (label optional), `*Read` (id + label, `from_attributes`).

- [ ] **Step 3: Create `schemas/item_image.py`** (same fields as old `instrument_image.py` but with `item_id` instead of `instrument_id`)

- [ ] **Step 4: Create `schemas/item_invoice.py`** (same fields as old `instrument_invoice.py` but with `item_id` instead of `instrument_id`)

- [ ] **Step 5: Update `schemas/loan.py`**

- `LoanCreate`: rename `instrument_id` → `item_id`
- `LoanRead`: replace `instrument: InstrumentRead` with `item: ItemRead` (use base `ItemRead`, not category-specific)
- `LoanUpdate`: rename `instrument_id` → `item_id` if present
- All `joinedload` references in service need updating accordingly

- [ ] **Step 6: Update `schemas/dashboard.py`** — add `items_by_category: list[ItemsByCategory]` with fields `category`, `label`, `count`

- [ ] **Step 7: Delete old schema files**

```bash
rm src/backend/mv_hofki/schemas/instrument.py
rm src/backend/mv_hofki/schemas/instrument_image.py
rm src/backend/mv_hofki/schemas/instrument_invoice.py
```

- [ ] **Step 8: Commit schemas**

```bash
git add -A
git commit -m "feat: add Phase 2 schemas for multi-category items"
```

### Step 5b: Services

- [ ] **Step 9: Implement `inventory_item.py` service**

Key constants and functions:
- `CATEGORY_PREFIXES = {"instrument": "I", "clothing": "K", "sheet_music": "N", "general_item": "A"}`
- `LOANABLE_CATEGORIES = {"instrument", "clothing", "general_item"}`
- `INVOICEABLE_CATEGORIES = {"instrument", "clothing", "general_item"}`
- `format_display_nr(category, inventory_nr)` — returns e.g. "I-001"
- `create(session, category, data)` — create InventoryItem + detail in one transaction:
  1. Auto-assign `inventory_nr`: `MAX(inventory_nr) WHERE category = :cat + 1`
  2. On `IntegrityError` (race condition on UNIQUE constraint): retry once with fresh MAX+1
  3. **Validate:** if `acquisition_cost` is set, `currency_id` must also be set (raise 400)
  4. Create detail record in same transaction
- `get_list(session, category, search, filters, limit, offset)` — query with detail join, enrichment
- `get_by_id(session, item_id)` — fetch with detail, enrich
- `update(session, item_id, data)` — update base + detail. **Validate** cost-requires-currency.
- `delete(session, item_id)` — delete DB row (CASCADE handles detail/images/invoices/loans), then **clean up upload directories**: `shutil.rmtree(data/uploads/images/{item_id}/, ignore_errors=True)` and `shutil.rmtree(data/uploads/invoices/{item_id}/, ignore_errors=True)`
- `_enrich(session, items)` — add `active_loan` + `profile_image_url` (same pattern as old instrument service, but using `Loan.item_id` and `ItemImage.item_id`)

- [ ] **Step 10: Implement `item_image.py` service**

Same logic as old `instrument_image.py` but:
- Upload path: `data/uploads/images/{item_id}/{filename}` (was `data/uploads/instruments/{instrument_id}/`)
- Uses `item_id` instead of `instrument_id`
- Image URL: `/uploads/images/{item_id}/{filename}`

- [ ] **Step 11: Implement `item_invoice.py` service**

Same logic as old `instrument_invoice.py` but:
- Upload path: `data/uploads/invoices/{item_id}/{filename}`
- Uses `item_id` instead of `instrument_id`
- `invoice_nr` is auto-assigned per item: `MAX(invoice_nr) WHERE item_id = :item_id + 1`
- **Validates** category is in `INVOICEABLE_CATEGORIES` (raise 400 for `sheet_music`)

- [ ] **Step 12: Create lookup type services** (`clothing_type.py`, `sheet_music_genre.py`, `general_item_type.py`)

Same pattern as existing `instrument_type.py` service: `get_all`, `get_by_id`, `create`, `update`, `delete`.

- [ ] **Step 13: Update `loan.py` service**

- Replace all `instrument_id` → `item_id`
- Replace `Loan.instrument_id` → `Loan.item_id` in queries
- Replace `joinedload(Loan.instrument)` → `joinedload(Loan.item)`
- On `create`: fetch `InventoryItem` by `item_id`, validate `item.category in LOANABLE_CATEGORIES` (raise 400 for `sheet_music`)
- Active loan check: `WHERE Loan.item_id == item_id AND end_date IS NULL`

- [ ] **Step 14: Update `dashboard.py` service**

- Query `InventoryItem` grouped by `category` for totals
- Keep `instruments_by_type` (join `InstrumentDetail` → `InstrumentType`)
- Add `items_by_category` count

- [ ] **Step 15: Delete old service files**

```bash
rm src/backend/mv_hofki/services/instrument.py
rm src/backend/mv_hofki/services/instrument_image.py
rm src/backend/mv_hofki/services/instrument_invoice.py
```

- [ ] **Step 16: Commit services**

```bash
git add -A
git commit -m "feat: add Phase 2 services for multi-category items"
```

### Step 5c: Routes + App Registration

- [ ] **Step 17: Create `routes/items.py`**

```
POST   /api/v1/items              — create (category in body, discriminated by category field)
GET    /api/v1/items              — list (query params: category (required), search, limit, offset)
GET    /api/v1/items/{id}         — get by id (returns category-specific read schema)
PUT    /api/v1/items/{id}         — update
DELETE /api/v1/items/{id}         — delete
```

The create endpoint inspects the `category` field in the request body to determine which schema to validate against. Use a dict mapping or `Discriminator` approach.

- [ ] **Step 18: Create `routes/item_images.py`**

```
GET    /api/v1/items/{item_id}/images              — list
POST   /api/v1/items/{item_id}/images              — upload
PUT    /api/v1/items/{item_id}/images/{id}/profile  — set profile
DELETE /api/v1/items/{item_id}/images/{id}          — delete
```

- [ ] **Step 19: Create `routes/item_invoices.py`**

```
GET    /api/v1/items/{item_id}/invoices              — list
GET    /api/v1/items/{item_id}/invoices/{id}         — get
POST   /api/v1/items/{item_id}/invoices              — create
PUT    /api/v1/items/{item_id}/invoices/{id}         — update
POST   /api/v1/items/{item_id}/invoices/{id}/file    — upload/replace file
DELETE /api/v1/items/{item_id}/invoices/{id}/file    — delete file
DELETE /api/v1/items/{item_id}/invoices/{id}         — delete
```

- [ ] **Step 20: Create lookup type routes** (`clothing_types.py`, `sheet_music_genres.py`, `general_item_types.py`)

Same pattern as existing `instrument_types.py` routes:
```
GET    /api/v1/clothing-types          (etc.)
POST   /api/v1/clothing-types
GET    /api/v1/clothing-types/{id}
PUT    /api/v1/clothing-types/{id}
DELETE /api/v1/clothing-types/{id}
```

Each route file calls its corresponding service.

- [ ] **Step 21: Update `routes/loans.py`** — rename `instrument_id` params to `item_id`

- [ ] **Step 22: Delete old route files**

```bash
rm src/backend/mv_hofki/api/routes/instruments.py
rm src/backend/mv_hofki/api/routes/instrument_images.py
rm src/backend/mv_hofki/api/routes/instrument_invoices.py
```

- [ ] **Step 23: Update `app.py`** — remove old routers, add new ones

Replace instrument router imports with:
```python
from mv_hofki.api.routes.items import router as items_router
from mv_hofki.api.routes.item_images import router as item_images_router
from mv_hofki.api.routes.item_invoices import router as item_invoices_router
from mv_hofki.api.routes.clothing_types import router as clothing_types_router
from mv_hofki.api.routes.sheet_music_genres import router as sheet_music_genres_router
from mv_hofki.api.routes.general_item_types import router as general_item_types_router
```

Register all new routers, remove old `instruments_router`, `instrument_images_router`, `instrument_invoices_router`.

- [ ] **Step 24: Commit routes**

```bash
git add -A
git commit -m "feat: add Phase 2 API routes — items, images, invoices, lookup types"
```

---

## Task 6: Backend Tests

**Files:**
- Create: `tests/backend/test_items.py`
- Create: `tests/backend/test_item_images.py`
- Create: `tests/backend/test_item_invoices.py`
- Create: `tests/backend/test_clothing_types.py`
- Create: `tests/backend/test_sheet_music_genres.py`
- Create: `tests/backend/test_general_item_types.py`
- Modify: `tests/backend/test_loans.py`
- Modify: `tests/backend/test_dashboard.py`
- Delete: `tests/backend/test_instruments.py`
- Delete: `tests/backend/test_instrument_images.py`

- [ ] **Step 1: Write `test_items.py`**

Fixtures:
- `setup_instrument_refs(client)` — creates currency + instrument type
- `setup_clothing_refs(client)` — creates currency + clothing type
- `setup_sheet_music_refs(client)` — creates sheet music genre (no currency needed)
- `setup_general_refs(client)` — creates currency + general item type
- `instrument_item(client, setup_instrument_refs)` — creates an instrument item
- Similar for each category

Tests:
- `test_create_instrument_item` — POST, verify category, inventory_nr=1, display_nr="I-001", instrument_type
- `test_create_clothing_item` — POST, verify display_nr="K-001", clothing_type, size, gender
- `test_create_sheet_music_item` — POST, verify display_nr="N-001", composer, genre
- `test_create_general_item` — POST, verify display_nr="A-001", general_item_type
- `test_inventory_nr_independent_per_category` — create 1 instrument + 1 clothing, both get nr=1
- `test_list_items_by_category` — create items in multiple categories, filter by category
- `test_list_items_search` — search across label, manufacturer
- `test_get_item_by_id` — GET specific item with detail
- `test_update_item` — PUT with partial update
- `test_delete_item` — DELETE, verify 204
- `test_cost_without_currency_fails` — POST with acquisition_cost but no currency_id → 400/422
- `test_delete_item_cleans_up_uploads` — create item, upload image, delete item, verify directory removed

- [ ] **Step 2: Run item tests**

```bash
python -m pytest tests/backend/test_items.py -v
```

- [ ] **Step 3: Write `test_item_images.py`**

Same pattern as old `test_instrument_images.py` but using `/api/v1/items/{id}/images`.

- [ ] **Step 4: Write `test_item_invoices.py`**

Tests:
- Create invoice on instrument item — success
- Create invoice on sheet music item — 400
- CRUD operations, file upload/replace/delete

- [ ] **Step 5: Write lookup type tests** (`test_clothing_types.py`, `test_sheet_music_genres.py`, `test_general_item_types.py`)

Same pattern as existing `test_instrument_types.py`.

- [ ] **Step 6: Update `test_loans.py`**

- Create items via `/api/v1/items` instead of `/api/v1/instruments`
- Use `item_id` instead of `instrument_id`
- Add test: creating loan for `sheet_music` item returns 400

- [ ] **Step 7: Update `test_dashboard.py`**

- Create items in multiple categories
- Verify `items_by_category` in response

- [ ] **Step 8: Delete old test files**

```bash
rm tests/backend/test_instruments.py
rm tests/backend/test_instrument_images.py
```

- [ ] **Step 9: Run all backend tests**

```bash
python -m pytest tests/backend/ -v
```

- [ ] **Step 10: Commit tests**

```bash
git add -A
git commit -m "feat: add Phase 2 backend tests for all categories"
```

---

## Task 7: Frontend — Category Config + Router + NavBar

**Files:**
- Create: `src/frontend/src/lib/categories.js`
- Modify: `src/frontend/src/router.js`
- Modify: `src/frontend/src/components/NavBar.vue`

- [ ] **Step 1: Create `categories.js` config**

```javascript
export const CATEGORIES = {
  instrument: {
    key: "instrument",
    prefix: "I",
    label: "Instrumente",
    labelSingular: "Instrument",
    routeBase: "/instrumente",
    apiCategory: "instrument",
    hasLoans: true,
    hasInvoices: true,
  },
  clothing: {
    key: "clothing",
    prefix: "K",
    label: "Kleidung",
    labelSingular: "Kleidung",
    routeBase: "/kleidung",
    apiCategory: "clothing",
    hasLoans: true,
    hasInvoices: true,
  },
  sheet_music: {
    key: "sheet_music",
    prefix: "N",
    label: "Noten",
    labelSingular: "Notenwerk",
    routeBase: "/noten",
    apiCategory: "sheet_music",
    hasLoans: false,
    hasInvoices: false,
  },
  general_item: {
    key: "general_item",
    prefix: "A",
    label: "Allgemein",
    labelSingular: "Gegenstand",
    routeBase: "/allgemein",
    apiCategory: "general_item",
    hasLoans: true,
    hasInvoices: true,
  },
};

export function formatDisplayNr(category, inventoryNr) {
  const cat = CATEGORIES[category];
  return `${cat.prefix}-${String(inventoryNr).padStart(3, "0")}`;
}
```

- [ ] **Step 2: Update `router.js`**

Use props functions to consistently pass `category` to all page components:

```javascript
// For each category (example: instrument):
{
  path: "/instrumente",
  name: "instrument-list",
  component: () => import("./pages/ItemListPage.vue"),
  props: () => ({ category: "instrument" }),
},
{
  path: "/instrumente/neu",
  name: "instrument-create",
  component: () => import("./pages/ItemFormPage.vue"),
  props: () => ({ category: "instrument" }),
},
{
  path: "/instrumente/:id",
  name: "instrument-detail",
  component: () => import("./pages/ItemDetailPage.vue"),
  props: (route) => ({ category: "instrument", id: route.params.id }),
},
{
  path: "/instrumente/:id/bearbeiten",
  name: "instrument-edit",
  component: () => import("./pages/ItemFormPage.vue"),
  props: (route) => ({ category: "instrument", id: route.params.id }),
},
// Repeat for /kleidung (clothing), /noten (sheet_music), /allgemein (general_item)
```

Add new settings routes:
```javascript
{ path: "/einstellungen/kleidungstypen", name: "clothing-types", component: () => import("./pages/ClothingTypeListPage.vue") },
{ path: "/einstellungen/notengenres", name: "sheet-music-genres", component: () => import("./pages/SheetMusicGenreListPage.vue") },
{ path: "/einstellungen/gegenstandstypen", name: "general-item-types", component: () => import("./pages/GeneralItemTypeListPage.vue") },
```

- [ ] **Step 3: Update NavBar**

Add category links to main nav: Instrumente, Kleidung, Noten, Allgemein. Add settings dropdown entries for Kleidungstypen, Notengenres, Gegenstandstypen.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat: add frontend category config, router, and navigation"
```

---

## Task 8: Frontend — Item List Page

**Files:**
- Create: `src/frontend/src/pages/ItemListPage.vue`
- Delete: `src/frontend/src/pages/InstrumentListPage.vue`
- Delete: `src/frontend/src/components/InstrumentIcon.vue`

- [ ] **Step 1: Create `ItemListPage.vue`**

Generic list page that receives `category` prop. Fetches from `/api/v1/items?category={category}`. Shows:
- Display number with prefix (e.g. I-001) using `formatDisplayNr()`
- Category-specific columns:
  - Instrument: Typ, Hersteller, Seriennr.
  - Clothing: Typ, Größe, Geschlecht
  - Sheet Music: Komponist, Arrangeur, Gattung
  - General: Typ
- Common columns: Bezeichnung, Eigentümer
- Status badge (Ausgeliehen/Verfügbar) only if `category.hasLoans`
- Search bar
- Table + card view toggle (persisted per category in localStorage key `viewMode_{category}`)
- Pagination (50/page)

Based on existing `InstrumentListPage.vue` patterns.

- [ ] **Step 2: Delete old pages**

```bash
rm src/frontend/src/pages/InstrumentListPage.vue
rm src/frontend/src/components/InstrumentIcon.vue
```

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "feat: add generic ItemListPage replacing InstrumentListPage"
```

---

## Task 9: Frontend — Item Form Page

**Files:**
- Create: `src/frontend/src/pages/ItemFormPage.vue`
- Delete: `src/frontend/src/pages/InstrumentFormPage.vue`

- [ ] **Step 1: Create `ItemFormPage.vue`**

Generic create/edit form with `category` and optional `id` props. Shows:
- Common fields always: label (required), manufacturer, acquisition_date, acquisition_cost + currency picker (inline), owner (default "MV Hofkirchen"), notes
- Category-specific fields rendered conditionally:
  - Instrument: instrument_type (select, required), label_addition, serial_nr, construction_year (**int input, not date**), distributor, container, particularities
  - Clothing: clothing_type (select, required), size, gender (select: Herren/Damen/leer)
  - Sheet Music: composer, arranger, difficulty, genre (select)
  - General: general_item_type (select, required)
- Fetches lookup data (types/genres) based on category from respective API endpoints
- Create: POST to `/api/v1/items` with `category` in body
- Edit: GET from `/api/v1/items/{id}`, PUT to `/api/v1/items/{id}`
- On save: navigate to detail page

Based on existing `InstrumentFormPage.vue` patterns (form layout, currency picker, error handling).

- [ ] **Step 2: Delete old page**

```bash
rm src/frontend/src/pages/InstrumentFormPage.vue
```

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "feat: add generic ItemFormPage replacing InstrumentFormPage"
```

---

## Task 10: Frontend — Item Detail Page + Component Updates

**Files:**
- Create: `src/frontend/src/pages/ItemDetailPage.vue`
- Delete: `src/frontend/src/pages/InstrumentDetailPage.vue`
- Modify: `src/frontend/src/components/ImageGallery.vue`
- Modify: `src/frontend/src/components/InvoiceModal.vue`

- [ ] **Step 1: Update `ImageGallery.vue`**

- Change prop from `instrumentId` to `itemId`
- Change fetch/upload URLs from `/api/v1/instruments/{id}/images` to `/api/v1/items/{id}/images`
- Change image URL prefix from `/uploads/instruments/` to `/uploads/images/`

- [ ] **Step 2: Update `InvoiceModal.vue`**

- Change prop from `instrumentId` to `itemId`
- Change API calls from `/api/v1/instruments/{id}/invoices` to `/api/v1/items/{id}/invoices`
- Change file URL prefix from `/uploads/invoices/` (verify current) to `/uploads/invoices/`

- [ ] **Step 3: Create `ItemDetailPage.vue`**

Generic detail page with `category` and `id` props. Shows:
- Display number + common fields (label, manufacturer, owner, acquisition info, notes)
- Category-specific detail fields rendered conditionally
- Image gallery (all categories) — `<ImageGallery :itemId="id" />`
- Invoice section (only if `CATEGORIES[category].hasInvoices`) — InvoiceModal
- Loan section (only if `CATEGORIES[category].hasLoans`):
  - Active loan status + return button
  - New loan form (musician selector + start_date)
- Loan history table
- Edit + Delete buttons

Based on existing `InstrumentDetailPage.vue`.

- [ ] **Step 4: Delete old page**

```bash
rm src/frontend/src/pages/InstrumentDetailPage.vue
```

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: add generic ItemDetailPage replacing InstrumentDetailPage"
```

---

## Task 11: Frontend — Lookup Type Pages + Updated Loan/Dashboard

**Files:**
- Create: `src/frontend/src/pages/ClothingTypeListPage.vue`
- Create: `src/frontend/src/pages/SheetMusicGenreListPage.vue`
- Create: `src/frontend/src/pages/GeneralItemTypeListPage.vue`
- Modify: `src/frontend/src/pages/LoanListPage.vue`
- Modify: `src/frontend/src/pages/DashboardPage.vue`

- [ ] **Step 1: Create lookup type pages**

Same pattern as `InstrumentTypeListPage.vue` — simple CRUD list with inline create form. Each fetches from their respective API endpoint (`/api/v1/clothing-types`, `/api/v1/sheet-music-genres`, `/api/v1/general-item-types`).

- [ ] **Step 2: Update `LoanListPage.vue`**

- Change `instrument_id` references to `item_id`
- Fetch items from `/api/v1/items?category=instrument` (and other loanable categories) instead of `/api/v1/instruments`
- Show display number with prefix in loan list (use `formatDisplayNr`)
- Item selector should only show loanable categories

- [ ] **Step 3: Update `DashboardPage.vue`**

- Show total items per category (from `items_by_category`)
- Keep instruments_by_type breakdown
- Add stat cards per category
- Update labels from "Instrumente" to category-aware

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat: add lookup type pages, update loans and dashboard for multi-category"
```

---

## Task 12: Final Cleanup + Full Test Run

**Files:**
- Clean up any remaining references to old model/route names

- [ ] **Step 1: Run all backend tests**

```bash
python -m pytest tests/backend/ -v
```

- [ ] **Step 2: Run linter**

```bash
pre-commit run --all-files
```

- [ ] **Step 3: Fix any lint errors**

- [ ] **Step 4: Restart server and frontend**

```bash
server-restart
frontend-restart
```

- [ ] **Step 5: Manual smoke test**

- Open dashboard — verify multi-category stats
- Create one item per category via the respective form pages
- Verify inventory numbers (I-001, K-001, N-001, A-001)
- Upload image to an item
- Create invoice on instrument (should work)
- Navigate to a Noten item — verify no invoice/loan sections shown
- Create loan on clothing item
- Return loan
- Check Leihregister page — verify item_id and display numbers

- [ ] **Step 6: Commit any remaining fixes**

```bash
git add -A
git commit -m "fix: cleanup and fixes from Phase 2 integration testing"
```
