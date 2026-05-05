# Tesseract-Based Text Detection + UI Overlay — Design Spec

## Ziel

Die TextMaskingStage von heuristischer CC-Cluster-Erkennung auf
`pytesseract.image_to_data()` umbauen. Tesseract erkennt direkt was Text ist
und was nicht — keine Verwechslung mit Musiksymbolen mehr. Erkannte
Textregionen werden in der DB persistiert und im Frontend als Overlay
mit dem erkannten Textinhalt angezeigt.

## Backend: TextMaskingStage Umbau

### Neuer Ablauf

1. Bild invertieren (Tesseract erwartet schwarz auf weiß)
2. `pytesseract.image_to_data(inverted, lang="deu", config="--psm 6",
   output_type=Output.DICT)` auf das gesamte Bild
3. Ergebnisse filtern: nur Einträge mit `conf > 30`
4. Pro Wort eine `TextRegionData` erzeugen (x, y, width, height, text,
   confidence)
5. Jede Region dem nächsten Staff per Y-Nähe zuordnen
6. Regionen in `processed_image` weiß setzen

### Entfernt wird

- `_detect_text_regions()` (CC-Heuristik, Y-Bänder, Clustering)
- `_ocr_region()` (einzelne Region-OCR)
- Alle Schwellwert-Logik (max_char_size, min_char_size, band_height, etc.)

## Datenstruktur

`TextRegionData` in `stages/base.py` wird erweitert:

```python
@dataclass
class TextRegionData:
    staff_index: int
    x: int
    y: int
    width: int
    height: int
    text: str | None = None
    confidence: float | None = None
```

## DB-Persistierung

### Neue Tabelle `detected_text_region`

| Spalte | Typ |
|--------|-----|
| id | Integer PK |
| scan_id | Integer FK → scans |
| staff_index | Integer |
| x | Integer |
| y | Integer |
| width | Integer |
| height | Integer |
| text | String nullable |
| confidence | Float nullable |

### Neue Dateien

- `models/detected_text_region.py` — SQLAlchemy Model (analog zu
  `detected_symbol.py`)
- `schemas/detected_text_region.py` — Pydantic Schema
  `DetectedTextRegionRead`
- Alembic Migration für die neue Tabelle

### Persistierung

In `sheet_music_scan.py` nach dem Pipeline-Run: `ctx.text_regions` in
`detected_text_region` Tabelle schreiben (alte Einträge für den Scan
vorher löschen, analog zum Symbol-Pattern).

## API

Neuer Endpoint:

```
GET /api/v1/scanner/scans/{scan_id}/text-regions
→ list[DetectedTextRegionRead]
```

## Frontend: Text-Overlay

### ScanCanvas.vue

- Neuer Prop: `textRegions: Array`, `showTextRegions: Boolean`
- SVG-Overlay: `<rect>` mit halbtransparenter Füllung + `<text>` mit
  erkanntem Text als Inhalt
- Farbe: `#10b981` (grün/teal)

### ScanEditorPage.vue

- Neuer `fetchTextRegions()` Aufruf an
  `GET /scans/{id}/text-regions`
- Daten als Prop an `ScanCanvas.vue`

### FilterDropdown.vue

- Neuer Toggle "Text" für `showTextRegions`

## Änderungen

| Datei | Änderung |
|-------|----------|
| `stages/text_masking.py` | CC-Heuristik ersetzen durch `image_to_data()` |
| `stages/base.py` | `confidence` Feld auf `TextRegionData` |
| `models/detected_text_region.py` | **Neu** — SQLAlchemy Model |
| `schemas/detected_text_region.py` | **Neu** — Pydantic Schema |
| `alembic/versions/...` | **Neu** — Migration |
| `api/routes/scan_processing.py` | Neuer Endpoint |
| `services/sheet_music_scan.py` | Text-Regionen in DB speichern |
| `ScanCanvas.vue` | SVG-Overlay: rect + text |
| `ScanEditorPage.vue` | `fetchTextRegions()`, Props |
| `FilterDropdown.vue` | Toggle "Text" |

## Testkriterium

"47er Regimentsmarsch - Tuba 1": Text wird per Tesseract erkannt, keine
Musiksymbole gelöscht, Overlay zeigt erkannten Text, "Trio" wird erkannt.
