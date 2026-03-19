# Phase 2: Mehrere Inventar-Kategorien

**Datum:** 2026-03-19
**Status:** Entwurf

## Zusammenfassung

Das Inventarsystem wird von reiner Instrumentenverwaltung auf vier Kategorien erweitert:
- **Instrumente** (bestehend)
- **Kleidung** (Tracht)
- **Noten** (als Paket: Partitur + Einzelstimmen)
- **Allgemeine Gegenstände** (Lautsprecher, Kabel, Notenständer, etc.)

Architektur: Gemeinsame Basis-Tabelle `inventory_item` mit kategorie-spezifischen Detail-Tabellen (1:1).

## Datenmodell

### `inventory_item` (Basis-Tabelle)

| Feld | Typ | Beschreibung |
|------|-----|-------------|
| id | INTEGER PK AUTO | |
| category | VARCHAR NOT NULL | `instrument`, `clothing`, `sheet_music`, `general_item` |
| inventory_nr | INTEGER NOT NULL | Fortlaufend pro Kategorie |
| label | VARCHAR NOT NULL | Hauptbezeichnung |
| manufacturer | VARCHAR NULL | Hersteller |
| acquisition_date | DATE NULL | Anschaffungsdatum |
| acquisition_cost | DECIMAL(10,2) NULL | Kosten |
| currency_id | FK → currency NULL | |
| owner | VARCHAR NOT NULL | Default: "MV Hofkirchen" |
| notes | TEXT NULL | |
| created_at | DATETIME DEFAULT now() | |

**Constraint:** `UNIQUE(category, inventory_nr)`

### `instrument_detail` (1:1 → inventory_item)

| Feld | Typ | Beschreibung |
|------|-----|-------------|
| id | INTEGER PK AUTO | |
| item_id | FK → inventory_item UNIQUE NOT NULL | |
| instrument_type_id | FK → instrument_type NOT NULL | |
| label_addition | VARCHAR NULL | Zusatzbezeichnung |
| serial_nr | VARCHAR NULL | Seriennummer |
| construction_year | INTEGER NULL | Baujahr |
| distributor | VARCHAR NULL | Händler |
| container | VARCHAR NULL | Koffer/Etui |
| particularities | TEXT NULL | Besonderheiten |

### `clothing_detail` (1:1 → inventory_item)

| Feld | Typ | Beschreibung |
|------|-----|-------------|
| id | INTEGER PK AUTO | |
| item_id | FK → inventory_item UNIQUE NOT NULL | |
| clothing_type_id | FK → clothing_type NOT NULL | Typ (Hut, Jacke, etc.) |
| size | VARCHAR NULL | Größe |
| gender | VARCHAR NULL | `Herren`, `Damen`, oder NULL |

### `sheet_music_detail` (1:1 → inventory_item)

| Feld | Typ | Beschreibung |
|------|-----|-------------|
| id | INTEGER PK AUTO | |
| item_id | FK → inventory_item UNIQUE NOT NULL | |
| title | VARCHAR NOT NULL | Titel des Stücks |
| composer | VARCHAR NULL | Komponist |
| arranger | VARCHAR NULL | Arrangeur |
| difficulty | VARCHAR NULL | Schwierigkeitsgrad |
| genre_id | FK → sheet_music_genre NULL | Gattung |

**Hinweis:** Noten werden als ganzes Paket (Partitur + alle Einzelstimmen) erfasst. Digitale Archivierung einzelner Stimmen ist als spätere Erweiterung (Phase 3) vorgesehen.

### `general_item_detail` (1:1 → inventory_item)

| Feld | Typ | Beschreibung |
|------|-----|-------------|
| id | INTEGER PK AUTO | |
| item_id | FK → inventory_item UNIQUE NOT NULL | |
| general_item_type_id | FK → general_item_type NOT NULL | Typ (Lautsprecher, etc.) |

## Lookup-Tabellen (Seed-Daten)

### `clothing_type`

| id | label |
|----|-------|
| 1 | Hut |
| 2 | Jacke |
| 3 | Hose |
| 4 | Weste |
| 5 | Schuhe |
| 6 | Bluse |
| 7 | Rock |
| 8 | Strümpfe |

### `sheet_music_genre`

| id | label |
|----|-------|
| 1 | Marsch |
| 2 | Polka |
| 3 | Walzer |
| 4 | Konzertwerk |
| 5 | Kirchenmusik |

### `general_item_type`

| id | label |
|----|-------|
| 1 | Lautsprecher |
| 2 | Kabel |
| 3 | Notenständer |
| 4 | Mischpult |
| 5 | Mikrofon |
| 6 | Verstärker |

### `instrument_type`

Bleibt wie bisher (20 Einträge).

### `currency`

Bleibt wie bisher (4 Einträge: EUR, ATS, USD, GBP).

## Inventarnummern

Jede Kategorie hat einen eigenen Nummernkreis mit Präfix:

| Kategorie | Präfix | Beispiel |
|-----------|--------|----------|
| Instrument | `I` | I-001 |
| Kleidung | `K` | K-001 |
| Noten | `N` | N-001 |
| Allgemein | `A` | A-001 |

- `inventory_nr` in der DB ist ein reiner Integer
- Anzeige-Format: `{prefix}-{nr:03d}` (im Code zusammengebaut)
- Auto-Assignment: `MAX(inventory_nr) + 1` gefiltert nach `category`

## Bestehende Tabellen — Umbau

| Alt | Neu | Änderung |
|-----|-----|----------|
| `instrument_image` | `item_image` | `instrument_id` → `item_id` FK → inventory_item |
| `instrument_invoice` | `item_invoice` | `instrument_id` → `item_id` FK → inventory_item |
| `loan_register` | `loan_register` | `instrument_id` → `item_id` FK → inventory_item |

### Kategorie-Einschränkungen

| Feature | Verfügbar für |
|---------|--------------|
| Bilder | Alle Kategorien |
| Rechnungen | Instrumente, Kleidung, Allgemeine Gegenstände (nicht Noten) |
| Ausleihe | Instrumente, Kleidung, Allgemeine Gegenstände (nicht Noten) |

Validierung auf App-Ebene im Service-Layer.

## Migrationsstrategie

Bestehende Daten werden nicht migriert (können gelöscht werden). Daher:

1. Alte Tabellen droppen: `instrument`, `instrument_image`, `instrument_invoice`, `loan_register`
2. Neue Tabellen erstellen: `inventory_item`, `instrument_detail`, `clothing_detail`, `sheet_music_detail`, `general_item_detail`, `item_image`, `item_invoice`, `loan_register` (neu), Lookup-Tabellen
3. Seed-Daten einspielen: bestehende Types + neue Lookup-Typen + Currencies
4. Upload-Ordner leeren: `data/uploads/`
5. Eine einzige Alembic-Migration

## Service-Layer

### Generischer `inventory_item` Service

- `create(category, base_data, detail_data)` — Erstellt Item + Detail in einer Transaktion, auto-assigns inventory_nr
- `get_list(category, search, filters, pagination)` — Listet Items mit Detail-Join, Enrichment (active_loan, profile_image_url)
- `get_by_id(id)` — Item + Detail + active_loan + profile_image
- `update(id, base_data, detail_data)` — Aktualisiert Basis + Detail
- `delete(id)` — Löscht Item + Detail + zugehörige Bilder/Rechnungen/Loans

### Angepasste Services

- `loan` — `instrument_id` → `item_id`, Validierung: Kategorie != `sheet_music`
- `item_image` — wie `instrument_image`, aber mit `item_id`
- `item_invoice` — wie `instrument_invoice`, aber mit `item_id`, Validierung: Kategorie != `sheet_music`

## Offene Punkte (Zukunft)

- **Phase 3:** Digitale Archivierung einzelner Noten-Stimmen (Unterstruktur zu sheet_music_detail)
