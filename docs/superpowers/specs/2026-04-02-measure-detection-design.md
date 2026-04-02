# Taktstruktur-Erkennung (Measure Detection)

## Problem

Nach dem Template Matching gibt es erkannte Barline-Symbole, aber keine Taktstruktur. Symbole können keinem Takt zugeordnet werden. Es fehlt ein Koordinatensystem (System × Takt) als Grundlage für die spätere Tonhöhen-Bestimmung und den Lilypond-Export.

## Lösung

### 1. Neues DB-Model: `DetectedMeasure`

| Feld | Typ | Beschreibung |
|---|---|---|
| `id` | Int, PK | |
| `scan_id` | Int, FK → sheet_music_scans, CASCADE | |
| `staff_id` | Int, FK → detected_staves, CASCADE | Referenz zum Staff für Y-Bounds |
| `staff_index` | Int | Welches Notensystem (0-basiert) |
| `measure_number_in_staff` | Int | Taktnummer innerhalb des Systems (1-basiert) |
| `global_measure_number` | Int | Fortlaufende Taktnummer über alle Systeme (1-basiert) |
| `x_start` | Int | Linke Grenze in Pixeln |
| `x_end` | Int | Rechte Grenze in Pixeln |

Cascade-Delete über `scan_id` — bei Re-Analyse werden Takte mitgelöscht.

### 2. Pipeline-Stage: `MeasureDetectionStage`

Neuer Stage nach `PostMatchingStage` in der Pipeline-Reihenfolge.

Algorithmus:
1. Filtere alle nicht-gefilterten Symbole deren Template-Kategorie `barline` ist (alle Typen: einfach, doppelt, Schluss, Wiederholungen)
2. Gruppiere nach `staff_index`
3. Sortiere pro Staff nach `staff_x_start`
4. Erzeuge Takte als Bereiche zwischen aufeinanderfolgenden Barlines:
   - Erster Takt: von `x_start` des ersten Symbols im Staff (oder 0) bis zur ersten Barline `staff_x_start`
   - Mittlere Takte: von Barline `staff_x_end` bis nächste Barline `staff_x_start`
   - Letzter Takt: von letzter Barline `staff_x_end` bis `x_end` des letzten Symbols im Staff (oder Bildbreite)
5. Vergebe `measure_number_in_staff` (1-basiert pro System)
6. Vergebe `global_measure_number` (fortlaufend über Systeme, aufsteigend nach `staff_index`)

Benötigte Daten aus dem Kontext:
- `ctx.symbols` — alle erkannten Symbole mit `staff_index`, `staff_x_start`, `staff_x_end`, Kategorie (über `matched_template_id` → Template-Lookup)
- `ctx.staves` — für Staff-Bounds
- Template-Display-Names/Kategorien müssen im Kontext verfügbar sein (werden bereits in `run_pipeline` geladen und können als Metadata durchgereicht werden)

Ergebnis: Liste von Measure-Daten im `PipelineContext` (neues Feld `measures`).

### 3. Persistence & API

**run_pipeline():**
- Nach dem neuen Stage: `DetectedMeasure`-Objekte persistieren
- Bei Re-Analyse: bestehende Measures für den Scan löschen (wie bei Staves/Symbols)

**Neuer API-Endpoint:**
`GET /api/v1/scanner/scans/{scan_id}/measures` → `list[DetectedMeasureRead]`

**Schema `DetectedMeasureRead`:**
Alle Felder aus dem Model exponieren.

### 4. Frontend — Takt-Overlay

**ScanCanvas.vue:**
- Neues Prop `measures` (Array von Measure-Objekten)
- Für jeden Takt: vertikale Linie bei `x_start` über die volle Staff-Höhe (`y_top` bis `y_bottom` des zugehörigen Staffs)
- Taktnummer-Label (`global_measure_number`) oberhalb des Staffs bei jeder Taktgrenze
- Farbe: Blau/Cyan (#3b82f6) um sich von Symbol-Boxen (grün/rot) abzuheben
- Stroke-Dasharray für dezente Darstellung

**ScanEditorPage.vue:**
- Measures vom API laden (zusammen mit Staves/Symbols in `fetchScanData` und `onAnalysisDone`)
- An ScanCanvas als Prop durchreichen
- Toggle-Button "Takte" in der Toolbar neben "Systeme" — steuert Sichtbarkeit

### 5. PipelineContext erweitern

Neues Feld auf `PipelineContext`:

```python
measures: list[MeasureData] = field(default_factory=list)
```

Neuer Dataclass `MeasureData`:

| Feld | Typ |
|---|---|
| `staff_index` | int |
| `measure_number_in_staff` | int |
| `global_measure_number` | int |
| `x_start` | int |
| `x_end` | int |

## Nicht im Scope

- Manuelle Taktgrenzen-Korrektur im Frontend (spätere Erweiterung)
- Tonhöhen-Bestimmung (Schritt 2)
- Symbol-zu-Takt-Zuordnung auf DB-Ebene (Symbole können über X-Position Takten zugeordnet werden — keine FK nötig)
- Wiederholungs-Semantik (welche Takte wiederholt werden)
- Beat-Position innerhalb eines Takts
