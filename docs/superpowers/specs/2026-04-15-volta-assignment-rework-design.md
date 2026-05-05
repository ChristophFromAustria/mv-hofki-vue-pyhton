# Volta-Zuweisung: Walk-Algorithmus und konfigurierbare Überlappung

## Problem

Die aktuelle Volta-Zuweisung markiert **alle** Takte, die mit einer Hitbox überlappen, mit
derselben `volta_number`. Bei einer durchgehenden Klammer, die über den Repeat-Taktstrich
hinweggeht, überschreibt Volta 2 die zuvor gesetzte Volta 1 — es wird nur eine Seite
angezeigt.

Beispiele aus "Alt-Starhemberg Marsch" Tuba 1:
- System 4: Klammer 2560–3475 px, Repeat bei ~3000 → nur Volta 2 sichtbar
- System 6: Klammer 2492–3173 px → nur Volta 1
- System 8: Klammer 2437–3504 px → nur Volta 1

## Scope

Nur die **Zuweisungslogik** wird geändert. Die Hitbox-Erkennung (Scan → Expand → Bridge →
Erase) bleibt unverändert.

## Algorithmus

Pro Repeat-Pair, nachdem beide Hitboxen (Volta 1 + Volta 2 Kandidat) erkannt sind:

1. Sammle alle Hitbox-Bounding-Boxes `(bx1, by1, bx2, by2)` dieses Pairs.
2. Sortiere die Takte desselben Staffs nach `x_start`.
3. Finde den Index `r` des Repeat-Takts (`pair_before`).
4. **Rückwärts ab `r`** (Volta 1): Prüfe Takt `r`, `r-1`, `r-2` …
   - Hat der Takt `>= volta_min_overlap_pct` X-Überlappung mit irgendeiner Hitbox?
   - Ja → `volta_number = 1`, `volta_group_id = group_id`. Weiter rückwärts.
   - Nein → Stopp.
5. **Vorwärts ab `r+1`** (Volta 2): Prüfe Takt `r+1`, `r+2` …
   - Gleiche Überlappungsprüfung.
   - Ja → `volta_number = 2`. Weiter vorwärts.
   - Nein → Stopp.

### Überlappungsberechnung

```
overlap_px = max(0, min(takt.x_end, hb.x_end) - max(takt.x_start, hb.x_start))
ratio = overlap_px / (takt.x_end - takt.x_start)
```

Ein Takt zählt als überlappt, wenn `ratio >= volta_min_overlap_pct` für **mindestens eine**
der gesammelten Hitboxen gilt.

### Cross-Staff

Der Walk operiert nur auf Takten des gleichen Staffs wie der jeweilige Kandidat. Beim
Cross-Staff-Fall (Volta 2 auf dem nächsten System) wird der Vorwärts-Walk auf dem Staff
von `pair_after` durchgeführt, startend beim ersten Takt dieses Staffs.

## Config-Parameter

Neuer Eintrag in `SCANNER_CONFIG_REGISTRY`:

| Feld          | Wert                                    |
|---------------|-----------------------------------------|
| key           | `volta_min_overlap_pct`                 |
| default_value | `"0.3"`                                 |
| type          | `"number"`                              |
| label         | `"Min. Überlappung Takt/Klammer (%)"` |
| group_path    | `"Nachbearbeitung\\Volta-Erkennung"`    |
| min           | 0.0                                     |
| max           | 1.0                                     |
| step          | 0.05                                    |
| sort_order    | 10                                      |

Zugriff in der Stage: `float(ctx.config.get("volta_min_overlap_pct", 0.3))`

## Strukturänderung

Die Volta-Zuweisung wird aus der Hitbox-Erkennungsschleife herausgezogen in eine eigene
Funktion `_assign_volta_numbers()`. Die Erkennungsschleife sammelt nur noch Hitboxen.

```
for pair_before, pair_after, group_id in repeat_pairs:
    hitboxes = []

    for volta_num, measure in candidates:
        # Erkennung wie bisher (scan, expand, erase, bridge, filter)
        # → SymbolData erstellen, logging
        # → hitboxes.append((bx1, by1, bx2, by2, staff_index))

    # Walk-Zuweisung mit allen gesammelten Hitboxes
    _assign_volta_numbers(
        ctx.measures, hitboxes, pair_before, pair_after, group_id, min_overlap
    )
```

## Betroffene Dateien

| Datei | Änderung |
|-------|----------|
| `src/backend/mv_hofki/services/scanner/stages/volta_detection.py` | Zuweisungslogik → `_assign_volta_numbers()`, Config-Zugriff |
| `src/backend/mv_hofki/services/scanner_config_registry.py` | Neuer Registry-Eintrag |
| `tests/backend/test_volta_detection.py` | Tests für Walk-Algorithmus, Überlappungsschwelle |
