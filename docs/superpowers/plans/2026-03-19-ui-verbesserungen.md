# UI-Verbesserungen Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Six UI/UX improvements: modal forms, currency picker, category-specific field changes (label-as-dropdown, remove general_item_type, add storage_location), invoice overview page, year dropdown for construction_year.

**Architecture:** Backend DB migration (add storage_location, remove label_addition, drop general_item_detail/type), service refactoring for general_item without detail table, new invoice overview endpoint. Frontend: ItemFormPage→ItemFormModal, category config changes, new InvoiceListPage.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async, Alembic, Vue 3, Pydantic v2

**Spec:** `docs/superpowers/specs/2026-03-19-ui-verbesserungen-design.md`

---

## File Structure

### New backend files
- `src/backend/mv_hofki/services/invoice_overview.py` — Global invoice query with filters + currency sums
- `src/backend/mv_hofki/api/routes/invoices.py` — Route for `GET /api/v1/invoices`
- `src/backend/mv_hofki/schemas/invoice_overview.py` — Schemas for global invoice response
- `tests/backend/test_invoice_overview.py` — Tests for global invoice endpoint

### Modified backend files
- `src/backend/mv_hofki/models/inventory_item.py` — Add `storage_location` column
- `src/backend/mv_hofki/models/instrument_detail.py` — Remove `label_addition` column
- `src/backend/mv_hofki/models/__init__.py` — Remove GeneralItemDetail + GeneralItemType exports
- `src/backend/mv_hofki/schemas/inventory_item.py` — Add `storage_location`, remove `label_addition`, simplify GeneralItem schemas (no type_id)
- `src/backend/mv_hofki/services/inventory_item.py` — `general_item` → `None` in CATEGORY_DETAIL_MAP, guard clauses
- `src/backend/mv_hofki/db/seed.py` — Remove GENERAL_ITEM_TYPES
- `src/backend/mv_hofki/api/app.py` — Remove general_item_types router, add invoices router
- `src/backend/mv_hofki/api/routes/items.py` — Remove GeneralItemType schema references
- `tests/backend/test_items.py` — Update general_item tests, add storage_location tests

### Deleted backend files
- `src/backend/mv_hofki/models/general_item_detail.py`
- `src/backend/mv_hofki/models/general_item_type.py`
- `src/backend/mv_hofki/schemas/general_item_type.py`
- `src/backend/mv_hofki/services/general_item_type.py`
- `src/backend/mv_hofki/api/routes/general_item_types.py`
- `tests/backend/test_general_item_types.py`

### New frontend files
- `src/frontend/src/components/ItemFormModal.vue` — Modal form replacing ItemFormPage
- `src/frontend/src/pages/InvoiceListPage.vue` — Invoice overview page

### Modified frontend files
- `src/frontend/src/lib/categories.js` — Add labelField config (dropdown vs text), labelFieldName
- `src/frontend/src/router.js` — Remove /neu and /bearbeiten routes, add /rechnungen
- `src/frontend/src/components/NavBar.vue` — Add Rechnungen link, remove Gegenstandstypen
- `src/frontend/src/pages/ItemListPage.vue` — Integrate ItemFormModal for create
- `src/frontend/src/pages/ItemDetailPage.vue` — Integrate ItemFormModal for edit, update detail fields
- `src/frontend/src/pages/DashboardPage.vue` — Remove general_item_type references if any

### Deleted frontend files
- `src/frontend/src/pages/ItemFormPage.vue`
- `src/frontend/src/pages/GeneralItemTypeListPage.vue`

### Alembic
- New migration: add storage_location, migrate label_addition→particularities, drop label_addition, drop general_item_detail + general_item_type

---

## Task 1: DB Migration — storage_location, remove label_addition, drop general_item tables

**Files:**
- Modify: `src/backend/mv_hofki/models/inventory_item.py`
- Modify: `src/backend/mv_hofki/models/instrument_detail.py`
- Delete: `src/backend/mv_hofki/models/general_item_detail.py`
- Delete: `src/backend/mv_hofki/models/general_item_type.py`
- Modify: `src/backend/mv_hofki/models/__init__.py`
- Modify: `src/backend/mv_hofki/db/seed.py`
- Create: `alembic/versions/<auto>_ui_improvements.py`

- [ ] **Step 1: Add `storage_location` to InventoryItem model**

In `src/backend/mv_hofki/models/inventory_item.py`, add after `notes`:
```python
storage_location: Mapped[str | None] = mapped_column(String(200))
```

- [ ] **Step 2: Remove `label_addition` from InstrumentDetail model**

In `src/backend/mv_hofki/models/instrument_detail.py`, remove the line:
```python
label_addition: Mapped[str | None] = mapped_column(String(100))
```

- [ ] **Step 3: Delete general_item model files**

```bash
rm src/backend/mv_hofki/models/general_item_detail.py
rm src/backend/mv_hofki/models/general_item_type.py
```

- [ ] **Step 4: Update `models/__init__.py`**

Remove imports and exports for `GeneralItemDetail` and `GeneralItemType`.

- [ ] **Step 5: Update `db/seed.py`**

Remove `GENERAL_ITEM_TYPES` list, `GeneralItemType` import, and the corresponding seed block in `seed_data()`.

- [ ] **Step 6: Generate Alembic migration**

```bash
PYTHONPATH=src/backend alembic revision --autogenerate -m "ui improvements: storage_location, drop label_addition and general_item tables"
```

- [ ] **Step 7: Edit migration to migrate label_addition data**

Before the `label_addition` column drop, add data migration:
```python
# Migrate label_addition values to particularities
op.execute("""
    UPDATE instrument_details
    SET particularities = label_addition
    WHERE label_addition IS NOT NULL AND (particularities IS NULL OR particularities = '')
""")
op.execute("""
    UPDATE instrument_details
    SET particularities = particularities || ' | ' || label_addition
    WHERE label_addition IS NOT NULL AND particularities IS NOT NULL AND particularities != ''
""")
```

- [ ] **Step 8: Run migration**

```bash
PYTHONPATH=src/backend alembic upgrade head
```

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "feat: DB migration — add storage_location, remove label_addition, drop general_item tables"
```

---

## Task 2: Backend — Update schemas + service for general_item without detail table

**Files:**
- Modify: `src/backend/mv_hofki/schemas/inventory_item.py`
- Modify: `src/backend/mv_hofki/services/inventory_item.py`
- Modify: `src/backend/mv_hofki/api/routes/items.py`
- Delete: `src/backend/mv_hofki/schemas/general_item_type.py`
- Delete: `src/backend/mv_hofki/services/general_item_type.py`
- Delete: `src/backend/mv_hofki/api/routes/general_item_types.py`
- Delete: `tests/backend/test_general_item_types.py`
- Modify: `src/backend/mv_hofki/api/app.py`
- Modify: `tests/backend/test_items.py`

- [ ] **Step 1: Update `schemas/inventory_item.py`**

Changes:
- Add `storage_location: str | None = None` to `ItemCreateBase` and `ItemUpdateBase`
- Add `storage_location: str | None = None` to `ItemRead`
- Remove `label_addition` from `InstrumentItemCreate`, `InstrumentItemUpdate`, `InstrumentItemRead`
- Simplify `GeneralItemCreate`: remove `general_item_type_id`, just `category: str = "general_item"` (inherits only base fields)
- Simplify `GeneralItemUpdate`: remove `general_item_type_id` (inherits only base fields)
- Simplify `GeneralItemRead`: remove `general_item_type_id` and `general_item_type` (inherits only base fields)
- Remove `from mv_hofki.schemas.general_item_type import GeneralItemTypeRead` import

- [ ] **Step 2: Update `services/inventory_item.py`**

Changes:
- Remove `GeneralItemDetail` import
- Change `CATEGORY_DETAIL_MAP` type hint to `dict[str, tuple[type, set[str]] | None]`
- Set `"general_item": None` in `CATEGORY_DETAIL_MAP`
- Remove `"general_item"` from `_DETAIL_JOINEDLOAD`
- Update `_split_fields()`: if `CATEGORY_DETAIL_MAP[category]` is `None`, return `(data_without_category, {})`
- Update `create()`: skip detail record creation when `CATEGORY_DETAIL_MAP[category]` is `None`
- Update `_get_detail()`: return `None` immediately when detail map entry is `None`
- Update `_build_read_dict()`: remove the `"general_item"` branch from the relationship section
- Remove `"label_addition"` from instrument detail field set in `CATEGORY_DETAIL_MAP`
- Category validation: change `if category not in CATEGORY_DETAIL_MAP` to `if category not in CATEGORY_PREFIXES` (since general_item is now `None` in the map but still a valid category)

- [ ] **Step 3: Update `api/routes/items.py`**

- Remove `GeneralItemRead`, `GeneralItemCreate`, `GeneralItemUpdate` from schema-specific imports (they still exist but are now simple base-class wrappers)
- Keep them in `_CREATE_SCHEMAS`, `_UPDATE_SCHEMAS`, `_READ_SCHEMAS` dicts — they still work, just have fewer fields

- [ ] **Step 4: Delete general_item_type files**

```bash
rm src/backend/mv_hofki/schemas/general_item_type.py
rm src/backend/mv_hofki/services/general_item_type.py
rm src/backend/mv_hofki/api/routes/general_item_types.py
rm tests/backend/test_general_item_types.py
```

- [ ] **Step 5: Update `api/app.py`**

Remove `general_item_types_router` import and `app.include_router(general_item_types_router)`.

- [ ] **Step 6: Update `tests/backend/test_items.py`**

- Update general_item creation test: no `general_item_type_id` needed, no `setup_general_refs` fixture needed (or simplify it to just currency)
- Remove any assertions on `general_item_type` in responses
- Add test for `storage_location`: create a sheet_music item with `storage_location`, verify it's returned
- Add test for `storage_location`: create a general_item with `storage_location`, verify it's returned
- Remove any tests referencing `label_addition`

- [ ] **Step 7: Run all tests**

```bash
python -m pytest tests/backend/ -v
```

- [ ] **Step 8: Run linter**

```bash
pre-commit run --all-files
```

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "feat: update schemas and service for general_item without detail table, add storage_location"
```

---

## Task 3: Backend — Invoice overview endpoint

**Files:**
- Create: `src/backend/mv_hofki/schemas/invoice_overview.py`
- Create: `src/backend/mv_hofki/services/invoice_overview.py`
- Create: `src/backend/mv_hofki/api/routes/invoices.py`
- Create: `tests/backend/test_invoice_overview.py`
- Modify: `src/backend/mv_hofki/api/app.py`

- [ ] **Step 1: Create `schemas/invoice_overview.py`**

```python
"""Invoice overview Pydantic schemas."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel

from mv_hofki.schemas.currency import CurrencyRead


class InvoiceOverviewItem(BaseModel):
    id: int
    invoice_nr: int
    item_id: int
    item_display_nr: str
    item_label: str
    item_category: str
    title: str
    date_issued: date
    amount: float
    currency: CurrencyRead
    filename: str | None
    file_url: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class CurrencyTotal(BaseModel):
    abbreviation: str
    total: float


class InvoiceOverviewResponse(BaseModel):
    items: list[InvoiceOverviewItem]
    total: int
    totals_by_currency: list[CurrencyTotal]
```

- [ ] **Step 2: Create `services/invoice_overview.py`**

Query `ItemInvoice` joined with `InventoryItem` and `Currency`. Support filters:
- `category`: filter by `InventoryItem.category`
- `search`: ilike on `ItemInvoice.title` and `ItemInvoice.invoice_issuer`
- `date_from` / `date_to`: filter on `ItemInvoice.date_issued`
- Pagination: `limit`, `offset`
- Default sort: `ItemInvoice.date_issued DESC`

Return items with `item_display_nr` and `item_label` from joined InventoryItem, plus `totals_by_currency` computed across full filtered set (not just current page).

The `file_url` is computed as `/uploads/invoices/{item_id}/{filename}` when `filename` is not None.

- [ ] **Step 3: Create `api/routes/invoices.py`**

```python
router = APIRouter(prefix="/api/v1/invoices", tags=["invoices"])

@router.get("")
async def list_invoices(
    category: str | None = None,
    search: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    ...
```

- [ ] **Step 4: Register route in `api/app.py`**

Add `from mv_hofki.api.routes.invoices import router as invoices_router` and `app.include_router(invoices_router)`.

- [ ] **Step 5: Write tests `tests/backend/test_invoice_overview.py`**

Tests:
- `test_list_invoices_empty` — no invoices returns empty list and zero totals
- `test_list_invoices_with_data` — create items + invoices, verify all fields in response
- `test_list_invoices_filter_by_category` — create invoices on instrument and clothing, filter by category
- `test_list_invoices_filter_by_date_range` — filter by date_from/date_to
- `test_list_invoices_search` — search by title
- `test_list_invoices_totals_by_currency` — create invoices in different currencies, verify sums

- [ ] **Step 6: Run tests**

```bash
python -m pytest tests/backend/test_invoice_overview.py -v
```

- [ ] **Step 7: Run all tests + lint**

```bash
python -m pytest tests/backend/ -v
pre-commit run --all-files
```

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat: add invoice overview endpoint with filters and currency sums"
```

---

## Task 4: Frontend — Category config + Router + NavBar updates

**Files:**
- Modify: `src/frontend/src/lib/categories.js`
- Modify: `src/frontend/src/router.js`
- Modify: `src/frontend/src/components/NavBar.vue`
- Delete: `src/frontend/src/pages/GeneralItemTypeListPage.vue`

- [ ] **Step 1: Update `categories.js`**

Add category-specific label configuration:

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
    labelField: "dropdown",      // "dropdown" = type select sets label
    labelFieldName: "Typ",       // Label for the dropdown
    typeEndpoint: "/instrument-types",  // API to fetch dropdown options
    typeValueField: "label",     // Which field of the type to use as label value
    typeIdField: "instrument_type_id",  // Which field to set on the item
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
    labelField: "dropdown",
    labelFieldName: "Typ",
    typeEndpoint: "/clothing-types",
    typeValueField: "label",
    typeIdField: "clothing_type_id",
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
    labelField: "text",
    labelFieldName: "Titel",
    hasStorageLocation: true,
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
    labelField: "text",
    labelFieldName: "Bezeichnung",
    hasStorageLocation: true,
  },
};
```

- [ ] **Step 2: Update `router.js`**

- Remove `/neu` and `/:id/bearbeiten` routes from the `categoryRoutes()` helper (keep only list and detail)
- Add `/rechnungen` route:
```javascript
{ path: "/rechnungen", name: "invoices", component: () => import("./pages/InvoiceListPage.vue") },
```
- Remove `/einstellungen/gegenstandstypen` route

- [ ] **Step 3: Update NavBar**

- Add "Rechnungen" link between "Leihregister" and "Einstellungen" dropdown
- Remove "Gegenstandstypen" from settings dropdown

- [ ] **Step 4: Delete GeneralItemTypeListPage**

```bash
rm src/frontend/src/pages/GeneralItemTypeListPage.vue
```

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: update category config, router, navbar — remove general_item_type, add invoices route"
```

---

## Task 5: Frontend — ItemFormModal component

**Files:**
- Create: `src/frontend/src/components/ItemFormModal.vue`
- Delete: `src/frontend/src/pages/ItemFormPage.vue`

- [ ] **Step 1: Create `ItemFormModal.vue`**

Props: `open` (Boolean), `category` (String, required), `itemId` (Number, null for create), `currencies` (Array)

Events: `@save` (emits after successful save), `@close`

Key behavior:
- If `itemId` is null → create mode, else edit mode (fetch data from `/items/{itemId}`)
- Modal style matches existing `InvoiceModal` (overlay + dialog, max-width 700px)
- **Label field** based on `CATEGORIES[category].labelField`:
  - `"dropdown"`: fetch types from `cat.typeEndpoint`, render `<select>` that sets both `form.label` (from `type.label`) and `form[cat.typeIdField]` (from `type.id`)
  - `"text"`: render `<input>` with label = `cat.labelFieldName`
- **Currency picker** for acquisition_cost: label shows "Anschaffungskosten (€)" with pencil icon, flyout panel for currency selection (reuse `InvoiceModal` pattern: `.currency-edit-btn` + `.currency-picker`)
- **Category-specific fields** rendered via `v-if`:
  - **instrument**: serial_nr, manufacturer, construction_year (year dropdown: `<select>` with options from current year down to 1950, default = current year), distributor, container, particularities
  - **clothing**: size, gender (select: Herren/Damen/empty)
  - **sheet_music**: composer, arranger, difficulty, genre (select from `/sheet-music-genres`), storage_location
  - **general_item**: manufacturer, storage_location
- Common fields always: label (dropdown or text), owner (default "MV Hofkirchen"), acquisition_date, acquisition_cost + currency, notes
- On save: POST/PUT to `/items`, emit `@save`, close modal
- Validation: label required (or type selection required for dropdown categories), owner required

- [ ] **Step 2: Delete old form page**

```bash
rm src/frontend/src/pages/ItemFormPage.vue
```

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "feat: add ItemFormModal component replacing ItemFormPage"
```

---

## Task 6: Frontend — Integrate modal into ItemListPage + ItemDetailPage

**Files:**
- Modify: `src/frontend/src/pages/ItemListPage.vue`
- Modify: `src/frontend/src/pages/ItemDetailPage.vue`

- [ ] **Step 1: Update `ItemListPage.vue`**

- Import and embed `ItemFormModal`
- Add state: `showCreateModal = ref(false)`, `currencies = ref([])`
- Fetch currencies on mount
- "Neu"-Button now opens modal: `@click="showCreateModal = true"` (instead of router-link to /neu)
- `<ItemFormModal :open="showCreateModal" :category="category" :currencies="currencies" @save="reload; showCreateModal = false" @close="showCreateModal = false" />`
- Update list columns for instrument: show manufacturer alongside display_nr+label for differentiation
- Remove any column referencing `label_addition` or `general_item_type`
- Add `storage_location` column for sheet_music and general_item if desired (or leave for detail page only)

- [ ] **Step 2: Update `ItemDetailPage.vue`**

- Import and embed `ItemFormModal`
- Add state: `showEditModal = ref(false)`
- "Bearbeiten"-Button now opens modal: `@click="showEditModal = true"` (instead of router-link to /bearbeiten)
- `<ItemFormModal :open="showEditModal" :category="category" :item-id="item.id" :currencies="currencies" @save="reload; showEditModal = false" @close="showEditModal = false" />`
- Update detail-grid:
  - Instrument: remove Bezeichnungszusatz row, show Typ (from instrument_type.label)
  - General item: remove Typ row (was general_item_type.label)
  - Sheet music + General item: show Lagerort row
  - Instrument: construction_year shows just the year number (already does since it's int)

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "feat: integrate ItemFormModal into list and detail pages"
```

---

## Task 7: Frontend — Invoice overview page

**Files:**
- Create: `src/frontend/src/pages/InvoiceListPage.vue`

- [ ] **Step 1: Create `InvoiceListPage.vue`**

Page at `/rechnungen` showing all invoices across categories.

- Filter toolbar:
  - Category dropdown: Alle / Instrumente / Kleidung / Allgemein
  - Date from/to inputs
  - Search bar (searches title, issuer)
- Table columns: Nr., Gegenstand (display_nr + label), Bezeichnung, Datum, Betrag (amount + currency abbreviation), Datei (badge)
- Click on row → navigate to item detail: `router.push(CATEGORIES[item.item_category].routeBase + "/" + item.item_id)`
- **Summenzeile** at bottom: show totals_by_currency from API response (e.g., "Gesamt: 1.234,50 € · 500 ATS")
- Pagination: 50 per page with prev/next buttons
- Fetch from `GET /invoices?category=&search=&date_from=&date_to=&limit=50&offset=0`

- [ ] **Step 2: Commit**

```bash
git add -A
git commit -m "feat: add InvoiceListPage with filters and currency sums"
```

---

## Task 8: Final cleanup + full test run

**Files:**
- Clean up any remaining references to old files/fields

- [ ] **Step 1: Run all backend tests**

```bash
python -m pytest tests/backend/ -v
```

- [ ] **Step 2: Run linter**

```bash
pre-commit run --all-files
```

- [ ] **Step 3: Fix any issues**

- [ ] **Step 4: Restart server and frontend**

```bash
# Restart server tmux session
tmux send-keys -t server C-c && sleep 1 && tmux send-keys -t server "PYTHONPATH=src/backend uvicorn mv_hofki.api.app:app --host 0.0.0.0 --port 8000 --reload" Enter
```

- [ ] **Step 5: Manual smoke test**

- Open /instrumente → click "Neu" → modal opens with type dropdown for label, year dropdown for Baujahr, currency picker with pencil icon
- Create instrument → modal closes, list refreshes
- Open instrument detail → click "Bearbeiten" → modal opens with prefilled data
- Open /noten → create with Titel (text field) + Lagerort
- Open /allgemein → create (no type dropdown, just Bezeichnung + Lagerort)
- Open /rechnungen → verify filter by category, date range, search; verify totals_by_currency

- [ ] **Step 6: Commit any remaining fixes**

```bash
git add -A
git commit -m "fix: cleanup from UI improvements integration testing"
```
