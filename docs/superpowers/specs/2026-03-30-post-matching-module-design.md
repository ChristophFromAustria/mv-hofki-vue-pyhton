# Post-Matching Module Design

## Ziel

Ein Post-Matching-Modul das die Ergebnisse des Template-Matchings bereinigt. Erste Sub-Operation: BarlineFilter zur Eliminierung falsch-positiver Taktstriche. Das Modul wird später um ein Referenz-Modul erweitert (z.B. Verzierungen auf Noten matchen).

## Architektur

### Neue Pipeline-Stage: `PostMatchingStage`

Wird nach `TemplateMatchingStage` in die Pipeline eingefügt. Enthält eine geordnete Liste von Sub-Operationen die sequentiell auf `PipelineContext` angewendet werden.

```
Pipeline: ... → TemplateMatchingStage → PostMatchingStage → ...
                                              │
                                    ┌─────────┴─────────┐
                                    │  Sub-Operationen:  │
                                    │  1. BarlineFilter  │
                                    │  2. (später: Ref.) │
                                    └────────────────────┘
```

### Sub-Operation Interface

```python
class PostMatchingOperation(ABC):
    name: str

    @abstractmethod
    def apply(self, ctx: PipelineContext) -> None:
        """Modifiziert ctx.symbols in-place (setzt filtered/filter_reason)."""
```

`PostMatchingStage` iteriert über seine Liste von `PostMatchingOperation`-Instanzen und ruft `apply()` auf.

## Datenmodell-Erweiterungen

### SymbolData (in-memory, `stages/base.py`)

Zwei neue Felder:

- `filtered: bool = False`
- `filter_reason: str | None = None`

### DetectedSymbol (DB-Modell, `models/detected_symbol.py`)

Zwei neue Spalten + Alembic Migration:

- `filtered: Boolean, default=False, nullable=False`
- `filter_reason: String(200), nullable=True`

Gefilterte Symbole werden in der DB gespeichert (nicht gelöscht), mit `filtered=True` und dem Grund.

## BarlineFilter — Logik

Ziel-Symbole: Alle Symbole mit `display_name` = "Einfacher Taktstrich" (`name` = `single_barline`).

### Schritt 1: Positionsfilter (wird zuerst angewendet)

Für jeden einfachen Taktstrich:

1. Hole die zugehörige `StaffData` über `staff_index`
2. Berechne den erlaubten y-Bereich: `staff.y_top - line_spacing` bis `staff.y_bottom + line_spacing`
3. Liegt die Mitte des Symbols (`y + height/2`) außerhalb dieses Bereichs:
   - `filtered = True`
   - `filter_reason = "barline_position_outside_staff"`

### Schritt 2: Überlappungsfilter

Für jeden verbleibenden (nicht gefilterten) einfachen Taktstrich:

1. Prüfe ob die Bounding-Box mit einem anderen (nicht gefilterten) Symbol überlappt
2. Falls Überlappung mit einem Symbol dessen `display_name` teilweise einen dieser Begriffe enthält:
   - "Wiederholung"
   - "Schlusstaktstrich"
   - "Achtel"
   - "Viertel"
   - "Sechzehntel"
   - "Halbe"
   - "Doppelter Taktstrich"
   → Taktstrich wird gefiltert: `filtered=True`, `filter_reason="barline_overlap_with_{display_name}"`
3. Falls Überlappung mit einem Symbol das **nicht** in der Prioritätsliste ist:
   → Das Symbol mit der niedrigeren Confidence wird gefiltert: `filter_reason="overlap_lower_confidence"`

Die Prioritätsliste und Positionsregeln sind hardcoded — keine Konfigurierbarkeit nötig.

### Template-Lookup

Die `TemplateMatchingStage` legt ein Mapping `template_id → display_name` in `ctx.metadata["template_display_names"]` ab. Der `BarlineFilter` nutzt dieses Mapping um den `display_name` eines Symbols anhand seiner `matched_template_id` zu ermitteln.

## Dateistruktur

### Neue Dateien

| Datei | Inhalt |
|-------|--------|
| `src/backend/mv_hofki/services/scanner/stages/post_matching.py` | `PostMatchingOperation` ABC, `PostMatchingStage`, `BarlineFilter` |
| Alembic Migration | `filtered` und `filter_reason` Spalten auf `detected_symbols` |

### Geänderte Dateien

| Datei | Änderung |
|-------|----------|
| `stages/base.py` | `SymbolData` + `filtered`, `filter_reason` Felder |
| `models/detected_symbol.py` | Zwei neue Spalten |
| `sheet_music_scan.py` | `PostMatchingStage` in Pipeline einfügen; `filtered`/`filter_reason` beim Speichern berücksichtigen |
| `stages/template_matching.py` | `ctx.metadata["template_display_names"]` Mapping anlegen |

### Unverändert

- Frontend — keine UI-Änderungen in diesem Scope
- Bestehende NMS-Logik — Post-Matching arbeitet auf NMS-bereinigten Ergebnissen
- `ScannerConfig` — keine neuen Konfigurationsfelder

## Erweiterbarkeit

Neue Sub-Operationen werden als Klassen hinzugefügt die `PostMatchingOperation` implementieren und in die Liste der `PostMatchingStage` eingehängt werden. Geplant:

- **ReferenceBuilder** — Verknüpft zusammengehörige Symbole (z.B. Akzent → Note, Bogen → Notengruppe). Wird als spätere Sub-Operation implementiert.
