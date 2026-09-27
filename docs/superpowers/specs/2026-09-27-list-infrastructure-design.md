# Listen-Infrastruktur: Filter, Sortierung, Nachladen: Design

Datum: 2026-09-27
Teilprojekt 2 von 4 der Überarbeitung „Filter, Gruppierung, Listen und Detailseiten“.
Die anderen Teilprojekte:
1. Kategorien für Allgemeine Items (erledigt)
3. Gruppierung und kompakte Karten
4. Detailseiten

## Ziel

Die Inventar-Listen bekommen einheitliche, in der URL gespeicherte Filter und eine Sortierung. Statt Zurück/Weiter wird beim Scrollen automatisch nachgeladen. Die API verwendet dafür `fastapi-filter` (ähnlich OData: `feld__operator=wert`, `order_by=-feld`).

Außerdem werden Auswahlfelder, die heute still bei 200 Einträgen abschneiden, durch eine Suche mit Vorschlägen bzw. durch vollständiges Laden ersetzt.

## Entscheidungen (vom Benutzer bestätigt)

- **Umfang:**
  - Umgestellt werden Items (alle 4 Arten), Musiker, Rechnungen und Leihregister, dazu die `limit=200`-Auswahlfelder.
  - Scan-Projekte: nur der Fehler „ab Projekt 51 unsichtbar“ wird behoben.
  - Symbolbibliothek und KI-Import-Sitzungen folgen später.
- **Oberfläche:**
  - Passende Filter je Liste, als Auswahl oder Chips. Kein generischer Filter-Builder.
  - Die Filter stehen in der URL.
  - Sortiert wird per Klick auf den Spaltenkopf; in der Kartenansicht über ein Auswahlfeld.
- **Nachladen:** beim Scrollen, kein virtuelles Scrollen.

## Filter und Sortierung je Liste

„Sortierschlüssel“ sind die öffentlichen Namen in `order_by`. Ein `-` davor kehrt die Richtung um. Die Standardsortierung ist fett.

| Liste | Filter-Parameter | Sortierschlüssel |
|---|---|---|
| Instrumente | `search`, `instrument_type_id__in`, `status`, `owner`, `construction_year__gte`, `construction_year__lte` | **`number`**, `type`, `manufacturer`, `construction_year` |
| Kleidung | `search`, `clothing_type_id__in`, `size`, `gender`, `status` | **`number`**, `type`, `size` |
| Noten | `search`, `genre_id__in`, `difficulty`, `storage_location__ilike` | **`number`**, `label`, `composer` |
| Allgemein | `search`, `category_id__in`, `without_category`, `storage_location__ilike`, `status` | **`number`**, `label`, `storage_location` |
| Musiker | `search`, `is_active`, `register_id__in`, `is_extern` | **`last_name`**, `first_name` |
| Rechnungen | `search`, `item_category`, `date_issued__gte`, `date_issued__lte`, `currency_id` | **`-date_issued`**, `amount`, `invoice_issuer` |
| Leihregister | `search`, `active`, `item_category`, `musician_id`, `item_id` | **`-start_date`**, `end_date` |

### Bedeutung der Filter

- **`status`:** `verfuegbar` bedeutet, das Item hat keine offene Leihe (`end_date IS NULL`); `verliehen` bedeutet, es hat eine.
- **`category_id__in` und `without_category`:** Beide gesetzt heißt ODER, also „hat eine dieser Kategorien *oder* hat gar keine“.
- **`storage_location__ilike`:** Der Wert wird als „enthält“ behandelt. Die API setzt die `%` selbst, der Client schickt nur den Text.
- **`search`:**
  - Items: wie bisher Bezeichnung, Hersteller, Notizen sowie die Inventarnummer (`TU-002`, `tu 2`).
  - Musiker: Vor- und Nachname, E-Mail, Ort.
  - Rechnungen: Titel und Aussteller.
  - Leihregister: Bezeichnung und Inventarnummer des Items sowie Vor- und Nachname des Musikers.
- **Musiker `is_active`:** fehlt der Parameter, heißt das „alle“. Die Oberfläche setzt standardmäßig `true` (wie heute).
- **Leihregister `active`:** `true` = offen, `false` = zurückgegeben, fehlt = alle. Standard in der Oberfläche: `true`.
- **Sortierung nach Text:** Sie bleibt wie bisher binär (SQLite-Standard), Umlaute landen also hinter „Z“. Das ist eine bekannte Einschränkung und kein Ziel dieses Teilprojekts.

### Sortierschlüssel

- `number` = `number_prefix`, dann `inventory_nr`.
- `type` = Label des Instrumenten- bzw. Kleidungstyps (verknüpfte Tabelle).
- NULL-Werte stehen immer am Ende.
- `id` wird immer als letzter Schlüssel angehängt. Damit ist die Reihenfolge eindeutig, und beim Nachladen erscheint nichts doppelt und nichts fehlt.

## Backend

### Abhängigkeit

`fastapi-filter[sqlalchemy]>=3,<4` kommt in `pyproject.toml`. Getestet ist 3.0.0 mit FastAPI 0.141, Pydantic 2.13 und SQLAlchemy 2.0.

### `mv_hofki/api/listing.py` (neu)

- **`ListFilter(fastapi_filter.contrib.sqlalchemy.Filter)`:** gemeinsame Basis mit diesen Konventionen:
  - **`Constants.columns: dict[str, ColumnElement]`:** ordnet einen öffentlichen Feldnamen einer Spalte zu, auch in verknüpften Tabellen. Ohne Eintrag gilt die Spalte gleichen Namens am `Constants.model`.
  - **Eigene Filter:** Eine Methode `filter_<feldname>(query, value)` behandelt ein Feld selbst, z.B. `status`, `without_category` oder `register_id__in`.
  - **Suche:** `search_clause(value) -> ColumnElement` (Standard: ilike über `Constants.search_model_fields`).
  - **`Constants.sort_fields: dict[str, list[ColumnElement]]`:** öffentliche Sortierschlüssel.
    - `order_by` wird dagegen geprüft; ein unbekannter Schlüssel ergibt 422.
    - `Constants.default_sort: list[str]` gilt, wenn `order_by` fehlt.
    - `sort()` sortiert immer mit NULL-Werten am Ende und hängt die `id` des Modells an.
  - **Operatoren:** wie bei fastapi-filter (`__in`, `__gte`, `__lte`, `__ilike`, `__isnull`, `__neq`).
    - Bei `__ilike` ergänzt die Basis `%…%`, wenn kein `%` enthalten ist. Die Warnung der Bibliothek unterbleibt dadurch.
- **`PageParams`** als Dependency: `limit` (Standard 50, 1–200) und `offset` (≥ 0).
- **`async paginate(session, query, page) -> tuple[list, int]`:** zählt über die gefilterte Abfrage (ohne Sortierung) und lädt die Seite.

### Endpunkte

Alle Antworten haben die Form `{items, total, limit, offset}` (`PaginatedResponse`). Die Rechnungen haben zusätzlich `totals_by_currency`.

**`GET /api/v1/items?category=…`:**
- Eine Filterklasse `ItemFilter` mit allen Feldern der Tabelle oben.
- Ein Filter oder Sortierschlüssel, der nicht zur gewählten Kategorie passt, ergibt 422 „Filter „size“ gibt es für Instrumente nicht“.
- Die Detailtabelle der Kategorie wird per Join eingebunden: InstrumentDetail + InstrumentType, ClothingDetail + ClothingType, SheetMusicDetail als Outer Join.
- Die Detaildaten werden für die ganze Seite in **einer** Abfrage geladen, nicht mehr pro Item (N+1 entfällt).

**`GET /api/v1/items/facets?category=…` (neu):** liefert die Auswahlwerte für die Filterfelder als sortierte, eindeutige Werte ohne NULL/leer. Welche Schlüssel kommen, hängt von der Kategorie ab:

| Kategorie | Schlüssel |
|---|---|
| instrument | `owners` |
| clothing | `sizes`, `genders` |
| sheet_music | `difficulties` |
| general_item | keine |

**`GET /api/v1/musicians`:**
- `MusicianFilter`.
- Die alten Parameter `active` und `register_id` entfallen; ihre Nachfolger sind `is_active` und `register_id__in`.

**`GET /api/v1/invoices`:**
- `InvoiceFilter`.
- `category` wird zu `item_category`; `date_from` und `date_to` werden zu `date_issued__gte` und `date_issued__lte`.
- `totals_by_currency` wird über alle gefilterten Rechnungen berechnet, nicht nur über die Seite.
- Die Antwort bekommt zusätzlich `limit` und `offset`.

**`GET /api/v1/loans`:**
- `LoanFilter`.
- Die Antwort ist jetzt paginiert, früher war es eine Liste.
- Die bestehenden Aufrufer (Detailseiten mit `item_id`/`musician_id`) werden umgestellt.

## Frontend

### `lib/api.js`

- **`getAll(path)`:** holt alle Seiten mit `limit=200`, bis `total` erreicht ist, und gibt ein Array zurück.
- Pfade, die schon `?` enthalten, bekommen `&limit=…&offset=…` angehängt.

### `composables/useListQuery.js` (neu)

```
useListQuery({ endpoint, filters, defaultSort, pageSize = 50, baseParams, mapItem })
→ { state, sort, items, total, loading, loadingMore, error, hasMore,
    loadMore, reload, resetFilters, activeFilterCount }
```

**Parameter:**
- **`filters`:** ein Objekt `{ key: { type, default } }` mit `type` aus `string | list | bool | number | date`. Der Schlüssel ist gleichzeitig der API-Parameter und der URL-Parameter.
- **`baseParams`:** eine Funktion, die feste Parameter liefert (z.B. `category`). Ändert sich ihr Ergebnis, wird neu geladen.

**Verhalten:**
- **URL:** Der Zustand wird mit `router.replace` in die URL geschrieben, bei Standardwerten ohne den Parameter.
  - Listen werden mit Komma getrennt, Booleans als `true`/`false` geschrieben.
  - Ein Standardwert, der nicht leer ist, wird beim Abwählen als `alle` geschrieben. Damit übersteht „alle“ ein Neuladen.
  - Ändert sich die URL von außen (Zurück-Taste), wird der Zustand übernommen und neu geladen.
- **Suche:** `search` wird 300 ms verzögert, alle anderen Filter sofort.
- **Neu laden:** Jede Änderung von Filter oder Sortierung setzt die Liste zurück und lädt die erste Seite.
- **Veraltete Antworten:** Eine Folgenummer pro Anfrage verwirft ältere Antworten.
- **`loadMore()`:** hängt die nächste Seite an. Läuft bereits eine Anfrage, wird der Aufruf ignoriert.
- **Fehler:** Ein Fehler bleibt sichtbar. Beim Nachladen bleiben die schon geladenen Einträge stehen.

### Komponenten

- **`InfiniteLoader.vue`:** ein Element am Listenende mit `IntersectionObserver` (Rand 400 px). Es löst `load-more` aus, wenn `hasMore` gilt und nichts lädt.
  - Es zeigt „50 von 157“, „Wird geladen …“ oder eine Schaltfläche „Weitere laden“. Die Schaltfläche ist ein Rückfall für Tastatur und falls der Observer fehlt.
  - Bei einem Fehler zeigt es den Text und „Erneut versuchen“.
- **`FilterBar.vue`:** bekommt `defs` (Filterfelder) und `v-model` (Zustand).
  - Feldtypen: `select`, `multiselect` (Checkbox-Liste in einem Aufklapp-Menü), `segmented` (Umschalter wie heute Aktiv/Inaktiv/Alle), `text`, `range` (von–bis), `daterange`.
  - Aktive Filter erscheinen als Chips mit Entfernen-Button, dazu „Filter zurücksetzen“.
  - Bis 640 px klappt die Leiste hinter eine Schaltfläche „Filter (n)“. Die Suche bleibt immer sichtbar.
- **`SortSelect.vue`:** Auswahl des Sortierschlüssels plus Umschalter für die Richtung. Gedacht für Kartenansichten.
- **`DataTable.vue`:** Neue Props `sort` (z.B. `-construction_year`) und `sortKey` pro Spalte.
  - Sortierbare Spaltenköpfe sind `<button>`s mit `aria-sort` und lösen `update:sort` aus.
  - Ein Klick auf die aktive Spalte kehrt die Richtung um.
  - In der Kartenansicht rendert `DataTable` ein `SortSelect`, wenn Spalten sortierbar sind.
- **`RemotePicker.vue`:** Auswahl eines Eintrags per Suche mit Vorschlägen (Combobox-Muster wie `TagSelect`).
  - Die Vorschläge kommen von `fetchOptions(text)` und werden 250 ms verzögert geholt, höchstens 20.
  - Props: `modelValue` (id oder null), `fetchOptions`, `label`, `placeholder`.
  - Emits: `update:modelValue`, `select(option)`.
  - Die gewählte Option erscheint als Text im Feld; ✕ leert die Auswahl.

### Seiten

- **ItemListPage:**
  - Filterfelder je Kategorie wie in der Tabelle oben.
  - Die Optionen kommen von `/instrument-types`, `/clothing-types`, `/sheet-music-genres`, `/general-item-categories` und `/items/facets`.
  - Tabelle mit sortierbaren Spalten. In der Kartenansicht gibt es `SortSelect`; das Karten-Grid bleibt sonst unverändert.
  - Das Blätter-Markup entfällt.
- **MusicianListPage:**
  - Die bisherige URL-Logik in `lib/musicians.js` (`parseActiveFilter`, `activeFilterQueryValue`, `parseRegisterFilter`, `buildMusicianQuery`) wird durch `useListQuery` ersetzt; `registerLabels` bleibt.
  - Der neue Filter „Extern“ kommt dazu.
  - Alte Links mit `?active=`/`?register=` müssen nicht weiter funktionieren.
- **InvoiceListPage:** Filterfelder und `InfiniteLoader`; die Summenzeile bezieht sich auf alle gefilterten Rechnungen.
- **LoanListPage:**
  - Filterfelder: offen/zurückgegeben/alle, Inventar-Art, Musiker (`RemotePicker`), Suche.
  - Nachladen per `InfiniteLoader`.
  - Im Formular „Neue Ausleihe“ werden die zwei `<select>` zu `RemotePicker`s:
    - **Gegenstand:** sucht in den drei verleihbaren Arten mit `status=verfuegbar`, je 7 Treffer. Beschriftung „TU-002 Tuba“.
    - **Musiker:** sucht in den aktiven Musikern.
- **ItemDetailPage:** Die Musikerauswahl beim Verleihen wird ein `RemotePicker`; die Leihhistorie wird mit `getAll` geladen.
- **MusicianDetailPage:** Die Leihhistorie wird mit `getAll` geladen.
- **ImportSessionPage:** Die Musikerliste wird mit `getAll("/musicians")` geladen.
- **ScanProjectListPage und ScanProjectDetailPage:** Die Projekte werden mit `getAll("/scanner/projects")` geladen.

### Zustände (Grundsatz „Tell the truth about state“)

Es gibt vier getrennt sichtbare Zustände:
- **Erstes Laden:** Spinner.
- **Keine Treffer:** „Keine Einträge für diese Filter.“ mit „Filter zurücksetzen“, bzw. „Noch keine Einträge“ ohne Filter.
- **Fehler:** inline mit „Erneut versuchen“.
- **Nachladen:** Anzeige unter der Liste.

## Nicht Teil dieses Teilprojekts

- Gruppierung, kompakte Karten und Sammelzuweisung (Teilprojekt 3).
- Scan-Bereiche, Symbolbibliothek und KI-Import-Liste als Listen-UI.
- Sortierung mit Umlauten (Kollation).

## Tests

**Backend:**
- `ListFilter` für sich: Spaltenzuordnung, eigene Filter-Methode, `ilike` mit automatischem `%`, unbekannter Sortierschlüssel ergibt 422, Standardsortierung, `id` als letzter Schlüssel, NULL-Werte am Ende.
- Je Endpunkt: jeder Filter, eine Kombination, jeder Sortierschlüssel, Nachladen über zwei Seiten ohne Lücken oder Doppelte bei gleichen Sortwerten.
- `/items`: 422 bei unpassendem Filter, `/items/facets` je Kategorie.
- Rechnungen: Summen über alle gefilterten Rechnungen, nicht nur die Seite.
- Die bestehenden Tests werden an die neuen Parameternamen und die neue Antwortform der Leihen angepasst.

**Frontend (Vitest):**
- `useListQuery`: URL hin und zurück, verzögerte Suche, veraltete Antwort verworfen, `loadMore` hängt an, Zurücksetzen.
- `getAll`: mehrere Seiten, Pfad mit `?`.
- `FilterBar`: Chips, Zurücksetzen, Mehrfachauswahl.
- `DataTable`: Sortierköpfe und `aria-sort`.
- `RemotePicker`: Verzögerung, Tastatur, Auswahl, Leeren.
- `InfiniteLoader`: Schaltfläche und Observer.

**Browser:** Jede umgestellte Seite wird am Desktop und bei 390 px Breite geprüft, im hellen und dunklen Theme.
