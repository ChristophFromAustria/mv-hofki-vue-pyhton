# Inventarsystem Verbesserungen — Design

## Ziel

4 gezielte Verbesserungen am bestehenden Inventarsystem Phase 1.

## Änderung 1: Inventarnummer auto-increment

**Backend:**
- `inventory_nr` wird beim Erstellen automatisch vergeben: `SELECT MAX(inventory_nr) + 1` (oder 1 bei leerem Bestand)
- `inventory_nr` aus `InstrumentCreate` Schema entfernen
- `inventory_nr` aus `InstrumentUpdate` Schema entfernen
- Service `instrument.create()` setzt `inventory_nr` automatisch

**Frontend:**
- Feld "Inventarnummer" aus `InstrumentFormPage.vue` entfernen
- Inventarnummer bleibt in Detailansicht und Listen sichtbar (read-only)

**Tests:**
- Bestehende Tests anpassen (kein `inventory_nr` mehr im POST-Body)
- Test: Automatische Vergabe aufsteigender Nummern

## Änderung 2: Leihe direkt aus Instrument-Detail

**InstrumentDetailPage.vue** bekommt einen neuen Abschnitt oberhalb der Leihhistorie:

- **Wenn ausgeliehen:** Zeigt aktuellen Leiher (Name, Link), Leihdatum, und "Rückgabe"-Aktion (siehe Änderung 3)
- **Wenn verfügbar:** Inline-Formular mit Musiker-Dropdown, Datums-Feld, "Ausleihen"-Button

Nach Ausleihe/Rückgabe wird die Seite neu geladen (Daten aktualisieren).

## Änderung 3: Rückgabe mit Datumsauswahl

**Backend:**
- `PUT /loans/{id}/return` akzeptiert optionalen Body `{ "end_date": "2026-03-15" }`
- Ohne Body oder `end_date: null` → `date.today()`
- Schema: `LoanReturn` mit `end_date: date | None = None`

**Frontend (überall wo Rückgabe möglich):**
- Beim Klick auf "Rückgabe" erscheint Inline-UI mit:
  - Button "Heute" → sofortige Rückgabe
  - Button "Datum wählen" → zeigt Datepicker, dann Bestätigung
- Betrifft: `InstrumentDetailPage.vue` (neu) und `LoanListPage.vue` (bestehend)

## Änderung 4: Karten-/Listenansicht mit Profilbild

**InstrumentListPage.vue:**
- Toggle-Buttons (Liste/Karten) in der Toolbar
- Auswahl in `localStorage` unter `instrument-view-mode` gespeichert
- Standardansicht: Liste (wie bisher)

**Kartenansicht:**
- CSS Grid, 3 Spalten
- Karte: Platzhalter-Bild oben, darunter Instrumententyp, Inv.-Nr., Hersteller, Leihstatus-Badge

**Platzhalter-Bild:**
- Neue Komponente `InstrumentIcon.vue`
- Generierter SVG: Grauer Hintergrund mit dem `label_short` des Typs als großer Text (z.B. "FL", "TR", "KL")
- Unterschiedliche Hintergrundfarben pro `label_short` (deterministisch aus String-Hash)

**Neue Styles:**
- `.instrument-grid` — CSS Grid für Kartenansicht
- `.instrument-card` — Einzelne Karte
