# Gruppierung, kompakte Karten, Sammelzuweisung: Design

Datum: 2026-09-27
Teilprojekt 3 von 4 der Überarbeitung „Filter, Gruppierung, Listen und Detailseiten“.
Voraussetzung ist Teilprojekt 2 (Listen-Infrastruktur mit `ListFilter`, `useListQuery`, `FilterBar`, `DataTable`).

## Ziel

- Listen lassen sich nach einem Merkmal gruppieren, mit einklappbaren Gruppenüberschriften und Anzahl.
- Instrumente sind standardmäßig nach Typ gruppiert.
- Am Handy wird die Kartenansicht der Items kompakt: ein kleines Bild links, der Text rechts.
- Allgemeine Items bekommen Kategorien per Mehrfachauswahl zugewiesen oder entfernt.

## Entscheidungen (vom Benutzer bestätigt)

- **Umfang:** gruppierbar sind die Inventar-Listen, Musiker und das Leihregister, nicht die Rechnungen.
- **Mehrfach-Zuordnungen** (Kategorien, Register): Ein Eintrag erscheint in **jeder** seiner Gruppen. Einträge ohne Zuordnung stehen in einer Gruppe „Ohne …“ am Ende.

## Gruppierungen je Liste

`group_by` ist ein URL- und API-Parameter wie die Filter. Fehlt er, gilt der Standard der Liste; „keine“ wird in der URL als `group_by=alle` gespeichert, wenn der Standard nicht leer ist.

| Liste | `group_by` | Gruppe, Reihenfolge | leere Gruppe | Standard |
|---|---|---|---|---|
| Instrumente | `type` | Instrumententyp, nach Label | – | **`type`** |
| | `status` | Ausgeliehen / Verfügbar | – | |
| | `owner` | Eigentümer | „Ohne Eigentümer“ | |
| Kleidung | `type` | Kleidungstyp | – | keine |
| | `size` | Größe | „Ohne Größe“ | |
| | `status` | wie oben | – | |
| Noten | `genre` | Gattung | „Ohne Gattung“ | keine |
| Allgemein | `category` (mehrfach) | Kategorie | „Ohne Kategorie“ | keine |
| | `room` | erster Teil des Lagerorts vor „ / “ (z.B. „Sesselarchiv (Boden/oben)“) | „Ohne Lagerort“ | |
| | `status` | wie oben | – | |
| Musiker | `register` (mehrfach) | Register, nach `sort_order` | „Ohne Register“ | keine |
| | `status` | Aktiv, dann Inaktiv | – | |
| Leihregister | `musician` | „Nachname Vorname“ | – | keine |
| | `item_category` | Instrumente / Kleidung / Allgemein | – | |
| | `status` | Offen, dann Zurückgegeben | – | |

## Backend

### `filters/base.py`

- **`GroupSpec`** (Dataclass):
  - `key`, `label` und optional `order` sind SQL-Ausdrücke. Ohne `order` wird nach `label` sortiert.
  - `empty_label` ist der Text für die NULL-Gruppe.
  - `join(query)` fügt nötige Outer Joins hinzu.
  - `multi` markiert, dass eine Zeile pro Zuordnung entsteht.
- **`ListFilter.group_by: str | None`:** geprüft gegen `Constants.group_fields`; ein unbekannter Wert ergibt 422 „„x“ ist keine gültige Gruppierung.“. `group_spec()` liefert die Spec; Unterklassen dürfen überschreiben, etwa `type` je Item-Art.
- **`async fetch_page(session, flt, query, page, *, options=()) -> ListPage`:**
  - Filtert und zählt `item_total` (verschiedene Einträge).
  - **Ohne Gruppe:** wie bisher `paginate`.
  - **Mit Gruppe:**
    - Die Abfrage bekommt die Joins der Spec sowie die Spalten `group_key`, `group_label` und `group_order`.
    - Sortiert wird zuerst nach `group_order` (NULL zuletzt), dann nach `group_key`, dann nach der Benutzer-Sortierung, zuletzt nach `id`.
    - `total` = Anzahl Zeilen, für das Nachladen.
    - `groups` = `[{key, label, count}]` über alle gefilterten Zeilen in derselben Reihenfolge; `count` zählt verschiedene Einträge.
- **Schlüssel:** Gruppenschlüssel sind im JSON immer Strings; die NULL-Gruppe hat den Schlüssel `""`.

### Antwort

`PaginatedResponse` bekommt optional:
- `item_total: int | None`
- `groups: list[{key: str, label: str, count: int}] | None`

Jede Zeile bekommt bei aktiver Gruppierung `group_key` und `group_label`. Für Musiker und Leihen gibt es dafür Zeilen-Schemas `MusicianListRow` und `LoanListRow` (das Lese-Schema plus die zwei Felder). Items sind schon Dicts.

### Items

- `ItemFilter.bind(category)` prüft `group_by` gegen die erlaubten Gruppen der Art. Ist eine Gruppe nicht erlaubt, gibt es 422 „Gruppierung „x“ gibt es für <Art> nicht“.
- `type` wird wie `sort_columns("type")` je Art aufgelöst.
- Der Lagerort-Raum ist `NULLIF(TRIM(SUBSTR(storage_location, 1, INSTR(storage_location || ' /', ' /') - 1)), '')`. Das ist SQLite-spezifisch, was hier genügt.

### Sammelzuweisung

**`POST /api/v1/items/bulk-categories`** mit `{item_ids: int[1..500], add_ids: int[] = [], remove_ids: int[] = []}`:

**Prüfungen, jede ergibt 422:**
- `add_ids` und `remove_ids` sind beide leer: „Keine Kategorien angegeben“.
- Eine ID steht in beiden Listen: „Kategorie kann nicht gleichzeitig hinzugefügt und entfernt werden“.
- Ein Item existiert nicht oder ist kein allgemeiner Gegenstand: „Nur allgemeine Gegenstände: <ids>“.
- Eine Kategorie ist unbekannt: wie bisher „Unbekannte Kategorie: …“.

**Wirkung:**
- Fehlende Verknüpfungen werden angelegt, zu entfernende gelöscht, alles in einer Transaktion.
- Die Antwort ist `{updated: <Anzahl Items>}`.

## Frontend

- **`useListQuery`:** liefert zusätzlich `groups` und `itemTotal` (aus der letzten Antwort). Jede Zeile bekommt `_key` = `"<group_key>:<id>"` bei Gruppierung, sonst die `id`.
- **`lib/grouping.js`:** `buildSegments(rows, groups, collapsed)` erzeugt `[{type:"group", …} | {type:"row", …}]`.
  - Vor jeder neuen `group_key`-Folge steht ein Gruppen-Segment.
  - Zeilen eingeklappter Gruppen fallen weg, die Überschrift bleibt.
  - Die Anzahl kommt aus `groups`.
- **`composables/useGroupCollapse(storageKey)`:** eingeklappte Gruppen je Liste und Gruppierung, gespeichert in `localStorage`. Lesen und Schreiben sind in `try/catch`, damit die Seite auch ohne Storage funktioniert.
- **`GroupHeader.vue`:** eine Schaltfläche mit `aria-expanded`, Pfeil, Label und Anzahl, mindestens 44 px hoch.
- **`GroupSelect.vue`:** „Gruppieren nach“, eine Auswahl mit „Keine“, wie `SortSelect`.
- **`DataTable`:**
  - Neue Props: `groups`, `collapsedGroups`, `selectable`, `selectedIds`.
  - Neue Events: `toggle-group(key)`, `toggle-select(row)`.
  - Die Zeilen-Keys werden `row._key ?? row.id`.
  - In der Tabelle ist eine Gruppe eine `<tr>` mit `<th colspan scope="rowgroup">`, in der Kartenansicht eine Überschrift.
  - Im Auswahlmodus gibt es eine Checkbox-Spalte (`aria-label` „„<Bezeichnung>“ auswählen“). Ein Klick auf die Zeile wählt dann aus, statt zu navigieren; das entscheidet die Seite über `row-click`.
- **`ItemCard.vue`** (neu, aus ItemListPage herausgelöst):
  - Normal ist die Karte ein `RouterLink`, also eine echte Verknüpfung. Im Auswahlmodus ist sie ein `<label>` mit Checkbox.
  - **Bis 640 px:** eine Zeile mit 56-px-Bild bzw. Platzhalter links, rechts Bezeichnung, Nummer · Hersteller, Kategorien und Status.
  - **Darüber:** das bisherige Kachel-Raster.
- **ItemListPage:**
  - `group_by` je Art, Standard `type` bei Instrumenten.
  - `GroupSelect` in der Toolbar.
  - Gruppen in Tabelle und Karten.
  - Nur bei Allgemein: die Schaltfläche „Auswählen“ und die Sammelzuweisung.
- **Sammelzuweisung (Oberfläche):**
  - **`BulkCategoryBar.vue`:** Leiste unten, sticky, mit „n ausgewählt“, „Alle geladenen auswählen“, „Kategorien hinzufügen“, „Kategorien entfernen“ und „Fertig“. Status und Fehler stehen inline.
  - **`CategoryPickDialog.vue`:** ein natives `<dialog>` mit Checkbox-Liste. „Hinzufügen“ bzw. „Entfernen“ ist erst aktiv, wenn mindestens eine Kategorie gewählt ist.
  - **Ablauf:** Nach Erfolg erscheint „12 Gegenstände aktualisiert.“, die Auswahl wird geleert und die Liste neu geladen.
- **MusicianListPage, LoanListPage:** `GroupSelect` und Gruppen in `DataTable`.

## Zustände

- Eingeklappte Gruppen zeigen weiter ihre Anzahl.
- Sind alle geladenen Gruppen eingeklappt, lädt `InfiniteLoader` weiter nach, weil das Listenende sichtbar ist.
- Die Sammelzuweisung sperrt ihre Schaltflächen, solange eine Anfrage läuft.

## Nicht Teil dieses Teilprojekts

- Detailseiten (Teilprojekt 4).
- Gruppieren der Rechnungen.
- Andere Sammelaktionen (z.B. Löschen, Lagerort ändern).

## Tests

**Backend:**
- `fetch_page` mit einer Test-Filterklasse: Einfach- und Mehrfachgruppen, Zähler, NULL-Gruppe am Ende, Nachladen über Mehrfachzeilen ohne Lücken oder Doppelte, `item_total`, ungültiges `group_by`.
- Je Liste die Gruppierungen und die 422 bei unpassender Gruppe für eine Item-Art.
- Sammelzuweisung: Erfolg und jeder Fehlerfall.

**Frontend:**
- `buildSegments`, `useGroupCollapse`, `GroupHeader`, `GroupSelect`
- `DataTable` mit Gruppen, Einklappen und Auswahl
- `ItemCard`, `BulkCategoryBar`, `CategoryPickDialog`
- `useListQuery` mit `_key` und `groups`

**Browser:** alle Listen bei Desktop-Breite und 390 px, im hellen und dunklen Theme; die Sammelzuweisung einmal mit Test-Kategorie und Test-Auswahl, danach vollständig rückgängig gemacht.
