# Volta-Klammern-Erkennung (1./2. Klammer)

## Problem

Volta-Klammern (1./2. Haus) sind visuell als horizontale Linien oberhalb der Notenzeile erkennbar, werden aber weder erkannt noch in den Lilypond-Export einbezogen. Ohne sie ist der generierte Code für Stücke mit Wiederholungen unvollständig.

## Lösung

### 1. Erkennung — Bildbasierter Pipeline-Stage

Neuer Stage `VoltaDetectionStage` nach `MeasureDetectionStage`.

Algorithmus:
1. Für jedes System: Volta-Region definieren = `y_top - 3*line_spacing` bis `y_top`
2. Bildstreifen aus dem Binärbild extrahieren (invertiert: schwarze Pixel = Vordergrund)
3. Morphologisches horizontales Opening mit breitem Kernel (z.B. halbe durchschnittliche Taktbreite × 1) — isoliert horizontale Linien
4. Connected Components oder Konturanalyse auf dem Ergebnis
5. Filtern: Mindestbreite = halbe durchschnittliche Taktbreite des Systems
6. Für jedes Segment: Start-X und End-X bestimmen, auf überdeckte Takte mappen

### 2. Volta-Nummern-Zuordnung

Aus der Position relativ zu Repeat-Barlines:
1. Finde den nächstgelegenen "Wiederholung Ende" oder "Wiederholung Beidseitig" Taktstrich
2. Klammer deren `x_end` ≤ Repeat-End X → Volta 1
3. Klammer deren `x_start` > Repeat-End X → Volta 2
4. Falls nur eine Klammer bei einem Repeat: Volta 1
5. Zusammengehörige Volta 1/2 Paare bekommen dieselbe `volta_group_id`

### 3. Datenmodell — Felder auf `DetectedMeasure`

Neue Felder (Alembic-Migration):

| Feld | Typ | Beschreibung |
|---|---|---|
| `volta_number` | Int, nullable | 1 oder 2 (null = kein Volta) |
| `volta_group_id` | Int, nullable | Gleiche ID gruppiert Klammern desselben Repeats |

`MeasureData` Dataclass bekommt dieselben Felder.

### 4. Lilypond-Generierung

Der Generator erkennt Volta-Gruppen und erzeugt:
```lilypond
\repeat volta 2 {
  c1 | c1 | c1 |
}
\alternative {
  \volta 1 { c1 | }
  \volta 2 { c1 | }
}
```

Logik:
1. Scanne Measures sequentiell pro System
2. Wenn ein Takt `volta_number=1` hat: sammle rückwärts bis zum vorherigen Repeat-Start (oder `\bar ".|:"` Barline) — das wird der `\repeat volta 2 { }` Body
3. Alle Takte mit gleicher `volta_group_id` und `volta_number=1` → `\volta 1 { }`
4. Alle Takte mit gleicher `volta_group_id` und `volta_number=2` → `\volta 2 { }`
5. Nach der Alternative geht der normale Code weiter

### 5. Pipeline-Context

`VoltaDetectionStage` benötigt:
- `ctx.processed_image` — das Binärbild für die Linienerkennung
- `ctx.staves` — für Staff-Positionen und line_spacing
- `ctx.measures` — für Taktgrenzen und Barline-Typen
- `ctx.metadata["template_display_names"]` — für Barline-Typ-Lookup (bereits verfügbar)
- `ctx.metadata["template_categories"]` — für Barline-Identifikation (bereits verfügbar)

Der Stage modifiziert `ctx.measures` in-place (setzt `volta_number` und `volta_group_id`).

### 6. Frontend — Overlay

Im ScanCanvas SVG-Overlay:
- Horizontale Linie oberhalb des Staffs über die betroffenen Takte
- Vertikaler Haken am Anfang der Klammer
- Nummer "1." / "2." als Label
- Farbe: Magenta (#d946ef)
- Toggle "Voltas" im FilterDropdown

### 7. Persistence & API

- `run_pipeline()` persistiert `volta_number` und `volta_group_id` auf `DetectedMeasure` (bereits Teil des Measure-Persistence-Blocks)
- `GET /scans/{id}/measures` gibt die Felder bereits mit zurück (Schema erweitern)
- Kein neuer API-Endpoint nötig

## Nicht im Scope

- OCR der Volta-Labels
- Manuelle Volta-Korrektur im UI
- Verschachtelte Wiederholungen (da-capo, dal-segno)
- Volta 3+ (nur 1 und 2)
