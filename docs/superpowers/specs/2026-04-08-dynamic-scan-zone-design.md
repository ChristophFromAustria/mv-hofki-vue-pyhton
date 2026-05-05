# Design: Kategorie-spezifische Scan-Zonen im Template Matching

**Datum:** 2026-04-08
**Status:** Genehmigt

## Problem

Dynamic-Zeichen (pp, ff, mf, etc.) erscheinen unterhalb der Notenzeile, teilweise
deutlich tiefer als andere Symbole. Um sie zu erkennen, muss `staff_margin_bottom`
groß gewählt werden. Das vergrößert den Scanbereich **aller** Kategorien gleichmäßig
und erzeugt false positives bei anderen Symbolen (Noten, Taktstriche, etc.).

## Lösung: Zonen-Konzept

Die `TemplateMatchingStage` bekommt ein Zonen-System. Jedes Template wird anhand
seiner Kategorie einer Scan-Zone zugeordnet:

| Zone           | Region                                                         | Templates           |
|----------------|----------------------------------------------------------------|----------------------|
| `staff`        | `y_top` bis `y_bottom` (bestehender Scanbereich)               | Alle außer Dynamics  |
| `below_staff`  | `bottom_line - 1 × line_spacing` bis nächster Staff / Seitenrand | Nur Dynamics         |

### below_staff-Region im Detail

- **y_start:** `max(staff.line_positions) - 1 × staff.line_spacing`
  (1 line_spacing über der untersten Notenlinie, weil Dynamic-Hitboxen in den
  Staff-Bereich hineinragen können)
- **y_end:** `min(next_staff.line_positions)` falls ein nächster Staff existiert,
  sonst `image_height` (unterer Seitenrand)

## Betroffene Dateien

### 1. `src/backend/mv_hofki/services/scanner/stages/template_matching.py`

**Constructor:** Neuer Parameter `template_categories: dict[int, str]`.

**Neue Hilfsmethode:** `_compute_below_staff_region(staff, next_staff, img_height) -> tuple[int, int]`
- Berechnet `(y_start, y_end)` für die below_staff-Zone.
- `y_start = max(0, int(max(staff.line_positions) - staff.line_spacing))`
- `y_end = min(next_staff.line_positions)` wenn `next_staff` existiert, sonst `img_height`

**Matching-Loop:** Die Templates werden vor dem Staff-Loop nach Zone gruppiert:
- `staff_templates`: alle Templates deren Kategorie != "dynamic"
- `below_staff_templates`: alle Templates mit Kategorie == "dynamic"

Pro Staff werden zwei Matching-Durchläufe ausgeführt:
1. `staff`-Zone mit `staff_templates` (Region: `y_top` bis `y_bottom`, wie bisher)
2. `below_staff`-Zone mit `below_staff_templates` (Region: berechnete below_staff-Region)

Die innere Matching-Logik (Skalierung, Multi-Scale, NMS-Vorbereitung) bleibt identisch.
Die Zone bestimmt nur, welcher Bildausschnitt (`region`) und welche Template-Teilmenge
verwendet wird.

**Staff-Zuordnung:** Detektionen aus der below_staff-Zone werden dem aktuellen Staff
zugeordnet (`staff_index`). `staff_y_top` und `staff_y_bottom` werden weiterhin
relativ zur untersten Linie des zugeordneten Staffs berechnet.

### 2. `src/backend/mv_hofki/services/sheet_music_scan.py`

**Pipeline-Aufbau:** `template_categories` wird an den `TemplateMatchingStage`-Constructor
übergeben. Das Dict existiert bereits (Zeile 220: `template_categories = {t.id: t.category for t in all_templates}`).

## Was sich nicht ändert

- **DynamicFilter** im PostMatching bleibt als Sicherheitsnetz
  (filtert Dynamics mit `staff_y_top > 1`)
- **NMS** läuft weiterhin global über alle Detektionen beider Zonen
- **Alle nachfolgenden Stages** (DynamicMasking, Hairpin, Measure, Volta) bleiben unverändert
- **Scanner-Config-Registry:** Keine neuen Config-Einträge nötig.
  Die Zone wird aus der Template-Kategorie abgeleitet.
- **`staff_margin_bottom`** kann nach der Umsetzung wieder auf einen kleineren Wert
  gesetzt werden (z.B. 2.0), da Dynamics ihren eigenen Bereich haben.

## Refactoring-Möglichkeit

Die innere Matching-Logik (Zeilen 104-239 in `template_matching.py`) wird für beide
Zonen identisch ausgeführt. Um Code-Duplikation zu vermeiden, wird die Logik in eine
private Methode extrahiert:

```python
def _match_templates_in_region(
    self,
    region: np.ndarray,
    edge_region: np.ndarray | None,
    staff: StaffData,
    template_indices: list[int],
    region_y_offset: int,
    config: MatchingConfig,
) -> list[SymbolData]:
```

Diese Methode enthält die Skalierung, Multi-Scale-Suche und Hit-Extraktion.
Der äußere Loop ruft sie zweimal pro Staff auf — einmal für die staff-Zone,
einmal für die below_staff-Zone — mit unterschiedlicher Region und Template-Teilmenge.

`region_y_offset` ist der absolute y-Offset der Region im Bild (bei staff-Zone =
`staff.y_top`, bei below_staff-Zone = berechnetes `y_start`), damit `abs_y` korrekt
berechnet wird.
