# Inventarsystem Verbesserungen Runde 2 — Design

## 1. Default-Werte beim Erstellen

- **Eigentümer:** Feld mit "MV Hofkirchen" vorausgefüllt in InstrumentFormPage
- **Währung:** Euro als Default (Währung mit Abkürzung "€")
- Rein Frontend, kein Backend-Änderung

## 2. Formvalidierung mit rotem Rand

- Alle Formulare: Beim Klick auf "Speichern" werden leere Pflichtfelder mit rotem Rand markiert
- Neue CSS-Klasse `.form-group.error input` mit rotem Border + kurze Fehlermeldung darunter
- Kein `alert()` oder native Browser-Validierung mehr
- Betrifft: InstrumentFormPage, MusicianFormPage, Inline-Formulare (LoanListPage, InstrumentDetailPage loan form)

## 3. Bilduploads für Instrumente

### Backend

**Neue DB-Tabelle `instrument_images`:**
- id (PK, autoincrement)
- instrument_id (FK → instruments.id, not null)
- filename (string, 255, not null)
- is_profile (boolean, default false)
- created_at (datetime, default utcnow)

**Speicherort:** `data/uploads/instruments/{instrument_id}/{filename}`

**Neue API-Endpunkte:**
- `POST /api/v1/instruments/{id}/images` — Multipart file upload, speichert Datei + DB-Eintrag
- `GET /api/v1/instruments/{id}/images` — Liste aller Bilder eines Instruments
- `PUT /api/v1/instruments/{id}/images/{image_id}/profile` — Als Profilbild setzen (setzt alle anderen is_profile=false)
- `DELETE /api/v1/instruments/{id}/images/{image_id}` — Bild löschen (Datei + DB)

**Statische Auslieferung:** FastAPI mountet `data/uploads` als StaticFiles unter `/uploads/`

**Neues ORM Model:** `InstrumentImage` in `models/instrument_image.py`
**Neuer Service:** `services/instrument_image.py`
**Neue Routes:** `routes/instrument_images.py`
**Neue Schemas:** `schemas/instrument_image.py` — InstrumentImageRead mit id, instrument_id, filename, is_profile, url (computed)

### Frontend — InstrumentDetailPage

- Bildergalerie oben auf der Seite mit Links/Rechts-Pfeil-Buttons
- Wenn keine Bilder: großer Platzhalter mit Plus-Icon, klick → Upload
- Klick auf Bild → Modal mit Großansicht
- Unter Galerie: "Als Profilbild" + "Löschen" Buttons
- Upload via hidden `<input type="file" accept="image/*">`
- Neue Komponente: `ImageGallery.vue`

### Frontend — Listen/Karten

- Kartenansicht: Profilbild statt SVG-Icon (Fallback auf InstrumentIcon)
- Tabellenansicht: kleines Thumbnail (40x40) in erster Spalte

## 4. Leihstatus in Instrumentenliste

### Backend
- `GET /instruments` Response erweitern: neues Feld `active_loan` im InstrumentRead
  - Entweder `null` (verfügbar) oder Objekt mit `musician_name`, `musician_id`, `is_extern`, `start_date`
- Dafür: Instrument-Service lädt aktive Leihe mit (LEFT JOIN auf loan_register WHERE end_date IS NULL)

### Frontend
- **Tabelle:** Neue Spalte "Status" mit Badge "Ausgeliehen" / "Verfügbar" + "Extern" Badge wenn zutreffend
- **Karten:** Status-Badge im Footer

## 5. Textsuche nach Instrumententyp

- Backend: `instrument.get_list()` Suchfilter erweitern um `InstrumentType.label.ilike(pattern)` via JOIN
- Bestehendes `or_()` um diese Bedingung ergänzen
- Kein Frontend-Änderung nötig

## Alembic Migration

Eine neue Migration für die `instrument_images` Tabelle.

## Dateien-Übersicht

### Neue Dateien
- `src/backend/mv_hofki/models/instrument_image.py`
- `src/backend/mv_hofki/schemas/instrument_image.py`
- `src/backend/mv_hofki/services/instrument_image.py`
- `src/backend/mv_hofki/api/routes/instrument_images.py`
- `src/frontend/src/components/ImageGallery.vue`
- `data/uploads/.gitkeep`

### Geänderte Dateien
- `src/backend/mv_hofki/models/__init__.py` — InstrumentImage re-export
- `src/backend/mv_hofki/schemas/instrument.py` — active_loan Feld in InstrumentRead
- `src/backend/mv_hofki/services/instrument.py` — Suche + active_loan laden
- `src/backend/mv_hofki/api/app.py` — neue Router + uploads StaticFiles mount
- `src/frontend/src/style.css` — .form-group.error, Galerie-Styles
- `src/frontend/src/pages/InstrumentFormPage.vue` — Defaults + Validierung
- `src/frontend/src/pages/MusicianFormPage.vue` — Validierung
- `src/frontend/src/pages/InstrumentDetailPage.vue` — Galerie + Upload
- `src/frontend/src/pages/InstrumentListPage.vue` — Status-Badges, Thumbnail
- `src/frontend/src/pages/LoanListPage.vue` — Validierung im Inline-Formular
