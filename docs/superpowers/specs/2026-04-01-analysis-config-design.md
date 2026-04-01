# Analysis Config Migration & DB Cleanup

## Problem

1. **Session-Config hat nie funktioniert** — `sessionConfig` wird im Frontend gespeichert aber nie an den Backend-Pipeline-Call gesendet. Das SSE-Endpoint hardcoded `config_overrides = None`.
2. **Keine scan-spezifische Analyse-Config** — jeder Scan verwendet die globale `scanner_config`-Tabelle. Es gibt keine Möglichkeit, pro Scan andere Matching-Parameter zu verwenden.
3. **Preprocessing-Felder doppelt im UI** — sowohl in der `ImageAdjustBar` (Slider) als auch im `ScannerConfigModal` unter "Vorverarbeitung".
4. **Geister-Spalten in der DB** — `corrected_image_path` (nicht mehr beschrieben) und `pipeline_config_json` (wurde nie verwendet) in `sheet_music_scans`.

## Lösung

### 1. Erweiterte `adjustments_json`-Struktur

```json
{
  "preprocessing": {
    "brightness": 0,
    "contrast": 1.0,
    "threshold": 128,
    "rotation": 0,
    "morphology_kernel_size": 2
  },
  "analysis": {
    "enabled": true,
    "confidence_threshold": 0.7,
    "matching_method": "TM_CCOEFF_NORMED",
    "multi_scale_enabled": false,
    "multi_scale_range": 0.05,
    "multi_scale_steps": 3,
    "edge_matching_enabled": false,
    "canny_low": 50,
    "canny_high": 150,
    "staff_removal_before_matching": false,
    "staff_removal_thickness_pct": 100,
    "staff_removal_symbol_padding": 0,
    "masked_matching_enabled": false,
    "mask_threshold": 200,
    "nms_iou_threshold": 0.3,
    "nms_method": "standard",
    "dewarp_enabled": false,
    "dewarp_smoothing": 50,
    "auto_verify_confidence": 0.85
  }
}
```

- `analysis.enabled`: Toggle-Flag. `true` → scan-spezifische Werte haben Vorrang vor globaler Config. `false` → globale Config wird verwendet, gespeicherte Werte bleiben erhalten zum Vergleich.
- Keine Datenmigration nötig — `analysis` Key wird erst beim ersten Speichern über das Modal geschrieben. Fehlt der Key, gelten die globalen Werte.

### 2. Backend — Config-Merging-Logik

Einheitliche Config-Assembly für `run_pipeline()` und `run_preview()`, extrahiert als Hilfsfunktion:

```
1. Globale scanner_config laden (DB-Tabelle) → Basis-Dict
2. Falls adjustments_json.preprocessing existiert → Preprocessing-Werte überschreiben
3. Falls adjustments_json.analysis existiert UND analysis.enabled == true
   → Analyse-Werte überschreiben (ohne den "enabled" Key selbst)
4. Ergebnis = PipelineContext.config
```

Die Merge-Logik ist aktuell in `run_pipeline()` und `run_preview()` dupliziert (5 Zeilen jeweils). Diese wird in eine dedizierte Funktion `merge_scan_adjustments(config: dict, adjustments_json: str | None) -> dict` extrahiert.

**Session-Config-System entfernen:**
- `config_overrides` Parameter aus `run_pipeline()` entfernen
- `ScannerConfigUpdate`-Parameter aus den Processing-Endpoints entfernen
- `get_effective_config(overrides=...)` vereinfachen (kein `overrides`-Parameter mehr nötig)

### 3. Frontend — Config-Modal Umbau

**ScannerConfigModal:**
- Empfängt neue Props: `scanAdjustments` (das aktuelle `adjustments_json`-Objekt) und `scanId`
- Neuer Toggle oben im Modal: "Scan-spezifische Parameter verwenden" (steuert `analysis.enabled`)
- Wenn Toggle aktiv: Felder zeigen die scan-spezifischen Werte (aus `adjustments_json.analysis`), Änderungen speichern in `adjustments_json.analysis` via `PUT /scanner/projects/.../scans/{scanId}`
- Wenn Toggle inaktiv: Felder zeigen die globalen Werte, "Global speichern" speichert in die DB
- "Nur diese Analyse" Button wird ersetzt durch "Für diesen Scan speichern"

**scanner-config.js:**
- Preprocessing-Felder entfernen (`adaptive_threshold_block_size`, `adaptive_threshold_c`, `morphology_kernel_size`, `deskew_method`) — leben nur noch in der ImageAdjustBar

**ScanEditorPage.vue:**
- `sessionConfig` Ref entfernen
- `onApplySessionConfig()` Handler entfernen
- "Sitzungsparameter aktiv ✕" Badge entfernen
- Config-Button Logik anpassen: zeigt `"Konfig. *"` wenn `adjustments.value.analysis?.enabled === true`
- Config-Modal bekommt `adjustments` und `scanId` als Props

### 4. DB-Aufräumung

Alembic-Migration:
- `corrected_image_path` Spalte aus `sheet_music_scans` entfernen
- `pipeline_config_json` Spalte aus `sheet_music_scans` entfernen
- Entsprechende Felder aus ORM-Model und Pydantic-Schemas entfernen

Preprocessing-Felder in `scanner_config`-Tabelle bleiben als globale Defaults erhalten. Die ImageAdjustBar befüllt Slider initial mit diesen Werten wenn kein scan-spezifischer Wert existiert.

## Nicht im Scope

- Migration bestehender globaler Config-Werte in scan-spezifische `adjustments_json` — Scans ohne `analysis` Key verwenden automatisch die globale Config
- Änderungen an der globalen Config-API (`GET/PUT /scanner/config`)
- Preprocessing-Felder aus der `scanner_config`-Tabelle entfernen (bleiben als Defaults)
