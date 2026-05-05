# Inventarsystem MV Hofkirchen — Status

## Phase 1: Kern (ABGESCHLOSSEN)

Alles aus der Phase-1-Spec ist umgesetzt und getestet:
- Instrumententypen CRUD + Seed-Daten (20 Typen)
- Währungen CRUD + Seed-Daten (4 Währungen)
- Instrumente CRUD mit auto-increment Inventarnummer, Suche, Pagination
- Musiker CRUD mit Suche, Pagination
- Leihregister mit Duplikat-Prüfung, Rückgabe (mit Datumsauswahl)
- Dashboard mit Kennzahlen
- 44 Backend-Tests, alle grün

### Zusätzlich implementiert (über Phase-1-Spec hinaus):
- Dark/Light Mode
- Karten-/Listenansicht für Instrumente mit SVG-Platzhalter-Icons
- Formvalidierung mit rotem Rand statt Browser-Validierung
- Default-Werte (Eigentümer "MV Hofkirchen", Währung Euro)
- Leihe direkt aus Instrument-Detailseite
- Textsuche nach Instrumententyp

## Phase 2: Dateiverwaltung und Bilder (IN ARBEIT)

### Bereits umgesetzt:
- **instrument_images Tabelle** — DB-Model, Migration, Service, API-Routen
- **Bildupload** — `POST /api/v1/instruments/{id}/images` (JPEG, PNG, WebP, GIF, max 10MB)
- **Profilbild** — Erstes Bild wird automatisch Profilbild, umschaltbar
- **Bildergalerie** — ImageGallery.vue Komponente mit Prev/Next, Thumbnails, Modal-Großansicht
- **Profilbilder in Listen** — Kartenansicht zeigt Profilbild (Fallback auf SVG-Icon)
- **Leihstatus in Listen** — Badges "Ausgeliehen"/"Verfügbar" + "Extern" in Tabelle und Karten
- Statische Bildauslieferung über `/uploads/`

### Noch offen (Phase 2):
- **files Tabelle** — Allgemeine Dateiverwaltung (aus Original-Schema)
- **instrument_invoices** — Rechnungen zu Instrumenten
- Erweiterte Features (Reports, Export)

## Technischer Stand

- **Backend:** FastAPI + SQLAlchemy 2.0 async + SQLite (`data/mv_hofki.db`)
- **Frontend:** Vue 3 + Vue Router, keine UI-Library
- **Tests:** 44 Backend-Tests (pytest-asyncio)
- **DB-Migrationen:** Alembic (2 Migrationen: initial + instrument_images)
- **Bilder:** Lokal unter `data/uploads/instruments/{id}/`
