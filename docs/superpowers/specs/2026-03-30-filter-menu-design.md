# Filter-Menu Design

## Ziel

Die zwei Toggle-Buttons ("Linien ausblenden" / "Symbole ausblenden") in der Scan-Editor-Toolbar durch ein Filter-Dropdown ersetzen. Zusätzlich: gefilterte Symbole (aus dem Post-Matching) im UI darstellbar machen und Symbole nach Kategorie ein-/ausblendbar machen.

## Backend: API-Schema-Erweiterung

### DetectedSymbolRead

Zwei neue Felder zum Pydantic-Schema hinzufügen:

```python
class DetectedSymbolRead(BaseModel):
    # ... bestehende Felder ...
    filtered: bool = False
    filter_reason: str | None = None
```

Die Felder existieren bereits in der DB (`DetectedSymbol` Model). Sie werden aktuell nur nicht serialisiert. Kein neuer Endpoint, keine Query-Änderung nötig.

### Kategorie-Info

Symbole haben bereits `matched_symbol.category` im API-Response. Das Frontend leitet die Kategorie-Liste daraus ab.

## Frontend: FilterDropdown Komponente

### Neues Component: `FilterDropdown.vue`

Ersetzt die zwei Toggle-Buttons in `ScanEditorPage.vue` Toolbar (Zeilen 450-465). Ein "Filter"-Button, bei Klick öffnet ein Dropdown.

**Dropdown-Inhalt:**

Bereich 1 — **Anzeige:**
- Checkbox "Notenlinien" (steuert `showStaves`)
- Checkbox "Gefilterte ausblenden" (Standard: **aktiviert**)

Trennlinie

Bereich 2 — **Symbolkategorien** (dynamisch):
- Je eine Checkbox pro Kategorie die in den aktuellen Symbolen vorkommt
- Anzeige mit Anzahl: z.B. "Noten (23)"
- Label aus bestehendem `categoryLabels`-Mapping: note → "Noten", rest → "Pausen", barline → "Taktstriche", clef → "Schlüssel", time_sig → "Taktarten", dynamic → "Dynamik", ornament → "Verzierungen", other → "Sonstige"
- Kategorien ohne Treffer werden nicht gezeigt
- Alle Kategorien sind standardmäßig aktiviert (sichtbar)

**Dropdown-Verhalten:**
- Klick auf "Filter"-Button öffnet/schließt das Dropdown
- Klick außerhalb schließt es
- Bleibt offen während Checkboxen angeklickt werden

### Props

- `showStaves: Boolean`
- `hideFiltered: Boolean`
- `symbols: Array` — vollständige Symbol-Liste (für Kategorie-Counts)
- `hiddenCategories: Set<string>` — Kategorie-Keys die ausgeblendet sind

### Events

- `update:showStaves` (Boolean)
- `update:hideFiltered` (Boolean)
- `update:hiddenCategories` (Set<string>)

## Frontend: Filterlogik in ScanEditorPage

### Neue Reactive State

```javascript
const hideFiltered = ref(true);          // Standard: gefilterte ausblenden
const hiddenCategories = ref(new Set()); // Leer = alle Kategorien sichtbar
```

### Computed: filteredSymbols

```javascript
const filteredSymbols = computed(() => {
  return symbols.value.filter(sym => {
    if (hideFiltered.value && sym.filtered) return false;
    const cat = sym.matched_symbol?.category ?? sym.corrected_symbol?.category;
    if (cat && hiddenCategories.value.has(cat)) return false;
    return true;
  });
});
```

### Toolbar-Änderungen

- Die zwei Toggle-Buttons ("Linien ausblenden" / "Symbole ausblenden") werden entfernt
- An ihrer Stelle kommt `<FilterDropdown>`
- `showSymbols` ref wird entfernt — Kategorie-Checkboxen steuern Sichtbarkeit
- `ScanCanvas` bekommt `filteredSymbols` statt `symbols`
- `showSymbols` Prop an ScanCanvas wird auf `true` gesetzt oder entfernt

### Status-Bar Update

Die Symbol-Anzahl in der Status-Bar (`statusMessage`) soll die gefilterte Anzahl reflektieren: z.B. "245 / 342 Symbole sichtbar · 180 verifiziert"

## Frontend: ScanCanvas — Visuelle Unterscheidung

Wenn `hideFiltered` deaktiviert ist und gefilterte Symbole sichtbar werden:
- Gestrichelte Umrandung (`stroke-dasharray="4,3"`) statt durchgezogener Linie
- Reduzierte Opacity (0.4)

Die `filtered`-Property ist am Symbol-Objekt vorhanden. `symbolColor()` bzw. die SVG-Attribute werden entsprechend angepasst.

## Dateistruktur

### Neue Dateien

| Datei | Inhalt |
|-------|--------|
| `src/frontend/src/components/FilterDropdown.vue` | Filter-Dropdown Komponente |

### Geänderte Dateien

| Datei | Änderung |
|-------|----------|
| `src/backend/mv_hofki/schemas/detected_symbol.py` | `filtered` + `filter_reason` Felder |
| `src/frontend/src/pages/ScanEditorPage.vue` | Toggle-Buttons entfernen, FilterDropdown einbinden, filteredSymbols computed |
| `src/frontend/src/components/ScanCanvas.vue` | Gestrichelte Darstellung für gefilterte Symbole |
