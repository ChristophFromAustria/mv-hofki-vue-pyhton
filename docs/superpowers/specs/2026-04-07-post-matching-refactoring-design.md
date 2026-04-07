# Post-Matching Refactoring & Taktgrenzen-Verfeinerung

**Datum:** 2026-04-07

## Zusammenfassung

Drei zusammenhaengende Aenderungen an der Scanner-Pipeline:
1. `post_matching.py` wird zum Package extrahiert (Orchestrator + separate Module)
2. `StaffRemovalStage` berechnet X-Grenzen pro Notenzeile und wird Pflicht
3. `MeasureDetectionStage` nutzt Barline-Start (nicht -Ende) als Taktgrenze und Staff-X-Grenzen statt Symbol-min/max

## 1. StaffData erweitern

`StaffData` in `base.py` bekommt zwei neue Felder:

```python
x_start: int | None = None
x_end: int | None = None
```

`StaffRemovalStage` berechnet diese Werte aus dem bereits vorhandenen `has_symbol`-Array (erstes/letztes `True` in der Spaltenanalyse) und schreibt sie in die Staff-Objekte.

## 2. Modul-Extraktion: post_matching Package

Das bisherige `post_matching.py` wird zu einem Package:

```
stages/
  post_matching/
    __init__.py          # PostMatchingStage + PostMatchingOperation ABC (reiner Orchestrator)
    barline_filter.py    # BarlineFilter Klasse (bestehende Filterlogik, unveraendert)
```

- `__init__.py` importiert `BarlineFilter` aus `barline_filter.py` und registriert ihn in der Operations-Liste
- Alle externen Imports (`from ...post_matching import PostMatchingStage`) bleiben kompatibel
- Die Logik des `BarlineFilter` aendert sich nicht

## 3. Taktgrenzen-Logik in MeasureDetectionStage

Drei Aenderungen in `measure_detection.py`:

- **Barline-Start als Grenze:** `prev_end = bl_start` statt `prev_end = bl_end`. Takt N endet bei `bl_start`, Takt N+1 beginnt bei `bl_start`. Keine Luecke, keine Ueberlappung.
- **Staff-X-Grenzen statt Symbol-min/max:** `min_x` kommt aus `staff.x_start`, `max_x` aus `staff.x_end`. Die bisherige Symbol-Iteration fuer min/max faellt weg.
- **Erster/letzter Takt:** Der erste Takt beginnt bei `staff.x_start`, der letzte endet bei `staff.x_end`.

## 4. StaffRemovalStage wird Pflicht

In `sheet_music_scan.py` wird der Config-Guard `if config.get("staff_removal_before_matching", False)` entfernt. `StaffRemovalStage()` wird immer in die Pipeline eingefuegt. Grund: Ohne Staff-Removal entstehen zu viele False Positives im Template-Matching.

## Betroffene Dateien

- `src/backend/mv_hofki/services/scanner/stages/base.py` — StaffData x_start/x_end
- `src/backend/mv_hofki/services/scanner/stages/staff_removal.py` — X-Grenzen berechnen
- `src/backend/mv_hofki/services/scanner/stages/post_matching.py` — wird zum Package
- `src/backend/mv_hofki/services/scanner/stages/measure_detection.py` — neue Grenzlogik
- `src/backend/mv_hofki/services/sheet_music_scan.py` — StaffRemoval immer aktiv
- `tests/backend/test_post_matching.py` — Import-Anpassung
- `tests/backend/test_measure_detection.py` — Tests fuer neue Grenzlogik
