# Crop Marks + PNG-Vorschau mit Zuschnitts-Overlay

## Problem

Die generierten Notenblätter müssen auf 165mm × 123mm zugeschnitten werden (A5 landscape = 210mm × 148mm). Es gibt keine visuelle Hilfe zum Zuschneiden und keine Vorschau im Frontend die den Zuschnittsbereich zeigt.

## Lösung

### 1. Backend — Crop Marks ins PDF

Nach dem Lilypond-Rendering und der 90°-Rotation werden L-förmige Eckenmarkierungen auf jede Seite des PDFs gezeichnet.

Maße:
- A5 landscape: 210mm × 148mm
- Zuschnitt: 165mm × 123mm, zentriert
- Offset links: (210 - 165) / 2 = 22.5mm
- Offset oben: (148 - 123) / 2 = 12.5mm
- Markierungen: 5mm lange Linien an jeder der 4 Ecken, 0.3pt schwarze Striche

Implementation: `reportlab` erzeugt eine transparente PDF-Seite mit den Crop Marks, `pypdf` merged sie über jede Seite des generierten PDFs.

### 2. Backend — PNG-Generierung

`render_lilypond_to_pdf()` wird zu `render_lilypond()` umbenannt und erzeugt zusätzlich zum PDF auch PNGs:
- Lilypond wird ein zweites Mal mit `--png -dresolution=150` aufgerufen
- PNGs landen im selben Verzeichnis: `generated.png` (bei einzelner Seite) oder `generated-page1.png`, `generated-page2.png` etc. (bei mehreren Seiten)
- Rückgabewert wird ein Dataclass/Dict mit `pdf_path` und `png_paths`

API-Response des `/generate-lilypond` Endpoints erweitert:
```json
{
  "lilypond_code": "...",
  "pdf_path": "data/scans/.../generated.pdf",
  "ly_path": "data/scans/.../generated.ly",
  "png_paths": ["data/scans/.../generated.png"]
}
```

### 3. Frontend — LilypondModal erweitern

Das bestehende `LilypondModal.vue` wird erweitert:

**Zwei Bereiche via Tabs:**
- **"Vorschau"** (Standard): PNG-Bild mit SVG-Overlay für das Zuschnittsrechteck
- **"Code"**: Lilypond-Code im `<pre>` Block (wie bisher)

**Vorschau-Bereich:**
- PNG wird in einem `<img>` Tag angezeigt, Container hat `position: relative`
- SVG-Overlay mit `position: absolute` darüber, viewBox = PNG-Dimensionen
- Zuschnittsrechteck als gestricheltes Cyan-Rechteck, zentriert, proportional berechnet aus dem Verhältnis 165/210 (X) und 123/148 (Y) der PNG-Dimensionen
- Zeigt Seite 1 (mehrseitige Navigation ist nicht im Scope)

**Footer:**
- PDF-Download-Link (wie bisher)
- "Schließen" Button

### 4. Dateien im Scan-Verzeichnis

- `generated.ly` — Lilypond-Quellcode
- `generated.pdf` — PDF mit Crop Marks und 90°-Rotation
- `generated.png` — PNG-Vorschau (150 DPI)

Werden bei erneutem Generieren überschrieben.

## Nicht im Scope

- Lilypond-Code-Editor im Frontend (spätere Erweiterung)
- Verschiebbares/konfigurierbares Crop-Overlay
- Mehrseitige PNG-Navigation
- Konfigurierbare Zuschnittsmaße
