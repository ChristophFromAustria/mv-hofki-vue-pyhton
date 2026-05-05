# Text Masking Stage — Design Spec

## Ziel

Textregionen (z.B. "cresc.", "dim.", "f", "1.") aus dem binären Bild entfernen,
bevor Hough-basierte Stages (Hairpin, Volta) laufen. Damit werden False Positives
durch Textfragmente eliminiert. Die erkannten Regionen werden als eigene
Datenstruktur gespeichert, damit sie später (z.B. für OCR oder UI-Overlay)
weiterverwendet werden können.

## Datenstruktur

Neues Dataclass in `stages/base.py`:

```python
@dataclass
class TextRegionData:
    staff_index: int
    x: int
    y: int
    width: int
    height: int
```

Neues Feld auf `PipelineContext`:

```python
text_regions: list[TextRegionData] = field(default_factory=list)
```

## Stage: `TextMaskingStage`

**Modul:** `stages/text_masking.py`
**Name:** `text_masking`

### Erkennungslogik

Pro Staff werden zwei Regionen gescannt:

- **Oberhalb:** `y_top` bis `min(line_positions)` — Volta-Text, Wiederholungsnummern
- **Unterhalb:** `max(line_positions)` bis `y_bottom` — Dynamik, Crescendo-Text

In jeder Region:

1. Bild invertieren (schwarze Pixel = Vordergrund)
2. Connected Components mit Stats finden (`cv2.connectedComponentsWithStats`)
3. Zeichengroße Komponenten identifizieren:
   - Höhe/Breite zwischen `0.15 * line_spacing` und `1.5 * line_spacing`
   - Seitenverhältnis < 5 (um Linienfragmente auszuschließen)
4. Horizontal benachbarte Komponenten clustern:
   - Maximaler horizontaler Abstand: `1.0 * line_spacing`
   - Vertikaler Overlap > 0
5. Cluster mit >= 3 Zeichen als Textregion werten
6. Pro Cluster eine `TextRegionData` erzeugen (mit Padding `0.3 * line_spacing`)

### Maskierung

Erkannte Textregionen werden in `ctx.processed_image` weiß gesetzt (Pixel = 255).
Das Ergebnis ist im UI über `processed.png` sichtbar und dient der visuellen
Bewertung der Erkennung.

### Logging

```
Text-Maskierung: {n} Textregionen in {m} Systemen erkannt
```

## Pipeline-Position

```
PostMatchingStage → TextMaskingStage → HairpinDetectionStage
```

Template-Matching läuft vorher auf dem unveränderten Bild.
Hairpin, Volta und alle zukünftigen Hough-Stages profitieren automatisch.

## Änderungen

| Datei | Änderung |
|-------|----------|
| `stages/base.py` | `TextRegionData` + `text_regions` Feld auf Context |
| `stages/text_masking.py` | **Neu** — `TextMaskingStage` |
| `stages/hairpin_detection.py` | Inline-Maskierung entfernen (Zeilen 50-53 + `_detect_text_mask`) |
| `services/sheet_music_scan.py` | `TextMaskingStage` einfügen nach PostMatching |

## Testkriterium

"47er Regimentsmarsch - Tuba 1": Nach Textfilterung soll die Hairpin-Detection
genau 4 Crescendo/Decrescendo erkennen (keine False Positives durch Text).
