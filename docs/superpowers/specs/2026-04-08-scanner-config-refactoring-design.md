# Scanner Config Refactoring — Zeilen-basiert mit Backend-Metadaten

**Datum:** 2026-04-08
**Status:** Approved

## Motivation

Die globale Scanner-Konfiguration ist aktuell als Single-Row-Tabelle mit 35+ Spalten implementiert. Jedes neue Feature erfordert: neues DB-Feld + Pydantic-Schema-Felder (x2) + Alembic-Migration + Frontend-Eintrag in `scanner-config.js`. Bei der hohen Frequenz neuer Features ist dieser Aufwand nicht tragbar.

## Ziele

- Neues Config-Feld = ein Dict in einer Python-Registry, kein Alembic/Schema/Frontend-Änderung
- Feld-Metadaten (min, max, step, label, group, options) kommen aus dem Backend — Frontend ist vollständig dynamisch
- 2-stufige Gruppenhierarchie über `group_path`-Spalte mit `\`-Separator
- User-Werte bleiben bei Metadaten-Updates erhalten
- Geänderte Werte sind im UI erkennbar, Default-Wert sichtbar, Einzelwert-Reset möglich

## Datenbank-Schema

Alte Tabelle `scanner_config` wird entfernt. Neue Tabelle `scanner_config_entry`:

| Spalte | Typ | Beschreibung |
|---|---|---|
| `key` | VARCHAR(100), PK | Eindeutiger Config-Key, z.B. `"confidence_threshold"` |
| `value` | TEXT, NOT NULL | Aktueller Wert als String |
| `default_value` | TEXT, NOT NULL | Default-Wert aus der Registry |
| `type` | VARCHAR(10), NOT NULL | `"number"`, `"toggle"`, `"select"` |
| `label` | VARCHAR(200), NOT NULL | Deutsches UI-Label |
| `group_path` | VARCHAR(200), NULL | Gruppenhierarchie mit `\`-Separator. NULL = Root |
| `min` | FLOAT, NULL | Nur bei type=number |
| `max` | FLOAT, NULL | Nur bei type=number |
| `step` | FLOAT, NULL | Nur bei type=number |
| `options` | TEXT (JSON), NULL | Nur bei type=select, z.B. `[{"value":"standard","label":"Standard"}]` |
| `sort_order` | INTEGER, NOT NULL | Reihenfolge innerhalb der Gruppe |

### Gruppierung

- `group_path = NULL` → Root-Level
- `group_path = "LilyPond Layout"` → Erste Ebene
- `group_path = "Post-Template-Matching\Text-Maskierung"` → Zweite Ebene (Obergruppe \ Untergruppe)

### Sortierung

- Gruppen: alphabetisch auf jeder Ebene
- Felder innerhalb einer Gruppe: nach `sort_order`

### Typ-Casting

Backend castet `value` und `default_value` anhand von `type`:
- `"number"` → `float` (bzw. `int` wenn `step >= 1` und `min`/`max` ganzzahlig)
- `"toggle"` → `bool` (`"true"`/`"false"`)
- `"select"` → `str`

## Backend-Registry & Seeding

### Registry

Python-Datenstruktur `SCANNER_CONFIG_REGISTRY` in `services/scanner_config_registry.py` — Single Source of Truth für Defaults und Metadaten:

```python
SCANNER_CONFIG_REGISTRY = [
    {
        "key": "confidence_threshold",
        "default_value": "0.6",
        "type": "number",
        "label": "Konfidenz-Schwellwert",
        "group_path": "Template Matching",
        "min": 0.0, "max": 1.0, "step": 0.05,
        "sort_order": 10,
    },
    {
        "key": "matching_method",
        "default_value": "TM_CCOEFF_NORMED",
        "type": "select",
        "label": "Matching-Methode",
        "group_path": "Template Matching",
        "options": [
            {"value": "TM_CCOEFF_NORMED", "label": "Kreuzkorrelationskoeffizient (Standard)"},
            ...
        ],
        "sort_order": 20,
    },
    # ... alle Einträge
]
```

### Seeding-Logik (App-Start)

1. Alle Keys aus der Registry laden
2. Alle existierenden Keys aus der DB laden
3. **Neue Keys:** Insert mit `value = default_value` + alle Metadaten
4. **Bestehende Keys:** Update Metadaten (`label`, `group_path`, `min`, `max`, `step`, `options`, `sort_order`, `default_value`, `type`). **`value` wird NIE überschrieben.**
5. **Gelöschte Keys** (in DB aber nicht in Registry): Zeile löschen

## API-Design

### GET `/api/v1/scanner/config`

Liefert alle Einträge mit Metadaten und gecasteten Werten:

```json
{
  "entries": [
    {
      "key": "confidence_threshold",
      "value": 0.8,
      "default_value": 0.6,
      "is_modified": true,
      "type": "number",
      "label": "Konfidenz-Schwellwert",
      "group_path": "Template Matching",
      "min": 0.0,
      "max": 1.0,
      "step": 0.05,
      "options": null,
      "sort_order": 10
    }
  ]
}
```

`is_modified` wird berechnet: `value != default_value`.

### PUT `/api/v1/scanner/config`

Partielles Update — nimmt Key-Value-Paare:

```json
{
  "values": {
    "confidence_threshold": 0.8,
    "dewarp_enabled": true
  }
}
```

Backend validiert jeden Wert gegen die Metadaten (min/max, gültige Option, bool). Response: aktualisierte Entry-Liste (gleich wie GET).

### POST `/api/v1/scanner/config/reset`

Setzt einzelne oder alle Keys auf Default zurück:

```json
{
  "keys": ["confidence_threshold"]
}
```

Leeres `keys`-Array oder weglassen → alle zurücksetzen. Response: aktualisierte Entry-Liste.

### `get_effective_config()` (intern)

Liest alle Zeilen, gibt `{key: casted_value}` Dict zurück für `PipelineContext`. Pipeline-Stages bleiben unverändert — `ctx.config.get("key", default)` funktioniert weiterhin.

## Frontend

### Feld-Definitionen

`scanner-config.js` wird gelöscht. Alle Informationen kommen aus der API.

### Gruppierung im UI

Frontend splittet `group_path` auf `\` und rendert verschachtelt:

```
▸ Post-Template-Matching          ← Ebene 1, collapsible
    ▸ Text-Maskierung             ← Ebene 2, collapsible, eingerückt
        Minimale Konfidenz [━━━━] ← Felder
    ▸ NMS                         ← Ebene 2
        IoU-Schwellwert [━━━━━━]
```

Gruppen alphabetisch sortiert auf jeder Ebene, Felder innerhalb nach `sort_order`.

### UI-Elemente pro Feld

- **Modifiziert-Indikator:** Visueller Marker bei `is_modified === true` (farbiger Punkt / eingefärbter Hintergrund)
- **Default-Anzeige:** Unter/neben dem Input der Default-Wert in grau, z.B. "Standard: 0.6"
- **Einzelwert-Reset:** Kleiner Reset-Button pro Feld, nur sichtbar wenn `is_modified`, ruft `POST /scanner/config/reset` mit dem einzelnen Key auf

### Betroffene Komponenten

- `ScannerConfigPage.vue` — Dynamisch aus API, Modified-Indikator, Einzel-Reset
- `ScannerConfigModal.vue` — Gleiche Änderungen, Override-Logik anpassen
- `ScanEditorPage.vue` — Minimale Anpassung

### Scan-spezifische Overrides

Mechanik bleibt gleich: `adjustments_json` als JSON-Blob auf dem Scan-Record, enthält nur abweichende Key-Value-Paare. `merge_scan_adjustments()` Logik bleibt identisch.

## Migration & Aufräumen

### Alembic-Migration

1. Neue Tabelle `scanner_config_entry` anlegen
2. Werte aus alter `scanner_config`-Tabelle lesen (die eine Zeile)
3. Für jeden Key aus der Registry: Eintrag anlegen — wenn alter Wert existiert und vom Default abweicht, `value` übernehmen, sonst `default_value`
4. Alte Tabelle `scanner_config` droppen
5. Alle `adjustments_json` in `sheet_music_scan` auf NULL setzen

### Zu löschende Dateien

- `src/backend/mv_hofki/models/scanner_config.py` → Ersetzt durch neues Model
- `src/backend/mv_hofki/schemas/scanner_config.py` → Ersetzt durch neue Schemas
- `src/frontend/src/lib/scanner-config.js` → Nicht mehr nötig

### Zu ändernde Dateien

- `services/scanner_config.py` → Neue Logik (Registry-Seeding, Cast-Logik, CRUD)
- `services/sheet_music_scan.py` → `merge_scan_adjustments()` und `get_effective_config()` anpassen
- `api/routes/scanner_config.py` → Neue Endpoints
- `db/seed.py` → Config-Seeding auf neue Funktion umstellen
- `ScannerConfigPage.vue` → Dynamisch aus API
- `ScannerConfigModal.vue` → Dynamisch aus API + Override-Logik
- `ScanEditorPage.vue` → Minimale Anpassung (adjustments-Struktur)

### Keine Änderung nötig

- Alle Pipeline-Stages (`ctx.config.get()` bleibt identisch)
- `api/routes/scan_processing.py`
- `api/routes/scans.py`
