# Staff-Bounds-Scan und Mindestbreite-Filter fuer Takte

**Datum:** 2026-04-07

## Zusammenfassung

Zwei Aenderungen an der Scanner-Pipeline:
1. Praezisere x_start/x_end Erkennung in StaffRemovalStage durch 5-Linien-Scan statt has_symbol
2. Mindestbreite-Filter in MeasureDetectionStage — Segmente schmaler als 1x line_spacing werden nicht als Takt gezaehlt

## 1. 5-Linien-Scan fuer x_start/x_end

**Datei:** `src/backend/mv_hofki/services/scanner/stages/staff_removal.py`

Die bestehende `has_symbol`-basierte x_start/x_end Berechnung (aus `_remove_empty_staff_segments`) wird ersetzt durch einen 5-Linien-Scan:

- **Von links scannen:** Fuer jede Spalte x (aufsteigend) pruefen, ob an allen 5 `line_positions` schwarze Pixel vorhanden sind (innerhalb der gemessenen `line_thickness`). Die erste Spalte wo alle 5 Linien schwarz sind ergibt `x_start`.
- **Von rechts scannen:** Gleiche Logik, absteigend ergibt `x_end`.
- Der Scan wird **vor** der Linien-Entfernung durchgefuehrt, da die Linien danach teilweise geloescht sind. Die Methode `_remove_empty_staff_segments` gibt weiterhin `(x_start, x_end)` zurueck, aber die Werte kommen aus dem neuen Scan statt aus `has_symbol`.
- Pruefung pro Spalte: An jeder der 5 `line_positions` wird im Bereich `line_y - half_thickness` bis `line_y + half_thickness` nach mindestens einem schwarzen Pixel (Wert 0) gesucht. Alle 5 muessen treffen.

## 2. Mindestbreite-Filter in MeasureDetectionStage

**Datei:** `src/backend/mv_hofki/services/scanner/stages/measure_detection.py`

Nach dem Aufbau der `boundary_list` werden Segmente gefiltert: Nur Segmente mit `(x_end - x_start) >= line_spacing` bekommen eine Taktnummer (`MeasureData`). Schmalere Segmente (Schlusstrich-Bereich, Bereich vor erstem Barline) werden verworfen.

`line_spacing` kommt aus `staff.line_spacing` und ist bereits verfuegbar.

## Betroffene Dateien

- `src/backend/mv_hofki/services/scanner/stages/staff_removal.py` — 5-Linien-Scan statt has_symbol
- `src/backend/mv_hofki/services/scanner/stages/measure_detection.py` — Mindestbreite-Filter
- `tests/backend/test_template_matching_features.py` — Test fuer neuen Scan anpassen
- `tests/backend/test_measure_detection.py` — Tests fuer Mindestbreite-Filter
