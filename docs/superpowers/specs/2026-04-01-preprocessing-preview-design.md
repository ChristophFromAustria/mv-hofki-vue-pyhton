# Preprocessing Preview & Adjustments Rework

## Problem

1. **Brightness/Contrast werden nicht an die Pipeline übergeben** — `run_pipeline()` kopiert nur `threshold` aus `adjustments_json`, obwohl `PreprocessStage` alle drei Werte konsumiert.
2. **Kein schneller Preprocessing-Preview** — um Parameter zu bewerten, muss die volle Analyse (inkl. Template Matching) durchlaufen.
3. **Morphology Kernel Size hat keinen UI-Slider** — nur über globale Scanner-Config änderbar.
4. **Rotation wird nie angewandt** — Frontend speichert den Wert, Backend ignoriert ihn.
5. **"Korrigiert"-Ansicht bringt keinen Mehrwert** — das Graustufenbild nach Deskew ist nicht aussagekräftig für die Bewertung des Pipeline-Inputs.
6. **Doppelte Deskew-Berechnung** — Deskew läuft einmal auf Binär- und einmal auf Graustufenbild, mit potenziell unterschiedlichen Ergebnissen.
7. **`adjustments_json` ist flach** — nicht vorbereitet für spätere Analyse-Parameter.

## Lösung

### 1. Neue `adjustments_json`-Struktur

**Alt:**
```json
{"brightness": 0, "contrast": 1.0, "rotation": 0, "threshold": 128}
```

**Neu:**
```json
{
  "preprocessing": {
    "brightness": 0,
    "contrast": 1.0,
    "threshold": 128,
    "rotation": 0,
    "morphology_kernel_size": 2
  }
}
```

- Alembic-Datenmigration: bestehende JSON-Werte in `preprocessing`-Gruppe überführen
- Erweiterbar für spätere `"analysis": { ... }` Gruppe
- Leere/null Einträge bleiben unverändert

### 2. Backend — Preview-Endpoint

`POST /api/v1/scanner/scans/{scan_id}/preview`

- Liest Originalbild
- Führt die vollständige `PreprocessStage` aus (Rotation → Brightness/Contrast → Binarisierung → Deskew → Morphologisches Opening)
- Speichert Ergebnis als `processed_image_path` (überschreibt vorheriges Preview/Analysebild)
- Speichert aktuelle Adjustment-Werte in `adjustments_json`
- Gibt `{ "processed_image_path": "..." }` als JSON zurück
- Kein SSE, kein Log-Modal

### 3. Backend — PreprocessStage erweitern

**Rotation hinzufügen** als erster Schritt in `PreprocessStage.process()`:
- Liest `rotation` aus Config (0, 90, 180, 270)
- Wendet `cv2.rotate()` an (ROTATE_90_CLOCKWISE etc.)
- Vor Grayscale-Konvertierung, damit Farb- und Graustufenbilder unterstützt werden

**Deskew-Fix:** `corrected_image`-Berechnung entfernen (Zeile 62 in preprocess.py). Deskew läuft nur noch einmal auf dem Binärbild.

### 4. Backend — `run_pipeline()` Fix

Alle Preprocessing-Werte aus `adjustments_json.preprocessing` in die Pipeline-Config mergen:
```python
adjustments = json.loads(scan.adjustments_json) if scan.adjustments_json else {}
preprocessing = adjustments.get("preprocessing", {})
for key in ("brightness", "contrast", "threshold", "rotation", "morphology_kernel_size"):
    if key in preprocessing:
        config[key] = preprocessing[key]
```

### 5. Backend — Aufräumen

- `corrected_image_path`: Spalte im Model behalten (breaking migration vermeiden), aber nicht mehr beschreiben
- `corrected_image`-Zuweisung in `PreprocessStage` entfernen
- Speicherlogik für corrected image in `sheet_music_scan.py` entfernen

### 6. Frontend — ImageAdjustBar.vue

**Neuer Slider:** Morphology Kernel Size (1–5, Default 2, Ganzzahl-Schritte)

**Neuer Button:** "Vorschau" — links neben "Analyse starten"

**Props erweitern:** `initialValues`-Prop um Slider beim Laden mit gespeicherten Werten zu befüllen

**Neues Event:** `"preview"` — emittiert die aktuellen Adjustment-Werte

**Datenstruktur:** Emittiert verschachtelte Struktur:
```js
emit("adjust", {
  preprocessing: {
    brightness: brightness.value,
    contrast: contrast.value,
    threshold: threshold.value,
    rotation: rotation.value,
    morphology_kernel_size: morphologyKernelSize.value,
  }
});
```

### 7. Frontend — ScanEditorPage.vue

**Preview-Handler:**
1. Speichert aktuelle Adjustments via PUT (wie bei `startAnalysis`)
2. Ruft `POST .../preview` auf
3. Wechselt auf Binär-Ansicht
4. Blendet Stave/Symbol-Overlays aus

**Laden gespeicherter Werte:**
Beim Laden eines Scans: falls `adjustments_json` die neue `preprocessing`-Struktur enthält, werden die Werte an `ImageAdjustBar` als `initialValues` übergeben. Falls keine gespeicherten Werte vorhanden sind, bleiben die globalen Defaults (brightness=0, contrast=1.0, threshold=128, rotation=0, morphology_kernel_size=2).

**"Korrigiert"-View entfernen:**
- Button aus der View-Mode-Leiste entfernen
- Nur noch "Original" und "Binär"

### 8. Frontend — ScanCanvas.vue

- `correctedImagePath`-Prop entfernen
- `viewMode === "corrected"` Logik entfernen
- Client-seitige Threshold-Vorschau im Original-Modus bleibt unverändert

## Nicht im Scope

- Analyse-Parameter in `adjustments_json` (späterer Ausbau)
- DB-Migration zum Entfernen von `corrected_image_path` Spalte
- Änderungen an der globalen Scanner-Config UI
