# Inventarsystem Phase 1 — Design

## Ziel

Inventarverwaltung für den Musikverein Hofkirchen. Phase 1 umfasst: Instrumente, Instrumententypen, Musiker, Leihregister, Währungen und ein Dashboard.

## Rahmenbedingungen

- **Keine Authentifizierung** — Zugang wird extern über Cloudflare Tunnel gesichert
- **Sprache:** UI komplett Deutsch, Code/Variablen Englisch
- **Datenbank:** SQLite (statt MS SQL aus dem Original-Schema)
- **Stack:** FastAPI + SQLAlchemy async + Vue 3

## Datenmodell

Portierung des bestehenden MS-SQL-Schemas auf SQLite/SQLAlchemy. Phase-2-Tabellen (files, instrument_pictures, instrument_invoices) werden nicht angelegt. `creator_id` entfällt (kein Login).

### Tabellen

**currencies**
- id (PK, autoincrement)
- label (string, 100)
- abbreviation (string, 100)

**instrument_types**
- id (PK, autoincrement)
- label (string, 255)
- label_short (string, 100)
- created_at (datetime, default utcnow)

**instruments**
- id (PK, autoincrement)
- inventory_nr (integer, not null)
- label_addition (string, 100)
- manufacturer (string, 100)
- serial_nr (string, 100)
- construction_year (date, nullable)
- acquisition_date (date, nullable)
- acquisition_cost (float, nullable)
- currency_id (FK → currencies.id, not null)
- distributor (string, 100)
- container (string, 100)
- particularities (string, 100)
- owner (string, 100, not null)
- notes (string, 100)
- instrument_type_id (FK → instrument_types.id, not null)
- created_at (datetime, default utcnow)

**musicians**
- id (PK, autoincrement)
- first_name (string, 100, not empty)
- last_name (string, 100, not empty)
- phone (string, 100)
- email (string, 100)
- street_address (string, 100)
- postal_code (integer, nullable)
- city (string, 100)
- is_extern (boolean, not null)
- notes (text)
- created_at (datetime, default utcnow)

**loan_register**
- id (PK, autoincrement)
- instrument_id (FK → instruments.id, not null)
- musician_id (FK → musicians.id, not null)
- start_date (date, not null)
- end_date (date, nullable — null = aktiv ausgeliehen)
- created_at (datetime, default utcnow)

### Seed-Daten

**instrument_types:** Querflöte (FL), Klarinette in Es (KL), Klarinette in B (KL), Bassklarinette (KL), Fagott (FA), Oboe (OB), Englischhorn (OB), Flügelhorn (FH), Saxophon (SA), Altsaxophon (SA), Tenorsaxophon (SA), Baritonsaxophon (SA), Trompete (TR), Tenorhorn (TE), Bariton (TE), Euphonium (TE), Horn (WH), Posaune (PO), Tuba (TU), Schlagwerk (SW)

**currencies:** Euro (€), Schilling (ATS), Dollar ($), Pfund (£)

## API-Endpunkte

Alle unter `/api/v1/`.

### Dashboard
- `GET /dashboard` — Kennzahlen: Anzahl Instrumente, Musiker, aktive Leihen, Instrumente nach Typ

### Instrumententypen
- `GET /instrument-types` — Liste aller Typen
- `POST /instrument-types` — Neuen Typ anlegen
- `GET /instrument-types/{id}` — Einzelner Typ
- `PUT /instrument-types/{id}` — Typ bearbeiten
- `DELETE /instrument-types/{id}` — Typ löschen (nur wenn keine Instrumente zugeordnet)

### Währungen
- `GET /currencies` — Liste aller Währungen
- `POST /currencies` — Neue Währung anlegen
- `GET /currencies/{id}` — Einzelne Währung
- `PUT /currencies/{id}` — Währung bearbeiten
- `DELETE /currencies/{id}` — Währung löschen (nur wenn nicht verwendet)

### Instrumente
- `GET /instruments?limit=&offset=&search=&type_id=` — Paginierte Liste mit optionaler Suche/Filter
- `POST /instruments` — Neues Instrument anlegen
- `GET /instruments/{id}` — Einzelnes Instrument mit Typ-Info und aktiver Leihe
- `PUT /instruments/{id}` — Instrument bearbeiten
- `DELETE /instruments/{id}` — Instrument löschen

### Musiker
- `GET /musicians?limit=&offset=&search=` — Paginierte Liste mit Suche
- `POST /musicians` — Neuen Musiker anlegen
- `GET /musicians/{id}` — Einzelner Musiker mit aktiven Leihen
- `PUT /musicians/{id}` — Musiker bearbeiten
- `DELETE /musicians/{id}` — Musiker löschen (nur wenn keine aktiven Leihen)

### Leihregister
- `GET /loans?active=true&instrument_id=&musician_id=` — Leihen filtern
- `POST /loans` — Neue Ausleihe anlegen
- `GET /loans/{id}` — Einzelne Leihe
- `PUT /loans/{id}` — Leihe bearbeiten
- `PUT /loans/{id}/return` — Instrument zurückgeben (setzt end_date)

## Frontend-Seiten

### Navigation
Hauptnavigation: Dashboard | Instrumente | Musiker | Leihregister | Einstellungen (Dropdown: Instrumententypen, Währungen)

### Seiten

| Route | Seite | Beschreibung |
|---|---|---|
| `/` | Dashboard | Kennzahlen-Kacheln, Schnellzugriff |
| `/instrumente` | Instrumentenliste | Tabelle mit Filter nach Typ, Suche |
| `/instrumente/neu` | Instrument anlegen | Formular |
| `/instrumente/:id` | Instrument Detail | Detailansicht mit Leihhistorie |
| `/instrumente/:id/bearbeiten` | Instrument bearbeiten | Formular |
| `/musiker` | Musikerliste | Tabelle mit Suche |
| `/musiker/neu` | Musiker anlegen | Formular |
| `/musiker/:id` | Musiker Detail | Detailansicht mit Leihen |
| `/musiker/:id/bearbeiten` | Musiker bearbeiten | Formular |
| `/leihen` | Leihregister | Aktive Leihen + Historie |
| `/einstellungen/instrumententypen` | Instrumententypen | CRUD-Verwaltung |
| `/einstellungen/waehrungen` | Währungen | CRUD-Verwaltung |

### UI-Stil
Einfach und funktional. Tabellen für Listen, Formulare für Eingabe. Keine externe UI-Library — aufbauend auf dem bestehenden CSS des Templates.

## Technische Details

- **ORM:** SQLAlchemy 2.0 mit async Engine (aiosqlite)
- **Migrationen:** Alembic (async)
- **DB-Pfad:** `data/mv_hofki.db`
- **Validation:** Pydantic v2 Schemas
- **Seed:** Instrumententypen und Währungen bei erster Migration
- **Frontend State:** Kein Pinia — einfache fetch-Calls über bestehende `api.js`
- **Pagination:** limit/offset mit Gesamtanzahl im Response
