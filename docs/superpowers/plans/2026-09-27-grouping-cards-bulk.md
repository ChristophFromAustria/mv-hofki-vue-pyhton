# Gruppierung, kompakte Karten, Sammelzuweisung: Implementierungsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Die Listen Items, Musiker und Leihen lassen sich serverseitig gruppieren (Instrumente standardmäßig nach Typ), mit einklappbaren Gruppenüberschriften. Die Item-Karten werden am Handy kompakt. Allgemeine Items bekommen Kategorien per Mehrfachauswahl.

**Architektur:**
- **Backend:** `ListFilter` bekommt `group_by` und `GroupSpec`. Die neue Funktion `fetch_page()` liefert Zeilen mit `group_key`/`group_label`, Gruppenzähler und `item_total`; Mehrfach-Zuordnungen erzeugen eine Zeile je Gruppe. Dazu kommt ein Endpunkt für die Sammelzuweisung.
- **Frontend:**
  - Ein reiner Helfer `buildSegments` fügt Gruppen-Segmente ein, `useGroupCollapse` merkt sich eingeklappte Gruppen.
  - `DataTable` und das neue `ItemCard` rendern Gruppen und Auswahl.
  - `BulkCategoryBar` und `CategoryPickDialog` bedienen die Sammelzuweisung.

**Tech Stack:** FastAPI, fastapi-filter 3, SQLAlchemy 2.0 async (SQLite), Pydantic 2; Vue 3.4, vue-router 4, Vitest und @vue/test-utils.

**Spec:** `docs/superpowers/specs/2026-09-27-grouping-cards-bulk-design.md`

## Global Constraints

- Ausführung, Commits, Sprache, Styling und Bedienbarkeit wie im letzten Plan:
  - **Container:** Befehle laufen per `IN_CONTAINER '<befehl>'` = `docker exec -w /workspaces/mv_hofki mv-hofki-vue-pyhton_devcontainer-devcontainer-1 bash -lc '<befehl>'`.
  - **Commits:** im Container mit Host-Identität (`-e GIT_AUTHOR_NAME/EMAIL -e GIT_COMMITTER_NAME/EMAIL` aus `git config`), Nachricht endet mit `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`. Nur eigene Dateien committen; niemals `git stash/reset/clean/add -A`.
  - **Text und Gestaltung:** Deutsch mit „…“, nur Tokens aus `style.css`, Touch-Ziele ≥ 44 px, benannte Buttons, Fehler inline statt `alert()` in neuem Code.
- **Bekannte fremde Testfehler, ignorieren:**
  - `tests/backend/test_item_invoices.py::test_create_invoice_on_sheet_music_rejected`
  - `tests/backend/test_scanner_config.py::test_sync_preserves_user_value`
  - `tests/frontend/App.test.js`
- **Gruppenschlüssel:** im JSON immer Strings; die NULL-Gruppe hat den Schlüssel `""` und das `empty_label` der Spec als Label.
- **Reihenfolge:**
  - **Gruppen:** zuerst `group_order` aufsteigend (NULL zuletzt), dann `group_key`.
  - **Zeilen:** wie die Gruppen, dann die Benutzer-Sortierung, zuletzt `id`.
  - **Zähler:** `count` zählt verschiedene Einträge pro Gruppe.
- **Mengen:**
  - `total` = Anzahl Zeilen (fürs Nachladen).
  - `item_total` = verschiedene Einträge.
  - Ohne Gruppierung gilt `total == item_total`, und es gibt kein `groups`.
- **Fehlertexte (422):**
  - „„x“ ist keine gültige Gruppierung.“
  - „Gruppierung „x“ gibt es für <Art> nicht“
  - „Keine Kategorien angegeben“
  - „Kategorie kann nicht gleichzeitig hinzugefügt und entfernt werden“
  - „Nur allgemeine Gegenstände: <ids kommagetrennt>“
- **Frontend:**
  - Die Zeilen-Keys sind `row._key ?? row.id`, mit `_key = "<group_key>:<id>"` bei Gruppierung.
  - `localStorage` wird nur in `try/catch` gelesen und geschrieben.
- **Browser-Prüfungen:** gegen die echte DB nur lesen. Einzige Ausnahme ist Task 7: eine Test-Kategorie „Test-Sammel“ anlegen, zwei Items zuweisen, wieder entfernen, die Kategorie löschen und zum Schluss prüfen, dass die Kategorien der betroffenen Items unverändert sind.

## Review Focus

1. **Mehrfachzeilen über Seitengrenzen:** Ein Gegenstand mit 2 Kategorien bei `limit=1`. Seite 1 und 2 liefern je eine Zeile desselben Gegenstands in verschiedenen Gruppen, und keine Zeile doppelt. (Test in Task 1)
2. **Gruppe am Seitenende geteilt:** Die Überschrift erscheint nur einmal, wenn eine Gruppe über zwei nachgeladene Seiten läuft; die Anzahl stammt aus `groups`, nicht aus den geladenen Zeilen. (Test in Task 5 für `buildSegments`)
3. **Auswahl bei doppelten Zeilen:** Wählt man einen Gegenstand, der in zwei Gruppen steht, sind beide Zeilen markiert, und er wird genau einmal gesendet. (Test in Task 7)
4. **Instrumente ohne `group_by` in der URL:** Die Seite gruppiert nach Typ. „Keine“ schreibt `group_by=alle` und überlebt ein Neuladen. (Browser in Task 6; die Logik ist durch die `useListQuery`-Tests abgedeckt)
5. **Eingeklappt und Nachladen:** Sind alle Gruppen eingeklappt, lädt die Liste weiter nach, statt stehenzubleiben, und neue Zeilen eingeklappter Gruppen bleiben verborgen. (Test in Task 5)

---

### Task 1: Gruppierung in `filters/base.py` und in der Antwortform

**Files:**
- Modify: `src/backend/mv_hofki/filters/base.py`
- Modify: `src/backend/mv_hofki/schemas/pagination.py`
- Test: `tests/backend/test_list_grouping.py` (neu)

**Interfaces (Produces):**
- `GroupSpec(key, label, empty_label, order=None, join=None, multi=False)` (frozen dataclass)
- `ListFilter.group_by: str | None`
- `ListFilter.Constants.group_fields: dict[str, GroupSpec | None]` (None = Unterklasse löst in `group_spec()` auf)
- `ListFilter.group_spec() -> GroupSpec | None`
- `ListPage(rows: list, total: int, item_total: int, row_groups: list[tuple[str, str]] | None, groups: list[dict] | None)`
- `async fetch_page(session, flt, query, page, *, options=()) -> ListPage`
- `schemas.pagination.GroupCount(key: str, label: str, count: int)`
- `PaginatedResponse` bekommt `item_total: int | None = None` und `groups: list[GroupCount] | None = None`
- `schemas.pagination.Grouped` (Mixin mit `group_key: str | None = None`, `group_label: str | None = None`)

- [ ] **Step 1: Failing tests** — `tests/backend/test_list_grouping.py`:

```python
"""fetch_page: grouping, counts, NULL group, multi-valued rows, paging."""

import pytest
from pydantic import ValidationError
from sqlalchemy import case, select

from mv_hofki.filters.base import GroupSpec, ListFilter, PageParams, fetch_page
from mv_hofki.models.musician import Musician
from mv_hofki.models.register import Register, musician_registers


def _join_registers(query):
    return query.outerjoin(
        musician_registers, musician_registers.c.musician_id == Musician.id
    ).outerjoin(Register, Register.id == musician_registers.c.register_id)


class _Filter(ListFilter):
    class Constants(ListFilter.Constants):
        model = Musician
        sort_fields = {"first_name": [Musician.first_name]}
        default_sort = ["first_name"]
        group_fields = {
            "city": GroupSpec(
                key=Musician.city, label=Musician.city, empty_label="Ohne Ort"
            ),
            "register": GroupSpec(
                key=Register.id,
                label=Register.label,
                order=Register.sort_order,
                empty_label="Ohne Register",
                join=_join_registers,
                multi=True,
            ),
            "status": GroupSpec(
                key=case((Musician.is_active, "aktiv"), else_="inaktiv"),
                label=case((Musician.is_active, "Aktiv"), else_="Inaktiv"),
                order=case((Musician.is_active, 0), else_=1),
                empty_label="—",
            ),
        }


@pytest.fixture
async def people(db_session):
    brass = Register(label="Blech", sort_order=2)
    wood = Register(label="Holz", sort_order=1)
    db_session.add_all([brass, wood])
    await db_session.flush()
    anna = Musician(first_name="Anna", last_name="A", city="Wels", is_active=True)
    berta = Musician(first_name="Berta", last_name="B", city="Linz", is_active=False)
    carl = Musician(first_name="Carl", last_name="C", city=None, is_active=True)
    dora = Musician(first_name="Dora", last_name="D", city="Linz", is_active=True)
    anna.registers = [brass, wood]
    berta.registers = [brass]
    db_session.add_all([anna, berta, carl, dora])
    await db_session.commit()
    return {"brass": brass.id, "wood": wood.id}


def _names(page):
    return [m.first_name for m in page.rows]


async def test_ungrouped_is_plain_paging(db_session, people):
    page = await fetch_page(db_session, _Filter(), select(Musician), PageParams(limit=50, offset=0))
    assert _names(page) == ["Anna", "Berta", "Carl", "Dora"]
    assert page.total == page.item_total == 4
    assert page.groups is None and page.row_groups is None


async def test_single_valued_groups_with_null_last(db_session, people):
    page = await fetch_page(
        db_session, _Filter(group_by="city"), select(Musician), PageParams(limit=50, offset=0)
    )
    assert _names(page) == ["Berta", "Dora", "Anna", "Carl"]
    assert page.row_groups == [
        ("Linz", "Linz"), ("Linz", "Linz"), ("Wels", "Wels"), ("", "Ohne Ort"),
    ]
    assert page.groups == [
        {"key": "Linz", "label": "Linz", "count": 2},
        {"key": "Wels", "label": "Wels", "count": 1},
        {"key": "", "label": "Ohne Ort", "count": 1},
    ]
    assert page.total == page.item_total == 4


async def test_multi_valued_rows_repeat_and_order_by_group_order(db_session, people):
    page = await fetch_page(
        db_session, _Filter(group_by="register"), select(Musician), PageParams(limit=50, offset=0)
    )
    # Holz (sort_order 1) before Blech (2), then no register
    assert [(m.first_name, g[1]) for m, g in zip(page.rows, page.row_groups)] == [
        ("Anna", "Holz"),
        ("Anna", "Blech"),
        ("Berta", "Blech"),
        ("Carl", "Ohne Register"),
        ("Dora", "Ohne Register"),
    ]
    assert page.total == 5
    assert page.item_total == 4
    assert page.groups == [
        {"key": str(people["wood"]), "label": "Holz", "count": 1},
        {"key": str(people["brass"]), "label": "Blech", "count": 2},
        {"key": "", "label": "Ohne Register", "count": 2},
    ]


async def test_multi_valued_paging_has_no_gaps(db_session, people):
    seen = []
    for offset in range(5):
        page = await fetch_page(
            db_session,
            _Filter(group_by="register"),
            select(Musician),
            PageParams(limit=1, offset=offset),
        )
        assert page.total == 5
        seen += [(m.id, g[0]) for m, g in zip(page.rows, page.row_groups)]
    assert len(seen) == 5 and len(set(seen)) == 5


async def test_case_expression_group(db_session, people):
    page = await fetch_page(
        db_session,
        _Filter(group_by="status"),
        select(Musician),
        PageParams(limit=50, offset=0),
    )
    assert [(m.first_name, g[1]) for m, g in zip(page.rows, page.row_groups)] == [
        ("Anna", "Aktiv"),
        ("Carl", "Aktiv"),
        ("Dora", "Aktiv"),
        ("Berta", "Inaktiv"),
    ]
    assert page.groups == [
        {"key": "aktiv", "label": "Aktiv", "count": 3},
        {"key": "inaktiv", "label": "Inaktiv", "count": 1},
    ]


def test_unknown_group_rejected():
    with pytest.raises(ValidationError) as exc:
        _Filter(group_by="nope")
    assert "keine gültige Gruppierung" in str(exc.value)


def test_empty_group_by_means_none():
    assert _Filter(group_by="").group_by is None
```

Zu `test_case_expression_group`: Die Reihenfolge der Gruppen kommt aus `order` (Aktiv = 0), innerhalb der Gruppe wird nach `first_name` sortiert.

Zu den Sortier-Details in `test_single_valued_groups_with_null_last`: Linz kommt vor Wels, weil nach Label aufsteigend sortiert wird; innerhalb von Linz stehen Berta und Dora nach `first_name`.

- [ ] **Step 2: Tests laufen lassen, sie müssen scheitern**

Run: `IN_CONTAINER 'python -m pytest tests/backend/test_list_grouping.py -q'`
Expected: ImportError (`GroupSpec`, `fetch_page`).

- [ ] **Step 3: Implementierung in `filters/base.py`**

Imports ergänzen: `from dataclasses import dataclass`. Der Docstring des Moduls bekommt einen Punkt dazu: „* ``Constants.group_fields`` defines optional grouping (see ``fetch_page``).“

Nach `PageParams`:

```python
@dataclass(frozen=True)
class GroupSpec:
    """How a list groups its rows. ``key``/``label``/``order`` are SQL
    expressions (``order`` defaults to ``label``); ``join`` adds the outer joins
    they need. With ``multi`` a row repeats once per group, e.g. an item with
    several categories; rows without one form the ``empty_label`` group."""

    key: Any
    label: Any
    empty_label: str
    order: Any = None
    join: Callable[[Select], Select] | None = None
    multi: bool = False


@dataclass
class ListPage:
    rows: list[Any]
    total: int
    item_total: int
    row_groups: list[tuple[str, str]] | None = None
    groups: list[dict[str, Any]] | None = None
```

In `ListFilter`:
- Feld `group_by: str | None = None` neben `search`/`order_by`.
- In `Constants`: `group_fields: dict[str, GroupSpec | None] = {}`.
- Validator:

```python
    @field_validator("group_by")
    @classmethod
    def validate_group_by(cls, value: str | None) -> str | None:
        if not value:
            return None
        if value not in cls.Constants.group_fields:
            raise ValueError(f"„{value}“ ist keine gültige Gruppierung.")
        return value

    def group_spec(self) -> GroupSpec | None:
        if not self.group_by:
            return None
        return self.Constants.group_fields[self.group_by]
```

- `filter()`: am Anfang der Schleife `if name == "group_by": continue`.

Nach `paginate`:

```python
def _key(value: Any) -> str:
    return "" if value is None else str(value)


async def fetch_page(
    session: AsyncSession,
    flt: ListFilter,
    query: Select,
    page: PageParams,
    *,
    options: Sequence[Any] = (),
) -> ListPage:
    """Filter, optionally group, sort and page ``query`` (a select of the
    filter's model). See ``GroupSpec`` for grouping."""
    filtered = flt.filter(query)
    distinct = filtered.order_by(None).subquery()
    item_total = (
        await session.scalar(select(func.count(func.distinct(distinct.c.id)))) or 0
    )
    spec = flt.group_spec()
    if spec is None:
        rows, total = await paginate(session, flt.sort(filtered), page, options=options)
        return ListPage(rows=rows, total=total, item_total=item_total)

    order = spec.order if spec.order is not None else spec.label
    grouped = spec.join(filtered) if spec.join else filtered
    grouped = grouped.add_columns(
        spec.key.label("group_key"),
        spec.label.label("group_label"),
        order.label("group_order"),
    )

    sub = grouped.order_by(None).subquery()
    total = await session.scalar(select(func.count()).select_from(sub)) or 0
    count_rows = await session.execute(
        select(sub.c.group_key, sub.c.group_label, func.count(func.distinct(sub.c.id)))
        .group_by(sub.c.group_key, sub.c.group_label, sub.c.group_order)
        .order_by(sub.c.group_order.asc().nulls_last(), sub.c.group_key.asc().nulls_last())
    )
    groups = [
        {
            "key": _key(key),
            "label": spec.empty_label if key is None else str(label),
            "count": count,
        }
        for key, label, count in count_rows.all()
    ]

    ordered = flt.sort(
        grouped.order_by(order.asc().nulls_last(), spec.key.asc().nulls_last())
    )
    result = await session.execute(
        ordered.options(*options).limit(page.limit).offset(page.offset)
    )
    rows = result.unique().all()
    return ListPage(
        rows=[r[0] for r in rows],
        total=total,
        item_total=item_total,
        row_groups=[
            (
                _key(r.group_key),
                spec.empty_label if r.group_key is None else str(r.group_label),
            )
            for r in rows
        ],
        groups=groups,
    )
```

Hinweise:
- Ein Subquery aus `select(Model, …labels)` enthält die Modellspalten, auch `id`.
- `unique()` auf Tupel-Zeilen funktioniert, weil ORM-Objekte hashbar sind.
- Meldet SQLAlchemy doppelte Spaltennamen (etwa bei Joins, deren Entities nicht ausgewählt werden), die Ursache im Report festhalten und nur die fraglichen Spalten per `.label()` umbenennen.

- [ ] **Step 4: `schemas/pagination.py`**

```python
class GroupCount(BaseModel):
    key: str
    label: str
    count: int


class Grouped(BaseModel):
    """Mixin for list rows: the group a row belongs to when grouping is on."""

    group_key: str | None = None
    group_label: str | None = None


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int
    item_total: int | None = None
    groups: list[GroupCount] | None = None
```

- [ ] **Step 5: Tests laufen lassen, sie müssen bestehen**

Run: `IN_CONTAINER 'python -m pytest tests/backend -q'`
Expected: die neuen Tests bestehen, und alle übrigen außer den bekannten fremden Fehlern.

- [ ] **Step 6: Commit**

Dateien: `filters/base.py`, `schemas/pagination.py`, `tests/backend/test_list_grouping.py`. Message: `feat(api): server-side grouping for list filters`.

---

### Task 2: Gruppierung für Musiker und Leihen (API)

**Files:**
- Modify: `src/backend/mv_hofki/filters/musician.py`, `filters/loan.py`
- Modify: `src/backend/mv_hofki/services/musician.py` (`get_list`), `services/loan.py` (`get_list`)
- Modify: `src/backend/mv_hofki/schemas/musician.py` (`MusicianListRow`), `schemas/loan.py` (`LoanListRow`)
- Modify: `src/backend/mv_hofki/api/routes/musicians.py` (`list_musicians`), `api/routes/loans.py` (`list_loans`)
- Test: `tests/backend/test_musicians.py`, `tests/backend/test_loans.py` (anhängen)

**Interfaces:**
- Consumes: `GroupSpec`, `fetch_page`, `ListPage`, `Grouped`, `GroupCount` aus Task 1.
- Produces:
  - `GET /musicians?group_by=register|status`
  - `GET /loans?group_by=musician|item_category|status`
  - Antworten mit `groups`, `item_total` und Zeilen mit `group_key`/`group_label`
  - `musician_service.get_list` und `loan_service.get_list` liefern jetzt `ListPage`

- [ ] **Step 1: Failing tests**

An `tests/backend/test_musicians.py` anhängen:

```python
async def test_group_by_register_repeats_members_and_counts(client):
    wood = (await client.post("/api/v1/registers", json={"label": "Holz", "sort_order": 1})).json()
    brass = (await client.post("/api/v1/registers", json={"label": "Blech", "sort_order": 2})).json()
    await _musician(client, "Anna", "Maier", register_ids=[wood["id"], brass["id"]])
    await _musician(client, "Berta", "Huber", register_ids=[brass["id"]])
    await _musician(client, "Carl", "Aigner")
    body = (await client.get("/api/v1/musicians?group_by=register")).json()
    assert [(m["first_name"], m["group_label"]) for m in body["items"]] == [
        ("Anna", "Holz"),
        ("Berta", "Blech"),
        ("Anna", "Blech"),
        ("Carl", "Ohne Register"),
    ]
    assert body["total"] == 4 and body["item_total"] == 3
    assert body["groups"] == [
        {"key": str(wood["id"]), "label": "Holz", "count": 1},
        {"key": str(brass["id"]), "label": "Blech", "count": 2},
        {"key": "", "label": "Ohne Register", "count": 1},
    ]


async def test_group_by_status_and_invalid_group(client):
    await _musician(client, "Anna", "Maier")
    await _musician(client, "Berta", "Huber", is_active=False)
    body = (await client.get("/api/v1/musicians?group_by=status")).json()
    assert [g["label"] for g in body["groups"]] == ["Aktiv", "Inaktiv"]
    assert (await client.get("/api/v1/musicians?group_by=city")).status_code == 422


async def test_without_grouping_no_group_fields(client):
    await _musician(client, "Anna", "Maier")
    body = (await client.get("/api/v1/musicians")).json()
    assert body["groups"] is None
    assert body["item_total"] == body["total"] == 1
    assert body["items"][0]["group_key"] is None
```

Zu `test_group_by_register_repeats_members_and_counts`:
- In „Blech“ werden Huber Berta und Maier Anna nach `last_name`, dann `first_name` sortiert; das ist die Standardsortierung der Musiker aus dem letzten Teilprojekt.
- Prüfe, ob `RegisterCreate` ein Feld `sort_order` annimmt; laut Schema ja.

An `tests/backend/test_loans.py` anhängen (die Helfer innerhalb von `test_loan_filters_sort_and_search` sind lokal; hier werden sie als Modul-Helfer neu angelegt):

```python
async def _setup_three_loans(client):
    tu = (await client.post("/api/v1/instrument-types", json={"label": "Tuba", "label_short": "TU"})).json()
    hat_type = (await client.post("/api/v1/clothing-types", json={"label": "Hut"})).json()

    async def item(**data):
        return (await client.post("/api/v1/items", json=data)).json()["id"]

    async def musician(first, last):
        return (await client.post("/api/v1/musicians", json={"first_name": first, "last_name": last})).json()["id"]

    tuba = await item(category="instrument", label="Tuba", instrument_type_id=tu["id"])
    tuba2 = await item(category="instrument", label="Tuba", instrument_type_id=tu["id"])
    hat = await item(category="clothing", label="Hut", clothing_type_id=hat_type["id"])
    anna = await musician("Anna", "Maier")
    berta = await musician("Berta", "Huber")
    for item_id, m, start in ((tuba, anna, "2026-01-01"), (hat, anna, "2026-02-01"), (tuba2, berta, "2026-03-01")):
        r = await client.post("/api/v1/loans", json={"item_id": item_id, "musician_id": m, "start_date": start})
        assert r.status_code == 201
    return anna, berta


async def test_loans_group_by_musician_category_status(client):
    anna, berta = await _setup_three_loans(client)
    body = (await client.get("/api/v1/loans?group_by=musician")).json()
    assert [g["label"] for g in body["groups"]] == ["Huber Berta", "Maier Anna"]
    assert [g["count"] for g in body["groups"]] == [1, 2]
    body = (await client.get("/api/v1/loans?group_by=item_category")).json()
    assert [(g["key"], g["label"]) for g in body["groups"]] == [
        ("instrument", "Instrumente"),
        ("clothing", "Kleidung"),
    ]
    body = (await client.get("/api/v1/loans?group_by=status")).json()
    assert body["groups"] == [{"key": "offen", "label": "Offen", "count": 3}]
    assert all(row["group_key"] == "offen" for row in body["items"])
```

Die Reihenfolge der Inventar-Arten legt `order` fest: Instrumente = 0, Kleidung = 1, Allgemein = 2.

- [ ] **Step 2: Tests laufen lassen, sie müssen scheitern.** Run: `IN_CONTAINER 'python -m pytest tests/backend/test_musicians.py tests/backend/test_loans.py -q'`.

- [ ] **Step 3: `filters/musician.py`**

```python
from sqlalchemy import case

from mv_hofki.filters.base import GroupSpec, ListFilter
from mv_hofki.models.register import Register, musician_registers


def _join_registers(query: Select) -> Select:
    return query.outerjoin(
        musician_registers, musician_registers.c.musician_id == Musician.id
    ).outerjoin(Register, Register.id == musician_registers.c.register_id)
```

In `MusicianFilter.Constants` ergänzen:

```python
        group_fields = {
            "register": GroupSpec(
                key=Register.id,
                label=Register.label,
                order=Register.sort_order,
                empty_label="Ohne Register",
                join=_join_registers,
                multi=True,
            ),
            "status": GroupSpec(
                key=case((Musician.is_active, "aktiv"), else_="inaktiv"),
                label=case((Musician.is_active, "Aktiv"), else_="Inaktiv"),
                order=case((Musician.is_active, 0), else_=1),
                empty_label="—",
            ),
        }
```

Achtung, Konflikt: `filter_register_id__in` filtert über eine Subquery, der Register-Join entsteht separat. Das ist richtig so, weil der Filter Musiker auswählt und die Gruppe ihre Register zeigt. Wer nach Register „Holz“ filtert und nach Register gruppiert, sieht diese Musiker also auch unter ihren anderen Registern. Das ist gewollt und entspricht „in jeder seiner Gruppen“.

- [ ] **Step 4: `filters/loan.py`**

```python
from sqlalchemy import case, literal

from mv_hofki.filters.base import GroupSpec, ListFilter

_CATEGORY_LABEL = case(
    (InventoryItem.category == "instrument", "Instrumente"),
    (InventoryItem.category == "clothing", "Kleidung"),
    else_="Allgemein",
)
_CATEGORY_ORDER = case(
    (InventoryItem.category == "instrument", 0),
    (InventoryItem.category == "clothing", 1),
    else_=2,
)
_MUSICIAN_LABEL = Musician.last_name + literal(" ") + Musician.first_name
```

In `LoanFilter.Constants`:

```python
        group_fields = {
            "musician": GroupSpec(
                key=Musician.id, label=_MUSICIAN_LABEL, empty_label="—"
            ),
            "item_category": GroupSpec(
                key=InventoryItem.category,
                label=_CATEGORY_LABEL,
                order=_CATEGORY_ORDER,
                empty_label="—",
            ),
            "status": GroupSpec(
                key=case((Loan.end_date.is_(None), "offen"), else_="zurueckgegeben"),
                label=case((Loan.end_date.is_(None), "Offen"), else_="Zurückgegeben"),
                order=case((Loan.end_date.is_(None), 0), else_=1),
                empty_label="—",
            ),
        }
```

Die Basis-Abfrage der Leihen joint `InventoryItem` und `Musician` bereits, darum braucht keine Spec ein `join`.

- [ ] **Step 5: Services, Schemas, Routen**

`services/musician.py`:

```python
async def get_list(
    session: AsyncSession, flt: MusicianFilter, page: PageParams
) -> ListPage:
    return await fetch_page(session, flt, select(Musician), page)
```

`services/loan.py`, analog:

```python
    query = (
        select(Loan)
        .join(InventoryItem, Loan.item_id == InventoryItem.id)
        .join(Musician, Loan.musician_id == Musician.id)
    )
    return await fetch_page(session, flt, query, page)
```

Die Imports werden entsprechend angepasst (`fetch_page` und `ListPage` statt `paginate`).

`schemas/musician.py`:
```python
class MusicianListRow(MusicianRead, Grouped):
    pass
```
`schemas/loan.py`:
```python
class LoanListRow(LoanRead, Grouped):
    pass
```
(Import `Grouped` aus `mv_hofki.schemas.pagination`. Führt das zu einem Zirkelimport, gehört `Grouped` in ein eigenes Modul `schemas/grouping.py`, und `pagination.py` importiert es von dort.)

Neuer gemeinsamer Helfer in `api/routes/_listing.py`:

```python
"""Turn a ListPage into a PaginatedResponse."""

from __future__ import annotations

from typing import Any

from mv_hofki.filters.base import ListPage, PageParams
from mv_hofki.schemas.pagination import PaginatedResponse


def page_response(lp: ListPage, page: PageParams, items: list[Any]) -> PaginatedResponse:
    """``items`` are the converted rows in the order of ``lp.rows``; group
    fields are attached when grouping is on (dicts or Grouped models)."""
    if lp.row_groups is not None:
        for item, (key, label) in zip(items, lp.row_groups):
            if isinstance(item, dict):
                item["group_key"], item["group_label"] = key, label
            else:
                item.group_key, item.group_label = key, label
    return PaginatedResponse(
        items=items,
        total=lp.total,
        limit=page.limit,
        offset=page.offset,
        item_total=lp.item_total,
        groups=lp.groups,
    )
```

`list_musicians`:

```python
@router.get("", response_model=PaginatedResponse[MusicianListRow])
async def list_musicians(
    flt: MusicianFilter = FilterDepends(MusicianFilter),
    page: PageParams = Depends(),
    db: AsyncSession = Depends(get_db),
):
    lp = await musician_service.get_list(db, flt, page)
    return page_response(lp, page, [MusicianListRow.model_validate(m) for m in lp.rows])
```

`list_loans`:

```python
@router.get("", response_model=PaginatedResponse[LoanListRow])
async def list_loans(...):
    lp = await loan_service.get_list(db, flt, page)
    rows = [LoanListRow(**_loan_to_read(loan).model_dump()) for loan in lp.rows]
    return page_response(lp, page, rows)
```

`MusicianRead` hat `model_config = {"from_attributes": True}`, das prüfen. Hat es keine, `model_validate(m, from_attributes=True)` verwenden.

- [ ] **Step 6: Tests laufen lassen, sie müssen bestehen.** Run: `IN_CONTAINER 'python -m pytest tests/backend -q'`.

- [ ] **Step 7: Commit.** Message: `feat(api): grouping for musicians and loans`.

---

### Task 3: Gruppierung für Items (API)

**Files:**
- Modify: `src/backend/mv_hofki/filters/inventory_item.py`
- Modify: `src/backend/mv_hofki/services/inventory_item.py` (`get_list`)
- Modify: `src/backend/mv_hofki/api/routes/items.py` (`list_items`)
- Test: `tests/backend/test_item_list_filters.py` (anhängen)

**Interfaces:**
- Produces: `GET /items?category=…&group_by=…`. Erlaubt sind je Art:
  - instrument: `type`, `status`, `owner`
  - clothing: `type`, `size`, `status`
  - sheet_music: `genre`
  - general_item: `category`, `room`, `status`
- `item_service.get_list` liefert `ListPage`, deren `rows` Dicts sind (wie bisher `_build_read_dict`).

- [ ] **Step 1: Failing tests** — an `tests/backend/test_item_list_filters.py` anhängen:

```python
async def _groups(client, query):
    resp = await client.get(f"{URL}?{query}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    return body, [(g["label"], g["count"]) for g in body["groups"]]


async def test_instruments_group_by_type_status_owner(client, refs):
    t1 = await _item(client, category="instrument", label="Tuba 1", instrument_type_id=refs["tuba"], owner="MV Hofkirchen")
    await _item(client, category="instrument", label="Horn 1", instrument_type_id=refs["horn"], owner="Privat")
    await _item(client, category="instrument", label="Tuba 2", instrument_type_id=refs["tuba"], owner="MV Hofkirchen")
    await client.post("/api/v1/loans", json={"item_id": t1["id"], "musician_id": await _musician(client), "start_date": "2026-01-01"})
    body, groups = await _groups(client, "category=instrument&group_by=type")
    assert groups == [("Horn", 1), ("Tuba", 2)]
    assert [i["label"] for i in body["items"]] == ["Horn 1", "Tuba 1", "Tuba 2"]
    assert body["items"][0]["group_key"] == str(refs["horn"])
    _, groups = await _groups(client, "category=instrument&group_by=status")
    assert groups == [("Ausgeliehen", 1), ("Verfügbar", 2)]
    _, groups = await _groups(client, "category=instrument&group_by=owner")
    assert groups == [("MV Hofkirchen", 2), ("Privat", 1)]


async def test_clothing_group_by_size_with_empty_group(client, refs):
    await _item(client, category="clothing", label="Hut", clothing_type_id=refs["hat"], size="M")
    await _item(client, category="clothing", label="Jacke", clothing_type_id=refs["jacket"])
    _, groups = await _groups(client, "category=clothing&group_by=size")
    assert groups == [("M", 1), ("Ohne Größe", 1)]
    _, groups = await _groups(client, "category=clothing&group_by=type")
    assert groups == [("Hut", 1), ("Jacke", 1)]


async def test_sheet_music_group_by_genre(client):
    genre = (await client.post("/api/v1/sheet-music-genres", json={"label": "Marsch"})).json()
    await _item(client, category="sheet_music", label="Radetzky", genre_id=genre["id"])
    await _item(client, category="sheet_music", label="Bolero")
    _, groups = await _groups(client, "category=sheet_music&group_by=genre")
    assert groups == [("Marsch", 1), ("Ohne Gattung", 1)]


async def test_general_items_group_by_category_repeats_and_room(client):
    deko = (await client.post("/api/v1/general-item-categories", json={"label": "Deko"})).json()
    fest = (await client.post("/api/v1/general-item-categories", json={"label": "Fest"})).json()
    await _item(client, category="general_item", label="Girlande",
                category_ids=[deko["id"], fest["id"]], storage_location="Sesselarchiv / Kasten 1")
    await _item(client, category="general_item", label="Leiter", storage_location="Bauhof")
    await _item(client, category="general_item", label="Kiste")
    body, groups = await _groups(client, "category=general_item&group_by=category")
    assert groups == [("Deko", 1), ("Fest", 1), ("Ohne Kategorie", 2)]
    assert [(i["label"], i["group_label"]) for i in body["items"]] == [
        ("Girlande", "Deko"), ("Girlande", "Fest"), ("Leiter", "Ohne Kategorie"), ("Kiste", "Ohne Kategorie"),
    ]
    assert body["total"] == 4 and body["item_total"] == 3
    _, groups = await _groups(client, "category=general_item&group_by=room")
    assert groups == [("Bauhof", 1), ("Sesselarchiv", 1), ("Ohne Lagerort", 1)]


async def test_group_not_for_category_is_422(client):
    resp = await client.get(f"{URL}?category=general_item&group_by=type")
    assert resp.status_code == 422
    assert resp.json()["detail"] == "Gruppierung „type“ gibt es für Allgemein nicht"
    assert (await client.get(f"{URL}?category=instrument&group_by=unsinn")).status_code == 422
```

Zur erwarteten Reihenfolge in `test_general_items_group_by_category_repeats_and_room`: Innerhalb „Ohne Kategorie“ wird nach `number` sortiert, und Leiter (A-002) steht vor Kiste (A-003).

- [ ] **Step 2: Tests laufen lassen, sie müssen scheitern.**

- [ ] **Step 3: `filters/inventory_item.py`**

Imports ergänzen: `case`, `literal`, `GroupSpec`, `SheetMusicGenre`, `GeneralItemCategory`.

```python
_ROOM = func.nullif(
    func.trim(
        func.substr(
            InventoryItem.storage_location,
            1,
            func.instr(InventoryItem.storage_location + literal(" /"), " /") - 1,
        )
    ),
    "",
)
_OPEN_LOAN = exists().where(Loan.item_id == InventoryItem.id, Loan.end_date.is_(None))


def _join_genre(query: Select) -> Select:
    return query.outerjoin(SheetMusicGenre, SheetMusicGenre.id == SheetMusicDetail.genre_id)


def _join_categories(query: Select) -> Select:
    return query.outerjoin(links, links.c.item_id == InventoryItem.id).outerjoin(
        GeneralItemCategory, GeneralItemCategory.id == links.c.category_id
    )


_CATEGORY_GROUPS = {
    "instrument": {"type", "status", "owner"},
    "clothing": {"type", "size", "status"},
    "sheet_music": {"genre"},
    "general_item": {"category", "room", "status"},
}
```

- `_COMMON_FIELDS` wird `{"search", "order_by", "group_by"}`.
- In `ItemFilter.Constants`:

```python
        group_fields = {
            "type": None,  # instrument or clothing type, see group_spec
            "status": GroupSpec(
                key=case((_OPEN_LOAN, "verliehen"), else_="verfuegbar"),
                label=case((_OPEN_LOAN, "Ausgeliehen"), else_="Verfügbar"),
                empty_label="—",
            ),
            "owner": GroupSpec(
                key=InventoryItem.owner, label=InventoryItem.owner, empty_label="Ohne Eigentümer"
            ),
            "size": GroupSpec(
                key=ClothingDetail.size, label=ClothingDetail.size, empty_label="Ohne Größe"
            ),
            "genre": GroupSpec(
                key=SheetMusicGenre.id,
                label=SheetMusicGenre.label,
                empty_label="Ohne Gattung",
                join=_join_genre,
            ),
            "category": GroupSpec(
                key=GeneralItemCategory.id,
                label=GeneralItemCategory.label,
                empty_label="Ohne Kategorie",
                join=_join_categories,
                multi=True,
            ),
            "room": GroupSpec(key=_ROOM, label=_ROOM, empty_label="Ohne Lagerort"),
        }
```

- In `bind`, nach der Sortierprüfung:

```python
        if self.group_by and self.group_by not in _CATEGORY_GROUPS[category]:
            raise HTTPException(
                status_code=422,
                detail=f"Gruppierung „{self.group_by}“ gibt es für {label} nicht",
            )
```

- `group_spec` überschreiben:

```python
    def group_spec(self) -> GroupSpec | None:
        if self.group_by == "type":
            model = InstrumentType if self._category == "instrument" else ClothingType
            return GroupSpec(key=model.id, label=model.label, empty_label="Ohne Typ")
        return super().group_spec()
```

Hinweis: Hängt der Operator `+` in `_ROOM` bei `String`-Spalten nicht `||` an, stattdessen `func.coalesce(InventoryItem.storage_location, "").concat(" /")` bzw. `InventoryItem.storage_location.concat(" /")` verwenden. Das Verhalten muss bleiben: NULL ergibt die Gruppe „Ohne Lagerort“.

- [ ] **Step 4: Service und Route**

`services/inventory_item.py`, `get_list` ersetzen:

```python
async def get_list(
    session: AsyncSession,
    *,
    category: str,
    flt: ItemFilter,
    page: PageParams,
) -> ListPage:
    if category not in CATEGORY_DETAIL_MAP:
        raise HTTPException(status_code=400, detail=f"Ungültige Kategorie: {category}")
    flt.bind(category)
    lp = await fetch_page(
        session, flt, _base_query(category), page, options=[joinedload(InventoryItem.currency)]
    )
    unique_items = list({i.id: i for i in lp.rows}.values())
    await _enrich(session, unique_items)
    details = await _get_details(session, [i.id for i in unique_items], category)
    lp.rows = [_build_read_dict(i, details.get(i.id)) for i in lp.rows]
    return lp
```

`api/routes/items.py`, `list_items`:

```python
    lp = await item_service.get_list(db, category=category, flt=flt, page=page)
    return page_response(lp, page, [_to_read(item) for item in lp.rows])
```

Import `page_response` aus `mv_hofki.api.routes._listing`. `_to_read` gibt Dicts zurück; `page_response` hängt die Gruppenfelder an.

- [ ] **Step 5: Tests laufen lassen, sie müssen bestehen.** Run: `IN_CONTAINER 'python -m pytest tests/backend -q'`.

- [ ] **Step 6: Commit.** Message: `feat(items): server-side grouping for all item kinds`.

---

### Task 4: Sammelzuweisung von Kategorien (API)

**Files:**
- Modify: `src/backend/mv_hofki/services/general_item_category.py` (neu: `bulk_update`)
- Modify: `src/backend/mv_hofki/schemas/general_item_category.py` (neu: `BulkCategoryUpdate`, `BulkCategoryResult`)
- Modify: `src/backend/mv_hofki/api/routes/items.py` (neu: `POST /bulk-categories` **vor** allen `/{item_id}`-Routen)
- Test: `tests/backend/test_bulk_categories.py` (neu)

- [ ] **Step 1: Failing tests**

```python
"""POST /items/bulk-categories."""

import pytest

URL = "/api/v1/items/bulk-categories"
CATS = "/api/v1/general-item-categories"


@pytest.fixture
async def data(client):
    deko = (await client.post(CATS, json={"label": "Deko"})).json()["id"]
    fest = (await client.post(CATS, json={"label": "Fest"})).json()["id"]

    async def item(label, **extra):
        r = await client.post("/api/v1/items", json={"category": "general_item", "label": label, **extra})
        return r.json()["id"]

    a = await item("Girlande", category_ids=[deko])
    b = await item("Leiter")
    return {"deko": deko, "fest": fest, "a": a, "b": b}


async def _cats(client, item_id):
    return [c["label"] for c in (await client.get(f"/api/v1/items/{item_id}")).json()["categories"]]


async def test_add_and_remove(client, data):
    r = await client.post(URL, json={"item_ids": [data["a"], data["b"]], "add_ids": [data["fest"]]})
    assert r.status_code == 200 and r.json() == {"updated": 2}
    assert await _cats(client, data["a"]) == ["Deko", "Fest"]
    assert await _cats(client, data["b"]) == ["Fest"]
    r = await client.post(URL, json={"item_ids": [data["a"], data["b"]], "remove_ids": [data["deko"]]})
    assert r.json() == {"updated": 2}
    assert await _cats(client, data["a"]) == ["Fest"]
    assert await _cats(client, data["b"]) == ["Fest"]


async def test_adding_twice_is_idempotent(client, data):
    body = {"item_ids": [data["a"]], "add_ids": [data["deko"]]}
    assert (await client.post(URL, json=body)).status_code == 200
    assert await _cats(client, data["a"]) == ["Deko"]


@pytest.mark.parametrize(
    "payload, detail",
    [
        ({"add_ids": [], "remove_ids": []}, "Keine Kategorien angegeben"),
        ({"add_ids": ["deko"], "remove_ids": ["deko"]},
         "Kategorie kann nicht gleichzeitig hinzugefügt und entfernt werden"),
        ({"add_ids": [999]}, "Unbekannte Kategorie: 999"),
    ],
)
async def test_validation_errors(client, data, payload, detail):
    payload = {k: [data[x] if isinstance(x, str) else x for x in v] for k, v in payload.items()}
    r = await client.post(URL, json={"item_ids": [data["a"]], **payload})
    assert r.status_code == 422
    assert r.json()["detail"] == detail
    assert await _cats(client, data["a"]) == ["Deko"]


async def test_non_general_items_rejected(client, data):
    tu = (await client.post("/api/v1/instrument-types", json={"label": "Tuba", "label_short": "TU"})).json()
    inst = (await client.post("/api/v1/items", json={"category": "instrument", "label": "Tuba", "instrument_type_id": tu["id"]})).json()["id"]
    r = await client.post(URL, json={"item_ids": [data["a"], inst, 999], "add_ids": [data["fest"]]})
    assert r.status_code == 422
    assert r.json()["detail"] == f"Nur allgemeine Gegenstände: {inst}, 999"
    assert await _cats(client, data["a"]) == ["Deko"]


async def test_item_ids_required(client, data):
    r = await client.post(URL, json={"item_ids": [], "add_ids": [data["fest"]]})
    assert r.status_code == 422
```

- [ ] **Step 2: Tests laufen lassen, sie müssen scheitern.**

- [ ] **Step 3: Schemas**

```python
class BulkCategoryUpdate(BaseModel):
    item_ids: list[int] = Field(min_length=1, max_length=500)
    add_ids: list[int] = []
    remove_ids: list[int] = []


class BulkCategoryResult(BaseModel):
    updated: int
```

- [ ] **Step 4: Service** in `services/general_item_category.py`:

```python
async def bulk_update(
    session: AsyncSession, item_ids: list[int], add_ids: list[int], remove_ids: list[int]
) -> int:
    """Add/remove categories on many general items in one transaction."""
    if not add_ids and not remove_ids:
        raise HTTPException(status_code=422, detail="Keine Kategorien angegeben")
    if set(add_ids) & set(remove_ids):
        raise HTTPException(
            status_code=422,
            detail="Kategorie kann nicht gleichzeitig hinzugefügt und entfernt werden",
        )
    wanted = sorted(set(item_ids))
    found = set(
        (
            await session.execute(
                select(InventoryItem.id).where(
                    InventoryItem.id.in_(wanted), InventoryItem.category == "general_item"
                )
            )
        ).scalars()
    )
    bad = [i for i in wanted if i not in found]
    if bad:
        raise HTTPException(
            status_code=422,
            detail=f"Nur allgemeine Gegenstände: {', '.join(str(i) for i in bad)}",
        )
    add = await check_category_ids(session, add_ids)
    remove = await check_category_ids(session, remove_ids)
    if remove:
        await session.execute(
            sa_delete(links).where(links.c.item_id.in_(wanted), links.c.category_id.in_(remove))
        )
    if add:
        existing = set(
            (
                await session.execute(
                    select(links.c.item_id, links.c.category_id).where(
                        links.c.item_id.in_(wanted), links.c.category_id.in_(add)
                    )
                )
            ).all()
        )
        new = [
            {"item_id": i, "category_id": c}
            for i in wanted
            for c in add
            if (i, c) not in existing
        ]
        if new:
            await session.execute(insert(links), new)
    await session.commit()
    return len(wanted)
```

Import `InventoryItem`. Prüfe vorher, dass `models/inventory_item.py` den Kategorien-Service nicht importiert, damit kein Zirkelimport entsteht; der Service importiert nur Modelle.

Die Reihenfolge der Prüfungen ist verbindlich (leere Listen → Überschneidung → Items → Kategorien), weil die Tests die jeweilige Meldung erwarten. `check_category_ids` wirft bei `[]` nicht, sondern liefert `[]`.

- [ ] **Step 5: Route** in `api/routes/items.py`, direkt nach `item_facets`:

```python
@router.post("/bulk-categories", response_model=BulkCategoryResult)
async def bulk_categories(data: BulkCategoryUpdate, db: AsyncSession = Depends(get_db)):
    updated = await category_service.bulk_update(
        db, data.item_ids, data.add_ids, data.remove_ids
    )
    return BulkCategoryResult(updated=updated)
```

Import `category_service` (`from mv_hofki.services import general_item_category as category_service`). Heißt der Import in der Datei schon anders, denselben Namen verwenden.

- [ ] **Step 6: Tests laufen lassen, sie müssen bestehen; Commit.** Message: `feat(items): bulk add/remove categories for general items`.

---

### Task 5: Frontend-Bausteine für Gruppen und Auswahl

**Files:**
- Create: `src/frontend/src/lib/grouping.js`
- Create: `src/frontend/src/composables/useGroupCollapse.js`
- Create: `src/frontend/src/components/GroupHeader.vue`, `components/GroupSelect.vue`
- Modify: `src/frontend/src/components/DataTable.vue`
- Modify: `src/frontend/src/composables/useListQuery.js` (`groups`, `itemTotal`, `_key`)
- Test: `tests/frontend/grouping.test.js`, `useGroupCollapse.test.js`, `GroupHeader.test.js`, `GroupSelect.test.js` (neu); `DataTable.test.js`, `useListQuery.test.js` (ergänzen)

**Interfaces (Produces):**
- **`buildSegments(rows, groups, collapsed) -> Segment[]`**
  - `Segment = {type:"group", key, groupKey, label, count, collapsed}` oder `{type:"row", key, row}`.
  - `groups` darf `null` sein (dann nur Zeilen).
  - `collapsed` ist ein `Set` von Gruppenschlüsseln.
- **`useGroupCollapse(storageKeyRef) -> { collapsed: Ref<Set<string>>, toggle(key) }`**
- **`<GroupHeader :label :count :collapsed @toggle />`**
- **`<GroupSelect :options="[{key,label}]" v-model="groupBy" />`:** `""` bedeutet „Keine“.
- **`DataTable`:**
  - Neue Props: `groups: Array|null = null`, `collapsedGroups: Set = new Set()`, `selectable: Boolean`, `selectedIds: Array = []`, `rowLabel: Function = (r) => r.label ?? ""`.
  - Neue Events: `toggle-group(key)`, `toggle-select(row)`.
- **`useListQuery`:** zusätzlich `groups` (computed, `lastResponse.groups ?? null`) und `itemTotal` (computed, `lastResponse.item_total ?? total`). Jede Zeile bekommt `_key`.

- [ ] **Step 1: Failing tests**

`tests/frontend/grouping.test.js`:

```js
import { describe, it, expect } from "vitest";
import { buildSegments } from "../../src/frontend/src/lib/grouping.js";

const rows = [
  { id: 1, _key: "a:1", group_key: "a" },
  { id: 2, _key: "a:2", group_key: "a" },
  { id: 3, _key: "b:3", group_key: "b" },
  { id: 1, _key: "b:1", group_key: "b" },
];
const groups = [
  { key: "a", label: "Alpha", count: 5 },
  { key: "b", label: "Beta", count: 2 },
];

describe("buildSegments", () => {
  it("returns only rows without groups", () => {
    const segs = buildSegments(rows.slice(0, 2), null, new Set());
    expect(segs.map((s) => s.type)).toEqual(["row", "row"]);
    expect(segs[0].key).toBe("a:1");
  });

  it("inserts one header per group run with counts from groups", () => {
    const segs = buildSegments(rows, groups, new Set());
    expect(segs.map((s) => (s.type === "group" ? `G:${s.label}:${s.count}` : s.row._key))).toEqual([
      "G:Alpha:5", "a:1", "a:2", "G:Beta:2", "b:3", "b:1",
    ]);
  });

  it("hides rows of collapsed groups but keeps the header", () => {
    const segs = buildSegments(rows, groups, new Set(["a"]));
    expect(segs.map((s) => (s.type === "group" ? `G:${s.groupKey}:${s.collapsed}` : s.row._key))).toEqual([
      "G:a:true", "G:b:false", "b:3", "b:1",
    ]);
  });

  it("falls back to the row label when a group is not in groups", () => {
    const segs = buildSegments([{ id: 9, _key: "x:9", group_key: "x", group_label: "Xeno" }], groups, new Set());
    expect(segs[0]).toMatchObject({ type: "group", label: "Xeno", count: null });
  });
});
```

`tests/frontend/useGroupCollapse.test.js`:

```js
import { describe, it, expect, beforeEach } from "vitest";
import { ref, nextTick } from "vue";
import { useGroupCollapse } from "../../src/frontend/src/composables/useGroupCollapse.js";

beforeEach(() => localStorage.clear());

describe("useGroupCollapse", () => {
  it("toggles and persists per storage key", async () => {
    const key = ref("instrument:type");
    const { collapsed, toggle } = useGroupCollapse(key);
    toggle("5");
    expect([...collapsed.value]).toEqual(["5"]);
    expect(JSON.parse(localStorage.getItem("groups-collapsed:instrument:type"))).toEqual(["5"]);
    key.value = "instrument:status";
    await nextTick();
    expect([...collapsed.value]).toEqual([]);
    key.value = "instrument:type";
    await nextTick();
    expect([...collapsed.value]).toEqual(["5"]);
    toggle("5");
    expect([...collapsed.value]).toEqual([]);
  });

  it("survives broken storage", () => {
    localStorage.setItem("groups-collapsed:x", "{kaputt");
    const { collapsed } = useGroupCollapse(ref("x"));
    expect([...collapsed.value]).toEqual([]);
  });
});
```

`tests/frontend/GroupHeader.test.js`:

```js
import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import GroupHeader from "../../src/frontend/src/components/GroupHeader.vue";

describe("GroupHeader", () => {
  it("shows label and count and toggles", async () => {
    const w = mount(GroupHeader, { props: { label: "Tuba", count: 7, collapsed: false } });
    const btn = w.find("button");
    expect(btn.text()).toContain("Tuba");
    expect(btn.text()).toContain("7");
    expect(btn.attributes("aria-expanded")).toBe("true");
    await btn.trigger("click");
    expect(w.emitted("toggle")).toHaveLength(1);
  });

  it("marks collapsed and omits a missing count", () => {
    const w = mount(GroupHeader, { props: { label: "Horn", count: null, collapsed: true } });
    expect(w.find("button").attributes("aria-expanded")).toBe("false");
    expect(w.find(".group-count").exists()).toBe(false);
  });
});
```

`tests/frontend/GroupSelect.test.js`:

```js
import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import GroupSelect from "../../src/frontend/src/components/GroupSelect.vue";

describe("GroupSelect", () => {
  it("offers 'Keine' plus options and emits the key", async () => {
    const w = mount(GroupSelect, {
      props: { options: [{ key: "type", label: "Typ" }, { key: "status", label: "Status" }], modelValue: "type" },
    });
    expect(w.findAll("option").map((o) => o.text())).toEqual(["Keine", "Typ", "Status"]);
    expect(w.find("select").element.value).toBe("type");
    await w.find("select").setValue("");
    expect(w.emitted("update:modelValue")).toEqual([[""]]);
    expect(w.find("label").text()).toBe("Gruppieren nach");
  });
});
```

In `tests/frontend/DataTable.test.js` anhängen:

```js
describe("DataTable groups and selection", () => {
  const cols = [{ key: "label", label: "Bezeichnung" }];
  const grows = [
    { id: 1, _key: "a:1", group_key: "a", label: "Eins" },
    { id: 2, _key: "b:2", group_key: "b", label: "Zwei" },
    { id: 1, _key: "b:1", group_key: "b", label: "Eins" },
  ];
  const groups = [
    { key: "a", label: "Alpha", count: 1 },
    { key: "b", label: "Beta", count: 2 },
  ];

  it("renders group rows with rowgroup headers and hides collapsed rows", async () => {
    const w = mount(DataTable, { props: { columns: cols, rows: grows, groups, collapsedGroups: new Set(["a"]) } });
    const headers = w.findAll('th[scope="rowgroup"]');
    expect(headers.map((h) => h.text())).toEqual([expect.stringContaining("Alpha"), expect.stringContaining("Beta")]);
    expect(w.findAll("tbody tr td").map((td) => td.text())).toEqual(["Zwei", "Eins"]);
    await headers[1].find("button").trigger("click");
    expect(w.emitted("toggle-group")).toEqual([["b"]]);
  });

  it("selection column marks every row of a selected id", async () => {
    const w = mount(DataTable, { props: { columns: cols, rows: grows, groups, selectable: true, selectedIds: [1] } });
    const boxes = w.findAll('input[type="checkbox"]');
    expect(boxes.map((b) => b.element.checked)).toEqual([true, false, true]);
    expect(boxes[1].attributes("aria-label")).toBe("„Zwei“ auswählen");
    await boxes[1].trigger("change");
    expect(w.emitted("toggle-select")[0][0]).toMatchObject({ id: 2 });
  });
});
```

In `tests/frontend/useListQuery.test.js` anhängen (es wird das dort vorhandene `setup()` genutzt):

```js
  it("exposes groups and itemTotal and keys rows by group", async () => {
    get.mockResolvedValue({
      items: [{ id: 1, group_key: "a" }, { id: 1, group_key: "b" }],
      total: 2,
      item_total: 1,
      groups: [{ key: "a", label: "A", count: 1 }, { key: "b", label: "B", count: 1 }],
    });
    const { list } = await setup();
    expect(list.items.value.map((r) => r._key)).toEqual(["a:1", "b:1"]);
    expect(list.itemTotal.value).toBe(1);
    expect(list.groups.value).toHaveLength(2);
  });

  it("keys rows by id without grouping", async () => {
    get.mockResolvedValue({ items: [{ id: 4 }], total: 1 });
    const { list } = await setup();
    expect(list.items.value[0]._key).toBe(4);
    expect(list.groups.value).toBe(null);
    expect(list.itemTotal.value).toBe(1);
  });
```

- [ ] **Step 2: Tests laufen lassen, sie müssen scheitern.** Run: `IN_CONTAINER 'cd src/frontend && npx vitest run grouping useGroupCollapse GroupHeader GroupSelect DataTable useListQuery'`.

- [ ] **Step 3: `lib/grouping.js`**

```js
/**
 * Interleave group headers into list rows (rows arrive sorted by group from
 * the API). Counts come from the API's `groups`, so they are right even while
 * only part of a group is loaded.
 */
export function buildSegments(rows, groups, collapsed) {
  if (!groups) return rows.map((row) => ({ type: "row", key: row._key ?? row.id, row }));
  const byKey = new Map(groups.map((g) => [g.key, g]));
  const out = [];
  let current;
  for (const row of rows) {
    const groupKey = row.group_key ?? "";
    if (groupKey !== current) {
      current = groupKey;
      const g = byKey.get(groupKey);
      out.push({
        type: "group",
        key: `group:${groupKey}`,
        groupKey,
        label: g?.label ?? row.group_label ?? "",
        count: g?.count ?? null,
        collapsed: collapsed.has(groupKey),
      });
    }
    if (!collapsed.has(groupKey)) out.push({ type: "row", key: row._key ?? row.id, row });
  }
  return out;
}
```

- [ ] **Step 4: `composables/useGroupCollapse.js`**

```js
/** Collapsed group keys of one list and grouping, remembered per browser. */
import { ref, watch } from "vue";

const PREFIX = "groups-collapsed:";

function read(key) {
  try {
    const raw = localStorage.getItem(PREFIX + key);
    const parsed = raw ? JSON.parse(raw) : [];
    return new Set(Array.isArray(parsed) ? parsed.map(String) : []);
  } catch {
    return new Set();
  }
}

function write(key, set) {
  try {
    localStorage.setItem(PREFIX + key, JSON.stringify([...set]));
  } catch {
    // storage unavailable: collapsing still works for this visit
  }
}

export function useGroupCollapse(storageKey) {
  const collapsed = ref(read(storageKey.value));
  watch(storageKey, (key) => (collapsed.value = read(key)));

  function toggle(groupKey) {
    const next = new Set(collapsed.value);
    if (next.has(groupKey)) next.delete(groupKey);
    else next.add(groupKey);
    collapsed.value = next;
    write(storageKey.value, next);
  }

  return { collapsed, toggle };
}
```

- [ ] **Step 5: `GroupHeader.vue`**

```vue
<script setup>
defineProps({
  label: { type: String, required: true },
  count: { type: Number, default: null },
  collapsed: Boolean,
});
defineEmits(["toggle"]);
</script>

<template>
  <button
    type="button"
    class="group-header"
    :aria-expanded="String(!collapsed)"
    @click="$emit('toggle')"
  >
    <span class="group-chevron" aria-hidden="true">{{ collapsed ? "▸" : "▾" }}</span>
    <span class="group-label">{{ label }}</span>
    <span v-if="count !== null" class="group-count">{{ count }}</span>
  </button>
</template>

<style scoped>
.group-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  width: 100%;
  min-height: 44px;
  padding: 0 var(--space-2);
  border: none;
  border-bottom: 1px solid var(--color-border);
  background: var(--color-bg-soft);
  color: var(--color-text);
  font: inherit;
  font-weight: 600;
  text-align: left;
  cursor: pointer;
}

.group-header:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: -2px;
}

.group-chevron {
  width: 1em;
  color: var(--color-muted);
}

.group-count {
  margin-left: auto;
  font-weight: 500;
  font-variant-numeric: tabular-nums;
  color: var(--color-muted);
}
</style>
```

- [ ] **Step 6: `GroupSelect.vue`**

```vue
<script setup>
defineProps({
  options: { type: Array, required: true },
  modelValue: { type: String, default: "" },
});
defineEmits(["update:modelValue"]);
const id = `group-select-${Math.random().toString(36).slice(2, 9)}`;
</script>

<template>
  <div class="group-select">
    <label :for="id">Gruppieren nach</label>
    <select :id="id" :value="modelValue" @change="$emit('update:modelValue', $event.target.value)">
      <option value="">Keine</option>
      <option v-for="o in options" :key="o.key" :value="o.key">{{ o.label }}</option>
    </select>
  </div>
</template>

<style scoped>
.group-select {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.group-select label {
  font-size: 0.875rem;
  color: var(--color-muted);
  white-space: nowrap;
}

.group-select select {
  width: auto;
  min-height: 44px;
}
</style>
```

- [ ] **Step 7: `DataTable.vue` erweitern**

**Script:**
- Import von `buildSegments` und `GroupHeader`.
- Props und Emits wie unter „Interfaces“.
- Dazu:
  ```js
  const segments = computed(() => buildSegments(props.rows, props.groups, props.collapsedGroups));
  const selectedSet = computed(() => new Set(props.selectedIds));
  const colspan = computed(() => props.columns.length + (props.selectable ? 1 : 0));
  ```

**Tabelle:**
- **Kopf:** Bei `selectable` kommt vor den Spalten `<th class="dt-select"><span class="sr-only">Auswahl</span></th>`.
- **Körper:**
  - Die bisherige `v-for="row in rows"`-Schleife wird zu `<template v-for="seg in segments" :key="seg.key">`.
  - Bei `seg.type === 'group'`: `<tr class="dt-group"><th :colspan="colspan" scope="rowgroup"><GroupHeader :label="seg.label" :count="seg.count" :collapsed="seg.collapsed" @toggle="emit('toggle-group', seg.groupKey)" /></th></tr>`.
  - Sonst die bisherige Zeile mit `seg.row`, bei `selectable` mit einer ersten Zelle:
    ```vue
    <td v-if="selectable" class="dt-select" @click.stop>
      <input type="checkbox" :checked="selectedSet.has(seg.row.id)" :aria-label="`„${rowLabel(seg.row)}“ auswählen`" @change="emit('toggle-select', seg.row)" />
    </td>
    ```
  - Die Colspans der Lade- und Leerzeile werden `colspan`.

**Kartenansicht:**
- Ebenfalls über `segments` iterieren.
- Ein Gruppen-Segment rendert `<GroupHeader …>` direkt als Block.
- Eine Zeile rendert wie bisher die Karte, bei `selectable` mit derselben Checkbox oben rechts (`class="dt-card-select"`).
- Karten-Keys: `seg.key`.

Styles:

```css
.dt-group th {
  padding: 0;
  background: var(--color-bg-soft);
}

.dt-select {
  width: 44px;
  text-align: center;
}

.dt-select input,
.dt-card-select input {
  width: 22px;
  height: 22px;
  margin: 0;
}

.dt-card {
  position: relative;
}

.dt-card-select {
  position: absolute;
  top: var(--space-2);
  right: var(--space-2);
  display: grid;
  place-items: center;
  width: 44px;
  height: 44px;
}
```

In der Kartenansicht steht die Checkbox rechts oben. Damit sie nicht über dem Text liegt, bekommt `.dt-card` bei `selectable` `padding-right: 3rem`, gesteuert über die Klasse `dt-card--selectable`.

- [ ] **Step 8: `useListQuery.js`**
- In `fetchPage`: `const mapped = data.items.map(mapItem).map((row) => ({ ...row, _key: row.group_key != null ? \`${row.group_key}:${row.id}\` : row.id }));`
- Zusätzlich:
  ```js
  const groups = computed(() => lastResponse.value?.groups ?? null);
  const itemTotal = computed(() => lastResponse.value?.item_total ?? total.value);
  ```
- Beide im Rückgabeobjekt ergänzen.

- [ ] **Step 9: Tests, Build, Commit**

Run: `IN_CONTAINER 'cd src/frontend && npx vitest run && npx vite build'`. Die bestehenden Seiten übergeben keine `groups` und rendern deshalb unverändert. Das kurz im Browser prüfen: `/musiker` und `/instrumente` laden.

Message: `feat(frontend): group headers, collapse state and row selection in lists`.

---

### Task 6: `ItemCard`, kompakte Karten, Gruppierung auf ItemListPage

**Files:**
- Create: `src/frontend/src/components/ItemCard.vue`
- Modify: `src/frontend/src/pages/ItemListPage.vue`
- Modify: `src/frontend/src/style.css` (`.instrument-*`-Regeln in ItemCard verschieben, sofern nirgends sonst benutzt; vorher per grep prüfen)
- Test: `tests/frontend/ItemCard.test.js` (neu)

**Interfaces:**
- **`<ItemCard :item :has-loans :to :selecting :selected @toggle-select />`:**
  - Die Wurzel ist ein `RouterLink` (nicht im Auswahlmodus) bzw. ein `<label>` mit Checkbox (im Auswahlmodus).
  - `to` ist ein Pfad-String.
- **ItemListPage:**
  - Neuer Filter `group_by: { type: "string", default: <"type" für instrument, sonst ""> }` in `FILTERS[…]`.
  - Gruppen-Optionen je Art:
    - instrument: Typ · Status · Eigentümer
    - clothing: Typ · Größe · Status
    - sheet_music: Gattung
    - general_item: Kategorie · Raum · Status

- [ ] **Step 1: Failing test** `tests/frontend/ItemCard.test.js`:

```js
import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import { createRouter, createMemoryHistory } from "vue-router";
import ItemCard from "../../src/frontend/src/components/ItemCard.vue";

const router = createRouter({ history: createMemoryHistory(), routes: [{ path: "/:p(.*)*", component: { render: () => null } }] });
const item = { id: 7, label: "Tuba", display_nr: "TU-002", manufacturer: "Yamaha", profile_image_url: null, active_loan: null, categories: [] };

function mountCard(props) {
  return mount(ItemCard, { props: { item, hasLoans: true, to: "/instrumente/7", ...props }, global: { plugins: [router] } });
}

describe("ItemCard", () => {
  it("is a link with label, number and status", () => {
    const w = mountCard({});
    const a = w.find("a");
    expect(a.attributes("href")).toBe("/instrumente/7");
    expect(w.text()).toContain("Tuba");
    expect(w.text()).toContain("TU-002 · Yamaha");
    expect(w.find(".badge").text()).toBe("Verfügbar");
    expect(w.find(".item-card-thumb").text()).toBe("TU-002");
  });

  it("becomes a selectable label in selection mode", async () => {
    const w = mountCard({ selecting: true, selected: true });
    expect(w.find("a").exists()).toBe(false);
    const box = w.find('input[type="checkbox"]');
    expect(box.element.checked).toBe(true);
    expect(box.attributes("aria-label")).toBe("„Tuba“ auswählen");
    await box.trigger("change");
    expect(w.emitted("toggle-select")).toHaveLength(1);
  });

  it("shows the profile image", () => {
    const w = mountCard({ item: { ...item, profile_image_url: "/x.jpg" } });
    expect(w.find("img").attributes("src")).toBe("/x.jpg");
    expect(w.find("img").attributes("alt")).toBe("");
  });
});
```

- [ ] **Step 2: Test laufen lassen, er muss scheitern.**

- [ ] **Step 3: `ItemCard.vue`**

```vue
<script setup>
import { RouterLink } from "vue-router";
import CategoryChips from "./CategoryChips.vue";

const props = defineProps({
  item: { type: Object, required: true },
  hasLoans: Boolean,
  to: { type: String, required: true },
  selecting: Boolean,
  selected: Boolean,
});
defineEmits(["toggle-select"]);
</script>

<template>
  <component
    :is="selecting ? 'label' : RouterLink"
    v-bind="selecting ? {} : { to }"
    class="item-card"
    :class="{ 'is-selected': selecting && selected }"
  >
    <input
      v-if="selecting"
      type="checkbox"
      class="item-card-check"
      :checked="selected"
      :aria-label="`„${props.item.label}“ auswählen`"
      @change="$emit('toggle-select')"
    />
    <span class="item-card-thumb">
      <img v-if="item.profile_image_url" :src="item.profile_image_url" alt="" />
      <span v-else>{{ item.display_nr }}</span>
    </span>
    <span class="item-card-body">
      <span class="item-card-title">
        {{ item.label }}
        <span v-if="item.quantity_label" class="item-card-quantity">{{ item.quantity_label }}</span>
      </span>
      <span class="item-card-meta">
        {{ item.display_nr }}{{ item.manufacturer ? " · " + item.manufacturer : "" }}
      </span>
      <CategoryChips v-if="item.categories?.length" :categories="item.categories" />
    </span>
    <span v-if="hasLoans" class="item-card-status">
      <span :class="item.active_loan ? 'badge badge-green' : 'badge badge-gray'">
        {{ item.active_loan ? "Ausgeliehen" : "Verfügbar" }}
      </span>
    </span>
  </component>
</template>

<style scoped>
.item-card {
  position: relative;
  display: flex;
  flex-direction: column;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  overflow: hidden;
  background: var(--color-bg);
  color: inherit;
  text-decoration: none;
  cursor: pointer;
}

.item-card:hover {
  box-shadow: var(--shadow-float);
}

.item-card:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}

.item-card.is-selected {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 2px var(--color-primary-light);
}

.item-card-check {
  position: absolute;
  top: var(--space-2);
  right: var(--space-2);
  width: 22px;
  height: 22px;
  margin: 0;
  z-index: 1;
}

.item-card-thumb {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 120px;
  background: var(--color-bg-soft);
  color: var(--color-muted);
  font-size: 1.1rem;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.item-card-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.item-card-body {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  padding: var(--space-3);
}

.item-card-title {
  font-size: 0.9rem;
  font-weight: 600;
}

.item-card-quantity {
  margin-left: var(--space-1);
  font-weight: 500;
  color: var(--color-muted);
  font-variant-numeric: tabular-nums;
}

.item-card-meta {
  font-size: 0.8rem;
  color: var(--color-muted);
}

.item-card-status {
  padding: 0 var(--space-3) var(--space-3);
}

/* Phone: one compact row per item, small picture on the left. */
@media (max-width: 640px) {
  .item-card {
    display: grid;
    grid-template-columns: 56px 1fr auto;
    align-items: center;
    gap: var(--space-3);
    min-height: 72px;
    padding: var(--space-2);
  }

  .item-card-thumb {
    width: 56px;
    height: 56px;
    border-radius: var(--radius-sm);
    overflow: hidden;
    font-size: 0.7rem;
    text-align: center;
  }

  .item-card-body {
    padding: 0;
    min-width: 0;
  }

  .item-card-title {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .item-card-status {
    padding: 0;
  }

  .item-card-check {
    position: static;
    grid-column: 1;
    grid-row: 1;
    justify-self: start;
    align-self: start;
  }
}
</style>
```

Am Handy liegt die Checkbox im Auswahlmodus über der linken oberen Ecke des Bildes (gleiche Zelle). Bei Platzproblemen darf das Bild im Auswahlmodus stattdessen 44 px breit sein; die Entscheidung wird im Report begründet.

- [ ] **Step 4: ItemListPage umbauen**

**Script:**
- Imports: `ItemCard`, `GroupHeader`, `GroupSelect`, `useGroupCollapse`, `buildSegments`.
- In jedes `FILTERS[…]` den Eintrag `group_by: { type: "string", default: props.category === "instrument" ? "type" : "" }` aufnehmen. `FILTERS` ist bisher eine Konstante auf Modulebene; den Standardwert je Art in einer Map `GROUP_DEFAULTS = { instrument: "type" }` ablegen und beim Aufruf einsetzen.
- Gruppen-Optionen:
  ```js
  const GROUP_OPTIONS = {
    instrument: [{ key: "type", label: "Typ" }, { key: "status", label: "Status" }, { key: "owner", label: "Eigentümer" }],
    clothing: [{ key: "type", label: "Typ" }, { key: "size", label: "Größe" }, { key: "status", label: "Status" }],
    sheet_music: [{ key: "genre", label: "Gattung" }],
    general_item: [{ key: "category", label: "Kategorie" }, { key: "room", label: "Raum" }, { key: "status", label: "Status" }],
  };
  ```
- Aus `useListQuery` zusätzlich `groups` und `itemTotal` holen.
- Einklappen:
  ```js
  const collapseKey = computed(() => `${props.category}:${state.group_by || "none"}`);
  const { collapsed, toggle: toggleGroup } = useGroupCollapse(collapseKey);
  const cardSegments = computed(() => buildSegments(items.value, groups.value, collapsed.value));
  ```
- `activeFilterCount` zählt `group_by` mit; das ist unerwünscht. Deshalb `filtered` als `activeFilterCount.value - (state.group_by !== defaults.group_by ? 1 : 0) > 0 || !!state.search.trim()` berechnen. Besser und verbindlich: In `useListQuery` bekommt `activeFilterCount` eine Ausnahmeliste `const NOT_FILTERS = ["search", "group_by"]`, und das wird im selben Commit mit einem Test in `useListQuery.test.js` abgesichert („group_by is not counted as a filter“).

**Template:**
- **Toolbar:** nach der `SearchBar` `<GroupSelect :options="GROUP_OPTIONS[category]" :model-value="state.group_by" @update:model-value="setFilter('group_by', $event)" />` einfügen.
- **Listenansicht:** `DataTable` bekommt `:groups="groups"`, `:collapsed-groups="collapsed"` und `@toggle-group="toggleGroup"`.
- **Kartenansicht:** Die bisherige `.instrument-grid`-Schleife wird zu:
  ```vue
  <div v-else class="item-grid">
    <template v-for="seg in cardSegments" :key="seg.key">
      <GroupHeader
        v-if="seg.type === 'group'"
        class="item-grid-group"
        :label="seg.label"
        :count="seg.count"
        :collapsed="seg.collapsed"
        @toggle="toggleGroup(seg.groupKey)"
      />
      <ItemCard
        v-else
        :item="seg.row"
        :has-loans="cat.hasLoans"
        :to="`${cat.routeBase}/${seg.row.id}`"
      />
    </template>
  </div>
  ```
- **Anzahl:** Unter der Toolbar, sobald geladen, `<p class="list-count">{{ itemTotal }} {{ itemTotal === 1 ? cat.labelSingular : cat.label }}</p>`. Die Klasse bekommt `font-variant-numeric: tabular-nums; color: var(--color-muted); margin: 0 0 var(--space-2);`.

**Styles im scoped-Block:**

```css
.item-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: var(--space-4);
}

.item-grid-group {
  grid-column: 1 / -1;
  border-radius: var(--radius-sm);
}

@media (max-width: 640px) {
  .item-grid {
    grid-template-columns: 1fr;
    gap: var(--space-2);
  }
}
```

- Die globalen `.instrument-grid`/`.instrument-card*`-Regeln aus `style.css` entfernen, falls `grep -rn "instrument-card\|instrument-grid" src/frontend/src` danach keine Treffer mehr hat.
- Die Klasse `card-placeholder` und `.card-quantity` im scoped-Block von ItemListPage entfernen, wenn sie ungenutzt sind.

- [ ] **Step 5: Tests, Build, Browser**

Run: `IN_CONTAINER 'cd src/frontend && npx vitest run && npx vite build'`.

Browser, nur lesen:
1. `/instrumente` ohne Query: nach Typ gruppiert, die Überschriften zeigen die Anzahl (die Summe = 157). Einklappen und Neuladen: der Zustand bleibt. „Keine“ gewählt ergibt `group_by=alle` in der URL, auch nach Neuladen.
2. `/allgemein` nach Kategorie: Items mit 2 Kategorien erscheinen zweimal. „Raum“ zeigt Raumnamen wie „Sesselarchiv (Boden/oben)“.
3. `/kleidung` nach Größe.
4. 390 px Breite, Kartenansicht: eine kompakte Zeile pro Item mit 56-px-Bild, 7 oder mehr Items sichtbar, Gruppenüberschriften über die volle Breite. Das dunkle Theme per Screenshot.
5. Die Karten sind echte Links: Mittelklick bzw. „In neuem Tab öffnen“ funktioniert, Tab und Enter öffnen das Item.

- [ ] **Step 6: Commit.** Message: `feat(items): grouped lists and compact phone cards`.

---

### Task 7: Sammelzuweisung in der Oberfläche

**Files:**
- Create: `src/frontend/src/components/BulkCategoryBar.vue`, `components/CategoryPickDialog.vue`
- Modify: `src/frontend/src/pages/ItemListPage.vue` (nur bei `cat.hasCategories`)
- Test: `tests/frontend/BulkCategoryBar.test.js`, `tests/frontend/CategoryPickDialog.test.js`, `tests/frontend/bulkSelection.test.js` (neu, für den Selektions-Helfer)

**Interfaces:**
- **`<BulkCategoryBar :count :busy :message :error @add @remove @select-all @done />`**
- **`<CategoryPickDialog :open :mode="'add'|'remove'" :categories="[{id,label}]" @confirm="ids => …" @cancel />`**
- **`lib/bulkSelection.js`:** `toggleId(ids: number[], id) -> number[]` und `uniqueIds(rows) -> number[]`.

- [ ] **Step 1: Failing tests**

`tests/frontend/bulkSelection.test.js`:

```js
import { describe, it, expect } from "vitest";
import { toggleId, uniqueIds } from "../../src/frontend/src/lib/bulkSelection.js";

describe("bulk selection", () => {
  it("toggles an id", () => {
    expect(toggleId([1, 2], 3)).toEqual([1, 2, 3]);
    expect(toggleId([1, 2], 1)).toEqual([2]);
  });
  it("collects each item once even when it appears in several groups", () => {
    expect(uniqueIds([{ id: 1 }, { id: 2 }, { id: 1 }])).toEqual([1, 2]);
  });
});
```

`tests/frontend/BulkCategoryBar.test.js`:

```js
import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import BulkCategoryBar from "../../src/frontend/src/components/BulkCategoryBar.vue";

describe("BulkCategoryBar", () => {
  it("shows the count and emits actions", async () => {
    const w = mount(BulkCategoryBar, { props: { count: 3 } });
    expect(w.text()).toContain("3 ausgewählt");
    const buttons = Object.fromEntries(w.findAll("button").map((b) => [b.text(), b]));
    await buttons["Alle geladenen auswählen"].trigger("click");
    await buttons["Kategorien hinzufügen"].trigger("click");
    await buttons["Kategorien entfernen"].trigger("click");
    await buttons["Fertig"].trigger("click");
    expect(Object.keys(w.emitted())).toEqual(expect.arrayContaining(["select-all", "add", "remove", "done"]));
  });

  it("disables actions without selection or while busy and shows status", () => {
    const empty = mount(BulkCategoryBar, { props: { count: 0 } });
    const add = empty.findAll("button").find((b) => b.text() === "Kategorien hinzufügen");
    expect(add.attributes("disabled")).toBeDefined();
    const busy = mount(BulkCategoryBar, { props: { count: 2, busy: true, message: "Wird gespeichert …" } });
    expect(busy.findAll("button").find((b) => b.text() === "Kategorien entfernen").attributes("disabled")).toBeDefined();
    expect(busy.find('[role="status"]').text()).toBe("Wird gespeichert …");
    const err = mount(BulkCategoryBar, { props: { count: 2, error: "Netz weg" } });
    expect(err.find('[role="alert"]').text()).toBe("Netz weg");
  });
});
```

`tests/frontend/CategoryPickDialog.test.js`:

```js
import { describe, it, expect, beforeAll } from "vitest";
import { mount } from "@vue/test-utils";
import CategoryPickDialog from "../../src/frontend/src/components/CategoryPickDialog.vue";

beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function () { this.setAttribute("open", ""); };
  HTMLDialogElement.prototype.close = function () { this.removeAttribute("open"); };
});

const categories = [{ id: 1, label: "Deko" }, { id: 2, label: "Fest" }];

describe("CategoryPickDialog", () => {
  it("confirms the chosen ids; the confirm button needs a choice", async () => {
    const w = mount(CategoryPickDialog, { props: { open: true, mode: "add", categories } });
    expect(w.find("h2").text()).toBe("Kategorien hinzufügen");
    const confirm = w.find(".dialog-confirm");
    expect(confirm.attributes("disabled")).toBeDefined();
    await w.findAll('input[type="checkbox"]')[1].setValue(true);
    await confirm.trigger("click");
    expect(w.emitted("confirm")).toEqual([[[2]]]);
  });

  it("uses remove wording and cancels", async () => {
    const w = mount(CategoryPickDialog, { props: { open: true, mode: "remove", categories } });
    expect(w.find("h2").text()).toBe("Kategorien entfernen");
    expect(w.find(".dialog-confirm").text()).toBe("Entfernen");
    await w.find(".dialog-cancel").trigger("click");
    expect(w.emitted("cancel")).toHaveLength(1);
  });

  it("resets the choice when reopened", async () => {
    const w = mount(CategoryPickDialog, { props: { open: true, mode: "add", categories } });
    await w.findAll('input[type="checkbox"]')[0].setValue(true);
    await w.setProps({ open: false });
    await w.setProps({ open: true });
    expect(w.findAll('input[type="checkbox"]').map((b) => b.element.checked)).toEqual([false, false]);
  });
});
```

- [ ] **Step 2: Tests laufen lassen, sie müssen scheitern.**

- [ ] **Step 3: `lib/bulkSelection.js`**

```js
/** Selection helpers: rows may repeat an item across groups, ids do not. */
export function toggleId(ids, id) {
  return ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id];
}

export function uniqueIds(rows) {
  return [...new Set(rows.map((r) => r.id))];
}
```

- [ ] **Step 4: `BulkCategoryBar.vue`**

```vue
<script setup>
defineProps({
  count: { type: Number, default: 0 },
  busy: Boolean,
  message: { type: String, default: "" },
  error: { type: String, default: "" },
});
defineEmits(["add", "remove", "select-all", "done"]);
</script>

<template>
  <div class="bulk-bar" role="region" aria-label="Sammelauswahl">
    <p class="bulk-count">{{ count }} ausgewählt</p>
    <div class="bulk-actions">
      <button type="button" class="btn-sm" :disabled="busy" @click="$emit('select-all')">
        Alle geladenen auswählen
      </button>
      <button type="button" class="btn-sm btn-primary" :disabled="busy || !count" @click="$emit('add')">
        Kategorien hinzufügen
      </button>
      <button type="button" class="btn-sm" :disabled="busy || !count" @click="$emit('remove')">
        Kategorien entfernen
      </button>
      <button type="button" class="btn-sm" :disabled="busy" @click="$emit('done')">Fertig</button>
    </div>
    <p v-if="error" class="form-error" role="alert">{{ error }}</p>
    <p v-else-if="message" class="bulk-message" role="status">{{ message }}</p>
  </div>
</template>

<style scoped>
.bulk-bar {
  position: sticky;
  bottom: 0;
  z-index: 15;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2) var(--space-4);
  margin-top: var(--space-4);
  padding: var(--space-3) var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  background: var(--color-bg);
  box-shadow: var(--shadow-float);
}

.bulk-count {
  margin: 0;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.bulk-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.bulk-actions .btn-sm {
  min-height: 44px;
}

.bulk-message,
.bulk-bar .form-error {
  flex-basis: 100%;
  margin: 0;
}
</style>
```

- [ ] **Step 5: `CategoryPickDialog.vue`**

```vue
<script setup>
import { computed, ref, watch, nextTick } from "vue";

const props = defineProps({
  open: Boolean,
  mode: { type: String, default: "add" },
  categories: { type: Array, default: () => [] },
});
const emit = defineEmits(["confirm", "cancel"]);

const dialog = ref(null);
const chosen = ref([]);
const title = computed(() => (props.mode === "add" ? "Kategorien hinzufügen" : "Kategorien entfernen"));
const confirmLabel = computed(() => (props.mode === "add" ? "Hinzufügen" : "Entfernen"));

watch(
  () => props.open,
  async (open) => {
    await nextTick();
    if (!dialog.value) return;
    if (open) {
      chosen.value = [];
      if (!dialog.value.open) dialog.value.showModal();
    } else if (dialog.value.open) {
      dialog.value.close();
    }
  },
  { immediate: true },
);

function toggle(id, checked) {
  chosen.value = checked ? [...chosen.value, id] : chosen.value.filter((x) => x !== id);
}
</script>

<template>
  <dialog ref="dialog" class="dialog pick-dialog" @cancel.prevent="emit('cancel')">
    <h2>{{ title }}</h2>
    <fieldset>
      <legend class="sr-only">Kategorien</legend>
      <label v-for="c in categories" :key="c.id" class="pick-option">
        <input type="checkbox" :checked="chosen.includes(c.id)" @change="toggle(c.id, $event.target.checked)" />
        {{ c.label }}
      </label>
      <p v-if="!categories.length" class="text-muted">Noch keine Kategorien angelegt.</p>
    </fieldset>
    <div class="dialog-actions">
      <button type="button" class="dialog-cancel" @click="emit('cancel')">Abbrechen</button>
      <button
        type="button"
        class="btn-primary dialog-confirm"
        :disabled="!chosen.length"
        @click="emit('confirm', [...chosen])"
      >
        {{ confirmLabel }}
      </button>
    </div>
  </dialog>
</template>

<style scoped>
.pick-dialog h2 {
  margin: 0 0 var(--space-3);
  font-size: 1.1rem;
}

.pick-dialog fieldset {
  max-height: 50vh;
  overflow-y: auto;
  margin: 0;
  padding: 0;
  border: none;
}

.pick-option {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-height: 44px;
}

.pick-option input {
  width: auto;
}

.dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
  margin-top: var(--space-4);
}

.dialog-actions button {
  min-height: 44px;
}
</style>
```

Prüfe, ob `ConfirmDialog.vue` bzw. `style.css` eine globale `.dialog`-Klasse für natives `<dialog>` hat; falls ja, sie verwenden (wie `ScanDocuments.vue`), sonst die Grundstile von dort übernehmen.

- [ ] **Step 6: ItemListPage, nur bei `cat.hasCategories`**

**Script:**

```js
import { post } from "../lib/api.js";
import { toggleId, uniqueIds } from "../lib/bulkSelection.js";
import BulkCategoryBar from "../components/BulkCategoryBar.vue";
import CategoryPickDialog from "../components/CategoryPickDialog.vue";

const selecting = ref(false);
const selectedIds = ref([]);
const pickMode = ref(null); // "add" | "remove" | null
const bulkBusy = ref(false);
const bulkMessage = ref("");
const bulkError = ref("");

function startSelecting() {
  selecting.value = true;
  selectedIds.value = [];
  bulkMessage.value = "";
  bulkError.value = "";
}

function stopSelecting() {
  selecting.value = false;
  selectedIds.value = [];
  pickMode.value = null;
}

function toggleSelect(row) {
  selectedIds.value = toggleId(selectedIds.value, row.id);
}

function selectAllLoaded() {
  selectedIds.value = uniqueIds(items.value);
}

async function applyBulk(ids) {
  const mode = pickMode.value;
  pickMode.value = null;
  bulkBusy.value = true;
  bulkError.value = "";
  bulkMessage.value = "Wird gespeichert …";
  try {
    const body = { item_ids: selectedIds.value, add_ids: mode === "add" ? ids : [], remove_ids: mode === "remove" ? ids : [] };
    const { updated } = await post("/items/bulk-categories", body);
    bulkMessage.value = `${updated} ${updated === 1 ? "Gegenstand" : "Gegenstände"} aktualisiert.`;
    selectedIds.value = [];
    await reload();
  } catch (e) {
    bulkMessage.value = "";
    bulkError.value = `Speichern fehlgeschlagen: ${e.message}`;
  } finally {
    bulkBusy.value = false;
  }
}
```

- `goTo(row)` wird: `if (selecting.value) toggleSelect(row); else router.push(...)`.
- Nach einer Sammelzuweisung ändern sich die Kategorien: Das Neuladen per `reload()` holt die Daten neu. Die Optionen (`typeOptions`) bleiben gleich, weil die Sammelzuweisung keine Kategorien anlegt.

**Template:**
- **Kopfbereich:** Neben „anlegen“ erscheint bei `cat.hasCategories && !selecting` der Button `<button type="button" class="btn btn-secondary" @click="startSelecting">Auswählen</button>`.
- **DataTable:** `:selectable="selecting"`, `:selected-ids="selectedIds"`, `@toggle-select="toggleSelect"`.
- **ItemCard:** `:selecting="selecting"`, `:selected="selectedIds.includes(seg.row.id)"`, `@toggle-select="toggleSelect(seg.row)"`.
- **Am Seitenende** vor dem Modal:
  ```vue
  <BulkCategoryBar
    v-if="selecting"
    :count="selectedIds.length"
    :busy="bulkBusy"
    :message="bulkMessage"
    :error="bulkError"
    @select-all="selectAllLoaded"
    @add="pickMode = 'add'"
    @remove="pickMode = 'remove'"
    @done="stopSelecting"
  />
  <CategoryPickDialog
    v-if="cat.hasCategories"
    :open="pickMode !== null"
    :mode="pickMode || 'add'"
    :categories="typeOptions"
    @confirm="applyBulk"
    @cancel="pickMode = null"
  />
  ```

`typeOptions` enthält bei `general_item` die Kategorien aus `/general-item-categories` mit den Feldern `id` und `label`.

- [ ] **Step 7: Tests, Build, Browser**

Run: `IN_CONTAINER 'cd src/frontend && npx vitest run && npx vite build'`.

Browser (echte DB, einzige erlaubte Schreibaktion laut Global Constraints):
1. Die Kategorien von A-001 und A-002 notieren.
2. Unter `/einstellungen/kategorien` die Kategorie „Test-Sammel“ anlegen.
3. `/allgemein`: „Auswählen“, dann A-001 und A-002 anhaken (Karten- und Listenansicht), „Kategorien hinzufügen“, „Test-Sammel“ und „Hinzufügen“. Die Meldung lautet „2 Gegenstände aktualisiert.“, und bei Gruppierung nach Kategorie gibt es eine Gruppe „Test-Sammel (2)“.
4. Beide erneut wählen, „Kategorien entfernen“ und „Test-Sammel“. Die Gruppe verschwindet.
5. „Test-Sammel“ löschen. Die Kategorien von A-001 und A-002 per API mit den notierten vergleichen: unverändert.
6. Am Handy (390 px) ist die Aktionsleiste unten sichtbar und bedienbar, auch im dunklen Theme.

- [ ] **Step 8: Commit.** Message: `feat(items): bulk category assignment for general items`.

---

### Task 8: Gruppierung auf Musiker- und Leihregister-Seite

**Files:**
- Modify: `src/frontend/src/pages/MusicianListPage.vue`, `src/frontend/src/pages/LoanListPage.vue`

**Interfaces:**
- Consumes: `GroupSelect`, `useGroupCollapse`, `DataTable` (`groups`, `collapsedGroups`, `toggle-group`), `useListQuery` (`groups`, `itemTotal`); dazu die API aus Task 2.

- [ ] **Step 1: MusicianListPage**
- Filter `group_by: { type: "string", default: "" }` ergänzen.
- `GROUP_OPTIONS = [{ key: "register", label: "Register" }, { key: "status", label: "Status" }]`.
- `GroupSelect` in der Toolbar, an `setFilter('group_by', $event)` gebunden.
- `useGroupCollapse(computed(() => \`musicians:${state.group_by || "none"}\`))`.
- `DataTable` bekommt `:groups`, `:collapsed-groups` und `@toggle-group`.
- `filtered` darf `group_by` nicht mitzählen; der Ausschluss kommt mit Task 6 in `activeFilterCount`.
- Anzahlzeile wie auf ItemListPage: „{{ itemTotal }} Musiker“.

- [ ] **Step 2: LoanListPage**
- Filter `group_by` (Standard `""`).
- Optionen:
  ```js
  [{ key: "musician", label: "Musiker" }, { key: "item_category", label: "Inventar-Art" }, { key: "status", label: "Status" }]
  ```
- Sonst wie bei den Musikern. Speicherschlüssel `loans:<group_by>`, Anzahlzeile „{{ itemTotal }} Leihen“.

- [ ] **Step 3: Tests, Build, Browser**

Run: `IN_CONTAINER 'cd src/frontend && npx vitest run && npx vite build'`.

Browser, nur lesen:
- `/musiker?group_by=register`: Musiker mit mehreren Registern erscheinen mehrfach, die Register stehen in Register-Reihenfolge, „Ohne Register“ zuletzt.
- `/leihen?group_by=musician`: eine Überschrift pro Musiker mit Anzahl. Einklappen, nachladen, Handy-Breite, dunkles Theme.

- [ ] **Step 4: Commit.** Message: `feat(frontend): grouping on musician and loan lists`.
