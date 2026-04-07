# Volta Bracket Detection — Design Spec

## Ziel

Die VoltaDetectionStage komplett umschreiben: von reinem Debug-Line-Dump
zu einer echten Erkennung von Wiederholungsklammern. Erkannte Klammern
werden als Symbole ("Wiederholungs Klammer") gespeichert und die
zugehörigen Takte mit `volta_number` / `volta_group_id` markiert.

## Erkennungslogik

**Input:** `ctx.measures` (Wiederholungs-Taktstriche als Ankerpunkte)

**Ablauf pro Staff:**

1. Wiederholungs-Taktstriche finden (`end_barline` enthält "Wiederholung")
2. Seed-Punkt direkt oberhalb setzen (Region zwischen `y_top` und
   `min(line_positions)`)
3. Hough-Linien in diesem Bereich suchen — nur nahezu horizontal (<=5°)
4. Horizontale Linien die den Taktstrich-X-Bereich berühren als
   Kandidaten nehmen
5. Per CC-Expansion (`_expand_to_connected`) die volle Klammer-Ausdehnung
   finden (fängt vertikalen Haken ein)
6. Ergebnis als `SymbolData` speichern mit Template-ID für
   "Wiederholungs Klammer"

**Zuordnung:** Erste Klammer (von links) = Volta 1, zweite = Volta 2.
`volta_group_id` wird pro Wiederholungs-Paar vergeben. Diese Felder
werden auf die betroffenen `MeasureData`-Einträge geschrieben.

**Stage-Position:** Nach `MeasureDetectionStage` (braucht Taktstriche
als Input). Ist bereits der Fall in der Pipeline-Reihenfolge.

## Datenstruktur

Keine neue Struktur nötig. Volta-Klammern werden als `SymbolData` in
`ctx.symbols` gespeichert, analog zu Crescendo/Decrescendo:

- `matched_template_id` → ID des "Wiederholungs Klammer" Templates
- `staff_x_start` / `staff_x_end` → X-Ausdehnung der Klammer
- `staff_y_top` / `staff_y_bottom` → Y-Position relativ zu Notenlinien
- `confidence` → 0.8 (statisch, da Hough+CC-basiert)

## Shared Utility: `_expand_to_connected`

Die CC-Expansion wird aktuell nur in `hairpin_detection.py` verwendet.
Da `volta_detection.py` dieselbe Logik braucht, wird die Funktion in
ein gemeinsames Utility extrahiert (z.B. `stages/utils.py`) oder als
Import aus `hairpin_detection` wiederverwendet.

## Frontend

**Keine neuen Komponenten nötig:**

- Volta-Klammern erscheinen als normale Symbole im Symbol-Overlay
  (klickbar, SymbolPanel zeigt Details)
- Die Volta-Nummern auf Measures (`volta_number`, `volta_group_id`)
  aktivieren das bestehende L-förmige Volta-Overlay in `ScanCanvas.vue`
- Toggle "Volta-Klammern anzeigen" existiert bereits in
  `FilterDropdown.vue`

## Änderungen

| Datei | Änderung |
|-------|----------|
| `stages/volta_detection.py` | Komplett umschreiben |
| `stages/hairpin_detection.py` | `_expand_to_connected` extrahieren |
| `stages/utils.py` | **Neu** — shared `expand_to_connected` |

## Testkriterium

Bei einem Marsch mit Wiederholungen: Klammern als "Wiederholungs Klammer"
Symbole erkannt, Hitboxen im UI sichtbar, Volta-Nummern auf betroffenen
Takten im Volta-Overlay.
