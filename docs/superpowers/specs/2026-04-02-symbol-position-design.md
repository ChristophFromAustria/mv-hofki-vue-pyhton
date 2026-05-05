# Symbol-Positionierung relativ zum Notensystem

## Problem

Erkannte Symbole speichern nur absolute Pixel-Koordinaten (`x`, `y`, `width`, `height`). Es fehlt eine Position relativ zum Notensystem, die für die spätere Tonhöhen-Bestimmung nötig ist. Das bestehende Feld `position_on_staff` (Int) wird nie gesetzt und ist zu ungenau für diesen Zweck.

## Lösung

### 1. Neue Felder auf `DetectedSymbol`

| Feld | Typ | Beschreibung |
|---|---|---|
| `staff_y_top` | `Float, nullable` | Oberkante der Hitbox in Notenlinien-Abständen, gemessen von der untersten Linie (positiv = über der Linie) |
| `staff_y_bottom` | `Float, nullable` | Unterkante der Hitbox, gleiche Einheit |
| `staff_x_start` | `Int, nullable` | Linke Kante der Hitbox in Pixeln (= `x`) |
| `staff_x_end` | `Int, nullable` | Rechte Kante der Hitbox in Pixeln (= `x + width`) |

### 2. Altes Feld entfernen

`position_on_staff` (Int, nullable) wird per Alembic-Migration entfernt. War nie gesetzt, wird vollständig durch die neuen Felder ersetzt.

### 3. Berechnung

Die Berechnung erfolgt im Template Matching Stage, dort wo `SymbolData` erstellt wird. Die `line_positions` des aktuellen Staves sind im Kontext verfügbar.

```
bottom_line_y = max(staff.line_positions)   # unterste Notenlinie
staff_y_top = (bottom_line_y - symbol.y) / staff.line_spacing
staff_y_bottom = (bottom_line_y - (symbol.y + symbol.height)) / staff.line_spacing
staff_x_start = symbol.x
staff_x_end = symbol.x + symbol.width
```

Beispiele:
- Oberkante genau auf der untersten Linie → `staff_y_top = 0.0`
- Oberkante eine Linie höher → `staff_y_top = 1.0`
- Oberkante zwischen zwei Linien → `staff_y_top = 0.5`
- Unterkante unter der untersten Linie → `staff_y_bottom = -0.5`

### 4. Datenfluss

- `SymbolData` Dataclass: `position_on_staff` entfernen, 4 neue Felder hinzufügen (`staff_y_top`, `staff_y_bottom`, `staff_x_start`, `staff_x_end`)
- Template Matching Stage: Berechnung bei SymbolData-Erstellung
- `run_pipeline()` Persistence: Neue Felder auf `DetectedSymbol` mappen
- Schema `DetectedSymbolRead`: Neue Felder exponieren
- Frontend: Symbol-Details-Panel zeigt die neuen Werte an

### 5. Frontend — Anzeige

Im Symbol-Details-Panel in der Seitenleiste:
- "X: 120 – 145 px"
- "Y (Staff): 2.0 – -1.5 Linien"

## Nicht im Scope

- Tonhöhen-Bestimmung aus der Y-Position
- Schlüssel-Offset-Logik
- Staff-relative X-Positionen (relativ zum Staff-Rand)
