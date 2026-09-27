# Listen-Infrastruktur (fastapi-filter + Nachladen) Implementierungsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Die Inventar-Listen (Items aller Arten, Musiker, Rechnungen, Leihregister) bekommen URL-gespeicherte Filter nach dem fastapi-filter-Schema, eine Sortierung per Spaltenkopf und Nachladen beim Scrollen. Auswahlfelder schneiden nicht mehr bei 200 Einträgen ab.

**Architektur:**
- **Backend:** Eine gemeinsame Basisklasse `ListFilter` auf `fastapi_filter.contrib.sqlalchemy.Filter` bildet öffentliche Namen auf Spalten ab, auch auf verknüpfte Tabellen. Sie kennt eigene `filter_<name>`-Methoden, eigene Sortierschlüssel und hängt immer `id` als letzten Sortierschlüssel an. Dazu kommen `PageParams` und `paginate()`.
- **Frontend:** Ein Composable `useListQuery` gleicht den Zustand mit der URL ab, lädt Seiten und verwirft veraltete Antworten. Die Komponenten `FilterBar`, `SortSelect`, `InfiniteLoader` und `RemotePicker` sowie Sortierköpfe in `DataTable` bauen darauf auf.
- **Umsetzung:** Jede Liste wird als durchgehende Aufgabe umgestellt, Backend und Seite gemeinsam, damit die laufende App nie halb umgestellt ist.

**Tech Stack:** FastAPI 0.141, fastapi-filter 3.0, SQLAlchemy 2.0 async (aiosqlite), Pydantic 2.13, pytest-asyncio; Vue 3.4 (`<script setup>`), vue-router 4, Vitest + @vue/test-utils (jsdom).

**Spec:** `docs/superpowers/specs/2026-09-27-list-infrastructure-design.md`

## Global Constraints

**Ausführung und Git**
- **Umgebung:** Claude arbeitet auf dem Host, die App läuft im Devcontainer. Jeder Python-, Node-, pip- und pre-commit-Befehl läuft so:
  `docker exec -w /workspaces/mv_hofki mv-hofki-vue-pyhton_devcontainer-devcontainer-1 bash -lc '<befehl>'`
  Im Plan steht dafür kurz `IN_CONTAINER '<befehl>'`. Bearbeitet werden die Dateien auf dem Host unter `/home/ai/Documents/mv-hofki-vue-pyhton`; das ist dasselbe Verzeichnis.
- **Committen:** im Container mit der Git-Identität des Hosts:
  ```bash
  cd /home/ai/Documents/mv-hofki-vue-pyhton && N=$(git config user.name); E=$(git config user.email); \
  docker exec -w /workspaces/mv_hofki -e GIT_AUTHOR_NAME="$N" -e GIT_AUTHOR_EMAIL="$E" -e GIT_COMMITTER_NAME="$N" -e GIT_COMMITTER_EMAIL="$E" \
    mv-hofki-vue-pyhton_devcontainer-devcontainer-1 bash -lc 'git add <dateien> && git commit -m "<msg>

  Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>" -- <dateien>'
  ```
  Committet werden nur die eigenen Dateien. Andere Claude-Sitzungen arbeiten gleichzeitig im Repo. **Niemals** `git stash`, `git reset`, `git clean` oder `git add -A`/`git add .` verwenden. Hat eine Datei, die du ändern musst, fremde nicht committete Änderungen (`git status --short <datei>`), stoppe und melde NEEDS_CONTEXT.
- **pre-commit:** Der Hook (ruff, ruff-format, mypy, eslint, prettier) läuft beim Commit. Formatiert er um, die Dateien neu `git add`en und erneut committen.
- **Bekannte fremde Testfehler, ignorieren und nicht anfassen:**
  - `tests/backend/test_item_invoices.py::test_create_invoice_on_sheet_music_rejected`
  - `tests/backend/test_scanner_config.py::test_sync_preserves_user_value`
  - `tests/frontend/App.test.js`

**Sprache und Gestaltung**
- **Sprache:** UI-Texte und API-Fehlertexte auf Deutsch, österreichische Schreibung, typografische Anführungszeichen „…“.
- **Styling:** Farben, Radien, Schatten und Abstände nur über Tokens aus `src/frontend/src/style.css` (`--color-*`, `--radius*`, `--space-*`, `--shadow-float`). Keine Farbliterale.
- **Bedienbarkeit:**
  - Touch-Ziele mindestens 44 px.
  - Alles Klickbare ist ein `<button>` oder Link mit sichtbarem Text oder `aria-label`.
  - Nichts funktioniert nur mit Maus oder Hover.
- **Fehler:** In neuem Code inline anzeigen, kein `alert()`.

**API-Vorgaben**
- **Seiten:** `limit` Standard 50, 1–200; `offset` ≥ 0. Die Antwortform ist `{items, total, limit, offset}`.
- **Sortierung:** `order_by` enthält kommagetrennte Sortierschlüssel, `-` für absteigend. Ein unbekannter Schlüssel ergibt 422. NULL-Werte stehen immer am Ende, `id` ist immer der letzte Schlüssel.
- **Parameternamen:** exakt wie in der Tabelle „Filter und Sortierung je Liste“ der Spec.
- **URL-Parameter im Frontend** heißen wie die API-Parameter. Standardwerte stehen nicht in der URL. Ein abgewählter Standardwert, der nicht leer ist, wird als `alle` geschrieben. Die Sortierung steht in `order_by`.

## Review Focus

1. **Nachladen bei gleichen Sortwerten:** Viele Einträge mit gleichem Wert, etwa 60 Musiker mit Nachnamen „Maier“, Seitengröße 50. Seite 1 und 2 zusammen liefern jeden Eintrag genau einmal. (Test in Task 5)
2. **Zurück-Taste:** Filter setzen, einen Eintrag öffnen, Zurück. Die Liste zeigt dieselben Filter und lädt passend dazu. Zweimal Zurück springt nicht in einer Schleife hin und her. (Test in Task 2: externe URL-Änderung übernehmen, eigene Änderung erzeugt keinen zweiten Aufruf)
3. **Veraltete Antwort:** Schnelles Umschalten zweier Filter. Eine langsame erste Antwort darf die zweite nicht überschreiben; auch `loadMore` einer alten Filterlage nicht. (Test in Task 2)
4. **Unpassender Filter für die Item-Art:** `?category=instrument&size=L` ergibt 422 mit deutschem Text, nicht 500 und nicht eine stille Filterung. (Test in Task 6)
5. **Leihen an bestehenden Stellen:** Detailseiten von Musiker und Item zeigen weiter die komplette Leihhistorie, jetzt über `getAll`. Die Import-Seite zeigt weiter alle Musiker. (Tests in Task 8 und Task 5)

---

## Dateiübersicht

| Datei | Aufgabe |
|---|---|
| `pyproject.toml` | Abhängigkeit `fastapi-filter[sqlalchemy]>=3,<4` |
| `src/backend/mv_hofki/filters/__init__.py`, `filters/base.py` (neu) | `ListFilter`, `PageParams`, `paginate` |
| `src/backend/mv_hofki/filters/musician.py` (neu) | `MusicianFilter` |
| `src/backend/mv_hofki/filters/inventory_item.py` (neu) | `ItemFilter`, `display_nr_condition` |
| `src/backend/mv_hofki/filters/invoice.py` (neu) | `InvoiceFilter` |
| `src/backend/mv_hofki/filters/loan.py` (neu) | `LoanFilter` |
| `services/musician.py`, `services/inventory_item.py`, `services/invoice_overview.py`, `services/loan.py` | `get_list` auf Filter + Page |
| `api/routes/musicians.py`, `items.py`, `invoices.py`, `loans.py` | Routen mit `FilterDepends` |
| `schemas/invoice_overview.py` | `limit`, `offset`, `invoice_issuer` |
| `src/frontend/src/lib/api.js` | `getAll` |
| `src/frontend/src/lib/pickers.js` (neu) | `fetchMusicianOptions`, `fetchLoanableItemOptions` |
| `src/frontend/src/composables/useListQuery.js` (neu) | Listen-Zustand, URL, Laden |
| `src/frontend/src/components/InfiniteLoader.vue`, `FilterBar.vue`, `SortSelect.vue`, `RemotePicker.vue` (neu) | UI-Bausteine |
| `src/frontend/src/components/DataTable.vue` | Sortierköpfe, `SortSelect` in Karten, `emptyText` |
| Seiten | `MusicianListPage`, `ItemListPage`, `InvoiceListPage`, `LoanListPage`, `ItemDetailPage`, `MusicianDetailPage`, `ImportSessionPage`, `ScanProjectListPage`, `ScanProjectDetailPage` |
| `src/frontend/src/lib/musicians.js` | Query-Helfer entfernen, `registerLabels` bleibt |

---

### Task 1: Backend-Grundlage `ListFilter`, `PageParams`, `paginate`

**Files:**
- Modify: `pyproject.toml` (Abschnitt `dependencies`)
- Create: `src/backend/mv_hofki/filters/__init__.py` (leer, nur Docstring)
- Create: `src/backend/mv_hofki/filters/base.py`
- Test: `tests/backend/test_list_filter.py`

**Interfaces:**
- Produces:
  - `ListFilter`: Pydantic-Modell mit den Feldern `search: str | None`, `order_by: list[str] | None`.
    - `Constants`: `model`, `columns: dict[str, col]`, `sort_fields: dict[str, list[col]]`, `default_sort: list[str]`, optional `search_model_fields: list[str]`.
    - Methoden: `filter(query) -> Select`, `sort(query) -> Select`, `column(field) -> col`, `sort_columns(key) -> list[col]`, `search_clause(value) -> ColumnElement | None`.
    - Hook: Eine Methode `filter_<feldname>(self, query, value) -> Select` behandelt ein Feld selbst.
  - `PageParams` (Dependency-Klasse mit `.limit` und `.offset`).
  - `async paginate(session, query, page, *, options=()) -> tuple[list, int]`.
  - Konstante `MAX_LIMIT = 200`.

- [ ] **Step 1: Abhängigkeit**

In `pyproject.toml` unter `dependencies` nach der fastapi-Zeile einfügen: `"fastapi-filter[sqlalchemy]>=3,<4",`.

Danach im Container installieren, genauso wie das Projekt installiert ist. Prüfe dazu, ob `pip show mv_hofki` einen editable Install zeigt:

Run: `IN_CONTAINER 'pip install "fastapi-filter[sqlalchemy]>=3,<4" && pip show fastapi-filter | grep Version'`
Expected: `Version: 3.0.0` (oder neuer 3.x).

- [ ] **Step 2: Failing tests schreiben**

`tests/backend/test_list_filter.py`:

```python
"""ListFilter base: column mapping, custom handlers, search, sorting, paging."""

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from mv_hofki.filters.base import ListFilter, PageParams, paginate
from mv_hofki.models.musician import Musician


class _Filter(ListFilter):
    last_name: str | None = None
    city__ilike: str | None = None
    town: str | None = None
    is_extern: bool | None = None
    id__in: list[int] | None = None
    initial: str | None = None

    class Constants(ListFilter.Constants):
        model = Musician
        search_model_fields = ["first_name", "last_name"]
        columns = {"town": Musician.city}
        sort_fields = {
            "last_name": [Musician.last_name],
            "city": [Musician.city],
            "name": [Musician.last_name, Musician.first_name],
        }
        default_sort = ["last_name"]

    def filter_initial(self, query, value):
        return query.where(Musician.last_name.like(f"{value}%"))


@pytest.fixture
async def people(db_session):
    rows = [
        Musician(first_name="Anna", last_name="Maier", city="Linz", is_extern=False),
        Musician(first_name="Berta", last_name="Maier", city=None, is_extern=True),
        Musician(first_name="Carl", last_name="Huber", city="Wels", is_extern=False),
        Musician(first_name="Dora", last_name="Aigner", city="Linz", is_extern=False),
    ]
    db_session.add_all(rows)
    await db_session.commit()
    return rows


async def _run(db_session, flt):
    result = await db_session.execute(flt.sort(flt.filter(select(Musician))))
    return [m.first_name for m in result.scalars()]


async def test_plain_field_and_default_sort(db_session, people):
    assert await _run(db_session, _Filter(last_name="Maier")) == ["Anna", "Berta"]
    assert await _run(db_session, _Filter()) == ["Dora", "Carl", "Anna", "Berta"]


async def test_mapped_column_and_ilike_adds_wildcards(db_session, people):
    assert await _run(db_session, _Filter(town="Wels")) == ["Carl"]
    assert await _run(db_session, _Filter(city__ilike="IN")) == ["Dora", "Anna"]


async def test_in_operator_and_bool(db_session, people):
    ids = [people[0].id, people[2].id]
    assert await _run(db_session, _Filter(id__in=ids)) == ["Carl", "Anna"]
    assert await _run(db_session, _Filter(is_extern=True)) == ["Berta"]


async def test_custom_handler(db_session, people):
    assert await _run(db_session, _Filter(initial="Hu")) == ["Carl"]


async def test_search_over_model_fields_ignores_blank(db_session, people):
    assert await _run(db_session, _Filter(search="dor")) == ["Dora"]
    assert len(await _run(db_session, _Filter(search="   "))) == 4


async def test_sort_desc_nulls_last_and_id_tiebreak(db_session, people):
    # city desc: Wels, Linz(Anna id1), Linz(Dora id4), NULL last
    assert await _run(db_session, _Filter(order_by=["-city"])) == [
        "Carl",
        "Anna",
        "Dora",
        "Berta",
    ]
    assert await _run(db_session, _Filter(order_by=["city"])) == [
        "Anna",
        "Dora",
        "Carl",
        "Berta",
    ]


async def test_multi_column_sort_key(db_session, people):
    assert await _run(db_session, _Filter(order_by=["-name"])) == [
        "Berta",
        "Anna",
        "Carl",
        "Dora",
    ]


def test_order_by_accepts_comma_string():
    assert _Filter(order_by="-city,last_name").order_by == ["-city", "last_name"]


def test_unknown_sort_key_rejected():
    with pytest.raises(ValidationError) as exc:
        _Filter(order_by=["first_name"])
    assert "kein gültiger Sortierschlüssel" in str(exc.value)


def test_duplicate_sort_key_rejected():
    with pytest.raises(ValidationError):
        _Filter(order_by=["city", "-city"])


async def test_paginate_counts_filtered_and_slices(db_session, people):
    flt = _Filter(city__ilike="linz")
    query = flt.sort(flt.filter(select(Musician)))
    rows, total = await paginate(db_session, query, PageParams(limit=1, offset=1))
    assert total == 2
    assert [m.first_name for m in rows] == ["Anna"]
```

Das Ergebnis in `test_sort_desc_nulls_last_and_id_tiebreak` erklärt sich so:
- Bei `-city` gilt nur für `city` absteigend. Der angehängte `id`-Schlüssel ist immer aufsteigend. Deshalb kommt Anna (id 1) vor Dora (id 4).
- Bei `city` aufsteigend steht Linz vor Wels.

`PageParams(limit=1, offset=1)` wird direkt aufgerufen; die `Query(...)`-Standardwerte greifen nur bei der Dependency-Injection.

- [ ] **Step 3: Tests laufen lassen, sie müssen scheitern**

Run: `IN_CONTAINER 'python -m pytest tests/backend/test_list_filter.py -q'`
Expected: FAIL mit `ModuleNotFoundError: mv_hofki.filters`.

- [ ] **Step 4: Implementierung**

`src/backend/mv_hofki/filters/__init__.py`:
```python
"""fastapi-filter based list filters for the API's list endpoints."""
```

`src/backend/mv_hofki/filters/base.py`:

```python
"""Shared plumbing for list endpoints.

``ListFilter`` builds on fastapi-filter's SQLAlchemy ``Filter`` (query syntax
``field__op=value``, ``order_by=-a,b``, list parsing, OpenAPI docs) and adds the
project's conventions:

* ``Constants.columns`` maps a public field name to any column, also one of a
  joined table; unmapped names use the model's attribute of the same name.
* A method ``filter_<field name>(query, value)`` handles a field itself.
* ``search_clause(value)`` builds the ``search`` condition.
* ``Constants.sort_fields`` defines the public sort keys (one key may sort by
  several columns); ``order_by`` is validated against them. NULLs always sort
  last and the model's ``id`` is always the final key, so paging is stable.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from fastapi import Query
from fastapi_filter.contrib.sqlalchemy import Filter
from pydantic import ValidationInfo, field_validator
from sqlalchemy import ColumnElement, Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

MAX_LIMIT = 200


def _ilike(column: Any, value: str) -> ColumnElement[bool]:
    return column.ilike(value if "%" in value else f"%{value}%")


_OPERATORS: dict[str, Callable[[Any, Any], ColumnElement[bool]]] = {
    "neq": lambda col, v: col != v,
    "gt": lambda col, v: col > v,
    "gte": lambda col, v: col >= v,
    "lt": lambda col, v: col < v,
    "lte": lambda col, v: col <= v,
    "in": lambda col, v: col.in_(v),
    "not_in": lambda col, v: col.not_in(v),
    "isnull": lambda col, v: col.is_(None) if v else col.is_not(None),
    "ilike": _ilike,
}


class PageParams:
    """``limit``/``offset`` query parameters of every list endpoint."""

    def __init__(
        self,
        limit: int = Query(50, ge=1, le=MAX_LIMIT),
        offset: int = Query(0, ge=0),
    ):
        self.limit = limit
        self.offset = offset


class ListFilter(Filter):
    search: str | None = None
    order_by: list[str] | None = None

    class Constants(Filter.Constants):
        columns: dict[str, Any] = {}
        sort_fields: dict[str, list[Any]] = {}
        default_sort: list[str] = []

    # Replaces fastapi-filter's validator of the same name, which only accepts
    # attributes of the model as sort keys.
    @field_validator("*", mode="before", check_fields=False)
    @classmethod
    def validate_order_by(cls, value: Any, field: ValidationInfo) -> Any:
        if field.field_name != cls.Constants.ordering_field_name:
            return value
        if not value:
            return None
        if isinstance(value, str):
            value = value.split(",")
        keys = [v.strip() for v in value if v and v.strip()]
        seen: set[str] = set()
        for key in keys:
            name = key.lstrip("+-")
            if name not in cls.Constants.sort_fields:
                raise ValueError(f"„{name}“ ist kein gültiger Sortierschlüssel.")
            if name in seen:
                raise ValueError(f"Sortierschlüssel „{name}“ ist doppelt angegeben.")
            seen.add(name)
        return keys or None

    def column(self, field: str) -> Any:
        if field in self.Constants.columns:
            return self.Constants.columns[field]
        return getattr(self.Constants.model, field)

    def sort_columns(self, key: str) -> list[Any]:
        return self.Constants.sort_fields[key]

    def search_clause(self, value: str) -> ColumnElement[bool] | None:
        value = value.strip()
        fields = getattr(self.Constants, "search_model_fields", [])
        if not value or not fields:
            return None
        return or_(*(self.column(f).ilike(f"%{value}%") for f in fields))

    def filter(self, query: Select) -> Select:  # type: ignore[override]
        for name, value in self.filtering_fields:
            if name == self.Constants.search_field_name:
                clause = self.search_clause(value)
                if clause is not None:
                    query = query.where(clause)
                continue
            handler = getattr(self, f"filter_{name}", None)
            if handler is not None:
                query = handler(query, value)
                continue
            field, _, op = name.partition("__")
            column = self.column(field)
            query = query.where(_OPERATORS[op](column, value) if op else column == value)
        return query

    def sort(self, query: Select) -> Select:  # type: ignore[override]
        for key in self.order_by or self.Constants.default_sort:
            descending = key.startswith("-")
            for col in self.sort_columns(key.lstrip("+-")):
                ordered = col.desc() if descending else col.asc()
                query = query.order_by(ordered.nulls_last())
        return query.order_by(self.Constants.model.id)


async def paginate(
    session: AsyncSession,
    query: Select,
    page: PageParams,
    *,
    options: Sequence[Any] = (),
) -> tuple[list[Any], int]:
    """(rows of one page, total of the filtered query). Loader ``options`` are
    applied to the page query only, not to the count."""
    total = await session.scalar(
        select(func.count()).select_from(query.order_by(None).subquery())
    )
    result = await session.execute(
        query.options(*options).limit(page.limit).offset(page.offset)
    )
    return list(result.unique().scalars().all()), total or 0
```

Hinweise:
- Die Validatoren `strip_order_by_values` und `split_str` der Bibliothek laufen weiterhin. `validate_order_by` akzeptiert deshalb sowohl einen String als auch eine Liste.
- Meldet mypy etwas zur Überschreibung von `Constants` mit Klassen-Attributen, `# type: ignore[misc]` nur an der betroffenen Zeile setzen.

- [ ] **Step 5: Tests laufen lassen, sie müssen bestehen**

Run: `IN_CONTAINER 'python -m pytest tests/backend/test_list_filter.py -q -W error::DeprecationWarning'`
Expected: alle PASS, ohne DeprecationWarning (die Bibliothek warnt bei `ilike` ohne `%`; die Basis vermeidet das).

Scheitert `test_unknown_sort_key_rejected`, weil der Validator der Bibliothek zuerst greift und eine englische Meldung liefert, dann wird er nicht überschrieben. In dem Fall in `ListFilter` zusätzlich `strip_order_by_values` mit derselben Signatur überschreiben, die den Wert nur durchreicht, und die Ursache im Report festhalten.

Run: `IN_CONTAINER 'python -m pytest tests/backend -q'`
Expected: nur die bekannten fremden Fehler.

- [ ] **Step 6: Commit**

Dateien: `pyproject.toml`, `src/backend/mv_hofki/filters/__init__.py`, `src/backend/mv_hofki/filters/base.py`, `tests/backend/test_list_filter.py`. Message: `feat(api): ListFilter base on fastapi-filter with paging helpers`.

---

### Task 2: Frontend-Grundlage `getAll`, `useListQuery`, `InfiniteLoader` sowie Behebung bei den Scan-Projekten

**Files:**
- Modify: `src/frontend/src/lib/api.js` (Export `getAll`)
- Create: `src/frontend/src/composables/useListQuery.js`
- Create: `src/frontend/src/components/InfiniteLoader.vue`
- Modify: `src/frontend/src/pages/ScanProjectListPage.vue:25-33` (`fetchProjects`), `src/frontend/src/pages/ScanProjectDetailPage.vue:70-78` (`fetchAllProjects`)
- Test: `tests/frontend/api.test.js` (ergänzen), `tests/frontend/useListQuery.test.js` (neu), `tests/frontend/InfiniteLoader.test.js` (neu)

**Interfaces:**
- **`getAll(path, pageSize = 200) -> Promise<any[]>`**
- **`useListQuery({ endpoint, filters, defaultSort = "", pageSize = 50, baseParams = () => ({}), mapItem = (x) => x, debounceMs = 300 })`** liefert:
  - Zustand: `state` (reactive), `sort` (ref), `setSort(value)`, `setFilter(key, raw)` (wandelt in den Typ des Filters um), `defaults` (Objekt), `activeFilterCount` (computed, ohne `search`)
  - Daten: `items`, `total`, `lastResponse` (die letzte ganze Antwort, z.B. für `totals_by_currency`)
  - Ladezustand: `loading` (erste Seite), `loadingMore`, `error` (String), `hasMore`
  - Aktionen: `loadMore()`, `reload()`, `resetFilters()`
- **`filters`:** `{ [key]: { type: "string"|"list"|"bool"|"number"|"date", default, debounce?: boolean } }`
- **Reine, exportierte Helfer:** `readState(filters, query)`, `writeQuery(filters, state, sort, defaultSort)`, `buildParams(filters, state, { sort, base, offset, limit })`
- **`<InfiniteLoader :has-more :loading :error :count :total @load-more />`**

- [ ] **Step 1: Failing tests schreiben**

In `tests/frontend/api.test.js` (gibt es schon; es stubbt `fetch`) einen Block anfügen:

```js
describe("getAll", () => {
  it("pages until total and appends limit/offset to paths with a query", async () => {
    const pages = [
      { items: [{ id: 1 }, { id: 2 }], total: 3 },
      { items: [{ id: 3 }], total: 3 },
    ];
    const calls = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url) => {
        calls.push(url);
        const body = pages[calls.length - 1];
        return {
          ok: true,
          headers: new Headers({ "content-type": "application/json" }),
          json: async () => body,
          text: async () => JSON.stringify(body),
        };
      }),
    );
    const { getAll } = await import("../../src/frontend/src/lib/api.js");
    const all = await getAll("/loans?item_id=5", 2);
    expect(all.map((x) => x.id)).toEqual([1, 2, 3]);
    expect(calls[0]).toMatch(/\/api\/v1\/loans\?item_id=5&limit=2&offset=0$/);
    expect(calls[1]).toMatch(/offset=2$/);
  });
});
```

Die Datei vorher lesen und bestehende Imports und Stub-Muster wiederverwenden. Liest `request()` den Body über `json()` statt `text()`, das Stub-Objekt entsprechend anpassen. Wichtig ist nur, dass beide Seiten geliefert werden.

`tests/frontend/useListQuery.test.js`:

```js
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { createRouter, createMemoryHistory } from "vue-router";
import { defineComponent, h, nextTick } from "vue";

vi.mock("../../src/frontend/src/lib/api.js", () => ({ get: vi.fn() }));
import { get } from "../../src/frontend/src/lib/api.js";
import {
  useListQuery,
  readState,
  writeQuery,
  buildParams,
} from "../../src/frontend/src/composables/useListQuery.js";

const FILTERS = {
  search: { type: "string", default: "", debounce: true },
  is_active: { type: "bool", default: true },
  register_id__in: { type: "list", default: [] },
  currency_id: { type: "number", default: null },
};

describe("pure helpers", () => {
  it("reads defaults, values and the 'alle' marker", () => {
    expect(readState(FILTERS, {})).toEqual({
      search: "",
      is_active: true,
      register_id__in: [],
      currency_id: null,
    });
    expect(
      readState(FILTERS, {
        search: "Maier",
        is_active: "alle",
        register_id__in: "3,5",
        currency_id: "2",
      }),
    ).toEqual({ search: "Maier", is_active: null, register_id__in: ["3", "5"], currency_id: 2 });
    expect(readState(FILTERS, { is_active: "false", currency_id: "x" })).toMatchObject({
      is_active: false,
      currency_id: null,
    });
  });

  it("writes only non-default values; an emptied non-empty default becomes 'alle'", () => {
    const defaults = readState(FILTERS, {});
    expect(writeQuery(FILTERS, defaults, "last_name", "last_name")).toEqual({});
    expect(
      writeQuery(
        FILTERS,
        { search: "Maier", is_active: null, register_id__in: ["3", "5"], currency_id: 2 },
        "-last_name",
        "last_name",
      ),
    ).toEqual({
      search: "Maier",
      is_active: "alle",
      register_id__in: "3,5",
      currency_id: "2",
      order_by: "-last_name",
    });
  });

  it("builds API params in a stable order without empty values", () => {
    const params = buildParams(
      FILTERS,
      { search: " Maier ", is_active: null, register_id__in: ["3", "5"], currency_id: null },
      { sort: "last_name", base: { category: "x" }, offset: 50, limit: 50 },
    );
    expect(params.toString()).toBe(
      "category=x&search=Maier&register_id__in=3%2C5&order_by=last_name&limit=50&offset=50",
    );
  });
});

async function setup(query = {}) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: "/", component: { render: () => null } }],
  });
  router.push({ path: "/", query });
  await router.isReady();
  let list;
  const Host = defineComponent({
    setup() {
      list = useListQuery({
        endpoint: "/musicians",
        filters: FILTERS,
        defaultSort: "last_name",
        pageSize: 2,
      });
      return () => h("div");
    },
  });
  mounted.push(mount(Host, { global: { plugins: [router] } }));
  await flushPromises();
  return { list, router };
}

const mounted = [];

const page = (ids, total) => ({ items: ids.map((id) => ({ id })), total });

describe("useListQuery", () => {
  beforeEach(() => get.mockReset());
  afterEach(() => {
    // Unmounting disposes the scope, so no debounce timer fires into the next test.
    mounted.splice(0).forEach((w) => w.unmount());
    vi.useRealTimers();
  });

  it("loads the first page from the URL state", async () => {
    get.mockResolvedValue(page([1, 2], 3));
    const { list } = await setup({ register_id__in: "3" });
    expect(get).toHaveBeenCalledTimes(1);
    expect(get).toHaveBeenCalledWith(
      "/musicians?is_active=true&register_id__in=3&order_by=last_name&limit=2&offset=0",
    );
    expect(list.items.value.map((i) => i.id)).toEqual([1, 2]);
    expect(list.hasMore.value).toBe(true);
    expect(list.activeFilterCount.value).toBe(1);
  });

  it("loadMore appends and stops at total", async () => {
    get.mockResolvedValueOnce(page([1, 2], 3)).mockResolvedValueOnce(page([3], 3));
    const { list } = await setup();
    await list.loadMore();
    expect(get).toHaveBeenLastCalledWith(
      "/musicians?is_active=true&order_by=last_name&limit=2&offset=2",
    );
    expect(list.items.value.map((i) => i.id)).toEqual([1, 2, 3]);
    expect(list.hasMore.value).toBe(false);
    await list.loadMore();
    expect(get).toHaveBeenCalledTimes(2);
  });

  it("a filter change resets the list and writes the URL without a second request", async () => {
    get.mockResolvedValue(page([1, 2], 3));
    const { list, router } = await setup();
    list.setFilter("is_active", false);
    await flushPromises();
    expect(router.currentRoute.value.query).toEqual({ is_active: "false" });
    expect(get).toHaveBeenCalledTimes(2);
    expect(get).toHaveBeenLastCalledWith(
      "/musicians?is_active=false&order_by=last_name&limit=2&offset=0",
    );
  });

  it("setFilter coerces raw values to the filter type", async () => {
    get.mockResolvedValue(page([], 0));
    const { list } = await setup();
    list.setFilter("currency_id", "4");
    list.setFilter("register_id__in", ["2"]);
    expect(list.state.currency_id).toBe(4);
    list.setFilter("currency_id", "");
    expect(list.state.currency_id).toBe(null);
  });

  it("debounces search", async () => {
    get.mockResolvedValue(page([], 0));
    const { list } = await setup();
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
    list.state.search = "Ma";
    await nextTick();
    list.state.search = "Mai";
    await nextTick();
    await vi.advanceTimersByTimeAsync(299);
    expect(get).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(1);
    await flushPromises();
    expect(get).toHaveBeenCalledTimes(2);
    expect(get).toHaveBeenLastCalledWith(
      "/musicians?search=Mai&is_active=true&order_by=last_name&limit=2&offset=0",
    );
  });

  it("drops a stale response", async () => {
    get.mockResolvedValueOnce(page([1], 1));
    const { list } = await setup();
    let resolveSlow;
    get
      .mockImplementationOnce(() => new Promise((r) => (resolveSlow = r)))
      .mockResolvedValueOnce(page([9], 1));
    list.setFilter("is_active", false);
    await nextTick();
    list.setFilter("is_active", null);
    await flushPromises();
    resolveSlow(page([7], 1));
    await flushPromises();
    expect(list.items.value.map((i) => i.id)).toEqual([9]);
    expect(list.loading.value).toBe(false);
  });

  it("applies external URL changes (back button)", async () => {
    get.mockResolvedValue(page([], 0));
    const { list, router } = await setup();
    await router.replace({ query: { is_active: "false", order_by: "-last_name" } });
    await flushPromises();
    expect(list.state.is_active).toBe(false);
    expect(list.sort.value).toBe("-last_name");
    expect(get).toHaveBeenCalledTimes(2);
  });

  it("resetFilters restores defaults and clears the URL", async () => {
    get.mockResolvedValue(page([], 0));
    const { list, router } = await setup({ is_active: "alle", search: "x" });
    list.resetFilters();
    await flushPromises();
    expect(list.state).toMatchObject({ search: "", is_active: true, register_id__in: [] });
    expect(router.currentRoute.value.query).toEqual({});
  });

  it("keeps loaded items when loading more fails", async () => {
    get.mockResolvedValueOnce(page([1, 2], 3)).mockRejectedValueOnce(new Error("Netz weg"));
    const { list } = await setup();
    await list.loadMore();
    expect(list.error.value).toBe("Netz weg");
    expect(list.items.value).toHaveLength(2);
  });

  it("a failed first load clears items and reports the error", async () => {
    get.mockRejectedValueOnce(new Error("Server nicht erreichbar"));
    const { list } = await setup();
    expect(list.error.value).toBe("Server nicht erreichbar");
    expect(list.items.value).toEqual([]);
    expect(list.loading.value).toBe(false);
  });
});
```

Zu „debounces search“: Die Suche wird in der Parameter-Reihenfolge der Filterdefinition gesendet, `search` also zuerst.

`tests/frontend/InfiniteLoader.test.js`:

```js
import { describe, it, expect, vi, afterEach } from "vitest";
import { mount } from "@vue/test-utils";
import { nextTick } from "vue";
import InfiniteLoader from "../../src/frontend/src/components/InfiniteLoader.vue";

afterEach(() => vi.unstubAllGlobals());

describe("InfiniteLoader", () => {
  it("shows the count and a fallback button", async () => {
    const w = mount(InfiniteLoader, { props: { hasMore: true, count: 50, total: 157 } });
    expect(w.text()).toContain("50 von 157");
    await w.find("button").trigger("click");
    expect(w.emitted("load-more")).toHaveLength(1);
  });

  it("shows loading and hides the button", () => {
    const w = mount(InfiniteLoader, {
      props: { hasMore: true, loading: true, count: 50, total: 157 },
    });
    expect(w.text()).toContain("Wird geladen …");
    expect(w.find("button").exists()).toBe(false);
  });

  it("shows an error with retry", async () => {
    const w = mount(InfiniteLoader, {
      props: { hasMore: true, error: "Netz weg", count: 50, total: 157 },
    });
    expect(w.find('[role="alert"]').text()).toContain("Netz weg");
    await w.find("button").trigger("click");
    expect(w.emitted("load-more")).toHaveLength(1);
  });

  it("emits when the sentinel becomes visible, and again after loading if still visible", async () => {
    let callback;
    vi.stubGlobal(
      "IntersectionObserver",
      class {
        constructor(cb) {
          callback = cb;
        }
        observe() {}
        disconnect() {}
      },
    );
    const w = mount(InfiniteLoader, { props: { hasMore: true, count: 2, total: 9 } });
    callback([{ isIntersecting: true }]);
    expect(w.emitted("load-more")).toHaveLength(1);
    await w.setProps({ loading: true });
    await w.setProps({ loading: false });
    await nextTick();
    expect(w.emitted("load-more")).toHaveLength(2);
  });

  it("renders nothing but the sentinel for an empty list", () => {
    const w = mount(InfiniteLoader, { props: { hasMore: false, count: 0, total: 0 } });
    expect(w.text()).toBe("");
  });
});
```

- [ ] **Step 2: Tests laufen lassen, sie müssen scheitern**

Run: `IN_CONTAINER 'cd src/frontend && npx vitest run useListQuery InfiniteLoader api'`
Expected: FAIL (Module fehlen, `getAll` fehlt).

- [ ] **Step 3: `getAll` in `src/frontend/src/lib/api.js`**

Nach der Definition von `get` (die Datei lesen und das bestehende Export-Muster übernehmen):

```js
/**
 * Every item of a paginated list endpoint ({items, total}), fetched page by page.
 * Use for pickers and histories that must not be cut off.
 */
export async function getAll(path, pageSize = 200) {
  const sep = path.includes("?") ? "&" : "?";
  const all = [];
  for (;;) {
    const page = await get(`${path}${sep}limit=${pageSize}&offset=${all.length}`);
    all.push(...page.items);
    if (!page.items.length || all.length >= page.total) return all;
  }
}
```

- [ ] **Step 4: `src/frontend/src/composables/useListQuery.js`**

```js
/**
 * State of a filterable, sortable list that loads more rows while scrolling.
 *
 * The filter state lives in the URL (same names as the API parameters), so the
 * back button and shared links restore it. Defaults are left out of the URL; a
 * cleared non-empty default is written as "alle" so it survives a reload.
 */
import { computed, onScopeDispose, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { get } from "../lib/api.js";

const ALL = "alle";

function emptyOf(type) {
  if (type === "list") return [];
  if (type === "bool" || type === "number") return null;
  return "";
}

function isEmpty(value) {
  return value === null || value === "" || (Array.isArray(value) && value.length === 0);
}

function same(a, b) {
  return JSON.stringify(a) === JSON.stringify(b);
}

function clone(value) {
  return Array.isArray(value) ? [...value] : value;
}

function coerce(type, raw) {
  if (type === "list") {
    if (Array.isArray(raw)) return raw.map(String);
    return raw == null || raw === "" ? [] : String(raw).split(",").filter(Boolean);
  }
  if (type === "bool") {
    if (raw === true || raw === "true") return true;
    if (raw === false || raw === "false") return false;
    return null;
  }
  if (type === "number") {
    if (raw === null || raw === undefined || raw === "") return null;
    const n = Number(raw);
    return Number.isFinite(n) ? n : null;
  }
  return raw == null ? "" : String(raw);
}

function parseFromQuery(def, raw) {
  if (raw === ALL) return emptyOf(def.type);
  const value = coerce(def.type, raw);
  // An unparsable bool/number in the URL falls back to the default.
  if ((def.type === "bool" || def.type === "number") && value === null) return clone(def.default);
  return value;
}

function serialize(value) {
  return Array.isArray(value) ? value.join(",") : String(value);
}

/** Filter state from a route query. */
export function readState(filters, query) {
  const state = {};
  for (const [key, def] of Object.entries(filters)) {
    const raw = query[key];
    state[key] = raw === undefined ? clone(def.default) : parseFromQuery(def, raw);
  }
  return state;
}

/** Route query for a filter state and sort (defaults omitted). */
export function writeQuery(filters, state, sort, defaultSort) {
  const query = {};
  for (const [key, def] of Object.entries(filters)) {
    const value = state[key];
    if (same(value, def.default)) continue;
    query[key] = isEmpty(value) ? ALL : serialize(value);
  }
  if (sort && sort !== defaultSort) query.order_by = sort;
  return query;
}

/** URLSearchParams for the API request. */
export function buildParams(filters, state, { sort, base = {}, offset = 0, limit = 50 }) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(base)) {
    if (!isEmpty(value)) params.set(key, serialize(value));
  }
  for (const key of Object.keys(filters)) {
    let value = state[key];
    if (typeof value === "string") value = value.trim();
    if (!isEmpty(value)) params.set(key, serialize(value));
  }
  if (sort) params.set("order_by", sort);
  params.set("limit", String(limit));
  params.set("offset", String(offset));
  return params;
}

function queryKey(query) {
  return JSON.stringify(
    Object.keys(query)
      .sort()
      .map((k) => [k, String(query[k])]),
  );
}

export function useListQuery({
  endpoint,
  filters,
  defaultSort = "",
  pageSize = 50,
  baseParams = () => ({}),
  mapItem = (x) => x,
  debounceMs = 300,
}) {
  const route = useRoute();
  const router = useRouter();

  const defaults = Object.fromEntries(
    Object.entries(filters).map(([k, def]) => [k, clone(def.default)]),
  );
  const debouncedKeys = Object.keys(filters).filter((k) => filters[k].debounce);
  const immediateKeys = Object.keys(filters).filter((k) => !filters[k].debounce);

  const state = reactive(readState(filters, route.query));
  const sort = ref(typeof route.query.order_by === "string" ? route.query.order_by : defaultSort);
  const items = ref([]);
  const total = ref(0);
  const lastResponse = ref(null);
  const loading = ref(false);
  const loadingMore = ref(false);
  const error = ref("");
  const hasMore = computed(() => items.value.length < total.value);
  const activeFilterCount = computed(
    () => Object.keys(filters).filter((k) => k !== "search" && !same(state[k], defaults[k])).length,
  );

  let seq = 0;
  // Queries this list wrote itself; their arrival in the route is not an
  // external change (a quick second change may already be pending).
  const ownQueries = new Set();

  async function fetchPage(append) {
    const my = ++seq;
    if (append) loadingMore.value = true;
    else loading.value = true;
    error.value = "";
    try {
      const params = buildParams(filters, state, {
        sort: sort.value,
        base: baseParams(),
        offset: append ? items.value.length : 0,
        limit: pageSize,
      });
      const data = await get(`${endpoint}?${params}`);
      if (my !== seq) return;
      const mapped = data.items.map(mapItem);
      items.value = append ? [...items.value, ...mapped] : mapped;
      total.value = data.total;
      lastResponse.value = data;
    } catch (e) {
      if (my !== seq) return;
      error.value = e?.message || "Laden fehlgeschlagen.";
      if (!append) {
        items.value = [];
        total.value = 0;
      }
    } finally {
      if (my === seq) {
        loading.value = false;
        loadingMore.value = false;
      }
    }
  }

  function reload() {
    return fetchPage(false);
  }

  function loadMore() {
    if (loading.value || loadingMore.value || !hasMore.value) return Promise.resolve();
    return fetchPage(true);
  }

  function pushUrl() {
    const foreign = Object.fromEntries(
      Object.entries(route.query).filter(([k]) => !(k in filters) && k !== "order_by"),
    );
    const next = { ...foreign, ...writeQuery(filters, state, sort.value, defaultSort) };
    const key = queryKey(next);
    if (key === queryKey(route.query)) return;
    ownQueries.add(key);
    router.replace({ query: next });
  }

  function onChange() {
    pushUrl();
    reload();
  }

  const snapshot = (keys) => JSON.stringify(keys.map((k) => state[k]));

  let timer = null;
  watch(
    () => snapshot(debouncedKeys),
    () => {
      clearTimeout(timer);
      timer = setTimeout(onChange, debounceMs);
    },
  );
  watch(() => snapshot(immediateKeys) + "|" + sort.value, onChange);
  watch(() => JSON.stringify(baseParams()), reload);

  // Back/forward or a link: adopt the URL. Our own replace() is skipped.
  watch(
    () => route.query,
    (query) => {
      const key = queryKey(query);
      if (ownQueries.has(key)) {
        ownQueries.delete(key);
        return;
      }
      Object.assign(state, readState(filters, query));
      sort.value = typeof query.order_by === "string" ? query.order_by : defaultSort;
    },
  );

  onScopeDispose(() => clearTimeout(timer));

  function setFilter(key, raw) {
    state[key] = coerce(filters[key].type, raw);
  }

  function setSort(value) {
    sort.value = value || defaultSort;
  }

  function resetFilters() {
    Object.assign(state, readState(filters, {}));
    sort.value = defaultSort;
  }

  reload();

  return {
    state,
    sort,
    setSort,
    setFilter,
    defaults,
    activeFilterCount,
    items,
    total,
    lastResponse,
    loading,
    loadingMore,
    error,
    hasMore,
    loadMore,
    reload,
    resetFilters,
  };
}
```

Anmerkungen:
- Die Route-Watch überspringt Queries, die `pushUrl` selbst geschrieben hat (`ownQueries`). Dadurch überschreibt eine verspätet ankommende eigene Navigation keine inzwischen neuere Filterwahl (Test „drops a stale response“). Eine Änderung von außen (Zurück-Taste) wird übernommen; die Watches laden dann neu, und `pushUrl` schreibt nichts, weil die URL schon passt.
- Bei `resetFilters()` ändern sich die Suche (verzögert) und die übrigen Filter (sofort). Die sofortige Watch lädt neu. Nach 300 ms feuert die verzögerte Watch und lädt ein zweites Mal mit demselben Zustand. Das ist harmlos, und der Test prüft die Anzahl hier nicht.

- [ ] **Step 5: `src/frontend/src/components/InfiniteLoader.vue`**

```vue
<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from "vue";

const props = defineProps({
  hasMore: Boolean,
  loading: Boolean,
  error: { type: String, default: "" },
  count: { type: Number, default: 0 },
  total: { type: Number, default: 0 },
});
const emit = defineEmits(["load-more"]);

const el = ref(null);
let observer = null;
let visible = false;

function maybeLoad() {
  if (visible && props.hasMore && !props.loading && !props.error) emit("load-more");
}

onMounted(() => {
  if (typeof IntersectionObserver === "undefined") return;
  observer = new IntersectionObserver(
    (entries) => {
      visible = entries.some((e) => e.isIntersecting);
      maybeLoad();
    },
    { rootMargin: "400px 0px" },
  );
  observer.observe(el.value);
});

onBeforeUnmount(() => observer?.disconnect());

// After a page arrives the sentinel may still be on screen (tall window).
watch(() => [props.loading, props.hasMore], maybeLoad, { flush: "post" });
</script>

<template>
  <div ref="el" class="infinite-loader" aria-live="polite">
    <p v-if="error" class="form-error" role="alert">
      {{ error }}
      <button type="button" class="btn-sm" @click="$emit('load-more')">Erneut versuchen</button>
    </p>
    <p v-else-if="loading" class="text-muted">Wird geladen …</p>
    <template v-else-if="total > 0">
      <p class="text-muted infinite-count">{{ count }} von {{ total }}</p>
      <button v-if="hasMore" type="button" class="btn-sm" @click="$emit('load-more')">
        Weitere laden
      </button>
    </template>
  </div>
</template>

<style scoped>
.infinite-loader {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2);
  min-height: 1px;
  padding: var(--space-4) 0;
}

.infinite-loader p {
  margin: 0;
}

.infinite-count {
  font-variant-numeric: tabular-nums;
}

.infinite-loader .btn-sm {
  min-height: 44px;
}
</style>
```

- [ ] **Step 6: Behebung bei den Scan-Projekten**

- `ScanProjectListPage.vue`:
  - Import um `getAll` ergänzen (`import { get, post, del, getAll } from "../lib/api.js";`, bestehende Namen übernehmen).
  - In `fetchProjects` ersetzen:
    ```js
        projects.value = await getAll("/scanner/projects");
    ```
    statt `const data = await get("/scanner/projects"); projects.value = data.items;`.
- `ScanProjectDetailPage.vue`, in `fetchAllProjects`:
  ```js
      allProjects.value = sortProjects(await getAll("/scanner/projects"));
  ```
  und `getAll` importieren.
- Wird `get` danach in einer Datei nicht mehr verwendet, den Import entfernen, sonst meckert eslint.

- [ ] **Step 7: Tests laufen lassen, sie müssen bestehen**

Run: `IN_CONTAINER 'cd src/frontend && npx vitest run'`
Expected: alle PASS, nur `App.test.js` scheitert wie bekannt.

- [ ] **Step 8: Commit**

Dateien: `lib/api.js`, `composables/useListQuery.js`, `components/InfiniteLoader.vue`, `pages/ScanProjectListPage.vue`, `pages/ScanProjectDetailPage.vue`, `tests/frontend/api.test.js`, `tests/frontend/useListQuery.test.js`, `tests/frontend/InfiniteLoader.test.js`. Message: `feat(frontend): list query composable, infinite loader and getAll`.

---

### Task 3: `FilterBar`, `SortSelect`, sortierbare `DataTable`

**Files:**
- Create: `src/frontend/src/components/FilterBar.vue`
- Create: `src/frontend/src/components/SortSelect.vue`
- Modify: `src/frontend/src/components/DataTable.vue`
- Test: `tests/frontend/FilterBar.test.js`, `tests/frontend/SortSelect.test.js`, `tests/frontend/DataTable.test.js` (alle neu)

**Interfaces:**
- **`<FilterBar :defs :state :defaults @change="(key, raw) => …" @reset />`**
  - `defs` ist ein Array aus Einträgen `{ key, label, type, options?, placeholder? }` oder, bei Bereichen, `{ keys: [von, bis], label, type: "range"|"daterange" }`.
  - `type` ist einer von `segmented | select | multiselect | text | range | daterange | toggle`.
  - `options` hat die Form `[{ value, label }]`. Bei `select` und `multiselect` sind die Werte Strings, bei `segmented` beliebig (`true`/`false`/`null`/String).
  - `change` liefert Rohwerte; die Seite reicht sie an `list.setFilter` weiter.
- **`<SortSelect :options="[{key,label}]" v-model="sort" />`**
- **`<DataTable … :sort="sort" empty-text="…" @update:sort="…" />`:** Spalten mit `sortKey` sind sortierbar.

- [ ] **Step 1: Failing tests**

`tests/frontend/FilterBar.test.js`:

```js
import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import FilterBar from "../../src/frontend/src/components/FilterBar.vue";

const defs = [
  {
    key: "is_active",
    label: "Status",
    type: "segmented",
    options: [
      { value: true, label: "Aktiv" },
      { value: false, label: "Inaktiv" },
      { value: null, label: "Alle" },
    ],
  },
  {
    key: "register_id__in",
    label: "Register",
    type: "multiselect",
    options: [
      { value: "1", label: "Flöte" },
      { value: "2", label: "Tuba" },
    ],
  },
  { key: "owner", label: "Eigentümer", type: "select", options: [{ value: "MV", label: "MV" }] },
  { keys: ["y__gte", "y__lte"], label: "Baujahr", type: "range" },
  { key: "without_category", label: "Ohne Kategorie", type: "toggle" },
];
const defaults = {
  is_active: true,
  register_id__in: [],
  owner: "",
  y__gte: null,
  y__lte: null,
  without_category: null,
};

function mountBar(state) {
  return mount(FilterBar, { props: { defs, defaults, state: { ...defaults, ...state } } });
}

describe("FilterBar", () => {
  it("shows no chips for defaults", () => {
    const w = mountBar({});
    expect(w.find(".filter-chips").exists()).toBe(false);
    expect(w.find('[aria-pressed="true"]').text()).toBe("Aktiv");
  });

  it("shows chips for non-default values, including 'Alle' against a non-empty default", () => {
    const w = mountBar({ is_active: null, register_id__in: ["2", "1"], y__gte: 1990 });
    const chips = w.findAll(".filter-chips .category-chip").map((c) => c.text());
    expect(chips).toEqual([
      "Status: Alle✕",
      "Register: Tuba, Flöte✕",
      "Baujahr: 1990–…✕",
    ]);
  });

  it("removing a chip emits the defaults of its keys", async () => {
    const w = mountBar({ y__gte: 1990, y__lte: 2000 });
    await w.find('button[aria-label="Filter „Baujahr“ entfernen"]').trigger("click");
    expect(w.emitted("change")).toEqual([
      ["y__gte", null],
      ["y__lte", null],
    ]);
  });

  it("segmented, multiselect, select, toggle and reset emit changes", async () => {
    const w = mountBar({ register_id__in: ["1"] });
    await w.findAll('[role="group"] button')[1].trigger("click");
    const boxes = w.findAll('input[type="checkbox"]');
    await boxes[1].setValue(true);
    await boxes[0].setValue(false);
    await w.find("select").setValue("MV");
    await boxes[2].setValue(true);
    await w.find('button[aria-label="Filter „Register“ entfernen"]').trigger("click");
    expect(w.emitted("change")).toEqual([
      ["is_active", false],
      ["register_id__in", ["1", "2"]],
      ["register_id__in", []],
      ["owner", "MV"],
      ["without_category", true],
      ["register_id__in", []],
    ]);
    await w.find(".filter-reset").trigger("click");
    expect(w.emitted("reset")).toHaveLength(1);
  });

  it("the phone toggle reports the active count", () => {
    const w = mountBar({ owner: "MV" });
    const toggle = w.find(".filter-toggle");
    expect(toggle.text()).toBe("Filter (1)");
    expect(toggle.attributes("aria-expanded")).toBe("false");
  });
});
```

Zum Test „segmented, multiselect …“:
- `boxes[2]` ist die Toggle-Checkbox „Ohne Kategorie“.
- Die Mehrfachauswahl emittiert immer den neuen ganzen Wert, gerechnet aus dem aktuellen Prop, das der Test nicht ändert. Deshalb liefert der erste Klick `["1","2"]` und der zweite `[]` (Abwahl von „1“ aus `["1"]`).

`tests/frontend/SortSelect.test.js`:

```js
import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import SortSelect from "../../src/frontend/src/components/SortSelect.vue";

const options = [
  { key: "number", label: "Nummer" },
  { key: "type", label: "Typ" },
];

describe("SortSelect", () => {
  it("changes the key keeping the direction and flips the direction", async () => {
    const w = mount(SortSelect, { props: { options, modelValue: "-number" } });
    await w.find("select").setValue("type");
    await w.find("button").trigger("click");
    expect(w.emitted("update:modelValue")).toEqual([["-type"], ["number"]]);
    expect(w.find("button").attributes("aria-label")).toBe(
      "Absteigend sortiert – auf aufsteigend umschalten",
    );
  });
});
```

`tests/frontend/DataTable.test.js`:

```js
import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import DataTable from "../../src/frontend/src/components/DataTable.vue";

const columns = [
  { key: "display_nr", label: "Nr.", sortKey: "number" },
  { key: "label", label: "Bezeichnung" },
  { key: "year", label: "Baujahr", sortKey: "construction_year" },
];
const rows = [{ id: 1, display_nr: "A-001", label: "Tisch", year: 1990 }];

describe("DataTable sorting", () => {
  it("marks the active column and toggles direction", async () => {
    const w = mount(DataTable, { props: { columns, rows, sort: "number" } });
    const ths = w.findAll("th");
    expect(ths[0].attributes("aria-sort")).toBe("ascending");
    expect(ths[1].attributes("aria-sort")).toBeUndefined();
    expect(ths[2].attributes("aria-sort")).toBe("none");
    await ths[0].find("button").trigger("click");
    await ths[2].find("button").trigger("click");
    expect(w.emitted("update:sort")).toEqual([["-number"], ["construction_year"]]);
  });

  it("uses the empty text", () => {
    const w = mount(DataTable, {
      props: { columns, rows: [], emptyText: "Keine Einträge für diese Filter." },
    });
    expect(w.text()).toContain("Keine Einträge für diese Filter.");
  });
});
```

- [ ] **Step 2: Tests laufen lassen, sie müssen scheitern**

Run: `IN_CONTAINER 'cd src/frontend && npx vitest run FilterBar SortSelect DataTable'`
Expected: FAIL.

- [ ] **Step 3: `SortSelect.vue`**

```vue
<script setup>
import { computed } from "vue";

const props = defineProps({
  options: { type: Array, required: true },
  modelValue: { type: String, default: "" },
});
const emit = defineEmits(["update:modelValue"]);

const id = `sort-select-${Math.random().toString(36).slice(2, 9)}`;
const key = computed(() => props.modelValue.replace(/^[-+]/, ""));
const desc = computed(() => props.modelValue.startsWith("-"));

function setKey(k) {
  emit("update:modelValue", desc.value ? `-${k}` : k);
}

function flip() {
  emit("update:modelValue", desc.value ? key.value : `-${key.value}`);
}
</script>

<template>
  <div class="sort-select">
    <label :for="id">Sortieren nach</label>
    <select :id="id" :value="key" @change="setKey($event.target.value)">
      <option v-for="o in options" :key="o.key" :value="o.key">{{ o.label }}</option>
    </select>
    <button
      type="button"
      class="btn-sm sort-dir"
      :aria-label="
        desc
          ? 'Absteigend sortiert – auf aufsteigend umschalten'
          : 'Aufsteigend sortiert – auf absteigend umschalten'
      "
      @click="flip"
    >
      <span aria-hidden="true">{{ desc ? "↓" : "↑" }}</span>
    </button>
  </div>
</template>

<style scoped>
.sort-select {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.sort-select label {
  font-size: 0.875rem;
  color: var(--color-muted);
  white-space: nowrap;
}

.sort-select select {
  width: auto;
  min-height: 44px;
}

.sort-dir {
  min-width: 44px;
  min-height: 44px;
}
</style>
```

- [ ] **Step 4: `FilterBar.vue`**

```vue
<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue";

const props = defineProps({
  defs: { type: Array, required: true },
  state: { type: Object, required: true },
  defaults: { type: Object, required: true },
});
const emit = defineEmits(["change", "reset"]);

const panelId = `filter-panel-${Math.random().toString(36).slice(2, 9)}`;
const open = ref(false);
const root = ref(null);

const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const keysOf = (def) => def.keys || [def.key];
const defKey = (def) => keysOf(def).join("+");
const isActive = (def) => keysOf(def).some((k) => !same(props.state[k], props.defaults[k]));
const activeDefs = computed(() => props.defs.filter(isActive));

function optionLabel(def, value) {
  const opt = (def.options || []).find((o) => String(o.value) === String(value));
  return opt ? opt.label : String(value);
}

function formatDate(iso) {
  const [y, m, d] = String(iso).split("-");
  return d ? `${d}.${m}.${y}` : iso;
}

function chipText(def) {
  if (def.type === "multiselect") {
    return `${def.label}: ${props.state[def.key].map((v) => optionLabel(def, v)).join(", ")}`;
  }
  if (def.type === "range" || def.type === "daterange") {
    const fmt = (v) =>
      v === null || v === "" ? "…" : def.type === "daterange" ? formatDate(v) : v;
    const [from, to] = def.keys.map((k) => props.state[k]);
    return `${def.label}: ${fmt(from)}–${fmt(to)}`;
  }
  if (def.type === "toggle") return def.label;
  if (def.type === "text") return `${def.label}: „${props.state[def.key]}“`;
  const v = props.state[def.key];
  return `${def.label}: ${v === null || v === "" ? "Alle" : optionLabel(def, v)}`;
}

function clear(def) {
  for (const k of keysOf(def)) emit("change", k, props.defaults[k]);
}

function toggleMulti(def, value, checked) {
  const current = props.state[def.key];
  emit(
    "change",
    def.key,
    checked ? [...current, value] : current.filter((v) => v !== value),
  );
}

// Close an open multiselect when clicking elsewhere.
function onDocumentClick(e) {
  for (const d of root.value?.querySelectorAll("details[open]") || []) {
    if (!d.contains(e.target)) d.removeAttribute("open");
  }
}
onMounted(() => document.addEventListener("click", onDocumentClick));
onBeforeUnmount(() => document.removeEventListener("click", onDocumentClick));
</script>

<template>
  <div ref="root" class="filter-bar">
    <button
      type="button"
      class="btn-sm filter-toggle"
      :aria-expanded="String(open)"
      :aria-controls="panelId"
      @click="open = !open"
    >
      Filter<template v-if="activeDefs.length"> ({{ activeDefs.length }})</template>
    </button>

    <div :id="panelId" class="filter-panel" :class="{ open }">
      <template v-for="def in defs" :key="defKey(def)">
        <div
          v-if="def.type === 'segmented'"
          class="view-toggle"
          role="group"
          :aria-label="def.label"
        >
          <button
            v-for="o in def.options"
            :key="String(o.value)"
            type="button"
            :class="{ active: same(state[def.key], o.value) }"
            :aria-pressed="String(same(state[def.key], o.value))"
            @click="$emit('change', def.key, o.value)"
          >
            {{ o.label }}
          </button>
        </div>

        <label v-else-if="def.type === 'select'" class="filter-field">
          <span class="filter-label">{{ def.label }}</span>
          <select
            :value="state[def.key] ?? ''"
            @change="$emit('change', def.key, $event.target.value)"
          >
            <option value="">Alle</option>
            <option v-for="o in def.options" :key="String(o.value)" :value="String(o.value)">
              {{ o.label }}
            </option>
          </select>
        </label>

        <details v-else-if="def.type === 'multiselect'" class="filter-multi">
          <summary>
            {{ def.label }}<template v-if="state[def.key].length">
              ({{ state[def.key].length }})</template
            >
          </summary>
          <fieldset>
            <legend class="sr-only">{{ def.label }}</legend>
            <label v-for="o in def.options" :key="String(o.value)" class="filter-check">
              <input
                type="checkbox"
                :checked="state[def.key].includes(String(o.value))"
                @change="toggleMulti(def, String(o.value), $event.target.checked)"
              />
              {{ o.label }}
            </label>
            <p v-if="!def.options.length" class="text-muted">Keine Einträge</p>
          </fieldset>
        </details>

        <label v-else-if="def.type === 'text'" class="filter-field">
          <span class="filter-label">{{ def.label }}</span>
          <input
            type="text"
            :value="state[def.key]"
            :placeholder="def.placeholder"
            @input="$emit('change', def.key, $event.target.value)"
          />
        </label>

        <label v-else-if="def.type === 'toggle'" class="filter-check filter-toggle-field">
          <input
            type="checkbox"
            :checked="state[def.key] === true"
            @change="$emit('change', def.key, $event.target.checked ? true : null)"
          />
          {{ def.label }}
        </label>

        <fieldset v-else-if="def.type === 'range' || def.type === 'daterange'" class="filter-range">
          <legend class="filter-label">{{ def.label }}</legend>
          <input
            :type="def.type === 'range' ? 'number' : 'date'"
            :value="state[def.keys[0]] ?? ''"
            :aria-label="`${def.label} von`"
            @change="$emit('change', def.keys[0], $event.target.value)"
          />
          <span aria-hidden="true">–</span>
          <input
            :type="def.type === 'range' ? 'number' : 'date'"
            :value="state[def.keys[1]] ?? ''"
            :aria-label="`${def.label} bis`"
            @change="$emit('change', def.keys[1], $event.target.value)"
          />
        </fieldset>
      </template>
    </div>

    <ul v-if="activeDefs.length" class="filter-chips category-chips" aria-label="Aktive Filter">
      <li v-for="def in activeDefs" :key="defKey(def)" class="category-chip">
        {{ chipText(def)
        }}<button
          type="button"
          class="filter-chip-remove"
          :aria-label="`Filter „${def.label}“ entfernen`"
          @click="clear(def)"
        >
          ✕
        </button>
      </li>
      <li>
        <button type="button" class="btn-sm filter-reset" @click="$emit('reset')">
          Filter zurücksetzen
        </button>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.filter-bar {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  margin-bottom: var(--space-4);
}

.filter-toggle {
  display: none;
  align-self: flex-start;
  min-height: 44px;
}

.filter-panel {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: var(--space-3);
}

.filter-field,
.filter-range {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  margin: 0;
  padding: 0;
  border: none;
}

.filter-range {
  flex-direction: row;
  flex-wrap: wrap;
  align-items: center;
}

.filter-range legend {
  width: 100%;
  padding: 0;
}

.filter-range input {
  width: 8rem;
}

.filter-label {
  font-size: 0.75rem;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  color: var(--color-muted);
}

.filter-field select,
.filter-field input {
  width: auto;
  min-width: 10rem;
  min-height: 44px;
}

.filter-multi {
  position: relative;
}

.filter-multi summary {
  display: flex;
  align-items: center;
  min-height: 44px;
  padding: 0 var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  background: var(--color-bg);
  cursor: pointer;
  list-style: none;
}

.filter-multi summary::-webkit-details-marker {
  display: none;
}

.filter-multi summary::after {
  content: "▾";
  margin-left: var(--space-2);
  color: var(--color-muted);
}

.filter-multi fieldset {
  position: absolute;
  z-index: 20;
  min-width: 14rem;
  max-height: 18rem;
  overflow-y: auto;
  margin: var(--space-1) 0 0;
  padding: var(--space-1) 0;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  background: var(--color-bg);
  box-shadow: var(--shadow-float);
}

.filter-check {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-height: 44px;
  padding: 0 var(--space-3);
  cursor: pointer;
}

.filter-check input {
  width: auto;
}

.filter-toggle-field {
  padding: 0;
}

.filter-chips {
  align-items: center;
}

.filter-chip-remove {
  position: relative;
  padding: 0;
  border: none;
  background: transparent;
  color: inherit;
  cursor: pointer;
  width: 1.25rem;
  height: 1.25rem;
}

.filter-chip-remove::after {
  content: "";
  position: absolute;
  top: 50%;
  left: 50%;
  width: 44px;
  height: 44px;
  transform: translate(-50%, -50%);
}

@media (max-width: 640px) {
  .filter-toggle {
    display: inline-flex;
    align-items: center;
  }

  .filter-panel:not(.open) {
    display: none;
  }

  .filter-panel {
    flex-direction: column;
    align-items: stretch;
  }

  .filter-field select,
  .filter-field input {
    width: 100%;
  }

  .filter-multi fieldset {
    position: static;
    box-shadow: none;
  }
}
</style>
```

`.view-toggle`, `.category-chips`, `.category-chip`, `.sr-only`, `.text-muted` und `.btn-sm` sind global in `style.css` definiert.

- [ ] **Step 5: `DataTable.vue` erweitern**

Script:
- Import `SortSelect` und `computed`.
- Props ergänzen: `sort: { type: String, default: "" }` und `emptyText: { type: String, default: "Keine Einträge" }`.
- `defineEmits(["row-click", "update:sort"])`, der Rückgabewert als `emit`.
- Dazu:
  ```js
  const sortKeyOf = (s) => s.replace(/^[-+]/, "");
  const sortOptions = computed(() =>
    props.columns.filter((c) => c.sortKey).map((c) => ({ key: c.sortKey, label: c.label })),
  );
  function ariaSort(col) {
    if (!col.sortKey) return undefined;
    if (sortKeyOf(props.sort) !== col.sortKey) return "none";
    return props.sort.startsWith("-") ? "descending" : "ascending";
  }
  function toggleSort(col) {
    const active = sortKeyOf(props.sort) === col.sortKey;
    emit("update:sort", active && !props.sort.startsWith("-") ? `-${col.sortKey}` : col.sortKey);
  }
  ```

Template:
- **Kartenansicht:** als erstes Kind in `.dt-cards` einfügen:
  ```vue
      <SortSelect
        v-if="sortOptions.length"
        class="dt-sort"
        :options="sortOptions"
        :model-value="sort"
        @update:model-value="emit('update:sort', $event)"
      />
  ```
- **Tabellenkopf:**
  ```vue
          <th
            v-for="col in columns"
            :key="col.key"
            :class="col.class"
            :aria-sort="ariaSort(col)"
          >
            <button v-if="col.sortKey" type="button" class="th-sort" @click="toggleSort(col)">
              {{ col.label
              }}<span v-if="ariaSort(col) !== 'none'" aria-hidden="true" class="th-sort-arrow">{{
                ariaSort(col) === "descending" ? "▼" : "▲"
              }}</span>
            </button>
            <template v-else>{{ col.label }}</template>
          </th>
  ```
- **Leertext:** Beide Stellen mit „Keine Einträge“ werden `{{ emptyText }}`.

Styles ergänzen:

```css
.th-sort {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  min-height: 44px;
  padding: 0;
  border: none;
  background: transparent;
  color: inherit;
  font: inherit;
  font-weight: inherit;
  cursor: pointer;
}

.th-sort:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}

.th-sort-arrow {
  font-size: 0.7em;
  color: var(--color-muted);
}

.dt-sort {
  align-self: flex-end;
}
```

- [ ] **Step 6: Tests laufen lassen, sie müssen bestehen**

Run: `IN_CONTAINER 'cd src/frontend && npx vitest run'`
Expected: alle PASS (außer `App.test.js`).

- [ ] **Step 7: Commit**

Dateien: `FilterBar.vue`, `SortSelect.vue`, `DataTable.vue`, 3 Testdateien. Message: `feat(frontend): filter bar, sort select and sortable table headers`.

---

### Task 4: `RemotePicker` und `lib/pickers.js`

**Files:**
- Create: `src/frontend/src/components/RemotePicker.vue`
- Create: `src/frontend/src/lib/pickers.js`
- Test: `tests/frontend/RemotePicker.test.js`, `tests/frontend/pickers.test.js`

**Interfaces:**
- **`<RemotePicker v-model="id" :fetch-options="fn" label="Musiker" placeholder="…" :selected-label="text" @select="opt => …" />`**
  - `fn(text)` liefert ein Promise auf `[{ id, label, description? }]`.
  - `selectedLabel`: der anzuzeigende Text, wenn `modelValue` von außen gesetzt ist (etwa aus der URL) und nichts gewählt wurde.
- **`fetchMusicianOptions(text, { activeOnly = true } = {})`:** höchstens 20 Treffer.
- **`fetchLoanableItemOptions(text)`:** drei Anfragen, je 7 Treffer, nur verfügbare Items.

- [ ] **Step 1: Failing tests**

`tests/frontend/RemotePicker.test.js`:

```js
import { describe, it, expect, vi, afterEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import RemotePicker from "../../src/frontend/src/components/RemotePicker.vue";

const OPTIONS = [
  { id: 1, label: "Maier Anna", description: "" },
  { id: 2, label: "Huber Carl", description: "extern" },
];

function setup(props = {}) {
  let w;
  const fetchOptions = props.fetchOptions || vi.fn().mockResolvedValue(OPTIONS);
  w = mount(RemotePicker, {
    props: {
      label: "Musiker",
      modelValue: null,
      fetchOptions,
      debounceMs: 0,
      "onUpdate:modelValue": (v) => w.setProps({ modelValue: v }),
      ...props,
    },
    attachTo: document.body,
  });
  return { w, fetchOptions };
}

const tick = () => new Promise((r) => setTimeout(r, 0));

afterEach(() => (document.body.innerHTML = ""));

describe("RemotePicker", () => {
  it("fetches on focus and shows options", async () => {
    const { w, fetchOptions } = setup();
    await w.find("input").trigger("focus");
    await tick();
    await flushPromises();
    expect(fetchOptions).toHaveBeenCalledWith("");
    expect(w.findAll('[role="option"]').map((o) => o.text())).toEqual([
      "Maier Anna",
      "Huber Carlextern",
    ]);
  });

  it("debounces typing and passes the trimmed text", async () => {
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
    const fetchOptions = vi.fn().mockResolvedValue(OPTIONS);
    const { w } = setup({ fetchOptions, debounceMs: 250 });
    const input = w.find("input");
    await input.setValue("Ma");
    await input.setValue("Mai ");
    await vi.advanceTimersByTimeAsync(249);
    expect(fetchOptions).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(1);
    expect(fetchOptions).toHaveBeenCalledTimes(1);
    expect(fetchOptions).toHaveBeenCalledWith("Mai");
    vi.useRealTimers();
  });

  it("selects with keyboard and shows the label", async () => {
    const { w } = setup();
    const input = w.find("input");
    await input.trigger("focus");
    await tick();
    await flushPromises();
    await input.trigger("keydown", { key: "ArrowDown" });
    await input.trigger("keydown", { key: "ArrowDown" });
    await input.trigger("keydown", { key: "Enter" });
    expect(w.emitted("update:modelValue").at(-1)).toEqual([2]);
    expect(w.emitted("select").at(-1)[0]).toMatchObject({ id: 2 });
    expect(input.element.value).toBe("Huber Carl");
    expect(input.attributes("aria-expanded")).toBe("false");
  });

  it("typing after a selection clears it; the clear button empties", async () => {
    const { w } = setup();
    const input = w.find("input");
    await input.trigger("focus");
    await tick();
    await flushPromises();
    await w.findAll('[role="option"]')[0].trigger("click");
    await w.find('button[aria-label="Auswahl entfernen"]').trigger("click");
    expect(w.emitted("update:modelValue").at(-1)).toEqual([null]);
    expect(input.element.value).toBe("");
  });

  it("shows 'Keine Treffer' and errors", async () => {
    const empty = setup({ fetchOptions: vi.fn().mockResolvedValue([]) });
    await empty.w.find("input").setValue("zzz");
    await tick();
    await flushPromises();
    expect(empty.w.text()).toContain("Keine Treffer");

    const failing = setup({ fetchOptions: vi.fn().mockRejectedValue(new Error("Netz weg")) });
    await failing.w.find("input").setValue("a");
    await tick();
    await flushPromises();
    expect(failing.w.find('[role="alert"]').text()).toBe("Netz weg");
  });

  it("shows selectedLabel for an externally set value and clears on null", async () => {
    const { w } = setup({ modelValue: 5, selectedLabel: "Aigner Dora" });
    expect(w.find("input").element.value).toBe("Aigner Dora");
    await w.setProps({ modelValue: null });
    expect(w.find("input").element.value).toBe("");
  });
});
```

`tests/frontend/pickers.test.js`:

```js
import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("../../src/frontend/src/lib/api.js", () => ({ get: vi.fn() }));
import { get } from "../../src/frontend/src/lib/api.js";
import {
  fetchMusicianOptions,
  fetchLoanableItemOptions,
} from "../../src/frontend/src/lib/pickers.js";

beforeEach(() => get.mockReset());

describe("pickers", () => {
  it("musician options: active only, max 20, search optional", async () => {
    get.mockResolvedValue({
      items: [{ id: 3, first_name: "Anna", last_name: "Maier", is_extern: true }],
      total: 1,
    });
    const opts = await fetchMusicianOptions("mai");
    expect(get).toHaveBeenCalledWith("/musicians?is_active=true&limit=20&search=mai");
    expect(opts).toEqual([{ id: 3, label: "Maier Anna", description: "extern" }]);
    await fetchMusicianOptions("", { activeOnly: false });
    expect(get).toHaveBeenLastCalledWith("/musicians?limit=20");
  });

  it("loanable items: three categories, available only, labelled", async () => {
    get.mockImplementation(async (path) => ({
      items: path.includes("instrument")
        ? [{ id: 1, display_nr: "TU-002", label: "Tuba", category: "instrument" }]
        : [],
      total: 0,
    }));
    const opts = await fetchLoanableItemOptions("tu");
    expect(get.mock.calls.map((c) => c[0])).toEqual([
      "/items?category=instrument&status=verfuegbar&limit=7&search=tu",
      "/items?category=clothing&status=verfuegbar&limit=7&search=tu",
      "/items?category=general_item&status=verfuegbar&limit=7&search=tu",
    ]);
    expect(opts).toEqual([{ id: 1, label: "TU-002 Tuba", description: "Instrument" }]);
  });
});
```

- [ ] **Step 2: Tests laufen lassen, sie müssen scheitern**

Run: `IN_CONTAINER 'cd src/frontend && npx vitest run RemotePicker pickers'`
Expected: FAIL.

- [ ] **Step 3: `lib/pickers.js`**

```js
/** Option loaders for RemotePicker (search-as-you-type selects). */
import { get } from "./api.js";
import { CATEGORIES } from "./categories.js";

export async function fetchMusicianOptions(text, { activeOnly = true } = {}) {
  const params = new URLSearchParams();
  if (activeOnly) params.set("is_active", "true");
  params.set("limit", "20");
  if (text) params.set("search", text);
  const page = await get(`/musicians?${params}`);
  return page.items.map((m) => ({
    id: m.id,
    label: `${m.last_name} ${m.first_name}`,
    description: m.is_extern ? "extern" : "",
  }));
}

const LOANABLE = ["instrument", "clothing", "general_item"];

export async function fetchLoanableItemOptions(text) {
  const pages = await Promise.all(
    LOANABLE.map((category) => {
      const params = new URLSearchParams({ category, status: "verfuegbar", limit: "7" });
      if (text) params.set("search", text);
      return get(`/items?${params}`);
    }),
  );
  return pages
    .flatMap((p) => p.items)
    .map((i) => ({
      id: i.id,
      label: `${i.display_nr} ${i.label}`,
      description: CATEGORIES[i.category]?.labelSingular || "",
    }));
}
```

- [ ] **Step 4: `RemotePicker.vue`**

```vue
<script setup>
import { computed, onBeforeUnmount, ref, watch } from "vue";

const props = defineProps({
  modelValue: { type: Number, default: null },
  fetchOptions: { type: Function, required: true },
  label: { type: String, required: true },
  placeholder: { type: String, default: "Suchen …" },
  selectedLabel: { type: String, default: "" },
  debounceMs: { type: Number, default: 250 },
});
const emit = defineEmits(["update:modelValue", "select"]);

const baseId = `remote-picker-${Math.random().toString(36).slice(2, 9)}`;
const query = ref(props.modelValue != null ? props.selectedLabel : "");
const options = ref([]);
const open = ref(false);
const activeIndex = ref(-1);
const loading = ref(false);
const error = ref("");
const selected = ref(null);
let timer = null;
let seq = 0;

watch(
  () => [props.modelValue, props.selectedLabel],
  ([value, label]) => {
    if (value == null) {
      selected.value = null;
      query.value = "";
    } else if (!selected.value || selected.value.id !== value) {
      selected.value = null;
      query.value = label || "";
    }
  },
);

async function search(text) {
  const my = ++seq;
  loading.value = true;
  error.value = "";
  try {
    const result = await props.fetchOptions(text.trim());
    if (my !== seq) return;
    options.value = result;
    activeIndex.value = -1;
  } catch (e) {
    if (my !== seq) return;
    options.value = [];
    error.value = e?.message || "Suche fehlgeschlagen.";
  } finally {
    if (my === seq) loading.value = false;
  }
}

function schedule() {
  clearTimeout(timer);
  timer = setTimeout(() => search(query.value), props.debounceMs);
}

function onFocus() {
  open.value = true;
  if (!selected.value && props.modelValue == null) schedule();
}

function onInput() {
  open.value = true;
  if (selected.value || props.modelValue != null) {
    selected.value = null;
    emit("update:modelValue", null);
  }
  schedule();
}

function choose(option) {
  selected.value = option;
  query.value = option.label;
  open.value = false;
  activeIndex.value = -1;
  emit("update:modelValue", option.id);
  emit("select", option);
}

function clear() {
  selected.value = null;
  query.value = "";
  options.value = [];
  emit("update:modelValue", null);
}

function onKeydown(e) {
  const count = options.value.length;
  if (e.key === "ArrowDown") {
    e.preventDefault();
    open.value = true;
    if (count) activeIndex.value = Math.min(count - 1, activeIndex.value + 1);
    else schedule();
  } else if (e.key === "ArrowUp") {
    e.preventDefault();
    if (count) activeIndex.value = Math.max(0, activeIndex.value - 1);
  } else if (e.key === "Enter") {
    if (open.value && activeIndex.value >= 0 && options.value[activeIndex.value]) {
      e.preventDefault();
      choose(options.value[activeIndex.value]);
    }
  } else if (e.key === "Escape" && open.value) {
    e.preventDefault();
    e.stopPropagation();
    open.value = false;
  }
}

function onFocusOut(e) {
  if (e.currentTarget.contains(e.relatedTarget)) return;
  open.value = false;
  activeIndex.value = -1;
  if (!selected.value && props.modelValue == null) query.value = "";
}

onBeforeUnmount(() => clearTimeout(timer));

const expanded = computed(
  () =>
    open.value &&
    (loading.value || !!error.value || options.value.length > 0 || query.value.trim() !== ""),
);
const showClear = computed(() => props.modelValue != null);
</script>

<template>
  <div class="remote-picker" @focusout="onFocusOut">
    <label :for="`${baseId}-input`">{{ label }}</label>
    <div class="remote-picker-control">
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
        :aria-busy="loading ? 'true' : undefined"
        :placeholder="placeholder"
        @focus="onFocus"
        @input="onInput"
        @keydown="onKeydown"
      />
      <button
        v-if="showClear"
        type="button"
        class="remote-picker-clear"
        aria-label="Auswahl entfernen"
        @click="clear"
      >
        ✕
      </button>
    </div>
    <div v-show="expanded" class="remote-picker-popup">
      <ul :id="`${baseId}-list`" role="listbox" :aria-label="label">
        <li
          v-for="(o, i) in options"
          :id="`${baseId}-opt-${i}`"
          :key="o.id"
          role="option"
          :aria-selected="String(i === activeIndex)"
          :class="{ active: i === activeIndex }"
          @mousedown.prevent
          @click="choose(o)"
        >
          <span>{{ o.label }}</span>
          <span v-if="o.description" class="remote-picker-desc">{{ o.description }}</span>
        </li>
      </ul>
      <p v-if="loading" class="remote-picker-status">Suche …</p>
      <p v-else-if="error" class="remote-picker-status form-error" role="alert">{{ error }}</p>
      <p v-else-if="!options.length" class="remote-picker-status">Keine Treffer</p>
    </div>
  </div>
</template>

<style scoped>
.remote-picker {
  position: relative;
}

.remote-picker label {
  display: block;
}

.remote-picker-control {
  position: relative;
  display: flex;
  align-items: center;
}

.remote-picker-control input {
  min-height: 44px;
  padding-right: 2.75rem;
}

.remote-picker-clear {
  position: absolute;
  right: 0;
  width: 44px;
  height: 44px;
  padding: 0;
  border: none;
  background: transparent;
  color: var(--color-muted);
  cursor: pointer;
}

.remote-picker-popup {
  position: absolute;
  z-index: 20;
  left: 0;
  right: 0;
  max-height: 18rem;
  overflow-y: auto;
  margin-top: var(--space-1);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  background: var(--color-bg);
  box-shadow: var(--shadow-float);
}

.remote-picker-popup ul {
  margin: 0;
  padding: var(--space-1) 0;
  list-style: none;
}

.remote-picker-popup li {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  min-height: 44px;
  padding: 0 var(--space-3);
  cursor: pointer;
}

.remote-picker-popup li.active,
.remote-picker-popup li:hover {
  background: var(--color-primary-light);
}

.remote-picker-desc {
  font-size: 0.8125rem;
  color: var(--color-muted);
}

.remote-picker-status {
  margin: 0;
  padding: var(--space-2) var(--space-3);
  color: var(--color-muted);
}
</style>
```

Zum Text „Huber Carlextern“ im Test: `w.text()` hängt die Texte der Elemente ohne Leerzeichen aneinander.

- [ ] **Step 5: Tests laufen lassen, sie müssen bestehen**

Run: `IN_CONTAINER 'cd src/frontend && npx vitest run'`
Expected: alle PASS (außer `App.test.js`).

- [ ] **Step 6: Commit**

Dateien: `RemotePicker.vue`, `lib/pickers.js`, 2 Testdateien. Message: `feat(frontend): RemotePicker with musician and loanable item loaders`.

---

### Task 5: Musiker durchgehend (API und Liste)

**Files:**
- Create: `src/backend/mv_hofki/filters/musician.py`
- Modify: `src/backend/mv_hofki/services/musician.py:16-56` (`get_list`)
- Modify: `src/backend/mv_hofki/api/routes/musicians.py:16-33`
- Modify: `src/frontend/src/pages/MusicianListPage.vue` (Script und Template neu, Style-Block behalten)
- Modify: `src/frontend/src/lib/musicians.js` (Query-Helfer entfernen)
- Modify: `src/frontend/src/pages/ImportSessionPage.vue:66-72` (Musiker per `getAll`)
- Test: `tests/backend/test_musicians.py` (ergänzen), `tests/backend/test_registers.py::test_musician_list_filters_active_and_register` (auf neue Parameter umstellen), `tests/frontend/inventory-helpers.test.js` (Tests der entfernten Helfer löschen)

**Interfaces:**
- Consumes: `ListFilter`, `PageParams`, `paginate` (Task 1); `useListQuery`, `InfiniteLoader` (Task 2); `FilterBar`, `DataTable`-Sortierung (Task 3); `getAll` (Task 2).
- Produces: `GET /api/v1/musicians?search&is_active&is_extern&register_id__in&order_by&limit&offset`.

- [ ] **Step 1: Failing Backend-Tests**

An `tests/backend/test_musicians.py` anhängen:

```python
# ---------------------------------------------------------------------------
# List filters, sorting and paging
# ---------------------------------------------------------------------------


async def _musician(client, first, last, **extra):
    resp = await client.post(
        "/api/v1/musicians", json={"first_name": first, "last_name": last, **extra}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_filters_active_extern_and_registers(client):
    flute = (
        await client.post("/api/v1/registers", json={"label": "Querflöte"})
    ).json()
    tuba = (await client.post("/api/v1/registers", json={"label": "Tuba"})).json()
    a = await _musician(client, "Anna", "Maier", register_ids=[flute["id"]])
    b = await _musician(client, "Berta", "Huber", is_extern=True, register_ids=[tuba["id"]])
    await _musician(client, "Carl", "Aigner", is_active=False)

    async def names(query):
        resp = await client.get(f"/api/v1/musicians?{query}")
        assert resp.status_code == 200, resp.text
        return [m["first_name"] for m in resp.json()["items"]]

    assert await names("is_active=true") == ["Berta", "Anna"]
    assert await names("") == ["Carl", "Berta", "Anna"]
    assert await names("is_extern=true") == ["Berta"]
    assert await names(f"register_id__in={flute['id']},{tuba['id']}") == ["Berta", "Anna"]
    assert await names(f"register_id__in={flute['id']}&is_active=true") == ["Anna"]
    assert a["id"] and b["id"]


async def test_sort_keys_and_unknown_key(client):
    await _musician(client, "Anna", "Maier")
    await _musician(client, "Zoe", "Maier")
    await _musician(client, "Carl", "Aigner")
    resp = await client.get("/api/v1/musicians?order_by=-first_name")
    assert [m["first_name"] for m in resp.json()["items"]] == ["Zoe", "Carl", "Anna"]
    resp = await client.get("/api/v1/musicians?order_by=city")
    assert resp.status_code == 422


async def test_paging_with_equal_sort_values_has_no_gaps(client):
    for i in range(60):
        await _musician(client, f"Vorname{i:02d}", "Maier")
    first = (await client.get("/api/v1/musicians?limit=50&offset=0")).json()
    second = (await client.get("/api/v1/musicians?limit=50&offset=50")).json()
    ids = [m["id"] for m in first["items"] + second["items"]]
    assert first["total"] == 60
    assert len(ids) == 60
    assert len(set(ids)) == 60
```

Vor dem Schreiben prüfen, wie `MusicianCreate` Register und Status annimmt: Die Feldnamen `register_ids` und `is_active` stehen in `src/backend/mv_hofki/schemas/musician.py`. Ebenso, ob `POST /api/v1/registers` ein `label` braucht (`schemas/register.py`). Heißen die Felder anders, die Test-Helfer anpassen; das Verhalten bleibt gleich.

In `tests/backend/test_registers.py::test_musician_list_filters_active_and_register` die alten Parameter umstellen: `active=` wird `is_active=`, `register_id=` wird `register_id__in=`. Die erwarteten Ergebnisse bleiben.

- [ ] **Step 2: Tests laufen lassen, sie müssen scheitern**

Run: `IN_CONTAINER 'python -m pytest tests/backend/test_musicians.py tests/backend/test_registers.py -q'`
Expected: FAIL. Die neuen Parameter werden ignoriert, `order_by=city` liefert 200.

- [ ] **Step 3: `filters/musician.py`**

```python
"""Filter for GET /musicians."""

from __future__ import annotations

from sqlalchemy import Select, select

from mv_hofki.filters.base import ListFilter
from mv_hofki.models.musician import Musician
from mv_hofki.models.register import musician_registers


class MusicianFilter(ListFilter):
    is_active: bool | None = None
    is_extern: bool | None = None
    register_id__in: list[int] | None = None

    class Constants(ListFilter.Constants):
        model = Musician
        search_model_fields = ["first_name", "last_name", "email", "city"]
        sort_fields = {
            "last_name": [Musician.last_name],
            "first_name": [Musician.first_name],
        }
        default_sort = ["last_name", "first_name"]

    def filter_register_id__in(self, query: Select, value: list[int]) -> Select:
        members = select(musician_registers.c.musician_id).where(
            musician_registers.c.register_id.in_(value)
        )
        return query.where(Musician.id.in_(members))
```

- [ ] **Step 4: Service und Route**

`services/musician.py`, `get_list` ersetzen:

```python
async def get_list(
    session: AsyncSession, flt: MusicianFilter, page: PageParams
) -> tuple[list[Musician], int]:
    query = flt.sort(flt.filter(select(Musician)))
    return await paginate(session, query, page)
```

Imports: `from mv_hofki.filters.base import PageParams, paginate` und `from mv_hofki.filters.musician import MusicianFilter`. Nicht mehr benutzte Imports (`or_`, `func`, `musician_registers`, sofern nirgends sonst in der Datei gebraucht) entfernen.

`api/routes/musicians.py`, `list_musicians` ersetzen:

```python
@router.get("", response_model=PaginatedResponse[MusicianRead])
async def list_musicians(
    flt: MusicianFilter = FilterDepends(MusicianFilter),
    page: PageParams = Depends(),
    db: AsyncSession = Depends(get_db),
):
    items, total = await musician_service.get_list(db, flt, page)
    return PaginatedResponse(
        items=items, total=total, limit=page.limit, offset=page.offset
    )
```

Imports: `from fastapi_filter import FilterDepends`, `from mv_hofki.filters.base import PageParams` und `from mv_hofki.filters.musician import MusicianFilter`. `Query` entfernen, falls nicht mehr benutzt.

- [ ] **Step 5: Backend-Tests laufen lassen, sie müssen bestehen**

Run: `IN_CONTAINER 'python -m pytest tests/backend -q'`
Expected: nur die bekannten fremden Fehler.

Scheitert ein anderer Test, der `/musicians?active=` oder `register_id=` benutzt (etwa `test_ai_import_*`), ihn auf die neuen Namen umstellen.

- [ ] **Step 6: `lib/musicians.js` verkleinern**

Entfernen: `ACTIVE_FILTERS`, `DEFAULT_ACTIVE_FILTER`, `ALL_QUERY_VALUE`, `parseActiveFilter`, `activeFilterQueryValue`, `parseRegisterFilter` und `buildMusicianQuery`. `registerLabels` bleibt, und der Datei-Docstring wird angepasst („Helpers for musician display“).

In `tests/frontend/inventory-helpers.test.js` die Tests der entfernten Funktionen löschen und den Import auf `registerLabels` reduzieren. Die übrigen Tests der Datei bleiben unverändert.

- [ ] **Step 7: `MusicianListPage.vue` neu**

Das `<style>` der Datei bleibt. Klassen, die danach nirgends mehr benutzt werden (`.pagination`-Varianten, `.register-filter`), aus dem Style-Block entfernen.

```vue
<script setup>
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { get } from "../lib/api.js";
import { registerLabels } from "../lib/musicians.js";
import { sortRegisters } from "../lib/registers.js";
import { useListQuery } from "../composables/useListQuery.js";
import DataTable from "../components/DataTable.vue";
import SearchBar from "../components/SearchBar.vue";
import FilterBar from "../components/FilterBar.vue";
import InfiniteLoader from "../components/InfiniteLoader.vue";

const router = useRouter();
const registers = ref([]);

const {
  state,
  sort,
  setSort,
  setFilter,
  defaults,
  activeFilterCount,
  items,
  total,
  loading,
  loadingMore,
  error,
  hasMore,
  loadMore,
  reload,
  resetFilters,
} = useListQuery({
  endpoint: "/musicians",
  filters: {
    search: { type: "string", default: "", debounce: true },
    is_active: { type: "bool", default: true },
    register_id__in: { type: "list", default: [] },
    is_extern: { type: "bool", default: null },
  },
  defaultSort: "last_name",
  mapItem: (m) => ({
    ...m,
    registers_label: registerLabels(m),
    is_extern_label: m.is_extern ? "Ja" : "Nein",
  }),
});

const filterDefs = computed(() => [
  {
    key: "is_active",
    label: "Status",
    type: "segmented",
    options: [
      { value: true, label: "Aktiv" },
      { value: false, label: "Inaktiv" },
      { value: null, label: "Alle" },
    ],
  },
  {
    key: "register_id__in",
    label: "Register",
    type: "multiselect",
    options: registers.value.map((r) => ({ value: String(r.id), label: r.label })),
  },
  {
    key: "is_extern",
    label: "Herkunft",
    type: "segmented",
    options: [
      { value: null, label: "Alle" },
      { value: false, label: "Verein" },
      { value: true, label: "Extern" },
    ],
  },
]);

const filtered = computed(() => activeFilterCount.value > 0 || !!state.search.trim());

const columns = [
  { key: "last_name", label: "Nachname", sortKey: "last_name" },
  { key: "first_name", label: "Vorname", sortKey: "first_name" },
  { key: "registers_label", label: "Register" },
  { key: "city", label: "Ort" },
  { key: "phone", label: "Telefon" },
  { key: "is_extern_label", label: "Extern" },
];

onMounted(async () => {
  try {
    registers.value = sortRegisters(await get("/registers"));
  } catch {
    registers.value = [];
  }
});

function goTo(row) {
  router.push(`/musiker/${row.id}`);
}
</script>

<template>
  <div>
    <div class="page-header">
      <h1>Musiker</h1>
      <router-link to="/musiker/neu" class="btn btn-primary"> Neuer Musiker </router-link>
    </div>

    <div class="toolbar">
      <SearchBar v-model="state.search" placeholder="Suche (Name, Ort, E-Mail …)" class="grow" />
    </div>

    <FilterBar :defs="filterDefs" :state="state" :defaults="defaults" @change="setFilter" @reset="resetFilters" />

    <div v-if="error && !items.length" class="alert alert-danger list-alert" role="alert">
      Musiker konnten nicht geladen werden: {{ error }}
      <button type="button" class="btn-sm" @click="reload">Erneut versuchen</button>
    </div>

    <template v-else>
      <DataTable
        :columns="columns"
        :rows="items"
        :loading="loading"
        :card-breakpoint="480"
        :sort="sort"
        :empty-text="filtered ? 'Keine Musiker für diese Filter.' : 'Noch keine Musiker erfasst.'"
        @update:sort="setSort"
        @row-click="goTo"
      >
        <template #last_name="{ row, value }">
          <span :class="{ 'text-muted': row.is_active === false }">{{ value }}</span>
          <span v-if="row.is_active === false" class="badge badge-gray inactive-badge">inaktiv</span>
        </template>
        <template #first_name="{ row, value }">
          <span :class="{ 'text-muted': row.is_active === false }">{{ value }}</span>
        </template>
      </DataTable>

      <p v-if="!loading && !items.length && filtered" class="empty-note">
        <button type="button" class="btn-sm" @click="resetFilters">Filter zurücksetzen</button>
      </p>

      <InfiniteLoader
        :has-more="hasMore"
        :loading="loadingMore"
        :error="items.length ? error : ''"
        :count="items.length"
        :total="total"
        @load-more="loadMore"
      />
    </template>
  </div>
</template>
```

Die früher verwendete Klasse `musician-toolbar` entfällt. Hatte der Style-Block Regeln dafür, werden sie entfernt.

- [ ] **Step 8: `ImportSessionPage.vue`**

In der `Promise.all` bei Zeile 66–72 `get("/musicians?limit=200")` durch `getAll("/musicians")` ersetzen und `getAll` importieren. Die Zuweisung `musicians.value = musicianData.items || musicianData;` wird `musicians.value = musicianData;`, denn `getAll` liefert ein Array.

- [ ] **Step 9: Frontend-Tests, Build, Browser**

Run: `IN_CONTAINER 'cd src/frontend && npx vitest run && npx vite build'`
Expected: Tests PASS (außer `App.test.js`), Build ok.

Browser (Playwright-MCP `mcp__playwright-lokal__*`, per ToolSearch laden). Die Adresse ist `http://172.17.0.1:<port>`, den Port liefert `docker port mv-hofki-vue-pyhton_devcontainer-devcontainer-1 8000`; falls das nicht erreichbar ist, `http://localhost:<port>`. Prüfen:
1. `/musiker`: Status „Alle“ wählen. Die URL enthält `is_active=alle`, und nach einem Neuladen der Seite ist „Alle“ noch gewählt.
2. Register (Mehrfachauswahl) und „Extern“: Die Chips erscheinen, das ✕ entfernt sie, „Filter zurücksetzen“ leert alles.
3. Auf die Spaltenköpfe Nachname und Vorname klicken: Die Sortierung wechselt, die URL enthält `order_by`.
4. Bis ans Listenende scrollen: Es wird nachgeladen, „143 von 143“ erscheint am Ende (die DB hat 143 Musiker).
5. Einen Musiker öffnen und mit Zurück zurückgehen: Die Filter sind noch gesetzt.
6. Breite 390 px: „Filter (n)“ klappt die Leiste auf, die Karten zeigen „Sortieren nach“.
7. Dunkles Theme per Screenshot.
8. `/import`, eine Sitzung öffnen, falls vorhanden: Das Musiker-Select ist befüllt.

- [ ] **Step 10: Commit**

Die geänderten Backend-, Frontend- und Testdateien. Message: `feat(musicians): fastapi-filter list with URL filters and endless scrolling`.

---

### Task 6: Items durchgehend (API, Facets, Liste)

**Files:**
- Create: `src/backend/mv_hofki/filters/inventory_item.py`
- Modify: `src/backend/mv_hofki/services/inventory_item.py` (`get_list`; neu `get_facets`, `_get_details`; `_DISPLAY_NR_RE` und die Regex-Bedingung wandern in den Filter)
- Modify: `src/backend/mv_hofki/api/routes/items.py` (`list_items`; neu `GET /facets` **vor** `GET /{item_id}`)
- Modify: `src/frontend/src/pages/ItemListPage.vue`
- Test: `tests/backend/test_item_list_filters.py` (neu); bestehende Tests in `test_items.py`/`test_instruments.py` müssen weiter bestehen

**Interfaces:**
- Consumes: Task 1–3.
- Produces:
  - `display_nr_condition(text: str) -> ColumnElement[bool] | None` in `mv_hofki.filters.inventory_item`. Wird in Task 8 für Leihen gebraucht.
  - `ItemFilter.bind(category) -> ItemFilter`: wirft 422, wenn ein Feld nicht zur Kategorie passt.
  - `GET /api/v1/items/facets?category=`: `{owners?|sizes?|genders?|difficulties?: string[]}`.

- [ ] **Step 1: Failing tests**

`tests/backend/test_item_list_filters.py`:

```python
"""GET /items filters, sorting, paging and facets."""

import pytest

URL = "/api/v1/items"


@pytest.fixture
async def refs(client):
    tuba = (
        await client.post(
            "/api/v1/instrument-types", json={"label": "Tuba", "label_short": "TU"}
        )
    ).json()
    horn = (
        await client.post(
            "/api/v1/instrument-types", json={"label": "Horn", "label_short": "HR"}
        )
    ).json()
    hat = (await client.post("/api/v1/clothing-types", json={"label": "Hut"})).json()
    jacket = (
        await client.post("/api/v1/clothing-types", json={"label": "Jacke"})
    ).json()
    return {"tuba": tuba["id"], "horn": horn["id"], "hat": hat["id"], "jacket": jacket["id"]}


async def _item(client, **data):
    resp = await client.post(URL, json=data)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _labels(client, query):
    resp = await client.get(f"{URL}?{query}")
    assert resp.status_code == 200, resp.text
    return [i["label"] for i in resp.json()["items"]]


async def _musician(client):
    resp = await client.post(
        "/api/v1/musicians", json={"first_name": "Anna", "last_name": "Maier"}
    )
    return resp.json()["id"]


async def test_instrument_filters(client, refs):
    t1 = await _item(
        client, category="instrument", label="Tuba 1", instrument_type_id=refs["tuba"],
        construction_year=1990, owner="MV Hofkirchen",
    )
    await _item(
        client, category="instrument", label="Horn 1", instrument_type_id=refs["horn"],
        construction_year=2010, owner="Privat",
    )
    await _item(
        client, category="instrument", label="Tuba 2", instrument_type_id=refs["tuba"],
        construction_year=2005, owner="MV Hofkirchen",
    )
    await client.post(
        "/api/v1/loans",
        json={"item_id": t1["id"], "musician_id": await _musician(client),
              "start_date": "2026-01-01"},
    )
    base = "category=instrument"
    assert await _labels(client, f"{base}&instrument_type_id__in={refs['tuba']}") == [
        "Tuba 1", "Tuba 2",
    ]
    assert await _labels(client, f"{base}&status=verliehen") == ["Tuba 1"]
    assert await _labels(client, f"{base}&status=verfuegbar") == ["Horn 1", "Tuba 2"]
    assert await _labels(client, f"{base}&owner=Privat") == ["Horn 1"]
    assert await _labels(
        client, f"{base}&construction_year__gte=2000&construction_year__lte=2006"
    ) == ["Tuba 2"]


async def test_instrument_sorting(client, refs):
    await _item(client, category="instrument", label="Tuba", instrument_type_id=refs["tuba"],
                manufacturer="Yamaha", construction_year=1990)
    await _item(client, category="instrument", label="Horn", instrument_type_id=refs["horn"],
                manufacturer="Alexander", construction_year=None)
    base = "category=instrument"
    assert await _labels(client, f"{base}") == ["Horn", "Tuba"]  # number: HR before TU
    assert await _labels(client, f"{base}&order_by=-type") == ["Tuba", "Horn"]
    assert await _labels(client, f"{base}&order_by=manufacturer") == ["Horn", "Tuba"]
    # NULL construction year last in both directions
    assert await _labels(client, f"{base}&order_by=construction_year") == ["Tuba", "Horn"]
    assert await _labels(client, f"{base}&order_by=-construction_year") == ["Tuba", "Horn"]


async def test_clothing_filters_and_type_sort(client, refs):
    await _item(client, category="clothing", label="Jacke L", clothing_type_id=refs["jacket"],
                size="L", gender="Herren")
    await _item(client, category="clothing", label="Hut M", clothing_type_id=refs["hat"],
                size="M", gender="Damen")
    base = "category=clothing"
    assert await _labels(client, f"{base}&clothing_type_id__in={refs['hat']}") == ["Hut M"]
    assert await _labels(client, f"{base}&size=L") == ["Jacke L"]
    assert await _labels(client, f"{base}&gender=Damen") == ["Hut M"]
    assert await _labels(client, f"{base}&order_by=type") == ["Hut M", "Jacke L"]


async def test_sheet_music_filters(client):
    genre = (await client.post("/api/v1/sheet-music-genres", json={"label": "Marsch"})).json()
    await _item(client, category="sheet_music", label="Radetzky", composer="Strauss",
                genre_id=genre["id"], difficulty="C", storage_location="Archiv Kasten 3")
    await _item(client, category="sheet_music", label="Bolero", composer="Ravel",
                difficulty="D")
    base = "category=sheet_music"
    assert await _labels(client, f"{base}&genre_id__in={genre['id']}") == ["Radetzky"]
    assert await _labels(client, f"{base}&difficulty=D") == ["Bolero"]
    assert await _labels(client, f"{base}&storage_location__ilike=kasten") == ["Radetzky"]
    assert await _labels(client, f"{base}&order_by=composer") == ["Bolero", "Radetzky"]


async def test_general_item_category_filters(client):
    deko = (await client.post("/api/v1/general-item-categories", json={"label": "Deko"})).json()
    gastro = (
        await client.post("/api/v1/general-item-categories", json={"label": "Gastro"})
    ).json()
    await _item(client, category="general_item", label="Girlande", category_ids=[deko["id"]])
    await _item(client, category="general_item", label="Gläser", category_ids=[gastro["id"]])
    await _item(client, category="general_item", label="Leiter")
    base = "category=general_item"
    assert await _labels(client, f"{base}&category_id__in={deko['id']}") == ["Girlande"]
    assert await _labels(client, f"{base}&without_category=true") == ["Leiter"]
    assert await _labels(
        client, f"{base}&category_id__in={deko['id']}&without_category=true"
    ) == ["Girlande", "Leiter"]
    assert await _labels(client, f"{base}&order_by=-label") == ["Leiter", "Gläser", "Girlande"]


async def test_search_keeps_display_number_match(client, refs):
    await _item(client, category="instrument", label="Tuba", instrument_type_id=refs["tuba"])
    await _item(client, category="instrument", label="Tuba", instrument_type_id=refs["tuba"])
    assert await _labels(client, "category=instrument&search=tu 2") == ["Tuba"]
    resp = await client.get(f"{URL}?category=instrument&search=tu-002")
    assert [i["display_nr"] for i in resp.json()["items"]] == ["TU-002"]


async def test_filter_not_for_category_is_422(client):
    resp = await client.get(f"{URL}?category=instrument&size=L")
    assert resp.status_code == 422
    assert resp.json()["detail"] == "Filter „size“ gibt es für Instrumente nicht"
    resp = await client.get(f"{URL}?category=general_item&order_by=type")
    assert resp.status_code == 422
    assert resp.json()["detail"] == "Sortierung „type“ gibt es für Allgemein nicht"


async def test_paging_is_stable(client):
    for i in range(7):
        await _item(client, category="general_item", label="Stuhl", owner="MV Hofkirchen")
    ids = []
    for offset in (0, 3, 6):
        page = (
            await client.get(f"{URL}?category=general_item&order_by=label&limit=3&offset={offset}")
        ).json()
        assert page["total"] == 7
        ids += [i["id"] for i in page["items"]]
    assert len(ids) == 7 and len(set(ids)) == 7


async def test_details_are_included_in_list(client, refs):
    await _item(client, category="instrument", label="Tuba", instrument_type_id=refs["tuba"],
                serial_nr="S-1")
    item = (await client.get(f"{URL}?category=instrument")).json()["items"][0]
    assert item["serial_nr"] == "S-1"
    assert item["instrument_type"]["label"] == "Tuba"


async def test_facets(client, refs):
    await _item(client, category="instrument", label="A", instrument_type_id=refs["tuba"],
                owner="Privat")
    await _item(client, category="instrument", label="B", instrument_type_id=refs["tuba"],
                owner="MV Hofkirchen")
    await _item(client, category="clothing", label="J", clothing_type_id=refs["jacket"],
                size="L", gender="")
    resp = await client.get(f"{URL}/facets?category=instrument")
    assert resp.status_code == 200
    assert resp.json() == {"owners": ["MV Hofkirchen", "Privat"]}
    assert (await client.get(f"{URL}/facets?category=clothing")).json() == {
        "sizes": ["L"],
        "genders": [],
    }
    assert (await client.get(f"{URL}/facets?category=general_item")).json() == {}
    assert (await client.get(f"{URL}/facets?category=unsinn")).status_code == 400
```

Vorab prüfen:
- Ob Kleidung beim Anlegen ein Pflichtfeld `owner` hat und ob `sheet-music-genres` ein `label` erwartet: in `schemas/inventory_item.py` bzw. `schemas/sheet_music_genre.py`.
- Wie Leihen angelegt werden (`POST /api/v1/loans` mit `item_id`, `musician_id`, `start_date`).
- `test_instrument_sorting`: Die Standardsortierung `number` ist `number_prefix`, dann `inventory_nr`, also HR vor TU.

- [ ] **Step 2: Tests laufen lassen, sie müssen scheitern**

Run: `IN_CONTAINER 'python -m pytest tests/backend/test_item_list_filters.py -q'`
Expected: FAIL.

- [ ] **Step 3: `filters/inventory_item.py`**

```python
"""Filter for GET /items. One class for all four item kinds; ``bind`` rejects
fields and sort keys that do not belong to the requested kind."""

from __future__ import annotations

import re
from typing import Any, Literal

from fastapi import HTTPException
from pydantic import PrivateAttr
from sqlalchemy import ColumnElement, Select, and_, exists, func, or_, select

from mv_hofki.filters.base import ListFilter
from mv_hofki.models.clothing_detail import ClothingDetail
from mv_hofki.models.clothing_type import ClothingType
from mv_hofki.models.general_item_category import general_item_category_links as links
from mv_hofki.models.instrument_detail import InstrumentDetail
from mv_hofki.models.instrument_type import InstrumentType
from mv_hofki.models.inventory_item import InventoryItem
from mv_hofki.models.loan import Loan
from mv_hofki.models.sheet_music_detail import SheetMusicDetail

# "TU-002", "tu 2", "TU2" -> ("TU", 2)
_DISPLAY_NR_RE = re.compile(r"^\s*([^\W\d_]+)\s*-?\s*0*(\d+)\s*$")

CATEGORY_LABELS = {
    "instrument": "Instrumente",
    "clothing": "Kleidung",
    "sheet_music": "Noten",
    "general_item": "Allgemein",
}

_COMMON_FIELDS = {"search", "order_by"}
_CATEGORY_FIELDS = {
    "instrument": {
        "instrument_type_id__in",
        "status",
        "owner",
        "construction_year__gte",
        "construction_year__lte",
    },
    "clothing": {"clothing_type_id__in", "size", "gender", "status"},
    "sheet_music": {"genre_id__in", "difficulty", "storage_location__ilike"},
    "general_item": {
        "category_id__in",
        "without_category",
        "storage_location__ilike",
        "status",
    },
}
_CATEGORY_SORTS = {
    "instrument": {"number", "type", "manufacturer", "construction_year"},
    "clothing": {"number", "type", "size"},
    "sheet_music": {"number", "label", "composer"},
    "general_item": {"number", "label", "storage_location"},
}


def display_nr_condition(text: str) -> ColumnElement[bool] | None:
    """Match an inventory number typed as "TU-002", "tu 2" or "TU2"."""
    match = _DISPLAY_NR_RE.match(text)
    if not match:
        return None
    return and_(
        func.upper(InventoryItem.number_prefix) == match[1].upper(),
        InventoryItem.inventory_nr == int(match[2]),
    )


class ItemFilter(ListFilter):
    instrument_type_id__in: list[int] | None = None
    clothing_type_id__in: list[int] | None = None
    genre_id__in: list[int] | None = None
    category_id__in: list[int] | None = None
    without_category: bool | None = None
    status: Literal["verfuegbar", "verliehen"] | None = None
    owner: str | None = None
    size: str | None = None
    gender: str | None = None
    difficulty: str | None = None
    storage_location__ilike: str | None = None
    construction_year__gte: int | None = None
    construction_year__lte: int | None = None

    _category: str = PrivateAttr(default="")

    class Constants(ListFilter.Constants):
        model = InventoryItem
        columns = {
            "instrument_type_id": InstrumentDetail.instrument_type_id,
            "construction_year": InstrumentDetail.construction_year,
            "clothing_type_id": ClothingDetail.clothing_type_id,
            "size": ClothingDetail.size,
            "gender": ClothingDetail.gender,
            "genre_id": SheetMusicDetail.genre_id,
            "difficulty": SheetMusicDetail.difficulty,
        }
        sort_fields = {
            "number": [InventoryItem.number_prefix, InventoryItem.inventory_nr],
            "type": [],  # instrument or clothing type label, see sort_columns
            "manufacturer": [InventoryItem.manufacturer],
            "construction_year": [InstrumentDetail.construction_year],
            "size": [ClothingDetail.size],
            "label": [InventoryItem.label],
            "composer": [SheetMusicDetail.composer],
            "storage_location": [InventoryItem.storage_location],
        }
        default_sort = ["number"]

    def bind(self, category: str) -> ItemFilter:
        label = CATEGORY_LABELS[category]
        allowed = _CATEGORY_FIELDS[category] | _COMMON_FIELDS
        for name in self.model_dump(exclude_none=True, exclude_unset=True):
            if name not in allowed:
                raise HTTPException(
                    status_code=422, detail=f"Filter „{name}“ gibt es für {label} nicht"
                )
        for key in self.order_by or []:
            name = key.lstrip("+-")
            if name not in _CATEGORY_SORTS[category]:
                raise HTTPException(
                    status_code=422,
                    detail=f"Sortierung „{name}“ gibt es für {label} nicht",
                )
        self._category = category
        return self

    def sort_columns(self, key: str) -> list[Any]:
        if key == "type":
            return [
                InstrumentType.label
                if self._category == "instrument"
                else ClothingType.label
            ]
        return super().sort_columns(key)

    def search_clause(self, value: str) -> ColumnElement[bool] | None:
        value = value.strip()
        if not value:
            return None
        pattern = f"%{value}%"
        conditions: list[ColumnElement[bool]] = [
            InventoryItem.label.ilike(pattern),
            InventoryItem.manufacturer.ilike(pattern),
            InventoryItem.notes.ilike(pattern),
        ]
        nr = display_nr_condition(value)
        if nr is not None:
            conditions.append(nr)
        return or_(*conditions)

    def filter_status(self, query: Select, value: str) -> Select:
        open_loan = exists().where(
            Loan.item_id == InventoryItem.id, Loan.end_date.is_(None)
        )
        return query.where(open_loan if value == "verliehen" else ~open_loan)

    def filter_category_id__in(self, query: Select, value: list[int]) -> Select:
        has_any = InventoryItem.id.in_(
            select(links.c.item_id).where(links.c.category_id.in_(value))
        )
        if self.without_category:
            has_none = ~InventoryItem.id.in_(select(links.c.item_id))
            return query.where(or_(has_any, has_none))
        return query.where(has_any)

    def filter_without_category(self, query: Select, value: bool) -> Select:
        # Combined with category_id__in as OR in filter_category_id__in.
        if not value or self.category_id__in:
            return query
        return query.where(~InventoryItem.id.in_(select(links.c.item_id)))
```

- [ ] **Step 4: Service**

In `services/inventory_item.py`:
- `_DISPLAY_NR_RE` und die Regex-Logik aus `get_list` entfernen. Wird `_DISPLAY_NR_RE` sonst noch in der Datei verwendet, ersatzweise `display_nr_condition` aus dem Filter importieren.
- Imports ergänzen: `from mv_hofki.filters.base import PageParams, paginate`, `from mv_hofki.filters.inventory_item import ItemFilter`, dazu `InstrumentType` (schon vorhanden), `ClothingType` und `SheetMusicDetail` (vorhanden).
- `get_list` ersetzen:

```python
def _base_query(category: str) -> Any:
    query: Any = select(InventoryItem).where(InventoryItem.category == category)
    if category == "instrument":
        query = query.outerjoin(
            InstrumentDetail, InstrumentDetail.item_id == InventoryItem.id
        ).outerjoin(InstrumentType, InstrumentType.id == InstrumentDetail.instrument_type_id)
    elif category == "clothing":
        query = query.outerjoin(
            ClothingDetail, ClothingDetail.item_id == InventoryItem.id
        ).outerjoin(ClothingType, ClothingType.id == ClothingDetail.clothing_type_id)
    elif category == "sheet_music":
        query = query.outerjoin(
            SheetMusicDetail, SheetMusicDetail.item_id == InventoryItem.id
        )
    return query


async def _get_details(
    session: AsyncSession, item_ids: list[int], category: str
) -> dict[int, Any]:
    """Detail rows of many items in one query."""
    detail_model, _ = CATEGORY_DETAIL_MAP[category]
    if detail_model is None or not item_ids:
        return {}
    query: Any = select(detail_model).where(detail_model.item_id.in_(item_ids))  # type: ignore[attr-defined]
    if category in _DETAIL_JOINEDLOAD:
        query = _DETAIL_JOINEDLOAD[category](query)
    result = await session.execute(query)
    return {d.item_id: d for d in result.unique().scalars()}


async def get_list(
    session: AsyncSession,
    *,
    category: str,
    flt: ItemFilter,
    page: PageParams,
) -> tuple[list[dict[str, Any]], int]:
    if category not in CATEGORY_DETAIL_MAP:
        raise HTTPException(status_code=400, detail=f"Ungültige Kategorie: {category}")
    flt.bind(category)
    query = flt.sort(flt.filter(_base_query(category)))
    items, total = await paginate(
        session, query, page, options=[joinedload(InventoryItem.currency)]
    )
    await _enrich(session, items)
    details = await _get_details(session, [i.id for i in items], category)
    return [_build_read_dict(i, details.get(i.id)) for i in items], total


FACETS: dict[str, dict[str, tuple[Any, Any]]] = {
    "instrument": {"owners": (None, InventoryItem.owner)},
    "clothing": {
        "sizes": (ClothingDetail, ClothingDetail.size),
        "genders": (ClothingDetail, ClothingDetail.gender),
    },
    "sheet_music": {"difficulties": (SheetMusicDetail, SheetMusicDetail.difficulty)},
    "general_item": {},
}


async def get_facets(session: AsyncSession, category: str) -> dict[str, list[str]]:
    """Distinct non-empty values that the list filters offer as choices."""
    if category not in FACETS:
        raise HTTPException(status_code=400, detail=f"Ungültige Kategorie: {category}")
    out: dict[str, list[str]] = {}
    for key, (detail_model, column) in FACETS[category].items():
        query: Any = select(column).distinct().select_from(InventoryItem)
        if detail_model is not None:
            query = query.join(detail_model, detail_model.item_id == InventoryItem.id)
        query = query.where(
            InventoryItem.category == category, column.is_not(None), column != ""
        )
        values = (await session.execute(query)).scalars().all()
        out[key] = sorted(values, key=str.casefold)
    return out
```

Hinweise:
- `_get_detail` für ein einzelnes Item bleibt (get_by_id/create/update nutzen es).
- Wird `ColumnElement`, `and_` oder `or_` in der Datei nicht mehr gebraucht, den Import entfernen.

- [ ] **Step 5: Route**

In `api/routes/items.py`:
- Imports: `from fastapi_filter import FilterDepends`, `from mv_hofki.filters.base import PageParams` und `from mv_hofki.filters.inventory_item import ItemFilter`.
- `list_items` ersetzen:

```python
@router.get("")
async def list_items(
    category: str = Query(
        ..., description="Category: instrument, clothing, sheet_music, general_item"
    ),
    flt: ItemFilter = FilterDepends(ItemFilter),
    page: PageParams = Depends(),
    db: AsyncSession = Depends(get_db),
):
    items, total = await item_service.get_list(
        db, category=category, flt=flt, page=page
    )
    return PaginatedResponse(
        items=[_to_read(item) for item in items],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get("/facets")
async def item_facets(category: str = Query(...), db: AsyncSession = Depends(get_db)):
    return await item_service.get_facets(db, category)
```

`/facets` muss **vor** `@router.get("/{item_id}")` stehen, sonst wird „facets“ als `item_id` gelesen und ergibt 422.

- [ ] **Step 6: Backend-Tests laufen lassen, sie müssen bestehen**

Run: `IN_CONTAINER 'python -m pytest tests/backend -q'`
Expected: nur die bekannten fremden Fehler. Die bestehenden Tests `test_items.py::test_list_*` und `test_search_matches_display_number` müssen unverändert bestehen.

- [ ] **Step 7: `ItemListPage.vue`**

Umbauen, wobei Kopfbereich, Ansichtsumschalter, `ItemFormModal`, `mapItem`, die Menge-Spalte und die Style-Regeln erhalten bleiben.

**Script:**
- Die Refs `items`, `total`, `loading`, `search`, `limit`, `offset` sowie die Funktionen `load`, `prevPage` und `nextPage` entfernen. Ebenso den `watch(search)` und den `watch(() => props.category)`: Die Seite wird pro Route ohnehin neu erzeugt, weil `App.vue` `RouterView` mit `:key="route.path"` verwendet.
- Imports ergänzen: `useListQuery`, `FilterBar`, `InfiniteLoader`, `SortSelect`.
- Dazu:

```js
const STATUS_OPTIONS = [
  { value: "", label: "Alle" },
  { value: "verfuegbar", label: "Verfügbar" },
  { value: "verliehen", label: "Verliehen" },
];

const search = { type: "string", default: "", debounce: true };
const FILTERS = {
  instrument: {
    search,
    instrument_type_id__in: { type: "list", default: [] },
    status: { type: "string", default: "" },
    owner: { type: "string", default: "" },
    construction_year__gte: { type: "number", default: null },
    construction_year__lte: { type: "number", default: null },
  },
  clothing: {
    search,
    clothing_type_id__in: { type: "list", default: [] },
    size: { type: "string", default: "" },
    gender: { type: "string", default: "" },
    status: { type: "string", default: "" },
  },
  sheet_music: {
    search,
    genre_id__in: { type: "list", default: [] },
    difficulty: { type: "string", default: "" },
    storage_location__ilike: { type: "string", default: "", debounce: true },
  },
  general_item: {
    search,
    category_id__in: { type: "list", default: [] },
    without_category: { type: "bool", default: null },
    storage_location__ilike: { type: "string", default: "", debounce: true },
    status: { type: "string", default: "" },
  },
};

const TYPE_ENDPOINTS = {
  instrument: "/instrument-types",
  clothing: "/clothing-types",
  sheet_music: "/sheet-music-genres",
  general_item: "/general-item-categories",
};

const typeOptions = ref([]);
const facets = ref({});

const list = useListQuery({
  endpoint: "/items",
  filters: FILTERS[props.category],
  defaultSort: "number",
  baseParams: () => ({ category: props.category }),
  mapItem,
});
const {
  state,
  sort,
  setSort,
  setFilter,
  defaults,
  activeFilterCount,
  items,
  total,
  loading,
  loadingMore,
  error,
  hasMore,
  loadMore,
  reload,
  resetFilters,
} = list;

const toOptions = (values) => (values || []).map((v) => ({ value: v, label: v }));
const typeChoice = computed(() =>
  typeOptions.value.map((t) => ({ value: String(t.id), label: t.label })),
);

const filterDefs = computed(() => {
  switch (props.category) {
    case "instrument":
      return [
        { key: "instrument_type_id__in", label: "Typ", type: "multiselect", options: typeChoice.value },
        { key: "status", label: "Status", type: "segmented", options: STATUS_OPTIONS },
        { key: "owner", label: "Eigentümer", type: "select", options: toOptions(facets.value.owners) },
        { keys: ["construction_year__gte", "construction_year__lte"], label: "Baujahr", type: "range" },
      ];
    case "clothing":
      return [
        { key: "clothing_type_id__in", label: "Typ", type: "multiselect", options: typeChoice.value },
        { key: "size", label: "Größe", type: "select", options: toOptions(facets.value.sizes) },
        { key: "gender", label: "Geschlecht", type: "select", options: toOptions(facets.value.genders) },
        { key: "status", label: "Status", type: "segmented", options: STATUS_OPTIONS },
      ];
    case "sheet_music":
      return [
        { key: "genre_id__in", label: "Gattung", type: "multiselect", options: typeChoice.value },
        { key: "difficulty", label: "Schwierigkeitsgrad", type: "select", options: toOptions(facets.value.difficulties) },
        { key: "storage_location__ilike", label: "Lagerort", type: "text", placeholder: "enthält …" },
      ];
    default:
      return [
        { key: "category_id__in", label: "Kategorie", type: "multiselect", options: typeChoice.value },
        { key: "without_category", label: "Ohne Kategorie", type: "toggle" },
        { key: "storage_location__ilike", label: "Lagerort", type: "text", placeholder: "enthält …" },
        { key: "status", label: "Status", type: "segmented", options: STATUS_OPTIONS },
      ];
  }
});

const filtered = computed(() => activeFilterCount.value > 0 || !!state.search.trim());
const sortOptions = computed(() =>
  columns.value.filter((c) => c.sortKey).map((c) => ({ key: c.sortKey, label: c.label })),
);
```

- `onMounted` ersetzen:

```js
onMounted(async () => {
  const [cur, types, facetData] = await Promise.all([
    get("/currencies"),
    get(TYPE_ENDPOINTS[props.category]).catch(() => []),
    get(`/items/facets?category=${props.category}`).catch(() => ({})),
  ]);
  currencies.value = cur;
  typeOptions.value = types;
  facets.value = facetData;
});
```

- `onModalSave` ruft `reload()` statt `load()`.

**Spalten** (`baseColumns`) ergänzen, sonst bleiben die Spalten gleich:
- Instrumente:
  - `display_nr` bekommt `sortKey: "number"`, `type_label` `sortKey: "type"`, `manufacturer` `sortKey: "manufacturer"`.
  - Neue Spalte nach `serial_nr`: `{ key: "construction_year", label: "Baujahr", sortKey: "construction_year", class: "col-num", hideEmptyInCard: true }`.
- Kleidung: `display_nr` → `number`, `type_label` → `type`, `size` → `size`.
- Noten: `display_nr` → `number`, `label` → `label`, `composer` → `composer`.
- Allgemein:
  - `display_nr` → `number`, `label` → `label`.
  - Neue Spalte nach `categories`: `{ key: "storage_location", label: "Lagerort", sortKey: "storage_location", hideEmptyInCard: true }`.

**Template:**
- Die `.toolbar` bleibt mit `<SearchBar v-model="state.search" …>` und dem Ansichtsumschalter.
- Darunter kommt `<FilterBar :defs="filterDefs" :state="state" :defaults="defaults" @change="setFilter" @reset="resetFilters" />`.
- Danach das Fehler-Banner wie in MusicianListPage („{{ cat.label }} konnten nicht geladen werden: …“ mit „Erneut versuchen“ → `reload`), sichtbar bei `error && !items.length`.
- **Listenansicht:** `DataTable` bekommt `:sort="sort"`, `@update:sort="setSort"` und `:empty-text="filtered ? 'Keine Einträge für diese Filter.' : 'Noch keine Einträge.'"`.
- **Kartenansicht:** vor `.instrument-grid` kommt `<SortSelect v-if="sortOptions.length" class="grid-sort" :options="sortOptions" :model-value="sort" @update:model-value="setSort" />`.
  - Bei `loading` zeigt die Kartenansicht `<LoadingSpinner />`; Import aus `../components/LoadingSpinner.vue`.
  - Bei leerer Liste zeigt sie `<p class="empty-note">` mit dem Leertext und, wenn gefiltert, „Filter zurücksetzen“.
- Das `.pagination`-Markup entfernen und durch `InfiniteLoader` ersetzen (Props wie in MusicianListPage).
- Style ergänzen: `.grid-sort { margin-bottom: var(--space-3); justify-content: flex-end; }`.

- [ ] **Step 8: Frontend-Tests, Build, Browser**

Run: `IN_CONTAINER 'cd src/frontend && npx vitest run && npx vite build'`
Expected: PASS (außer `App.test.js`), Build ok.

Browser (wie in Task 5, echte DB, nur lesen):
1. `/instrumente` (157 Stück):
   - Typ-Mehrfachauswahl, Status verliehen/verfügbar, Eigentümer, Baujahr von–bis.
   - Die URL spiegelt die Filter, Neuladen behält sie.
   - Sortieren nach Typ in der Tabelle; in der Kartenansicht über „Sortieren nach“.
   - Nachladen bis „157 von 157“.
2. `/kleidung`: Größe, Geschlecht, Typ.
3. `/allgemein`: Kategorie plus „Ohne Kategorie“, Lagerort-Text (verzögert).
4. `/noten`: Die Seite lädt fehlerfrei, auch wenn es noch keine Noten gibt, und zeigt „Noch keine Einträge.“.
5. Handy-Breite 390 px und dunkles Theme.

- [ ] **Step 9: Commit**

Message: `feat(items): fastapi-filter list, facets and endless scrolling for all item kinds`.

---

### Task 7: Rechnungen durchgehend

**Files:**
- Create: `src/backend/mv_hofki/filters/invoice.py`
- Modify: `src/backend/mv_hofki/services/invoice_overview.py`, `src/backend/mv_hofki/schemas/invoice_overview.py`, `src/backend/mv_hofki/api/routes/invoices.py`
- Modify: `src/frontend/src/pages/InvoiceListPage.vue` (neu schreiben)
- Test: `tests/backend/test_invoice_overview.py` (bestehende Aufrufe auf neue Parameter umstellen und Tests ergänzen)

**Interfaces:**
- Produces: `GET /api/v1/invoices?search&item_category&date_issued__gte&date_issued__lte&currency_id&order_by&limit&offset`. Die Antwort ist `{items, total, limit, offset, totals_by_currency}`, und `items[]` enthält zusätzlich `invoice_issuer`.

- [ ] **Step 1: Failing tests**

In `tests/backend/test_invoice_overview.py`:
- Bestehende Aufrufe umstellen: `category=` wird `item_category=`, `date_from=` wird `date_issued__gte=`, `date_to=` wird `date_issued__lte=`. Die Erwartungen bleiben.
- Anhängen (Rechnungen werden wie in der Fixture `setup_invoices` per JSON an `POST /api/v1/items/{id}/invoices` angelegt):

```python
async def _invoice(client, item_id, title, amount, currency_id, date_issued, issuer):
    resp = await client.post(
        f"/api/v1/items/{item_id}/invoices",
        json={
            "title": title,
            "amount": amount,
            "currency_id": currency_id,
            "date_issued": date_issued,
            "invoice_issuer": issuer,
        },
    )
    assert resp.status_code == 201, resp.text


def _titles(resp):
    assert resp.status_code == 200, resp.text
    return [i["title"] for i in resp.json()["items"]]


@pytest.fixture
async def three_invoices(client):
    eur = (
        await client.post("/api/v1/currencies", json={"label": "Euro", "abbreviation": "EUR"})
    ).json()
    chf = (
        await client.post("/api/v1/currencies", json={"label": "Franken", "abbreviation": "CHF"})
    ).json()
    item = (
        await client.post(
            "/api/v1/items", json={"category": "general_item", "label": "Zelt", "owner": "MV"}
        )
    ).json()
    await _invoice(client, item["id"], "A", 100.0, eur["id"], "2026-01-10", "Musikhaus")
    await _invoice(client, item["id"], "B", 50.0, eur["id"], "2026-02-01", "Alpha")
    await _invoice(client, item["id"], "C", 70.0, chf["id"], "2026-01-20", "Zeta")
    return {"eur": eur["id"], "chf": chf["id"], "item": item["id"]}


async def test_sort_by_amount_and_issuer_and_currency_filter(client, three_invoices):
    assert _titles(await client.get("/api/v1/invoices")) == ["B", "C", "A"]
    assert _titles(await client.get("/api/v1/invoices?order_by=amount")) == ["B", "C", "A"]
    assert _titles(await client.get("/api/v1/invoices?order_by=-invoice_issuer")) == [
        "C",
        "A",
        "B",
    ]
    resp = await client.get(f"/api/v1/invoices?currency_id={three_invoices['chf']}")
    assert _titles(resp) == ["C"]
    assert resp.json()["totals_by_currency"] == [{"abbreviation": "CHF", "total": 70.0}]
    assert resp.json()["items"][0]["invoice_issuer"] == "Zeta"


async def test_totals_cover_all_filtered_rows_not_just_the_page(client, three_invoices):
    body = (await client.get("/api/v1/invoices?limit=1")).json()
    assert len(body["items"]) == 1
    assert body["total"] == 3
    assert body["limit"] == 1 and body["offset"] == 0
    assert body["totals_by_currency"] == [
        {"abbreviation": "CHF", "total": 70.0},
        {"abbreviation": "EUR", "total": 150.0},
    ]


async def test_unknown_invoice_sort_key_is_422(client):
    assert (await client.get("/api/v1/invoices?order_by=title")).status_code == 422
```

Heißt das Feld für den Aussteller im Schema zum Anlegen einer Rechnung (`schemas/item_invoice.py`) nicht `invoice_issuer`, den Helfer anpassen; die Werte bleiben.

Die Summen sind jetzt nach Währungskürzel sortiert. Erwartet ein bestehender Summen-Test eine andere Reihenfolge, passt er die Erwartung an die alphabetische an.

- [ ] **Step 2: Tests laufen lassen, sie müssen scheitern**

Run: `IN_CONTAINER 'python -m pytest tests/backend/test_invoice_overview.py -q'`
Expected: FAIL.

- [ ] **Step 3: `filters/invoice.py`**

```python
"""Filter for GET /invoices."""

from __future__ import annotations

from datetime import date
from typing import Literal

from mv_hofki.filters.base import ListFilter
from mv_hofki.models.inventory_item import InventoryItem
from mv_hofki.models.item_invoice import ItemInvoice


class InvoiceFilter(ListFilter):
    item_category: Literal["instrument", "clothing", "sheet_music", "general_item"] | None = None
    date_issued__gte: date | None = None
    date_issued__lte: date | None = None
    currency_id: int | None = None

    class Constants(ListFilter.Constants):
        model = ItemInvoice
        search_model_fields = ["title", "invoice_issuer"]
        columns = {"item_category": InventoryItem.category}
        sort_fields = {
            "date_issued": [ItemInvoice.date_issued],
            "amount": [ItemInvoice.amount],
            "invoice_issuer": [ItemInvoice.invoice_issuer],
        }
        default_sort = ["-date_issued"]
```

- [ ] **Step 4: Schema, Service, Route**

`schemas/invoice_overview.py`:
- `InvoiceOverviewItem` bekommt `invoice_issuer: str | None = None`.
- `InvoiceOverviewResponse` bekommt `limit: int` und `offset: int`.

`services/invoice_overview.py`:
- `_build_filters` entfernen.
- `get_list` wird:

```python
async def get_list(
    session: AsyncSession, flt: InvoiceFilter, page: PageParams
) -> InvoiceOverviewResponse:
    base = select(ItemInvoice).join(InventoryItem, ItemInvoice.item_id == InventoryItem.id)
    filtered = flt.filter(base)

    # Totals over every filtered invoice, not only the loaded page.
    rows = filtered.order_by(None).subquery()
    totals_q = (
        select(Currency.abbreviation, func.sum(rows.c.amount))
        .select_from(rows)
        .join(Currency, Currency.id == rows.c.currency_id)
        .group_by(Currency.abbreviation)
        .order_by(Currency.abbreviation)
    )
    totals_by_currency = [
        CurrencyTotal(abbreviation=abbr, total=amount)
        for abbr, amount in (await session.execute(totals_q)).all()
    ]

    invoice_rows, total = await paginate(
        session, flt.sort(filtered), page, options=[joinedload(ItemInvoice.currency)]
    )
    # … der bestehende Block ab "item_ids = list({inv.item_id …})" bis zur
    # Liste `items` bleibt unverändert, ergänzt um
    #     invoice_issuer=inv.invoice_issuer,
    # im InvoiceOverviewItem(...).
    return InvoiceOverviewResponse(
        items=items,
        total=total,
        limit=page.limit,
        offset=page.offset,
        totals_by_currency=totals_by_currency,
    )
```

Imports: `PageParams`, `paginate`, `InvoiceFilter`; `date` wird nicht mehr gebraucht.

`api/routes/invoices.py`:

```python
@router.get("", response_model=InvoiceOverviewResponse)
async def list_invoices(
    flt: InvoiceFilter = FilterDepends(InvoiceFilter),
    page: PageParams = Depends(),
    db: AsyncSession = Depends(get_db),
) -> InvoiceOverviewResponse:
    return await invoice_overview_service.get_list(db, flt, page)
```

- [ ] **Step 5: Backend-Tests laufen lassen, sie müssen bestehen**

Run: `IN_CONTAINER 'python -m pytest tests/backend -q'`
Expected: nur die bekannten fremden Fehler.

- [ ] **Step 6: `InvoiceListPage.vue` neu**

```vue
<script setup>
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { get } from "../lib/api.js";
import { CATEGORIES } from "../lib/categories.js";
import { useListQuery } from "../composables/useListQuery.js";
import DataTable from "../components/DataTable.vue";
import SearchBar from "../components/SearchBar.vue";
import FilterBar from "../components/FilterBar.vue";
import InfiniteLoader from "../components/InfiniteLoader.vue";

const router = useRouter();
const currencies = ref([]);

const {
  state,
  sort,
  setSort,
  setFilter,
  defaults,
  activeFilterCount,
  items,
  total,
  lastResponse,
  loading,
  loadingMore,
  error,
  hasMore,
  loadMore,
  reload,
  resetFilters,
} = useListQuery({
  endpoint: "/invoices",
  filters: {
    search: { type: "string", default: "", debounce: true },
    item_category: { type: "string", default: "" },
    date_issued__gte: { type: "date", default: "" },
    date_issued__lte: { type: "date", default: "" },
    currency_id: { type: "number", default: null },
  },
  defaultSort: "-date_issued",
});

const filterDefs = computed(() => [
  {
    key: "item_category",
    label: "Inventar-Art",
    type: "select",
    options: ["instrument", "clothing", "general_item"].map((c) => ({
      value: c,
      label: CATEGORIES[c].label,
    })),
  },
  { keys: ["date_issued__gte", "date_issued__lte"], label: "Datum", type: "daterange" },
  {
    key: "currency_id",
    label: "Währung",
    type: "select",
    options: currencies.value.map((c) => ({ value: String(c.id), label: c.abbreviation })),
  },
]);

const filtered = computed(() => activeFilterCount.value > 0 || !!state.search.trim());
const totalsByCurrency = computed(() => lastResponse.value?.totals_by_currency || []);

const columns = [
  { key: "invoice_nr", label: "Nr.", class: "col-num" },
  { key: "item", label: "Gegenstand" },
  { key: "title", label: "Bezeichnung" },
  { key: "invoice_issuer", label: "Aussteller", sortKey: "invoice_issuer", hideEmptyInCard: true },
  { key: "date_issued", label: "Datum", sortKey: "date_issued" },
  { key: "amount", label: "Betrag", sortKey: "amount", class: "col-num" },
  { key: "filename", label: "Datei" },
];

function formatAmount(inv) {
  const n = Number(inv.amount).toLocaleString("de-AT", { minimumFractionDigits: 2 });
  return `${n} ${inv.currency?.abbreviation || ""}`;
}

function formatTotals() {
  return totalsByCurrency.value
    .map(
      (t) =>
        `${Number(t.total).toLocaleString("de-AT", { minimumFractionDigits: 2 })} ${t.abbreviation}`,
    )
    .join(" · ");
}

onMounted(async () => {
  try {
    currencies.value = await get("/currencies");
  } catch {
    currencies.value = [];
  }
});

function goToItem(inv) {
  const cat = CATEGORIES[inv.item_category];
  if (cat) router.push(cat.routeBase + "/" + inv.item_id);
}
</script>

<template>
  <div>
    <div class="page-header">
      <h1>Rechnungen</h1>
    </div>

    <div class="toolbar">
      <SearchBar v-model="state.search" placeholder="Suche (Titel, Aussteller …)" class="grow" />
    </div>

    <FilterBar :defs="filterDefs" :state="state" :defaults="defaults" @change="setFilter" @reset="resetFilters" />

    <div v-if="error && !items.length" class="alert alert-danger list-alert" role="alert">
      Rechnungen konnten nicht geladen werden: {{ error }}
      <button type="button" class="btn-sm" @click="reload">Erneut versuchen</button>
    </div>

    <template v-else>
      <p v-if="totalsByCurrency.length" class="invoice-totals">
        Gesamt ({{ total }} {{ total === 1 ? "Rechnung" : "Rechnungen" }}): {{ formatTotals() }}
      </p>

      <DataTable
        :columns="columns"
        :rows="items"
        :loading="loading"
        :card-breakpoint="640"
        :sort="sort"
        :empty-text="filtered ? 'Keine Rechnungen für diese Filter.' : 'Noch keine Rechnungen.'"
        @update:sort="setSort"
        @row-click="goToItem"
      >
        <template #item="{ row }">{{ row.item_display_nr }} {{ row.item_label }}</template>
        <template #amount="{ row }">{{ formatAmount(row) }}</template>
        <template #filename="{ row }">
          <span :class="row.filename ? 'badge badge-green' : 'badge badge-gray'">
            {{ row.filename ? "Ja" : "Nein" }}
          </span>
        </template>
      </DataTable>

      <p v-if="!loading && !items.length && filtered" class="empty-note">
        <button type="button" class="btn-sm" @click="resetFilters">Filter zurücksetzen</button>
      </p>

      <InfiniteLoader
        :has-more="hasMore"
        :loading="loadingMore"
        :error="items.length ? error : ''"
        :count="items.length"
        :total="total"
        @load-more="loadMore"
      />
    </template>
  </div>
</template>

<style scoped>
.invoice-totals {
  margin: 0 0 var(--space-3);
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius);
  background: var(--color-bg-soft);
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

:deep(td.col-num),
:deep(th.col-num) {
  text-align: right;
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}
</style>
```

Die Summenzeile steht bewusst über der Tabelle, weil beim Nachladen das Listenende wandert.

- [ ] **Step 7: Frontend-Tests, Build, Browser**

Run: `IN_CONTAINER 'cd src/frontend && npx vitest run && npx vite build'`

Browser `/rechnungen` (11 Rechnungen in der DB):
- Datum von–bis, Inventar-Art, Währung
- Sortieren nach Betrag und Aussteller
- Die Summe ändert sich mit den Filtern
- Handy-Breite und dunkles Theme

- [ ] **Step 8: Commit**

Message: `feat(invoices): fastapi-filter list with totals over the filtered set`.

---

### Task 8: Leihregister durchgehend, Auswahlfelder, Leihhistorien

**Files:**
- Create: `src/backend/mv_hofki/filters/loan.py`
- Modify: `src/backend/mv_hofki/services/loan.py:19-42` (`get_list`), `src/backend/mv_hofki/api/routes/loans.py:47-56` (`list_loans`)
- Modify: `src/frontend/src/pages/LoanListPage.vue` (Script und Template neu)
- Modify: `src/frontend/src/pages/ItemDetailPage.vue` (Leihen per `getAll`, Musiker-Select wird `RemotePicker`, `/musicians?limit=200` entfällt)
- Modify: `src/frontend/src/pages/MusicianDetailPage.vue:21` (Leihen per `getAll`)
- Test: `tests/backend/test_loans.py` (anpassen und ergänzen), `tests/backend/test_ai_import_importer.py:175-176` (Liste statt dict-oder-Liste)

**Interfaces:**
- Consumes: `display_nr_condition` (Task 6), `RemotePicker`, `fetchMusicianOptions`, `fetchLoanableItemOptions` (Task 4), `getAll` (Task 2).
- Produces: `GET /api/v1/loans?search&active&item_category&musician_id&item_id&order_by&limit&offset`, Antwort `PaginatedResponse[LoanRead]`.

- [ ] **Step 1: Failing tests**

In `tests/backend/test_loans.py`:
- Jeden bestehenden `GET /api/v1/loans`-Aufruf, der die Antwort als Liste liest, auf `resp.json()["items"]` umstellen.
- Anhängen:

```python
async def test_loan_filters_sort_and_search(client):
    tu = (
        await client.post("/api/v1/instrument-types", json={"label": "Tuba", "label_short": "TU"})
    ).json()
    hr = (
        await client.post("/api/v1/instrument-types", json={"label": "Horn", "label_short": "HR"})
    ).json()
    hat_type = (await client.post("/api/v1/clothing-types", json={"label": "Hut"})).json()

    async def item(**data):
        resp = await client.post("/api/v1/items", json=data)
        assert resp.status_code == 201, resp.text
        return resp.json()["id"]

    async def musician(first, last):
        resp = await client.post(
            "/api/v1/musicians", json={"first_name": first, "last_name": last}
        )
        return resp.json()["id"]

    async def lend(item_id, musician_id, start):
        resp = await client.post(
            "/api/v1/loans",
            json={"item_id": item_id, "musician_id": musician_id, "start_date": start},
        )
        assert resp.status_code == 201, resp.text
        return resp.json()["id"]

    tuba = await item(category="instrument", label="Tuba", instrument_type_id=tu["id"])
    hat = await item(category="clothing", label="Hut", clothing_type_id=hat_type["id"])
    horn = await item(category="instrument", label="Horn", instrument_type_id=hr["id"])
    anna_id = await musician("Anna", "Maier")
    berta_id = await musician("Berta", "Huber")
    await lend(tuba, anna_id, "2026-01-01")
    hat_loan = await lend(hat, anna_id, "2026-02-01")
    await client.put(f"/api/v1/loans/{hat_loan}/return", json={"end_date": "2026-03-01"})
    await lend(horn, berta_id, "2026-03-01")

    def labels(r):
        assert r.status_code == 200, r.text
        return [loan["item"]["label"] for loan in r.json()["items"]]

    assert labels(await client.get("/api/v1/loans")) == ["Horn", "Hut", "Tuba"]
    assert labels(await client.get("/api/v1/loans?active=true")) == ["Horn", "Tuba"]
    assert labels(await client.get("/api/v1/loans?active=false")) == ["Hut"]
    assert labels(await client.get("/api/v1/loans?item_category=clothing")) == ["Hut"]
    assert labels(await client.get(f"/api/v1/loans?musician_id={anna_id}")) == ["Hut", "Tuba"]
    assert labels(await client.get("/api/v1/loans?search=huber")) == ["Horn"]
    assert labels(await client.get("/api/v1/loans?search=tu-001")) == ["Tuba"]
    assert labels(await client.get("/api/v1/loans?order_by=start_date")) == [
        "Tuba", "Hut", "Horn",
    ]
    # NULL end dates last
    assert labels(await client.get("/api/v1/loans?order_by=-end_date")) == [
        "Hut", "Tuba", "Horn",
    ]
    body = (await client.get("/api/v1/loans?limit=2")).json()
    assert body["total"] == 3 and len(body["items"]) == 2
```

Die Reihenfolge bei `-end_date` ergibt sich so: Hut hat als einzige Leihe ein Enddatum. Tuba und Horn haben NULL, stehen deshalb am Ende und untereinander nach `id` (Tuba wurde zuerst angelegt).

In `tests/backend/test_ai_import_importer.py:175-176` die Unterscheidung „dict oder Liste“ durch `loans = resp.json()["items"]` ersetzen, bei unverändertem `limit=100`-Aufruf.

- [ ] **Step 2: Tests laufen lassen, sie müssen scheitern**

Run: `IN_CONTAINER 'python -m pytest tests/backend/test_loans.py -q'`
Expected: FAIL.

- [ ] **Step 3: `filters/loan.py`**

```python
"""Filter for GET /loans."""

from __future__ import annotations

from typing import Literal

from sqlalchemy import ColumnElement, Select, or_

from mv_hofki.filters.base import ListFilter
from mv_hofki.filters.inventory_item import display_nr_condition
from mv_hofki.models.inventory_item import InventoryItem
from mv_hofki.models.loan import Loan
from mv_hofki.models.musician import Musician


class LoanFilter(ListFilter):
    active: bool | None = None
    item_category: Literal["instrument", "clothing", "general_item"] | None = None
    musician_id: int | None = None
    item_id: int | None = None

    class Constants(ListFilter.Constants):
        model = Loan
        columns = {"item_category": InventoryItem.category}
        sort_fields = {
            "start_date": [Loan.start_date],
            "end_date": [Loan.end_date],
        }
        default_sort = ["-start_date"]

    def filter_active(self, query: Select, value: bool) -> Select:
        return query.where(
            Loan.end_date.is_(None) if value else Loan.end_date.is_not(None)
        )

    def search_clause(self, value: str) -> ColumnElement[bool] | None:
        value = value.strip()
        if not value:
            return None
        pattern = f"%{value}%"
        conditions: list[ColumnElement[bool]] = [
            InventoryItem.label.ilike(pattern),
            Musician.first_name.ilike(pattern),
            Musician.last_name.ilike(pattern),
        ]
        nr = display_nr_condition(value)
        if nr is not None:
            conditions.append(nr)
        return or_(*conditions)
```

- [ ] **Step 4: Service und Route**

`services/loan.py`, `get_list`:

```python
async def get_list(
    session: AsyncSession, flt: LoanFilter, page: PageParams
) -> tuple[list[Loan], int]:
    query = (
        select(Loan)
        .join(InventoryItem, Loan.item_id == InventoryItem.id)
        .join(Musician, Loan.musician_id == Musician.id)
    )
    return await paginate(session, flt.sort(flt.filter(query)), page)
```

Imports: `Musician`, `PageParams`, `paginate` und `LoanFilter`. Die Beziehungen `Loan.item` und `Loan.musician` laden über `lazy="joined"` weiterhin eager; `paginate` ruft `.unique()` auf.

`api/routes/loans.py`, `list_loans`:

```python
@router.get("", response_model=PaginatedResponse[LoanRead])
async def list_loans(
    flt: LoanFilter = FilterDepends(LoanFilter),
    page: PageParams = Depends(),
    db: AsyncSession = Depends(get_db),
):
    loans, total = await loan_service.get_list(db, flt, page)
    return PaginatedResponse(
        items=[_loan_to_read(loan) for loan in loans],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )
```

Imports: `PaginatedResponse`, `FilterDepends`, `PageParams` und `LoanFilter`.

- [ ] **Step 5: Backend-Tests laufen lassen, sie müssen bestehen**

Run: `IN_CONTAINER 'python -m pytest tests/backend -q'`
Expected: nur die bekannten fremden Fehler.

- [ ] **Step 6: Detailseiten**

- **`MusicianDetailPage.vue:21`:** `get(\`/loans?musician_id=${route.params.id}\`)` wird `getAll(\`/loans?musician_id=${route.params.id}\`)`, mit Import `getAll`. Die Weiterverarbeitung erwartete schon ein Array.
- **`ItemDetailPage.vue`:**
  - Zeile 58: `loans.value = await get(\`/loans?item_id=${props.id}\`)` wird `getAll(...)`.
  - `promises.push(get("/musicians?limit=200"))` (Zeile 98) samt Auswertung `musicians.value = results[1].items;` und dem Ref `musicians` entfernen. Liegen danach andere `results[…]`-Indizes falsch, diese anpassen.
  - Das Musiker-`<select>` im Ausleih-Formular (um Zeile 385) ersetzen durch:
    ```vue
    <RemotePicker
      v-model="<bisheriges v-model des selects>"
      :fetch-options="fetchMusicianOptions"
      label="Musiker"
      placeholder="Name eingeben …"
    />
    ```
    mit Import von `RemotePicker` und `fetchMusicianOptions` aus `../lib/pickers.js`. Ein vorhandenes `<label>` des Selects entfällt, denn `RemotePicker` bringt ein eigenes mit. Fehlertexte und Validierung des Formulars bleiben.

- [ ] **Step 7: `LoanListPage.vue` neu**

Die Funktionen `validateForm`, `createLoan`, `returnToday`, `returnWithDate` und die Rückgabe-Refs bleiben. Der Aufruf `load()` darin wird überall zu `reload()`. Neu bzw. ersetzt:

```js
import { computed, ref } from "vue";
import { get, post, put } from "../lib/api.js";
import { CATEGORIES } from "../lib/categories.js";
import { fetchLoanableItemOptions, fetchMusicianOptions } from "../lib/pickers.js";
import { useListQuery } from "../composables/useListQuery.js";
import DataTable from "../components/DataTable.vue";
import SearchBar from "../components/SearchBar.vue";
import FilterBar from "../components/FilterBar.vue";
import InfiniteLoader from "../components/InfiniteLoader.vue";
import RemotePicker from "../components/RemotePicker.vue";

const showForm = ref(false);
const form = ref({ item_id: null, musician_id: null, start_date: "" });
const formErrors = ref({});
const formError = ref("");
const returningLoanId = ref(null);
const returnDate = ref("");
const filterMusicianLabel = ref("");

const {
  state, sort, setSort, setFilter, defaults, activeFilterCount, items, total,
  loading, loadingMore, error, hasMore, loadMore, reload, resetFilters,
} = useListQuery({
  endpoint: "/loans",
  filters: {
    search: { type: "string", default: "", debounce: true },
    active: { type: "bool", default: true },
    item_category: { type: "string", default: "" },
    musician_id: { type: "number", default: null },
  },
  defaultSort: "-start_date",
});

const filterDefs = computed(() => [
  {
    key: "active",
    label: "Status",
    type: "segmented",
    options: [
      { value: true, label: "Offen" },
      { value: false, label: "Zurückgegeben" },
      { value: null, label: "Alle" },
    ],
  },
  {
    key: "item_category",
    label: "Inventar-Art",
    type: "select",
    options: ["instrument", "clothing", "general_item"].map((c) => ({
      value: c,
      label: CATEGORIES[c].label,
    })),
  },
]);

const filtered = computed(
  () => activeFilterCount.value > 0 || !!state.search.trim(),
);

const columns = [
  { key: "item", label: "Gegenstand" },
  { key: "display_nr", label: "Inv.-Nr." },
  { key: "musician", label: "Musiker" },
  { key: "start_date", label: "Von", sortKey: "start_date" },
  { key: "end_date", label: "Bis", sortKey: "end_date" },
  { key: "status", label: "Status" },
  { key: "actions", label: "" },
];

// Musician filter from the URL: show the name in the picker.
if (state.musician_id != null) {
  get(`/musicians/${state.musician_id}`)
    .then((m) => (filterMusicianLabel.value = `${m.last_name} ${m.first_name}`))
    .catch(() => (filterMusicianLabel.value = ""));
}

function itemRouteBase(category) {
  return CATEGORIES[category]?.routeBase || "/instrumente";
}
```

- `createLoan`: das `alert` durch `formError.value = e.message` ersetzen; vor jedem Versuch `formError.value = ""`.
- Zusätzlich `const actionError = ref("");`. `returnToday` und `returnWithDate` bekommen ein `try/catch`: vorher `actionError.value = ""`, im catch `actionError.value = \`Rückgabe fehlgeschlagen: ${e.message}\``. Im Template steht direkt über der Tabelle `<p v-if="actionError" class="form-error" role="alert">{{ actionError }}</p>`.

**Template:**
- **Formular „Neue Ausleihe“:** die zwei `<select>` samt ihrer `<label>` ersetzen durch
  ```vue
  <RemotePicker v-model="form.item_id" :fetch-options="fetchLoanableItemOptions" label="Gegenstand *" placeholder="Nummer oder Bezeichnung …" />
  <RemotePicker v-model="form.musician_id" :fetch-options="fetchMusicianOptions" label="Musiker *" placeholder="Name …" />
  ```
  in denselben `.form-group`-Containern mit ihren Fehlertexten. Unter den Buttons steht `<p v-if="formError" class="form-error" role="alert">{{ formError }}</p>`.
- **Toolbar:** Die Checkbox „Nur aktive Leihen“ entfällt. Stattdessen `<SearchBar v-model="state.search" placeholder="Suche (Gegenstand, Nummer, Musiker …)" class="grow" />` und
  ```vue
  <RemotePicker
    class="loan-musician-filter"
    :model-value="state.musician_id"
    :selected-label="filterMusicianLabel"
    :fetch-options="(t) => fetchMusicianOptions(t, { activeOnly: false })"
    label="Musiker"
    placeholder="Alle Musiker"
    @update:model-value="setFilter('musician_id', $event)"
    @select="(o) => (filterMusicianLabel = o.label)"
  />
  ```
- **Danach:** `<FilterBar … />`, das Fehler-Banner (`error && !items.length`) und `DataTable` mit `:rows="items"`, `:sort`, `@update:sort="setSort"`, `:card-breakpoint="640"` und `:empty-text="filtered ? 'Keine Leihen für diese Filter.' : 'Noch keine Leihen.'"`.
- **Slots:**
  - `#item`: `router-link` auf das Item mit `row.item.label`.
  - `#display_nr`: `{{ row.item.display_nr }}`.
  - `#musician`: `router-link` auf `/musiker/${row.musician.id}` mit Vor- und Nachname.
  - `#end_date`: `{{ row.end_date || "—" }}`.
  - `#status`: das Badge wie bisher.
  - `#actions`: der bisherige Rückgabe-Block. Zur Rückgabe gehören die Buttons „Heute“ und „Datum“; sie bekommen `@click.stop`, damit kein Zeilenklick ausgelöst wird.
- **Am Ende:** `InfiniteLoader` wie in den anderen Seiten.
- **Nach dem Anlegen einer Leihe:** `reload()`.

Style:

```css
.loan-musician-filter {
  min-width: 14rem;
}
```

- [ ] **Step 8: Frontend-Tests, Build, Browser**

Run: `IN_CONTAINER 'cd src/frontend && npx vitest run && npx vite build'`

Browser `/leihen` (125 Leihen in der DB, nur lesen und filtern, **keine** Leihe anlegen oder zurückgeben):
1. Offen, Zurückgegeben und Alle; Inventar-Art; der Musiker-Filter per `RemotePicker` setzt `musician_id` in der URL, und nach dem Neuladen steht der Name im Feld.
2. Suche „tu“ zeigt Tuben.
3. Sortieren nach Von und Bis; Nachladen bis „… von …“.
4. „Neue Ausleihe“ öffnen: Der Gegenstand-Picker findet bei „tu“ verfügbare Tuben; der Musiker-Picker findet Namen. **Nicht absenden.**
5. Eine Instrument-Detailseite: Die Leihhistorie ist vollständig, und der Musiker-Picker im Ausleih-Formular funktioniert. **Nicht absenden.**
6. Eine Musiker-Detailseite mit Leihen: Die Historie ist vollständig.
7. Handy-Breite: Die Leihen erscheinen als Karten, „Heute“ und „Datum“ sind bedienbar. Dazu das dunkle Theme.

- [ ] **Step 9: Commit**

Message: `feat(loans): fastapi-filter list, search pickers for new loans, full histories`.
