# Scan Analysis Reset

**Datum:** 2026-04-07

## Zusammenfassung

Bestehenden `PUT /scans/{scan_id}/reset-status` Endpoint erweitern, um Analysedaten zu loeschen und den Scan-Status zurueckzusetzen. Im Frontend einen Reset-Button pro Scan-Thumbnail auf der ScanProjectDetailPage hinzufuegen.

## Backend: Endpoint erweitern

**Endpoint:** `PUT /scans/{scan_id}/reset-status` in `src/backend/mv_hofki/api/routes/scan_processing.py`

Aenderungen:
- Status-Guard erweitern: Reset von jedem Status ausser `"processing"` erlaubt (statt nur `"processing"` und `"error"`)
- Vor dem Status-Reset alle Analysedaten loeschen:
  - `detected_symbols` (ueber `staff_id IN detected_staves WHERE scan_id`)
  - `detected_measures` (ueber `scan_id`)
  - `detected_text_regions` (ueber `scan_id`)
  - `detected_staves` (ueber `scan_id`)
- Status auf `"uploaded"` setzen
- Response bleibt: `{"status": "ok", "new_status": "uploaded"}`

Die Loeschlogik entspricht der bestehenden Logik in `sheet_music_scan.py:run_pipeline` (Zeilen 287-294, 357-358, 396-397), nur zusammengefasst in einem Endpoint.

## Frontend: Reset-Button

**Datei:** `src/frontend/src/pages/ScanProjectDetailPage.vue`

- Kleiner Reset-Button ("↺" oder aehnliches Zeichen) neben dem bestehenden "x"-Delete-Button auf jedem Scan-Thumbnail
- Nur sichtbar wenn `scan.status !== 'uploaded'`
- Kein Bestaetigungsdialog
- API-Call: `PUT /api/v1/scanner/scans/{scanId}/reset-status`
- Nach erfolgreichem Reset: Scan-Liste neu laden (bestehende `fetchData()` aufrufen)

## Betroffene Dateien

- `src/backend/mv_hofki/api/routes/scan_processing.py` — Endpoint erweitern
- `src/frontend/src/pages/ScanProjectDetailPage.vue` — Reset-Button hinzufuegen
- `tests/backend/test_scan_processing.py` (falls vorhanden) — Tests fuer erweiterten Endpoint
