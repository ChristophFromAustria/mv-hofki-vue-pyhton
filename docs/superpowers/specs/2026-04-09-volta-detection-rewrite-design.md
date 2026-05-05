# Volta-Erkennung Neuschreibung: Run-Length Scanning

## Zusammenfassung

Neuschreibung der `VoltaDetectionStage` mit zeilenweisem Run-Length Scanning statt Hough Lines. Suche wird gezielt auf Taktbereiche rund um Wiederholungszeichen eingeschraenkt.

## Algorithmus

### 1. Wiederholungs-Enden sammeln

Iteriere ueber `ctx.measures` und finde alle Takte mit `end_barline` in `{"Wiederholung Ende", "Wiederholung Beidseitig"}`. Fuer jeden solchen Takt bestimme:

- **Takt davor** (der Takt selbst, enthaelt das Wiederholungszeichen am Ende) — hier wird Volta 1 gesucht
- **Takt danach** (naechster Takt nach dem Wiederholungszeichen) — hier wird Volta 2 gesucht. Kann auf demselben Staff oder auf dem naechsten Staff liegen (Zeilenumbruch)

### 2. Suchregion definieren

Fuer jeden Kandidaten-Takt:

- **X-Bereich**: `measure.x_start` bis `measure.x_end`
- **Y-Bereich**: `staff.y_top` bis `top_line - line_spacing` (Region ueber dem Notensystem)

### 3. Zeilenweises Run-Length Scanning

Fuer jede Pixelzeile im Y-Bereich, eingeschraenkt auf den X-Bereich:

1. Finde zusammenhaengende schwarze Pixel-Laeufe (Pixelwert < 128)
2. Behalte nur Runs mit Laenge >= `min_run_length` (2 x line_spacing)
3. Gruppiere Runs ueber benachbarte Zeilen: Runs auf Zeile y und y+1 gehoeren zusammen, wenn sie sich im X-Bereich stark ueberlappen (>= 80% Ueberlappung)
4. Eine Gruppe ist ein Linienkandidat wenn sie mindestens `line_thickness` Zeilen hoch ist
5. Pruefe Horizontalitaet: der X-Mittelpunkt der Runs darf ueber die Hoehe der Gruppe maximal `tan(2 Grad) x Gruppenhoehe` Pixel driften

### 4. Expand to Connected

Fuer jeden Linienkandidaten: nimm die Bounding Box des Runs und rufe `expand_to_connected()` auf. Das liefert die vollstaendige Hitbox der Klammer (inklusive vertikaler Haken, Ziffer etc.).

### 5. Hitbox filtern

- Die Hitbox muss breiter als hoch sein (mindestens Faktor 2)
- Die Hitbox muss im plausiblen Y-Bereich liegen (oberhalb der Notenlinien)

### 6. Takte zuordnen

Fuer jede gefundene Hitbox: alle Takte deren X-Bereich mit der Hitbox ueberlappt werden als Teil dieser Klammer markiert.

### 7. Volta-Nummern vergeben

- Klammer vor dem Wiederholungszeichen: `volta_number = 1`
- Klammer nach dem Wiederholungszeichen: `volta_number = 2`
- Beide erhalten dieselbe `volta_group_id`

## Randfall: Zeilenumbruch

Wenn das Wiederholungszeichen am Ende einer Notenzeile steht, ist der "naechste Takt" der erste Takt des naechsten Staffs. Die Volta-2-Suche laeuft dann ueber dem naechsten Staff im Y-Bereich dieses Staffs.

## Einschraenkungen

- Maximal zwei Volta-Klammern pro Wiederholungszeichen (1 und 2)
- Keine Ziffererkennung — Zuordnung rein positionsbasiert (vor = 1, nach = 2)

## Aenderungen vs. aktueller Code

| Aktuell | Neu |
|---------|-----|
| Hough Lines + Canny | Zeilenweises Run-Length Scanning |
| Winkelfilter +/-5 Grad | Horizontalitaetspruefung +/-2 Grad |
| Suche ueber gesamte Staffbreite | Suche nur in Taktbereichen rund um Wiederholungszeichen |
| `_near_repeat()` Filterung nachtraeglich | Direkt nur relevante Taktbereiche scannen |
| Volta-Nummern sequenziell links->rechts | Positionsbasiert: vor=1, nach=2 |

## Was bleibt

- `expand_to_connected()` aus `utils.py`
- `SymbolData` mit `matched_template_id` fuer "Wiederholungs Klammer"
- `MeasureData.volta_number` und `volta_group_id`
- Debug-Output in `ctx.metadata`

## Betroffene Dateien

- `src/backend/mv_hofki/services/scanner/stages/volta_detection.py` — komplette Neuschreibung
- `tests/backend/test_volta_detection.py` — Tests anpassen
