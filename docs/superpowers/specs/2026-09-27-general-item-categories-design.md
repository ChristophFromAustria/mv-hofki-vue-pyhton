# Kategorien für Allgemeine Items — Design

Datum: 2026-09-27
Teilprojekt 1 von 4 der Überarbeitung „Filter, Gruppierung, Listen und Detailseiten“
(2: Listen-Infrastruktur mit fastapi-filter + Endlos-Scrollen, 3: Listen-Darstellung mit
Gruppierung/kompakten Karten/Sammelzuweisung, 4: einklappbare Detailseiten + Inline-Editor).

## Ziel

Allgemeine Items (`category = "general_item"`, 164 Stück, Nummern `A-xxx`) sind eine bunte
Mischung (Schaukasten, Gläser, Scheinwerfer, Schlagwerk …) ohne jede Einordnung. Sie bekommen
frei pflegbare Kategorien, damit sie später gefiltert und gruppiert werden können.

## Entscheidungen (vom Benutzer bestätigt)

- **Mehrere Kategorien pro Item (Tags), optional.** Ein Item kann keine, eine oder mehrere haben.
- **Nur für Allgemeine Items.** Instrumente, Kleidung und Noten behalten Typ bzw. Genre.
- **Inventarnummer unverändert.** Kategorien beeinflussen `number_prefix`/`inventory_nr` nicht;
  Nummern bleiben `A-xxx`, auch beim Ändern von Kategorien.
- **Anlegen an zwei Stellen:** Verwaltungsseite unter Einstellungen *und* direkt im Item-Formular.
- **Bestand:** einmaliger Zuordnungsvorschlag für die 164 Items, vom Benutzer geprüft, dann per
  Skript eingespielt. Sammelzuweisung in der Liste folgt in Teilprojekt 3.

## Datenmodell

Neue Tabellen (Alembic-Migration):

```
general_item_categories
  id          INTEGER PK
  label       VARCHAR(50) NOT NULL UNIQUE

general_item_category_links
  item_id     INTEGER NOT NULL FK inventory_items.id  ON DELETE CASCADE
  category_id INTEGER NOT NULL FK general_item_categories.id ON DELETE CASCADE
  PRIMARY KEY (item_id, category_id)
```

- ORM: `GeneralItemCategory` in `models/general_item_category.py`; Assoziationstabelle als
  `Table` im selben Modul. `InventoryItem` bekommt keine neue Spalte.
- Kein Seed: die Tabelle startet leer; Startkategorien kommen über das Bestandsskript.
- Labels werden getrimmt; leere Labels → 422. Eindeutigkeit ohne Rücksicht auf Groß-/Kleinschreibung
  wird im Service geprüft (`func.lower(label)`) → 409 „Kategorie existiert bereits“.
- SQLite erzwingt `ON DELETE CASCADE` nur mit `PRAGMA foreign_keys=ON`. Der Service löscht
  Verknüpfungen deshalb explizit, statt sich auf die DB zu verlassen.

## Backend-API

### `/api/v1/general-item-categories`

Nach dem Muster von `clothing_types` (Route, Service, Schema je eigenes Modul).

| Methode | Pfad | Verhalten |
|---|---|---|
| GET | `` | Liste sortiert nach `label`, jeweils mit `item_count` |
| POST | `` | `{label}` → 201; Duplikat → 409 |
| GET | `/{id}` | 404 wenn unbekannt |
| PUT | `/{id}` | `{label}` umbenennen; Duplikat → 409 |
| DELETE | `/{id}` | 204; entfernt die Kategorie auch von allen Items (kein 409 wie bei Kleidungstypen) |

`GeneralItemCategoryRead`: `{id, label, item_count}`.

### Items (`/api/v1/items`)

- **Anlegen/Ändern** (`general_item`): optionales Feld `category_ids: list[int]`.
  - Beim Anlegen fehlt es → keine Kategorien.
  - Beim Ändern fehlt es → Kategorien bleiben unverändert; `[]` → alle entfernen; sonst ersetzt die
    Liste die bisherige Zuordnung. Doppelte IDs werden zusammengefasst.
  - Unbekannte IDs → 422 mit Hinweis „Unbekannte Kategorie“.
  - `category_ids` bei anderen Inventar-Arten → 422. Die Pydantic-Schemas ignorieren unbekannte
    Felder, daher prüft die Route das explizit.
- **Lesen** (Liste und Detail, nur `general_item`): `categories: [{id, label}]`, sortiert nach Label.
  In der Liste werden die Kategorien für alle Items der Seite mit **einer** Abfrage geladen
  (`WHERE item_id IN (...)`), nicht pro Item.
- Keine Filter-Parameter in diesem Teilprojekt (kommt mit fastapi-filter in Teilprojekt 2).

## Frontend

### Einstellungsseite

- Route `/einstellungen/kategorien`, Seite `GeneralItemCategoryListPage.vue`, Eintrag im
  Einstellungs-Menü der `NavBar` („Kategorien (Allgemein)“).
- Aufbau wie `ClothingTypeListPage.vue` (Anlegen, Umbenennen inline, Löschen), zusätzliche Spalte
  „Gegenstände“ mit `item_count`.
- Löschen mit `ConfirmDialog`; bei `item_count > 0` lautet der Text z.B.
  „Die Kategorie „Deko“ wird von 12 Gegenständen entfernt.“
- Fehler (409 Duplikat) inline am Eingabefeld, kein `alert()`.

### `TagSelect.vue` (neue Komponente)

Mehrfachauswahl mit Anlegen, für das Item-Formular.

- Props: `modelValue: number[]` (IDs), `options: {id,label}[]`, `label: string`.
  Emits: `update:modelValue`, `create(label)` → Elternkomponente legt an und gibt die neue Option
  zurück (Promise), die dann ausgewählt wird.
- Gewählte Kategorien als Chips mit Entfernen-Button (`aria-label="„Deko“ entfernen"`).
- Eingabefeld als Combobox (ARIA `combobox`/`listbox`): Tippen filtert Vorschläge (ohne bereits
  gewählte, Groß-/Kleinschreibung egal); ist kein exakter Treffer vorhanden, erscheint als letzte
  Option „„Xyz“ als neue Kategorie anlegen“.
- Tastatur: ↑/↓ bewegt, Enter wählt/legt an, Escape schließt, Backspace in leerem Feld entfernt den
  letzten Chip.
- Touch-Ziele ≥ 44 px; Farben/Radien nur aus `style.css`-Tokens; Chips funktionieren in Hell und Dunkel.
- Fehler beim Anlegen erscheinen unter dem Feld.

### Item-Formular, Detailseite, Liste

- `ItemFormModal.vue`: für `general_item` ein `TagSelect` „Kategorien“ unter „Bezeichnung“. Die
  Optionen lädt das Formular von `/general-item-categories`. Gesendet wird `category_ids`.
- `lib/categories.js`: `general_item` bekommt `hasCategories: true`, damit Seiten dies abfragen
  statt auf den Kategorie-Schlüssel zu prüfen.
- `ItemDetailPage.vue`: in den Stammdaten eine Zeile „Kategorien“ mit Chips; ohne Kategorien „—“.
- `ItemListPage.vue`: Spalte „Kategorien“ (Chips, `hideEmptyInCard`), ebenso in der Bilder-Kartenansicht
  unter der Bezeichnung.
- Eine kleine gemeinsame Chip-Darstellung (`CategoryChips.vue`) für Detail, Liste und `TagSelect`.

## Bestandsübernahme (einmalig)

1. Ein Skript liest alle 164 Items (Nummer, Bezeichnung, Lagerort) und erzeugt eine Vorschlagsdatei
   `data/general_item_categories_proposal.csv` (Spalten `display_nr;label;storage_location;categories`,
   Kategorien durch `|` getrennt). Die Vorschläge erstellt Claude anhand der Bezeichnungen mit einem
   Startsatz von ca. 8–12 Kategorien.
2. Der Benutzer prüft und korrigiert die CSV.
3. `scripts/apply_general_item_categories.py <csv>` legt fehlende Kategorien an und setzt die
   Zuordnungen (ersetzt bestehende Zuordnung je Item). Idempotent, meldet unbekannte Nummern, ändert
   nichts anderes. Läuft im Devcontainer mit der normalen DB-Konfiguration.

Das Skript bleibt im Repo (klein, wiederverwendbar für spätere Massenkorrekturen); die CSV nicht.

## Nicht Teil dieses Teilprojekts

- Filtern nach Kategorie in der API/Liste (Teilprojekt 2).
- Gruppieren nach Kategorie und Sammelzuweisung per Mehrfachauswahl (Teilprojekt 3). Offene Frage
  dort: bei mehreren Kategorien erscheint ein Item in jeder seiner Gruppen.
- Inline-Bearbeitung in der Detailseite (Teilprojekt 4); bis dahin über `ItemFormModal`.

## Tests

- Backend (`tests/backend/test_general_item_categories.py`): CRUD, `item_count`, Duplikat
  case-insensitiv → 409, leeres Label → 422, Löschen entfernt Verknüpfungen.
- Backend (`tests/backend/test_items.py`): Anlegen mit `category_ids`, Ändern ersetzt / `[]` leert /
  fehlend lässt unverändert, unbekannte ID → 422, `category_ids` bei Instrument → 422, Liste liefert
  `categories`, Löschen eines Items entfernt Verknüpfungen.
- Backend: Test für das Übernahmeskript (CSV → Zuordnung, idempotent, unbekannte Nummer gemeldet).
- Frontend (`tests/frontend/TagSelect.test.js`): Filtern, Auswählen, Entfernen, Anlegen-Option nur
  ohne exakten Treffer, Tastatursteuerung, `create`-Ablauf.
