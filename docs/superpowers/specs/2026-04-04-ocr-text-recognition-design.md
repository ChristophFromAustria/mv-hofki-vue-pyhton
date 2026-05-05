# OCR Text Recognition for Text Masking Stage — Design Spec

## Ziel

Tesseract-OCR in die bestehende TextMaskingStage integrieren, um erkannte
Textregionen inhaltlich zu identifizieren. Damit wird:

1. Text wie "Trio" erkannt und als Markierung auf `TextRegionData.text` gespeichert
2. Die Texterkennung verbessert — auch Copyright-Zeichen, Attributionstext
   ("bearb. Hans Kliment jr.") und andere bisher nicht erkannte Textfragmente
   werden erfasst und maskiert
3. Die Grundlage geschaffen, um in Zukunft weitere Textmarker (D.C., Fine, etc.)
   zu erkennen

## Devcontainer-Änderungen

### Dockerfile

Tesseract-OCR Systempaket + deutsche Sprachdaten:

```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr tesseract-ocr-deu \
    && rm -rf /var/lib/apt/lists/*
```

### pyproject.toml

Neue Python-Dependency:

```toml
"pytesseract>=0.3,<1"
```

## Datenstruktur

Erweiterung von `TextRegionData` in `stages/base.py`:

```python
@dataclass
class TextRegionData:
    staff_index: int
    x: int
    y: int
    width: int
    height: int
    text: str | None = None
```

Das `text`-Feld enthält den per OCR erkannten Text (z.B. "Trio", "cresc.",
"Copyright ...") oder `None` wenn OCR keinen Text erkennt.

## TextMaskingStage-Erweiterung

### Cluster-Erkennung

- `max_char_size` wird von `2.0` auf `3.0 × line_spacing` angehoben, damit
  auch größerer Text (Copyright, Attribution) erkannt wird
- Minimum-Cluster-Größe wird von `>= 3` auf `>= 1` Zeichen gesenkt, aber nur
  für Komponenten mit Mindestgröße `>= 0.5 × line_spacing` in beide Richtungen.
  Das verhindert, dass Notenköpfe oder Punkte fälschlich als Text erkannt werden.

### OCR-Ablauf

Nach der Cluster-Erkennung, vor der Maskierung:

1. Für jede erkannte `TextRegionData` den Bildausschnitt aus `processed_image`
   extrahieren
2. `pytesseract.image_to_string()` auf den Ausschnitt anwenden
3. Erkannten Text in `region.text` speichern (gestrippt, oder `None` bei leerem
   Ergebnis)

### Maskierung

Wie bisher: alle erkannten Textregionen in `processed_image` weiß setzen.

## Änderungen

| Datei | Änderung |
|-------|----------|
| `.devcontainer/Dockerfile` | `tesseract-ocr` + `tesseract-ocr-deu` installieren |
| `pyproject.toml` | `pytesseract>=0.3,<1` hinzufügen |
| `stages/base.py` | `text: str \| None = None` Feld auf `TextRegionData` |
| `stages/text_masking.py` | OCR pro Region, max_char_size 3.0, min Cluster 1 mit Mindestgröße |

## Testkriterien

"47er Regimentsmarsch - Tuba 1":

- Copyright-Zeichen wird erkannt und gelöscht
- "bearb. Hans Kliment jr." wird erkannt und gelöscht
- "Trio" wird erkannt und in `region.text` gespeichert
- Weiterhin 4 Hairpins ohne False Positives durch Text
