# Kategorien für Allgemeine Items: Implementierungsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allgemeine Items (`category="general_item"`) bekommen frei pflegbare Kategorien (mehrere pro Item). Diese lassen sich unter Einstellungen und direkt im Item-Formular anlegen und werden in Detail- und Listenansicht angezeigt.

**Architecture:**
- Neue Nachschlagetabelle `general_item_categories` und Verknüpfungstabelle `general_item_category_links`.
- Ein eigener Service mit Route nach dem Muster von `clothing_types`.
- Der Item-Service lädt die Kategorien in `_enrich` gesammelt für alle Items einer Seite.
- Im Frontend: eine Combobox-Komponente `TagSelect`, eine Chip-Anzeige `CategoryChips` und eine Einstellungsseite.
- Ein einmaliges Skript spielt eine geprüfte CSV mit Zuordnungen ein.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async (aiosqlite), Alembic, Pydantic v2, pytest-asyncio; Vue 3.4 (`<script setup>`), Vitest und @vue/test-utils (jsdom).

**Spec:** `docs/superpowers/specs/2026-09-27-general-item-categories-design.md`

## Global Constraints

- **Wo Befehle laufen:** Claude arbeitet auf dem Host, die App läuft im Devcontainer. Jeder Python-, Node-, Alembic- und pre-commit-Befehl läuft mit:
  `docker exec -w /workspaces/mv_hofki mv-hofki-vue-pyhton_devcontainer-devcontainer-1 bash -lc '<befehl>'`
  Im Plan steht dafür kurz `IN_CONTAINER '<befehl>'`. Dateien werden auf dem Host unter `/home/ai/Documents/mv-hofki-vue-pyhton` bearbeitet; das ist dasselbe Verzeichnis.
- **Committen:**
  - Im Container, mit der Git-Identität des Hosts:
    ```bash
    cd /home/ai/Documents/mv-hofki-vue-pyhton && N=$(git config user.name); E=$(git config user.email); \
    docker exec -w /workspaces/mv_hofki -e GIT_AUTHOR_NAME="$N" -e GIT_AUTHOR_EMAIL="$E" -e GIT_COMMITTER_NAME="$N" -e GIT_COMMITTER_EMAIL="$E" \
      mv-hofki-vue-pyhton_devcontainer-devcontainer-1 bash -lc 'git add <dateien> && git commit -m "<msg>

    Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>" -- <dateien>'
    ```
  - Nur die eigenen Dateien committen. In diesem Repo arbeiten andere Claude-Sitzungen gleichzeitig. **Niemals** `git stash`, `git reset`, `git clean` oder `git add -A`/`git add .` verwenden.
  - Der pre-commit-Hook (ruff, ruff-format, mypy, eslint, prettier) läuft beim Commit. Formatiert er Dateien um, die Dateien erneut `git add`en und noch einmal committen.
- **Sprache:**
  - UI-Texte auf Deutsch, österreichische Schreibung, typografische Anführungszeichen „…“.
  - API-Fehlermeldungen (`detail`) ebenfalls auf Deutsch.
- **Styling:** Farben, Radien, Schatten und Abstände nur über Tokens aus `src/frontend/src/style.css` (`--color-*`, `--radius*`, `--space-*`, `--shadow-float`). Keine Farbliterale in Komponenten.
- **Bedienbarkeit:** Touch-Ziele mindestens 44 px. Alles Klickbare ist ein `<button>` oder Link mit sichtbarem Text oder `aria-label`.
- **Fehleranzeige:** Fehler erscheinen inline, nicht per `alert()`. Das gilt für neuen Code; bestehende `alert()`-Aufrufe bleiben unangetastet.
- **Nummern:** Inventarnummern (`number_prefix`, `inventory_nr`) werden von Kategorien nie verändert.
- **SQLite:** Die Verbindung setzt kein `PRAGMA foreign_keys=ON`, `ON DELETE CASCADE` greift also nicht. Verknüpfungen werden immer explizit gelöscht.
- **Kategorie-Labels:**
  - Maximal 50 Zeichen und getrimmt.
  - Leeres Label ergibt 422.
  - Eindeutig ohne Rücksicht auf Groß-/Kleinschreibung, verglichen in Python mit `str.casefold()`, weil SQLite-`lower()` keine Umlaute kennt. Ein Duplikat ergibt 409 „Kategorie existiert bereits“.

## Review Focus

1. **Groß-/Kleinschreibung mit Umlauten:** „Küche“ und „KÜCHE“ gelten als Duplikat. Anlegen und Umbenennen liefern dann 409. Umbenennen einer Kategorie auf ihr eigenes Label in anderer Schreibung ist erlaubt. (Tests in Task 1)
2. **Item löschen:** Wird ein Item mit Kategorien gelöscht, bleiben keine Verknüpfungen zurück, und `item_count` sinkt. Das gilt auch für `wipe_inventory`. (Tests in Task 2)
3. **Fehlgeschlagenes Anlegen:** Scheitert `POST /items` an einer unbekannten Kategorie-ID, darf kein halbes Item in der Datenbank bleiben. Die Prüfung läuft deshalb vor dem Anlegen. (Test in Task 2)
4. **Enter im Formular:** Enter im `TagSelect`-Eingabefeld darf das umgebende `<form>` nicht absenden, solange Text im Feld steht oder eine Option markiert ist. (Test in Task 4)
5. **Übernahmeskript:** Lagerort-Spalte oder BOM in der CSV, leere Kategorien-Spalte (entfernt alle Kategorien), unbekannte Nummer (wird gemeldet, nicht abgebrochen), zweiter Lauf (keine neuen Kategorien, gleiche Zuordnung). (Tests in Task 3)

---

## Dateiübersicht

| Datei | Aufgabe |
|---|---|
| `src/backend/mv_hofki/models/general_item_category.py` (neu) | ORM-Modell `GeneralItemCategory` und `Table` `general_item_category_links` |
| `src/backend/mv_hofki/models/__init__.py` | Export ergänzen |
| `alembic/versions/d1f3a5c7e9b2_general_item_categories.py` (neu) | Migration |
| `src/backend/mv_hofki/schemas/general_item_category.py` (neu) | Create/Update/Ref/Read-Schemas |
| `src/backend/mv_hofki/services/general_item_category.py` (neu) | CRUD sowie `check_category_ids`, `set_item_categories`, `categories_for_items`, `delete_links_for_items` |
| `src/backend/mv_hofki/api/routes/general_item_categories.py` (neu) | Route `/api/v1/general-item-categories` |
| `src/backend/mv_hofki/api/app.py` | Router registrieren |
| `src/backend/mv_hofki/schemas/inventory_item.py` | `category_ids` und `categories` bei den General-Schemas |
| `src/backend/mv_hofki/services/inventory_item.py` | create/update/delete/_enrich/_build_read_dict |
| `src/backend/mv_hofki/api/routes/items.py` | `category_ids` bei anderen Inventar-Arten ablehnen |
| `src/backend/mv_hofki/services/inventar_import.py` | `wipe_inventory` löscht auch Verknüpfungen |
| `src/backend/mv_hofki/services/general_item_category_import.py` (neu) | CSV lesen und Zuordnungen anwenden |
| `scripts/apply_general_item_categories.py` (neu) | CLI-Hülle mit DB-Backup |
| `src/frontend/src/components/CategoryChips.vue` (neu) | Chip-Liste (Anzeige) |
| `src/frontend/src/components/TagSelect.vue` (neu) | Combobox: Mehrfachauswahl mit Anlegen |
| `src/frontend/src/style.css` | globale `.category-chips` / `.category-chip` |
| `src/frontend/src/pages/GeneralItemCategoryListPage.vue` (neu) | Einstellungsseite |
| `src/frontend/src/router.js`, `components/NavBar.vue` | Route und Menüeintrag |
| `src/frontend/src/lib/categories.js` | `hasCategories: true` für `general_item` |
| `src/frontend/src/components/ItemFormModal.vue` | TagSelect im Formular |
| `src/frontend/src/pages/ItemDetailPage.vue`, `pages/ItemListPage.vue` | Anzeige |
| Tests | `tests/backend/test_general_item_categories.py` (neu), `tests/backend/test_items.py`, `tests/backend/test_general_item_category_import.py` (neu), `tests/frontend/TagSelect.test.js` (neu), `tests/frontend/CategoryChips.test.js` (neu) |

---

### Task 1: Kategorien-Tabelle, Migration und CRUD-API

**Files:**
- Create: `src/backend/mv_hofki/models/general_item_category.py`
- Modify: `src/backend/mv_hofki/models/__init__.py`
- Create: `alembic/versions/d1f3a5c7e9b2_general_item_categories.py`
- Create: `src/backend/mv_hofki/schemas/general_item_category.py`
- Create: `src/backend/mv_hofki/services/general_item_category.py`
- Create: `src/backend/mv_hofki/api/routes/general_item_categories.py`
- Modify: `src/backend/mv_hofki/api/app.py` (Import neben `clothing_types_router` in Zeile 14, `include_router` neben Zeile 96)
- Test: `tests/backend/test_general_item_categories.py`

**Interfaces:**
- Produces:
  - `mv_hofki.models.general_item_category.GeneralItemCategory` (id, label)
  - `general_item_category_links` (Table: item_id, category_id)
  - Schemas `GeneralItemCategoryCreate`, `GeneralItemCategoryUpdate`, `GeneralItemCategoryRef{id,label}`, `GeneralItemCategoryRead{id,label,item_count}`
  - Service-Funktionen `get_all(session) -> list[dict]`, `get_by_id(session, id) -> dict`, `create`, `update`, `delete`
  - Endpunkt `/api/v1/general-item-categories`

- [ ] **Step 1: Failing tests schreiben**

`tests/backend/test_general_item_categories.py`:

```python
"""GeneralItemCategory API tests."""

import pytest

URL = "/api/v1/general-item-categories"


@pytest.fixture
async def deko(client):
    resp = await client.post(URL, json={"label": "Deko"})
    assert resp.status_code == 201
    return resp.json()


async def test_create_category_trims_label(client):
    resp = await client.post(URL, json={"label": "  Gastro  "})
    assert resp.status_code == 201
    data = resp.json()
    assert data["label"] == "Gastro"
    assert data["item_count"] == 0


async def test_empty_label_rejected(client):
    resp = await client.post(URL, json={"label": "   "})
    assert resp.status_code == 422


async def test_label_too_long_rejected(client):
    resp = await client.post(URL, json={"label": "x" * 51})
    assert resp.status_code == 422


async def test_duplicate_ignores_case_including_umlauts(client):
    assert (await client.post(URL, json={"label": "Küche"})).status_code == 201
    resp = await client.post(URL, json={"label": "KÜCHE"})
    assert resp.status_code == 409
    assert resp.json()["detail"] == "Kategorie existiert bereits"


async def test_list_sorted_by_label(client):
    for label in ("technik", "Deko", "Gastro"):
        await client.post(URL, json={"label": label})
    resp = await client.get(URL)
    assert resp.status_code == 200
    assert [c["label"] for c in resp.json()] == ["Deko", "Gastro", "technik"]


async def test_get_category(client, deko):
    resp = await client.get(f"{URL}/{deko['id']}")
    assert resp.status_code == 200
    assert resp.json() == {"id": deko["id"], "label": "Deko", "item_count": 0}


async def test_get_unknown_category_404(client):
    resp = await client.get(f"{URL}/999")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Kategorie nicht gefunden"


async def test_rename_category(client, deko):
    resp = await client.put(f"{URL}/{deko['id']}", json={"label": "Dekoration"})
    assert resp.status_code == 200
    assert resp.json()["label"] == "Dekoration"


async def test_rename_to_own_label_other_case_allowed(client, deko):
    resp = await client.put(f"{URL}/{deko['id']}", json={"label": "DEKO"})
    assert resp.status_code == 200
    assert resp.json()["label"] == "DEKO"


async def test_rename_to_existing_label_rejected(client, deko):
    await client.post(URL, json={"label": "Gastro"})
    resp = await client.put(f"{URL}/{deko['id']}", json={"label": "gastro"})
    assert resp.status_code == 409


async def test_delete_category(client, deko):
    resp = await client.delete(f"{URL}/{deko['id']}")
    assert resp.status_code == 204
    assert (await client.get(f"{URL}/{deko['id']}")).status_code == 404


async def test_delete_unknown_category_404(client):
    assert (await client.delete(f"{URL}/999")).status_code == 404
```

- [ ] **Step 2: Test laufen lassen, er muss scheitern**

Run: `IN_CONTAINER 'python -m pytest tests/backend/test_general_item_categories.py -v'`
Expected: FAIL mit 404-Antworten (Route existiert nicht).

- [ ] **Step 3: Modell**

`src/backend/mv_hofki/models/general_item_category.py`:

```python
"""GeneralItemCategory lookup ORM model and its item link table."""

from __future__ import annotations

from sqlalchemy import Column, ForeignKey, Integer, String, Table
from sqlalchemy.orm import Mapped, mapped_column

from mv_hofki.db.base import Base

# Many-to-many: a general item can carry several categories. SQLite runs without
# PRAGMA foreign_keys, so the services delete links explicitly.
general_item_category_links = Table(
    "general_item_category_links",
    Base.metadata,
    Column(
        "item_id",
        Integer,
        ForeignKey("inventory_items.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "category_id",
        Integer,
        ForeignKey("general_item_categories.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class GeneralItemCategory(Base):
    __tablename__ = "general_item_categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
```

In `src/backend/mv_hofki/models/__init__.py` alphabetisch nach `Currency` ergänzen:
`from mv_hofki.models.general_item_category import GeneralItemCategory` und `"GeneralItemCategory",` in `__all__`.

- [ ] **Step 4: Migration**

Zuerst den aktuellen Head prüfen: `IN_CONTAINER 'PYTHONPATH=src/backend alembic heads'`. Beim Schreiben des Plans war es `c9e1a3b5d7f9`. Ist es ein anderer, `down_revision` entsprechend anpassen.

`alembic/versions/d1f3a5c7e9b2_general_item_categories.py`:

```python
"""General items get free categories (many per item)

Revision ID: d1f3a5c7e9b2
Revises: c9e1a3b5d7f9
Create Date: 2026-09-27 22:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d1f3a5c7e9b2"
down_revision: str | Sequence[str] | None = "c9e1a3b5d7f9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "general_item_categories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("label", sa.String(50), nullable=False, unique=True),
    )
    op.create_table(
        "general_item_category_links",
        sa.Column(
            "item_id",
            sa.Integer(),
            sa.ForeignKey("inventory_items.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "category_id",
            sa.Integer(),
            sa.ForeignKey("general_item_categories.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )


def downgrade() -> None:
    op.drop_table("general_item_category_links")
    op.drop_table("general_item_categories")
```

- [ ] **Step 5: Schemas**

`src/backend/mv_hofki/schemas/general_item_category.py`:

```python
"""GeneralItemCategory Pydantic schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


def _clean_label(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("Bezeichnung darf nicht leer sein")
    return value


class GeneralItemCategoryCreate(BaseModel):
    label: str = Field(max_length=50)

    @field_validator("label")
    @classmethod
    def clean_label(cls, value: str) -> str:
        return _clean_label(value)


class GeneralItemCategoryUpdate(BaseModel):
    label: str | None = Field(None, max_length=50)

    @field_validator("label")
    @classmethod
    def clean_label(cls, value: str | None) -> str | None:
        return None if value is None else _clean_label(value)


class GeneralItemCategoryRef(BaseModel):
    id: int
    label: str

    model_config = {"from_attributes": True}


class GeneralItemCategoryRead(GeneralItemCategoryRef):
    item_count: int = 0
```

Hinweis: `max_length` prüft vor dem Trimmen. `"x"*51` scheitert, `"  Gastro  "` geht durch. Das ist gewollt.

- [ ] **Step 6: Service (CRUD-Teil)**

`src/backend/mv_hofki/services/general_item_category.py`:

```python
"""GeneralItemCategory CRUD and the links between general items and categories."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.models.general_item_category import (
    GeneralItemCategory,
    general_item_category_links as links,
)
from mv_hofki.schemas.general_item_category import (
    GeneralItemCategoryCreate,
    GeneralItemCategoryUpdate,
)


def _sort_key(label: str) -> str:
    return label.casefold()


def _as_dict(category: GeneralItemCategory, item_count: int) -> dict:
    return {"id": category.id, "label": category.label, "item_count": item_count}


async def _get(session: AsyncSession, category_id: int) -> GeneralItemCategory:
    obj = await session.get(GeneralItemCategory, category_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Kategorie nicht gefunden")
    return obj


async def _item_count(session: AsyncSession, category_id: int) -> int:
    return await session.scalar(
        select(func.count()).select_from(links).where(links.c.category_id == category_id)
    ) or 0


async def _ensure_unique(
    session: AsyncSession, label: str, exclude_id: int | None = None
) -> None:
    # Compared in Python: SQLite's lower() leaves umlauts alone.
    rows = await session.execute(
        select(GeneralItemCategory.id, GeneralItemCategory.label)
    )
    wanted = label.casefold()
    for other_id, other_label in rows.all():
        if other_id != exclude_id and other_label.casefold() == wanted:
            raise HTTPException(status_code=409, detail="Kategorie existiert bereits")


async def get_all(session: AsyncSession) -> list[dict]:
    result = await session.execute(
        select(GeneralItemCategory, func.count(links.c.item_id))
        .outerjoin(links, links.c.category_id == GeneralItemCategory.id)
        .group_by(GeneralItemCategory.id)
    )
    rows = [_as_dict(category, count) for category, count in result.all()]
    return sorted(rows, key=lambda r: _sort_key(r["label"]))


async def get_by_id(session: AsyncSession, category_id: int) -> dict:
    obj = await _get(session, category_id)
    return _as_dict(obj, await _item_count(session, category_id))


async def create(session: AsyncSession, data: GeneralItemCategoryCreate) -> dict:
    await _ensure_unique(session, data.label)
    obj = GeneralItemCategory(label=data.label)
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return _as_dict(obj, 0)


async def update(
    session: AsyncSession, category_id: int, data: GeneralItemCategoryUpdate
) -> dict:
    obj = await _get(session, category_id)
    if data.label is not None:
        await _ensure_unique(session, data.label, exclude_id=category_id)
        obj.label = data.label
    await session.commit()
    await session.refresh(obj)
    return _as_dict(obj, await _item_count(session, category_id))


async def delete(session: AsyncSession, category_id: int) -> None:
    obj = await _get(session, category_id)
    await session.execute(sa_delete(links).where(links.c.category_id == category_id))
    await session.delete(obj)
    await session.commit()
```

- [ ] **Step 7: Route und Registrierung**

`src/backend/mv_hofki/api/routes/general_item_categories.py`:

```python
"""GeneralItemCategory API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.api.deps import get_db
from mv_hofki.schemas.general_item_category import (
    GeneralItemCategoryCreate,
    GeneralItemCategoryRead,
    GeneralItemCategoryUpdate,
)
from mv_hofki.services import general_item_category as category_service

router = APIRouter(
    prefix="/api/v1/general-item-categories", tags=["general-item-categories"]
)


@router.get("", response_model=list[GeneralItemCategoryRead])
async def list_categories(db: AsyncSession = Depends(get_db)):
    return await category_service.get_all(db)


@router.post("", response_model=GeneralItemCategoryRead, status_code=201)
async def create_category(
    data: GeneralItemCategoryCreate, db: AsyncSession = Depends(get_db)
):
    return await category_service.create(db, data)


@router.get("/{category_id}", response_model=GeneralItemCategoryRead)
async def get_category(category_id: int, db: AsyncSession = Depends(get_db)):
    return await category_service.get_by_id(db, category_id)


@router.put("/{category_id}", response_model=GeneralItemCategoryRead)
async def update_category(
    category_id: int,
    data: GeneralItemCategoryUpdate,
    db: AsyncSession = Depends(get_db),
):
    return await category_service.update(db, category_id, data)


@router.delete("/{category_id}", status_code=204)
async def delete_category(category_id: int, db: AsyncSession = Depends(get_db)):
    await category_service.delete(db, category_id)
    return Response(status_code=204)
```

In `src/backend/mv_hofki/api/app.py` den Import `from mv_hofki.api.routes.general_item_categories import router as general_item_categories_router` alphabetisch zu den anderen Route-Imports stellen und `app.include_router(general_item_categories_router)` direkt nach `app.include_router(clothing_types_router)` einfügen.

- [ ] **Step 8: Tests laufen lassen, sie müssen bestehen**

Run: `IN_CONTAINER 'python -m pytest tests/backend/test_general_item_categories.py -v'`
Expected: alle PASS.

- [ ] **Step 9: Migration gegen die echte DB anwenden**

Run: `IN_CONTAINER 'PYTHONPATH=src/backend alembic upgrade head && PYTHONPATH=src/backend alembic current'`
Expected: `d1f3a5c7e9b2 (head)`.

- [ ] **Step 10: Commit**

Dateien: die 6 neuen Dateien, `models/__init__.py`, `api/app.py`. Message: `feat(inventory): categories for general items (table + API)`.

---

### Task 2: Kategorien an Allgemeinen Items (Anlegen, Ändern, Lesen, Löschen)

**Files:**
- Modify: `src/backend/mv_hofki/services/general_item_category.py` (Link-Helfer anhängen)
- Modify: `src/backend/mv_hofki/schemas/inventory_item.py` (`GeneralItemCreate`, `GeneralItemUpdate`, `GeneralItemRead`)
- Modify: `src/backend/mv_hofki/services/inventory_item.py` (`_enrich`, `_build_read_dict`, `create`, `update`, `delete`)
- Modify: `src/backend/mv_hofki/api/routes/items.py` (`create_item`, `update_item`)
- Modify: `src/backend/mv_hofki/services/inventar_import.py:1110-1125` (`wipe_inventory`)
- Test: `tests/backend/test_items.py` (Tests anhängen)

**Interfaces:**
- Consumes (aus Task 1): `general_item_category_links`, `GeneralItemCategory`, `GeneralItemCategoryRef`.
- Produces:
  - `async check_category_ids(session, ids: list[int]) -> list[int]`: dedupliziert und sortiert; wirft 422 bei unbekannten IDs.
  - `async set_item_categories(session, item_id: int, ids: list[int]) -> None`: ersetzt die Zuordnung; erwartet geprüfte IDs; ohne Commit.
  - `async categories_for_items(session, item_ids: list[int]) -> dict[int, list[dict]]`: je Item eine Liste `{id,label}`, sortiert nach Label.
  - `async delete_links_for_items(session, item_ids: list[int] | None) -> None`: bei `None` werden alle Verknüpfungen gelöscht.
  - API: `category_ids` in POST/PUT `/items` (`general_item`) und `categories: [{id,label}]` in jedem Read eines `general_item`.

- [ ] **Step 1: Failing tests anhängen**

Am Ende von `tests/backend/test_items.py` anfügen:

```python
# ---------------------------------------------------------------------------
# Categories of general items
# ---------------------------------------------------------------------------

CATS = "/api/v1/general-item-categories"


async def _cat(client, label):
    resp = await client.post(CATS, json={"label": label})
    assert resp.status_code == 201
    return resp.json()["id"]


async def _general(client, **extra):
    resp = await client.post(
        "/api/v1/items",
        json={"category": "general_item", "label": "Stehtisch", **extra},
    )
    return resp


async def test_general_item_without_categories_has_empty_list(client):
    resp = await _general(client)
    assert resp.status_code == 201
    assert resp.json()["categories"] == []


async def test_create_general_item_with_categories_sorted_and_deduped(client):
    gastro = await _cat(client, "Gastro")
    deko = await _cat(client, "deko")
    resp = await _general(client, category_ids=[gastro, deko, gastro])
    assert resp.status_code == 201
    assert resp.json()["categories"] == [
        {"id": deko, "label": "deko"},
        {"id": gastro, "label": "Gastro"},
    ]


async def test_unknown_category_rejected_and_no_item_created(client):
    resp = await _general(client, category_ids=[999])
    assert resp.status_code == 422
    assert "Unbekannte Kategorie" in resp.json()["detail"]
    listing = await client.get("/api/v1/items?category=general_item")
    assert listing.json()["total"] == 0


async def test_update_replaces_keeps_or_clears_categories(client):
    gastro = await _cat(client, "Gastro")
    deko = await _cat(client, "Deko")
    item = (await _general(client, category_ids=[gastro])).json()
    url = f"/api/v1/items/{item['id']}"

    resp = await client.put(url, json={"category_ids": [deko]})
    assert [c["label"] for c in resp.json()["categories"]] == ["Deko"]

    resp = await client.put(url, json={"notes": "wackelt"})
    assert [c["label"] for c in resp.json()["categories"]] == ["Deko"]

    resp = await client.put(url, json={"category_ids": []})
    assert resp.json()["categories"] == []


async def test_update_with_unknown_category_rejected_and_unchanged(client):
    gastro = await _cat(client, "Gastro")
    item = (await _general(client, category_ids=[gastro])).json()
    resp = await client.put(
        f"/api/v1/items/{item['id']}", json={"category_ids": [gastro, 999]}
    )
    assert resp.status_code == 422
    detail = (await client.get(f"/api/v1/items/{item['id']}")).json()
    assert [c["label"] for c in detail["categories"]] == ["Gastro"]


async def test_category_ids_rejected_for_other_item_kinds(client, setup_refs):
    gastro = await _cat(client, "Gastro")
    resp = await client.post(
        "/api/v1/items",
        json={
            "category": "instrument",
            "label": "Flöte",
            **setup_refs,
            "category_ids": [gastro],
        },
    )
    assert resp.status_code == 422
    assert resp.json()["detail"] == "Kategorien gibt es nur für allgemeine Gegenstände"


async def test_list_contains_categories(client):
    gastro = await _cat(client, "Gastro")
    await _general(client, category_ids=[gastro])
    await _general(client)
    items = (await client.get("/api/v1/items?category=general_item")).json()["items"]
    assert [i["categories"] for i in items] == [
        [{"id": gastro, "label": "Gastro"}],
        [],
    ]


async def test_item_count_and_delete_item_removes_links(client):
    gastro = await _cat(client, "Gastro")
    item = (await _general(client, category_ids=[gastro])).json()
    assert (await client.get(f"{CATS}/{gastro}")).json()["item_count"] == 1
    assert (await client.delete(f"/api/v1/items/{item['id']}")).status_code == 204
    assert (await client.get(f"{CATS}/{gastro}")).json()["item_count"] == 0


async def test_delete_category_removes_it_from_items(client):
    gastro = await _cat(client, "Gastro")
    item = (await _general(client, category_ids=[gastro])).json()
    assert (await client.delete(f"{CATS}/{gastro}")).status_code == 204
    detail = (await client.get(f"/api/v1/items/{item['id']}")).json()
    assert detail["categories"] == []
```

(`setup_refs` ist die bestehende Fixture oben in der Datei und liefert `currency_id` und `instrument_type_id`.) Außerdem einen Test für `wipe_inventory` anfügen:

```python
async def test_wipe_inventory_removes_category_links(client, db_session):
    from sqlalchemy import func, select

    from mv_hofki.models.general_item_category import general_item_category_links
    from mv_hofki.services.inventar_import import wipe_inventory

    gastro = await _cat(client, "Gastro")
    await _general(client, category_ids=[gastro])
    await wipe_inventory(db_session)
    await db_session.commit()
    count = await db_session.scalar(
        select(func.count()).select_from(general_item_category_links)
    )
    assert count == 0
```

- [ ] **Step 2: Tests laufen lassen, sie müssen scheitern**

Run: `IN_CONTAINER 'python -m pytest tests/backend/test_items.py -v -k "categor or wipe"'`
Expected: FAIL (`KeyError: 'categories'` bzw. 201 statt 422).

- [ ] **Step 3: Link-Helfer im Kategorien-Service**

An `src/backend/mv_hofki/services/general_item_category.py` anhängen (und `insert` zum SQLAlchemy-Import hinzufügen):

```python
async def check_category_ids(session: AsyncSession, ids: list[int]) -> list[int]:
    """Deduplicated, sorted ids; 422 if any id is unknown."""
    wanted = sorted(set(ids))
    if not wanted:
        return []
    found = set(
        (
            await session.execute(
                select(GeneralItemCategory.id).where(GeneralItemCategory.id.in_(wanted))
            )
        ).scalars()
    )
    missing = [i for i in wanted if i not in found]
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"Unbekannte Kategorie: {', '.join(str(i) for i in missing)}",
        )
    return wanted


async def set_item_categories(
    session: AsyncSession, item_id: int, ids: list[int]
) -> None:
    """Replace an item's categories. ``ids`` must come from check_category_ids."""
    await session.execute(sa_delete(links).where(links.c.item_id == item_id))
    if ids:
        await session.execute(
            insert(links), [{"item_id": item_id, "category_id": i} for i in ids]
        )


async def categories_for_items(
    session: AsyncSession, item_ids: list[int]
) -> dict[int, list[dict]]:
    """{item_id: [{id, label}, ...]} sorted by label, one query for all items."""
    if not item_ids:
        return {}
    result = await session.execute(
        select(links.c.item_id, GeneralItemCategory.id, GeneralItemCategory.label)
        .join(GeneralItemCategory, GeneralItemCategory.id == links.c.category_id)
        .where(links.c.item_id.in_(item_ids))
    )
    out: dict[int, list[dict]] = {}
    for item_id, cat_id, label in result.all():
        out.setdefault(item_id, []).append({"id": cat_id, "label": label})
    for cats in out.values():
        cats.sort(key=lambda c: _sort_key(c["label"]))
    return out


async def delete_links_for_items(
    session: AsyncSession, item_ids: list[int] | None
) -> None:
    """Remove the category links of the given items (all links if None)."""
    stmt = sa_delete(links)
    if item_ids is not None:
        stmt = stmt.where(links.c.item_id.in_(item_ids))
    await session.execute(stmt)
```

- [ ] **Step 4: Schemas**

In `src/backend/mv_hofki/schemas/inventory_item.py`:
- Import: `from mv_hofki.schemas.general_item_category import GeneralItemCategoryRef`.
- `GeneralItemCreate`: `category_ids: list[int] = Field(default_factory=list)`.
- `GeneralItemUpdate` (statt `pass`): `category_ids: list[int] | None = None`.
- `GeneralItemRead` (statt `pass`): `categories: list[GeneralItemCategoryRef] = []`.

- [ ] **Step 5: Item-Service**

In `src/backend/mv_hofki/services/inventory_item.py`:

Import ergänzen:
```python
from mv_hofki.services import general_item_category as category_service
```

**`_enrich`:** nach dem Block mit den Profilbildern und vor der abschließenden Schleife einfügen:
```python
    general_ids = [i.id for i in items if i.category == "general_item"]
    cat_map = await category_service.categories_for_items(session, general_ids)
```
In der Schleife ergänzen:
```python
        if item.category == "general_item":
            item.categories = cat_map.get(item.id, [])  # type: ignore[attr-defined]
```

**`_build_read_dict`:** vor `if detail:` einfügen:
```python
    if item.category == "general_item":
        d["categories"] = getattr(item, "categories", [])
```

**`create`:**
- Direkt nach der Kategorie-Validierung (vor `_split_fields`) einfügen:
  ```python
      category_ids = data.pop("category_ids", None)
      if category_ids:
          category_ids = await category_service.check_category_ids(session, category_ids)
  ```
  Die Prüfung läuft so vor dem Anlegen, und bei unbekannten IDs entsteht kein halbes Item.
- Nach dem Detail-Block, vor `await session.commit()`:
  ```python
      if category_ids:
          await category_service.set_item_categories(session, item.id, category_ids)
  ```
- Wichtig: `data` ist das von der Route übergebene Dict. `pop` ändert nur dieses Dict, das ist in Ordnung.

**`update`:**
- Direkt nach dem 404-Check einfügen:
  ```python
      category_ids = data.pop("category_ids", None)
      if category_ids is not None:
          category_ids = await category_service.check_category_ids(session, category_ids)
  ```
- Vor `await session.commit()`:
  ```python
      if category_ids is not None:
          await category_service.set_item_categories(session, item.id, category_ids)
  ```
- Hinweis: `data.pop` muss vor `_split_fields` stehen, sonst landet `category_ids` in `base_fields` und `setattr` setzt ein nicht existierendes Attribut.
- `[]` ist `not None`, leert also die Zuordnung. Wurde das Feld nicht gesendet, ergibt `pop` `None`, und die Zuordnung bleibt unverändert.

**`delete`:** vor `await session.delete(item)`:
```python
    await category_service.delete_links_for_items(session, [item_id])
```

- [ ] **Step 6: Route lehnt `category_ids` bei anderen Inventar-Arten ab**

In `src/backend/mv_hofki/api/routes/items.py`:
- In `create_item` nach der Kategorie-Prüfung (`if not category or category not in _CREATE_SCHEMAS: ...`) einfügen:
  ```python
      if "category_ids" in body and category != "general_item":
          raise HTTPException(
              status_code=422,
              detail="Kategorien gibt es nur für allgemeine Gegenstände",
          )
  ```
- In `update_item` nach `category = current["category"]` denselben Block einfügen. `HTTPException` wird dort bereits lokal importiert (`from fastapi import HTTPException` wie in `create_item`); falls nicht, den Import ergänzen.

- [ ] **Step 7: `wipe_inventory`**

In `src/backend/mv_hofki/services/inventar_import.py`, `wipe_inventory`, direkt nach `await db.execute(delete(musician_registers))`:
```python
    await delete_links_for_items(db, None)
```
Oben importieren: `from mv_hofki.services.general_item_category import delete_links_for_items`. Vorher prüfen, dass kein Zirkelimport entsteht; `general_item_category` importiert nur Modelle und Schemas.

- [ ] **Step 8: Tests laufen lassen, sie müssen bestehen**

Run: `IN_CONTAINER 'python -m pytest tests/backend/ -q'`
Expected: alles PASS, auch die bestehenden Item-, Import- und Leih-Tests.

- [ ] **Step 9: Commit**

Dateien: die 5 geänderten Backend-Dateien und `tests/backend/test_items.py`. Message: `feat(inventory): assign categories to general items`.

---

### Task 3: Übernahme-Skript für den Bestand

**Files:**
- Create: `src/backend/mv_hofki/services/general_item_category_import.py`
- Create: `scripts/apply_general_item_categories.py`
- Test: `tests/backend/test_general_item_category_import.py`

**Interfaces:**
- Consumes: `check_category_ids`, `set_item_categories` (Task 2), `GeneralItemCategory`, `InventoryItem`.
- Produces:
  - `read_proposal(path: Path) -> list[ProposalRow]`
  - `ProposalRow(display_nr: str, categories: list[str])`
  - `async apply_assignments(session, rows) -> AssignmentReport`
  - `AssignmentReport(created_categories: list[str], updated_items: int, unknown_numbers: list[str])`

CSV-Format (Trennzeichen `;`, UTF-8, BOM erlaubt):

```
display_nr;label;storage_location;categories
A-001;Glas-Schaukasten;Foyer / Haupteingang;Möbel|Deko
A-013;Papiertonne;Vorraum;Entsorgung
A-020;Holzspieße;Sesselarchiv;
```

- Ausgewertet werden nur `display_nr` und `categories`; `label` und `storage_location` dienen beim Prüfen der Lesbarkeit.
- Kategorien sind durch `|` getrennt und werden getrimmt; leere Einträge fallen weg. Eine leere Spalte bedeutet „keine Kategorien“.

- [ ] **Step 1: Failing tests**

`tests/backend/test_general_item_category_import.py`:

```python
"""Applying a reviewed category proposal CSV to general items."""

from sqlalchemy import select

from mv_hofki.models.general_item_category import GeneralItemCategory
from mv_hofki.services.general_item_category_import import (
    ProposalRow,
    apply_assignments,
    read_proposal,
)


async def _general(client, label):
    resp = await client.post(
        "/api/v1/items", json={"category": "general_item", "label": label}
    )
    assert resp.status_code == 201
    return resp.json()


def test_read_proposal_handles_bom_and_blank_categories(tmp_path):
    csv = tmp_path / "p.csv"
    csv.write_text(
        "﻿display_nr;label;storage_location;categories\n"
        "A-001;Schaukasten;Foyer;Möbel | Deko |\n"
        "A-002;Holzspieße;Archiv;\n",
        encoding="utf-8",
    )
    assert read_proposal(csv) == [
        ProposalRow("A-001", ["Möbel", "Deko"]),
        ProposalRow("A-002", []),
    ]


async def test_apply_creates_categories_and_assigns(client, db_session):
    a1 = await _general(client, "Schaukasten")
    a2 = await _general(client, "Gläser")
    rows = [
        ProposalRow("A-001", ["Möbel", "Deko"]),
        ProposalRow("a-2", ["gastro"]),
        ProposalRow("A-099", ["Deko"]),
    ]
    report = await apply_assignments(db_session, rows)
    assert sorted(report.created_categories) == ["Deko", "Möbel", "gastro"]
    assert report.updated_items == 2
    assert report.unknown_numbers == ["A-099"]

    d1 = (await client.get(f"/api/v1/items/{a1['id']}")).json()
    d2 = (await client.get(f"/api/v1/items/{a2['id']}")).json()
    assert [c["label"] for c in d1["categories"]] == ["Deko", "Möbel"]
    assert [c["label"] for c in d2["categories"]] == ["gastro"]


async def test_apply_reuses_existing_category_ignoring_case(client, db_session):
    await client.post("/api/v1/general-item-categories", json={"label": "Küche"})
    await _general(client, "Topf")
    report = await apply_assignments(db_session, [ProposalRow("A-001", ["KÜCHE"])])
    assert report.created_categories == []
    labels = (await db_session.execute(select(GeneralItemCategory.label))).scalars()
    assert list(labels) == ["Küche"]


async def test_apply_is_idempotent_and_empty_list_clears(client, db_session):
    item = await _general(client, "Stehtisch")
    rows = [ProposalRow("A-001", ["Möbel"])]
    await apply_assignments(db_session, rows)
    again = await apply_assignments(db_session, rows)
    assert again.created_categories == []
    detail = (await client.get(f"/api/v1/items/{item['id']}")).json()
    assert [c["label"] for c in detail["categories"]] == ["Möbel"]

    await apply_assignments(db_session, [ProposalRow("A-001", [])])
    detail = (await client.get(f"/api/v1/items/{item['id']}")).json()
    assert detail["categories"] == []
```

- [ ] **Step 2: Tests laufen lassen, sie müssen scheitern**

Run: `IN_CONTAINER 'python -m pytest tests/backend/test_general_item_category_import.py -v'`
Expected: FAIL mit `ModuleNotFoundError`.

- [ ] **Step 3: Service**

`src/backend/mv_hofki/services/general_item_category_import.py`:

```python
"""Apply a reviewed CSV of category assignments to general items (one-off
bulk step; also usable for later mass corrections)."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.models.general_item_category import GeneralItemCategory
from mv_hofki.models.inventory_item import InventoryItem
from mv_hofki.services.general_item_category import set_item_categories

# "A-001", "a-1", "A 1" -> ("A", 1)
_NR_RE = re.compile(r"^\s*([^\W\d_]+)\s*-?\s*0*(\d+)\s*$")


@dataclass
class ProposalRow:
    display_nr: str
    categories: list[str]


@dataclass
class AssignmentReport:
    created_categories: list[str] = field(default_factory=list)
    updated_items: int = 0
    unknown_numbers: list[str] = field(default_factory=list)


def read_proposal(path: Path) -> list[ProposalRow]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh, delimiter=";")
        return [
            ProposalRow(
                display_nr=(row.get("display_nr") or "").strip(),
                categories=[
                    part.strip()
                    for part in (row.get("categories") or "").split("|")
                    if part.strip()
                ],
            )
            for row in reader
            if (row.get("display_nr") or "").strip()
        ]


async def apply_assignments(
    session: AsyncSession, rows: list[ProposalRow]
) -> AssignmentReport:
    report = AssignmentReport()
    by_label = {
        c.label.casefold(): c
        for c in (await session.execute(select(GeneralItemCategory))).scalars()
    }

    for row in rows:
        match = _NR_RE.match(row.display_nr)
        item_id = None
        if match:
            item_id = await session.scalar(
                select(InventoryItem.id).where(
                    InventoryItem.category == "general_item",
                    func.upper(InventoryItem.number_prefix) == match[1].upper(),
                    InventoryItem.inventory_nr == int(match[2]),
                )
            )
        if item_id is None:
            report.unknown_numbers.append(row.display_nr)
            continue

        ids: set[int] = set()
        for label in row.categories:
            category = by_label.get(label.casefold())
            if category is None:
                category = GeneralItemCategory(label=label[:50])
                session.add(category)
                await session.flush()
                by_label[label.casefold()] = category
                report.created_categories.append(category.label)
            ids.add(category.id)
        await set_item_categories(session, item_id, sorted(ids))
        report.updated_items += 1

    await session.commit()
    return report
```

- [ ] **Step 4: Tests laufen lassen, sie müssen bestehen**

Run: `IN_CONTAINER 'python -m pytest tests/backend/test_general_item_category_import.py -v'`
Expected: alle PASS.

- [ ] **Step 5: CLI-Skript**

`scripts/apply_general_item_categories.py`:

```python
#!/usr/bin/env python
"""Apply a reviewed category proposal to the general items.

Usage (inside the devcontainer, from the project root):

    PYTHONPATH=src/backend python scripts/apply_general_item_categories.py \
        data/general_item_categories_proposal.csv

CSV: ``display_nr;label;storage_location;categories`` (``;`` separated, categories
joined with ``|``; an empty cell removes all categories of that item). Missing
categories are created. Each listed item's categories are replaced; nothing else
changes. The database is copied to data/backups/ first.
"""

from __future__ import annotations

import argparse
import asyncio
import shutil
from datetime import datetime
from pathlib import Path

from mv_hofki.core.config import settings
from mv_hofki.db.engine import async_session_factory
from mv_hofki.services.general_item_category_import import (
    apply_assignments,
    read_proposal,
)

ROOT = Path(settings.PROJECT_ROOT)
DB_FILE = ROOT / "data" / "mv_hofki.db"


def _backup() -> Path:
    target = ROOT / "data" / "backups"
    target.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = target / f"mv_hofki-{stamp}-vor-kategorien.db"
    shutil.copy2(DB_FILE, dest)
    return dest


async def _run(csv_path: Path) -> None:
    rows = read_proposal(csv_path)
    print(f"{len(rows)} Zeilen gelesen, Sicherung: {_backup()}")
    async with async_session_factory() as session:
        report = await apply_assignments(session, rows)
    print(f"Gegenstände aktualisiert: {report.updated_items}")
    print(f"Neue Kategorien ({len(report.created_categories)}): "
          f"{', '.join(report.created_categories) or '—'}")
    if report.unknown_numbers:
        print(f"Unbekannte Nummern: {', '.join(report.unknown_numbers)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("csv", type=Path)
    asyncio.run(_run(parser.parse_args().csv))


if __name__ == "__main__":
    main()
```

Prüfen, dass `async_session_factory` so in `mv_hofki.db.engine` heißt (`scripts/inventar_import.py` importiert es genauso). Smoke-Test mit einer leeren CSV (nur Kopfzeile), die nichts ändert:

Run: `IN_CONTAINER 'printf "display_nr;label;storage_location;categories\n" > /tmp/leer.csv && PYTHONPATH=src/backend python scripts/apply_general_item_categories.py /tmp/leer.csv'`
Expected: `0 Zeilen gelesen, Sicherung: …`, `Gegenstände aktualisiert: 0`, `Neue Kategorien (0): —`.

- [ ] **Step 6: Commit**

Dateien: die 3 neuen Dateien. Message: `feat(inventory): script to apply reviewed general item categories`.

---

### Task 4: Frontend-Komponenten `CategoryChips` und `TagSelect`

**Files:**
- Create: `src/frontend/src/components/CategoryChips.vue`
- Create: `src/frontend/src/components/TagSelect.vue`
- Modify: `src/frontend/src/style.css` (globale Chip-Klassen, direkt nach dem `.badge-warning`-Block, etwa Zeile 755)
- Test: `tests/frontend/CategoryChips.test.js`, `tests/frontend/TagSelect.test.js`

**Interfaces:**
- Produces:
  - `<CategoryChips :categories="[{id,label}]" />`: rendert `ul.category-chips > li.category-chip`, bei leerer Liste `<span class="text-muted">—</span>`.
  - `<TagSelect v-model="ids" :options="[{id,label}]" label="Kategorien" :create-option="async (label) => ({id,label})" />`: `createOption` ist optional. Wird es übergeben, muss die Elternkomponente die neue Option selbst in `options` aufnehmen, bevor sie sie zurückgibt.

- [ ] **Step 1: Failing tests**

`tests/frontend/CategoryChips.test.js`:

```js
import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import CategoryChips from "../../src/frontend/src/components/CategoryChips.vue";

describe("CategoryChips", () => {
  it("renders one chip per category", () => {
    const w = mount(CategoryChips, {
      props: { categories: [{ id: 1, label: "Deko" }, { id: 2, label: "Gastro" }] },
    });
    expect(w.findAll(".category-chip").map((c) => c.text())).toEqual(["Deko", "Gastro"]);
  });

  it("shows a dash without categories", () => {
    const w = mount(CategoryChips, { props: { categories: [] } });
    expect(w.find(".category-chips").exists()).toBe(false);
    expect(w.text()).toBe("—");
  });
});
```

`tests/frontend/TagSelect.test.js`:

```js
import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";
import TagSelect from "../../src/frontend/src/components/TagSelect.vue";

const options = [
  { id: 1, label: "Deko" },
  { id: 2, label: "Gastro" },
  { id: 3, label: "Küche" },
];

// Mounts TagSelect and keeps v-model in sync like a parent would.
function setup(props = {}) {
  let w;
  w = mount(TagSelect, {
    props: {
      label: "Kategorien",
      options,
      modelValue: [],
      "onUpdate:modelValue": (v) => w.setProps({ modelValue: v }),
      ...props,
    },
    attachTo: document.body,
  });
  return w;
}

function optionTexts(w) {
  return w.findAll('[role="option"]').map((o) => o.text());
}

describe("TagSelect", () => {
  it("shows selected ids as chips with a named remove button", () => {
    const w = setup({ modelValue: [2] });
    expect(w.findAll(".category-chip").map((c) => c.text().replace("✕", "").trim())).toEqual([
      "Gastro",
    ]);
    expect(w.find('button[aria-label="„Gastro“ entfernen"]').exists()).toBe(true);
  });

  it("filters suggestions case-insensitively and hides selected ones", async () => {
    const w = setup({ modelValue: [1] });
    const input = w.find("input");
    await input.trigger("focus");
    expect(optionTexts(w)).toEqual(["Gastro", "Küche"]);
    await input.setValue("KÜ");
    expect(optionTexts(w)).toEqual(["Küche"]);
  });

  it("selects a suggestion with arrow keys and Enter", async () => {
    const w = setup();
    const input = w.find("input");
    await input.trigger("focus");
    await input.trigger("keydown", { key: "ArrowDown" });
    await input.trigger("keydown", { key: "ArrowDown" });
    await input.trigger("keydown", { key: "Enter" });
    expect(w.emitted("update:modelValue").at(-1)).toEqual([[2]]);
  });

  it("selects an exact match with Enter without arrow keys", async () => {
    const w = setup();
    const input = w.find("input");
    await input.setValue("deko");
    await input.trigger("keydown", { key: "Enter" });
    expect(w.emitted("update:modelValue").at(-1)).toEqual([[1]]);
  });

  it("removes a chip by button and by Backspace in an empty field", async () => {
    const w = setup({ modelValue: [1, 2] });
    await w.find('button[aria-label="„Deko“ entfernen"]').trigger("click");
    expect(w.emitted("update:modelValue").at(-1)).toEqual([[2]]);
    await w.find("input").trigger("keydown", { key: "Backspace" });
    expect(w.emitted("update:modelValue").at(-1)).toEqual([[]]);
  });

  it("offers creation only without an exact match and only with createOption", async () => {
    const w = setup();
    const input = w.find("input");
    await input.setValue("Licht");
    expect(optionTexts(w)).toEqual([]);

    const w2 = setup({ createOption: vi.fn() });
    const input2 = w2.find("input");
    await input2.setValue("Licht");
    expect(optionTexts(w2)).toEqual(["„Licht“ als neue Kategorie anlegen"]);
    await input2.setValue("gastro");
    expect(optionTexts(w2)).toEqual(["Gastro"]);
  });

  it("creates a trimmed new category and selects it", async () => {
    const createOption = vi.fn().mockResolvedValue({ id: 9, label: "Technik" });
    const w = setup({ createOption });
    const input = w.find("input");
    await input.setValue("  Technik ");
    await input.trigger("keydown", { key: "Enter" });
    await new Promise((r) => setTimeout(r, 0));
    expect(createOption).toHaveBeenCalledWith("Technik");
    expect(w.emitted("update:modelValue").at(-1)).toEqual([[9]]);
    expect(input.element.value).toBe("");
  });

  it("shows an inline error when creation fails", async () => {
    const createOption = vi.fn().mockRejectedValue(new Error("Kategorie existiert bereits"));
    const w = setup({ createOption });
    const input = w.find("input");
    await input.setValue("Technik");
    await input.trigger("keydown", { key: "Enter" });
    await new Promise((r) => setTimeout(r, 0));
    expect(w.find('[role="alert"]').text()).toBe("Kategorie existiert bereits");
    expect(w.emitted("update:modelValue")).toBeUndefined();
  });

  it("does not submit the surrounding form on Enter while typing", async () => {
    const onSubmit = vi.fn((e) => e.preventDefault());
    const Host = {
      components: { TagSelect },
      template: `<form @submit="onSubmit"><TagSelect label="Kategorien" :options="options" :model-value="[]" /></form>`,
      setup: () => ({ onSubmit, options }),
    };
    const w = mount(Host, { attachTo: document.body });
    const input = w.find("input");
    await input.setValue("Lic");
    const ev = new KeyboardEvent("keydown", { key: "Enter", cancelable: true, bubbles: true });
    input.element.dispatchEvent(ev);
    expect(ev.defaultPrevented).toBe(true);
  });

  it("closes the list on Escape and wires ARIA", async () => {
    const w = setup();
    const input = w.find("input");
    await input.trigger("focus");
    expect(input.attributes("role")).toBe("combobox");
    expect(input.attributes("aria-expanded")).toBe("true");
    await input.trigger("keydown", { key: "Escape" });
    expect(input.attributes("aria-expanded")).toBe("false");
  });
});
```

- [ ] **Step 2: Tests laufen lassen, sie müssen scheitern**

Run: `IN_CONTAINER 'cd src/frontend && npx vitest run ../../tests/frontend/TagSelect.test.js ../../tests/frontend/CategoryChips.test.js'`
Expected: FAIL (Komponenten fehlen). Findet Vitest die Dateien mit relativem Pfad nicht, weil `root` auf das Projekt zeigt, mit Filter aufrufen: `npx vitest run TagSelect CategoryChips`.

- [ ] **Step 3: Globale Chip-Styles**

In `src/frontend/src/style.css` nach dem `.badge-warning`-Block:

```css
/* Category chips (general items) */
.category-chips {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
  margin: 0;
  padding: 0;
  list-style: none;
}

.category-chip {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: 0.125rem 0.5rem;
  border-radius: 9999px;
  font-size: 0.8125rem;
  line-height: 1.4;
  background: var(--color-primary-light);
  color: var(--color-text);
  white-space: nowrap;
}
```

- [ ] **Step 4: `CategoryChips.vue`**

```vue
<script setup>
defineProps({
  categories: { type: Array, default: () => [] },
});
</script>

<template>
  <ul v-if="categories.length" class="category-chips">
    <li v-for="c in categories" :key="c.id" class="category-chip">{{ c.label }}</li>
  </ul>
  <span v-else class="text-muted">—</span>
</template>
```

- [ ] **Step 5: `TagSelect.vue`**

```vue
<script setup>
import { computed, ref } from "vue";

const props = defineProps({
  modelValue: { type: Array, default: () => [] },
  options: { type: Array, default: () => [] },
  label: { type: String, required: true },
  createOption: { type: Function, default: null },
});
const emit = defineEmits(["update:modelValue"]);

const baseId = `tag-select-${Math.random().toString(36).slice(2, 9)}`;
const query = ref("");
const open = ref(false);
const activeIndex = ref(-1);
const error = ref("");
const busy = ref(false);

const norm = (s) => s.trim().toLocaleLowerCase("de-AT");
const byLabel = (a, b) => a.label.localeCompare(b.label, "de-AT");

const selected = computed(() =>
  props.modelValue.map((id) => props.options.find((o) => o.id === id)).filter(Boolean),
);

const exactOption = computed(() => {
  const q = norm(query.value);
  return q ? props.options.find((o) => norm(o.label) === q) || null : null;
});

const entries = computed(() => {
  const q = norm(query.value);
  const list = props.options
    .filter((o) => !props.modelValue.includes(o.id))
    .filter((o) => !q || norm(o.label).includes(q))
    .sort(byLabel)
    .map((o) => ({ type: "option", key: `o${o.id}`, option: o }));
  if (props.createOption && q && !exactOption.value) {
    list.push({ type: "create", key: "create", label: query.value.trim() });
  }
  return list;
});

const expanded = computed(() => open.value && entries.value.length > 0);

function emitIds(ids) {
  emit("update:modelValue", ids);
}

function pick(option) {
  if (!props.modelValue.includes(option.id)) emitIds([...props.modelValue, option.id]);
  query.value = "";
  activeIndex.value = -1;
}

function remove(id) {
  emitIds(props.modelValue.filter((x) => x !== id));
}

async function create(label) {
  if (busy.value) return;
  busy.value = true;
  error.value = "";
  try {
    const option = await props.createOption(label);
    emitIds([...props.modelValue, option.id]);
    query.value = "";
    activeIndex.value = -1;
  } catch (e) {
    error.value = e?.message || "Kategorie konnte nicht angelegt werden.";
  } finally {
    busy.value = false;
  }
}

function choose(entry) {
  if (entry.type === "option") pick(entry.option);
  else create(entry.label);
}

function onInput() {
  open.value = true;
  activeIndex.value = -1;
  error.value = "";
}

function onKeydown(e) {
  const count = entries.value.length;
  switch (e.key) {
    case "ArrowDown":
      e.preventDefault();
      open.value = true;
      if (count) activeIndex.value = Math.min(count - 1, activeIndex.value + 1);
      break;
    case "ArrowUp":
      e.preventDefault();
      if (count) activeIndex.value = Math.max(0, activeIndex.value - 1);
      break;
    case "Enter": {
      if (activeIndex.value < 0 && !query.value.trim()) return; // let the form submit
      e.preventDefault();
      if (activeIndex.value >= 0 && entries.value[activeIndex.value]) {
        choose(entries.value[activeIndex.value]);
      } else if (exactOption.value) {
        pick(exactOption.value);
      } else if (props.createOption && query.value.trim()) {
        create(query.value.trim());
      }
      break;
    }
    case "Escape":
      if (expanded.value) {
        e.preventDefault();
        e.stopPropagation();
      }
      open.value = false;
      activeIndex.value = -1;
      break;
    case "Backspace":
      if (!query.value && props.modelValue.length) {
        remove(props.modelValue[props.modelValue.length - 1]);
      }
      break;
  }
}

function onFocusOut(e) {
  if (!e.currentTarget.contains(e.relatedTarget)) {
    open.value = false;
    activeIndex.value = -1;
  }
}
</script>

<template>
  <div class="tag-select" @focusout="onFocusOut">
    <label :for="`${baseId}-input`">{{ label }}</label>
    <div class="tag-select-control">
      <ul v-if="selected.length" class="category-chips">
        <li v-for="o in selected" :key="o.id" class="category-chip">
          {{ o.label }}
          <button
            type="button"
            class="tag-select-remove"
            :aria-label="`„${o.label}“ entfernen`"
            @click="remove(o.id)"
          >
            ✕
          </button>
        </li>
      </ul>
      <input
        :id="`${baseId}-input`"
        v-model="query"
        type="text"
        role="combobox"
        autocomplete="off"
        aria-autocomplete="list"
        :aria-expanded="String(expanded)"
        :aria-controls="`${baseId}-list`"
        :aria-activedescendant="activeIndex >= 0 ? `${baseId}-opt-${activeIndex}` : undefined"
        :aria-busy="busy ? 'true' : undefined"
        placeholder="Kategorie suchen oder anlegen …"
        @focus="open = true"
        @input="onInput"
        @keydown="onKeydown"
      />
    </div>
    <ul v-show="expanded" :id="`${baseId}-list`" role="listbox" class="tag-select-list">
      <li
        v-for="(entry, i) in entries"
        :id="`${baseId}-opt-${i}`"
        :key="entry.key"
        role="option"
        :aria-selected="String(i === activeIndex)"
        :class="{ active: i === activeIndex, create: entry.type === 'create' }"
        @mousedown.prevent
        @click="choose(entry)"
      >
        <template v-if="entry.type === 'option'">{{ entry.option.label }}</template>
        <template v-else>„{{ entry.label }}“ als neue Kategorie anlegen</template>
      </li>
    </ul>
    <span v-if="error" class="form-error" role="alert">{{ error }}</span>
  </div>
</template>

<style scoped>
.tag-select {
  position: relative;
}

.tag-select-control {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-1);
  min-height: 44px;
  padding: var(--space-1) var(--space-2);
  border: 1px solid var(--color-border);
  border-radius: 6px;
  background: var(--color-bg);
}

.tag-select-control:focus-within {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px var(--color-focus-ring);
}

.tag-select-control input {
  flex: 1 1 10rem;
  min-width: 8rem;
  min-height: 36px;
  border: none;
  padding: 0 var(--space-1);
  background: transparent;
  box-shadow: none;
}

.tag-select-control input:focus {
  box-shadow: none;
}

.tag-select-remove {
  position: relative;
  display: inline-grid;
  place-items: center;
  width: 1.25rem;
  height: 1.25rem;
  padding: 0;
  border: none;
  border-radius: 9999px;
  background: transparent;
  color: inherit;
  font-size: 0.75rem;
  cursor: pointer;
}

/* 44 px touch target without enlarging the chip */
.tag-select-remove::after {
  content: "";
  position: absolute;
  top: 50%;
  left: 50%;
  width: 44px;
  height: 44px;
  transform: translate(-50%, -50%);
}

.tag-select-remove:hover,
.tag-select-remove:focus-visible {
  background: var(--color-primary-light);
}

.tag-select-list {
  position: absolute;
  z-index: 20;
  left: 0;
  right: 0;
  max-height: 16rem;
  margin: var(--space-1) 0 0;
  padding: var(--space-1) 0;
  overflow-y: auto;
  list-style: none;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  background: var(--color-bg);
  box-shadow: var(--shadow-float);
}

.tag-select-list li {
  display: flex;
  align-items: center;
  min-height: 44px;
  padding: 0 var(--space-3);
  cursor: pointer;
}

.tag-select-list li.active,
.tag-select-list li:hover {
  background: var(--color-primary-light);
}

.tag-select-list li.create {
  color: var(--color-primary);
  font-weight: 500;
}
</style>
```

`--color-focus-ring`, `.form-error` und `.text-muted` sind in `style.css` global und für beide Themes definiert.

- [ ] **Step 6: Tests laufen lassen, sie müssen bestehen**

Run: `IN_CONTAINER 'cd src/frontend && npx vitest run'`
Expected: alle PASS, auch die bestehenden.

- [ ] **Step 7: Commit**

Dateien: `CategoryChips.vue`, `TagSelect.vue`, `style.css`, die zwei Testdateien. Message: `feat(frontend): TagSelect combobox and category chips`.

---

### Task 5: Einstellungsseite, Formular, Detail- und Listenanzeige

**Files:**
- Create: `src/frontend/src/pages/GeneralItemCategoryListPage.vue`
- Modify: `src/frontend/src/router.js` (Route nach `/einstellungen/kleidungstypen`, ca. Zeile 114-118)
- Modify: `src/frontend/src/components/NavBar.vue` (Link nach „Kleidungstypen“, ca. Zeile 74-76)
- Modify: `src/frontend/src/lib/categories.js` (`general_item.hasCategories: true`)
- Modify: `src/frontend/src/components/ItemFormModal.vue`
- Modify: `src/frontend/src/pages/ItemDetailPage.vue` (Stammdaten, Block `category === 'general_item'`, ca. Zeile 311-314)
- Modify: `src/frontend/src/pages/ItemListPage.vue` (Spalten `general_item`, ca. Zeile 77-83; Kartenansicht ca. Zeile 211-217)

**Interfaces:**
- Consumes: API aus Task 1 und 2 (`/general-item-categories` mit `{id,label,item_count}`; Items mit `categories`), `TagSelect` und `CategoryChips` aus Task 4.

- [ ] **Step 1: `lib/categories.js`**

Im Objekt `general_item` nach `hasStorageLocation: true,` ergänzen: `hasCategories: true,`.

- [ ] **Step 2: Einstellungsseite**

`src/frontend/src/pages/GeneralItemCategoryListPage.vue`:

```vue
<script setup>
import { ref, computed, onMounted } from "vue";
import { get, post, put, del } from "../lib/api.js";
import ConfirmDialog from "../components/ConfirmDialog.vue";

const items = ref([]);
const loading = ref(true);
const loadError = ref("");
const editing = ref(null);
const form = ref({ label: "" });
const formError = ref("");
const deleteTarget = ref(null);
const deleteError = ref("");

async function load() {
  loading.value = true;
  loadError.value = "";
  try {
    items.value = await get("/general-item-categories");
  } catch (e) {
    loadError.value = `Kategorien konnten nicht geladen werden: ${e.message}`;
  } finally {
    loading.value = false;
  }
}

onMounted(load);

function startEdit(item) {
  editing.value = item.id;
  form.value = { label: item.label };
  formError.value = "";
}

function startCreate() {
  editing.value = "new";
  form.value = { label: "" };
  formError.value = "";
}

function cancel() {
  editing.value = null;
  formError.value = "";
}

async function save() {
  if (!form.value.label.trim()) {
    formError.value = "Bitte eine Bezeichnung eingeben.";
    return;
  }
  try {
    if (editing.value === "new") {
      await post("/general-item-categories", form.value);
    } else {
      await put(`/general-item-categories/${editing.value}`, form.value);
    }
    editing.value = null;
    await load();
  } catch (e) {
    formError.value = typeof e.message === "string" ? e.message : "Speichern fehlgeschlagen.";
  }
}

const deleteMessage = computed(() => {
  const t = deleteTarget.value;
  if (!t) return "";
  if (t.item_count === 0) return `Soll die Kategorie „${t.label}“ gelöscht werden?`;
  const n = t.item_count === 1 ? "einem Gegenstand" : `${t.item_count} Gegenständen`;
  return `Die Kategorie „${t.label}“ wird von ${n} entfernt und gelöscht.`;
});

async function remove() {
  try {
    await del(`/general-item-categories/${deleteTarget.value.id}`);
    deleteTarget.value = null;
    deleteError.value = "";
    await load();
  } catch (e) {
    deleteError.value = `Löschen fehlgeschlagen: ${e.message}`;
    deleteTarget.value = null;
  }
}
</script>

<template>
  <div>
    <div class="page-header">
      <h1>Kategorien (Allgemein)</h1>
      <button class="btn btn-primary" @click="startCreate">Neue Kategorie</button>
    </div>

    <p v-if="loadError" class="form-error" role="alert">{{ loadError }}</p>
    <p v-if="deleteError" class="form-error" role="alert">{{ deleteError }}</p>

    <div style="overflow-x: auto; -webkit-overflow-scrolling: touch">
      <table>
        <thead>
          <tr>
            <th>Bezeichnung</th>
            <th class="col-num">Gegenstände</th>
            <th style="width: 160px"></th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="editing === 'new'">
            <td colspan="2">
              <input
                v-model="form.label"
                maxlength="50"
                placeholder="Bezeichnung"
                aria-label="Bezeichnung der neuen Kategorie"
                @keydown.enter.prevent="save"
                @keydown.esc="cancel"
              />
              <span v-if="formError" class="form-error" role="alert">{{ formError }}</span>
            </td>
            <td>
              <div style="display: flex; gap: 0.25rem">
                <button class="btn-sm btn-primary" @click="save">Speichern</button>
                <button class="btn-sm" @click="cancel">Abbrechen</button>
              </div>
            </td>
          </tr>
          <tr v-if="loading">
            <td colspan="3" class="text-muted">Wird geladen …</td>
          </tr>
          <tr v-else-if="!items.length && editing !== 'new'">
            <td colspan="3" class="text-muted">
              Noch keine Kategorien. Lege die erste mit „Neue Kategorie“ an.
            </td>
          </tr>
          <tr v-for="item in items" :key="item.id">
            <template v-if="editing === item.id">
              <td colspan="2">
                <input
                  v-model="form.label"
                  maxlength="50"
                  :aria-label="`Neue Bezeichnung für „${item.label}“`"
                  @keydown.enter.prevent="save"
                  @keydown.esc="cancel"
                />
                <span v-if="formError" class="form-error" role="alert">{{ formError }}</span>
              </td>
              <td>
                <div style="display: flex; gap: 0.25rem">
                  <button class="btn-sm btn-primary" @click="save">Speichern</button>
                  <button class="btn-sm" @click="cancel">Abbrechen</button>
                </div>
              </td>
            </template>
            <template v-else>
              <td>{{ item.label }}</td>
              <td class="col-num">{{ item.item_count }}</td>
              <td>
                <div style="display: flex; gap: 0.25rem">
                  <button class="btn-sm" @click="startEdit(item)">Bearbeiten</button>
                  <button
                    class="btn-sm btn-danger"
                    :aria-label="`„${item.label}“ löschen`"
                    @click="deleteTarget = item"
                  >
                    Löschen
                  </button>
                </div>
              </td>
            </template>
          </tr>
        </tbody>
      </table>
    </div>

    <ConfirmDialog
      :open="!!deleteTarget"
      title="Kategorie löschen"
      :message="deleteMessage"
      @confirm="remove"
      @cancel="deleteTarget = null"
    />
  </div>
</template>
```

`ConfirmDialog` hat die Props `open`/`title`/`message` und die Events `confirm`/`cancel`. `.col-num` ist bereits global (ItemListPage nutzt es).

- [ ] **Step 3: Route und Menü**

`router.js`, nach dem Eintrag `/einstellungen/kleidungstypen`:
```js
  {
    path: "/einstellungen/kategorien",
    name: "general-item-categories",
    component: () => import("./pages/GeneralItemCategoryListPage.vue"),
  },
```
`NavBar.vue`, nach dem RouterLink „Kleidungstypen“:
```vue
            <RouterLink to="/einstellungen/kategorien" @click="closeMenu">
              Kategorien (Allgemein)
            </RouterLink>
```

- [ ] **Step 4: Item-Formular**

In `src/frontend/src/components/ItemFormModal.vue`:
- Import: `import TagSelect from "./TagSelect.vue";` und `post` ist schon importiert.
- State: `const categoryOptions = ref([]);`
- `defaultForm()`: `category_ids: [],` ergänzen.
- `loadTypeOptions()` am Ende:
  ```js
  if (cat.value.hasCategories) {
    categoryOptions.value = await get("/general-item-categories");
  }
  ```
- Edit-Zweig im `watch` (Objekt `form.value = {...}`): `category_ids: (item.categories || []).map((c) => c.id),`
- Neue Funktion:
  ```js
  async function createCategory(label) {
    const created = await post("/general-item-categories", { label });
    categoryOptions.value = [...categoryOptions.value, created];
    return created;
  }
  ```
- `buildPayload()`, im Zweig `general_item` ergänzen: `data.category_ids = form.value.category_ids;`
- Template: direkt nach dem Block `<div v-if="cat.labelField === 'text'" class="form-group" ...>…</div>` (Bezeichnung) einfügen:
  ```vue
          <div v-if="cat.hasCategories" class="form-group">
            <TagSelect
              v-model="form.category_ids"
              :options="categoryOptions"
              label="Kategorien"
              :create-option="createCategory"
            />
          </div>
  ```
- `TagSelect` bringt sein eigenes `<label>` mit. Prüfen, dass `.form-group label` global so gestylt ist, dass es wie die anderen Feldlabels aussieht.

- [ ] **Step 5: Detailseite**

In `src/frontend/src/pages/ItemDetailPage.vue`:
- Import: `import CategoryChips from "../components/CategoryChips.vue";`
- Im Block `<template v-if="category === 'general_item'">` vor „Lagerort“:
  ```vue
          <dt>Kategorien</dt>
          <dd><CategoryChips :categories="item.categories || []" /></dd>
  ```

- [ ] **Step 6: Liste und Karten**

In `src/frontend/src/pages/ItemListPage.vue`:
- Import: `import CategoryChips from "../components/CategoryChips.vue";`
- Spalten `general_item`: nach `{ key: "label", label: "Bezeichnung" },` einfügen:
  `{ key: "categories", label: "Kategorien", hideEmptyInCard: true },`
  `DataTable` wertet für `hideEmptyInCard` nur `""` und `null` als leer, ein leeres Array nicht (`DataTable.vue:16-20`). In `mapItem` deshalb im zurückgegebenen Objekt `categories: i.categories?.length ? i.categories : null` setzen.
- Die Einfügestelle der Menge-Spalte (`base.slice(0, 2)`) bleibt unverändert: Nummer, Bezeichnung, Menge, Kategorien …
- `DataTable`-Slot für die Zelle (im `<DataTable …>`-Element):
  ```vue
      <template #categories="{ value }">
        <CategoryChips :categories="value || []" />
      </template>
  ```
  Gibt es dort schon andere Slot-Templates, daneben setzen.
- Kartenansicht (`.instrument-card-body`), nach dem `<p>…display_nr…</p>`:
  ```vue
          <CategoryChips v-if="item.categories?.length" :categories="item.categories" />
  ```

- [ ] **Step 7: Build, Tests und Lint**

Run: `IN_CONTAINER 'cd src/frontend && npx vitest run && npx vite build'`
Expected: Tests PASS, Build ohne Fehler.
Run: `IN_CONTAINER 'pre-commit run --files <alle in Task 5 geänderten Dateien>'`
Expected: alle Hooks Passed (eslint, prettier).

- [ ] **Step 8: Im Browser prüfen**

- Den Host-Port ermitteln: `docker port mv-hofki-vue-pyhton_devcontainer-devcontainer-1 8000`.
- Mit den Playwright-Werkzeugen (`mcp__playwright-lokal__*`) auf `http://localhost:<port>` prüfen:
  1. `/einstellungen/kategorien`: Kategorie „Test-Kategorie“ anlegen und umbenennen. Ein Duplikat zeigt einen Inline-Fehler.
  2. `/allgemein`: ein Item öffnen, „Bearbeiten“, im Feld „Kategorien“ „Test-Kategorie“ auswählen, „Neu-Test“ tippen und mit Enter anlegen, speichern. Die Detailseite zeigt beide Chips.
  3. Die Liste `/allgemein` zeigt die Chips in der Tabelle und in der Kartenansicht. Das in dunklem Theme per Screenshot prüfen.
  4. Aufräumen: beide Test-Kategorien löschen. Der Bestätigungstext nennt die Anzahl („von einem Gegenstand entfernt“).
- Achtung, das ist die echte Datenbank: Nur Test-Kategorien verwenden und sie am Ende wieder löschen. Danach am Item keine Kategorien mehr.

- [ ] **Step 9: Commit**

Dateien: die 7 Frontend-Dateien aus Task 5. Message: `feat(frontend): manage and show categories of general items`.

---

### Task 6 (Controller, keine Subagent-Aufgabe): Vorschlag für den Bestand

Diese Aufgabe erledigt der Controller selbst mit dem Benutzer. Sie ändert keinen Repo-Code.

- [ ] Die 164 Items (`display_nr`, `label`, `storage_location`) aus `data/mv_hofki.db` lesen.
- [ ] Einen Startsatz von 8–12 Kategorien festlegen und jedem Item 0–n Kategorien zuordnen.
- [ ] Das Ergebnis nach `data/general_item_categories_proposal.csv` schreiben (Format wie in Task 3; `data/` ist nicht im Git).
- [ ] Dem Benutzer die Kategorien mit Anzahl zeigen, die Datei zur Prüfung übergeben und **auf Freigabe warten**.
- [ ] Nach der Freigabe: `IN_CONTAINER 'PYTHONPATH=src/backend python scripts/apply_general_item_categories.py data/general_item_categories_proposal.csv'` ausführen und die Ausgabe melden.
