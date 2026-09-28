# Detailseiten: einklappbare Abschnitte und Bearbeiten Feld für Feld: Design

Datum: 2026-09-28
Teilprojekt 4 von 4 der Überarbeitung „Filter, Gruppierung, Listen und Detailseiten“.

## Ziel

- Auf den Detailseiten lassen sich lange Abschnitte einklappen, damit man schnell z.B. zu den Rechnungen kommt.
- Stammdaten werden direkt auf der Seite Feld für Feld bearbeitet, ohne Formular-Dialog.

## Entscheidungen (vom Benutzer bestätigt)

- **Einklappen:**
  - Der Zustand gilt pro Abschnitt und Seitentyp und wird im Browser gespeichert. Klappt man bei einem Instrument die Stammdaten ein, sind sie bei allen Instrumenten eingeklappt.
  - Beim ersten Besuch ist alles offen.
  - Eingeklappt zeigt der Kopf eine Kurzinfo.
- **Bearbeiten:** Feld für Feld; es wird jeweils nur ein Feld gespeichert.
- **Umfang:**
  - Item-Detailseiten (alle 4 Arten) und die Musiker-Detailseite.
  - Die bestehenden „Bearbeiten“-Formulare bleiben.

## Abschnitte

| Seite | Abschnitt (Schlüssel) | Kurzinfo, wenn eingeklappt |
|---|---|---|
| Item | Fotos (`photos`) | „3 Fotos“ / „Keine Fotos“ |
| | Unterlagen (`scans`, nur wenn vorhanden) | „3 Seiten“ |
| | Stammdaten (`master`) | „TU-002 · Yamaha“ (Hersteller nur, wenn vorhanden) |
| | Ausleihe (`loan`, verleihbare Arten) | „an Anna Maier seit 01.03.2026“ / „verfügbar“ |
| | Rechnungen (`invoices`) | „2 · 1.250,00 €“ (Summe je Währung) / „keine“ |
| | Leihhistorie (`history`, wenn vorhanden) | „5 Einträge“ |
| Musiker | Mitgliedschaft (`membership`) | „Aktiv · Tuba, Horn“ |
| | Kontakt (`contact`) | Telefon, sonst E-Mail, sonst „—“ |
| | Leihhistorie (`history`) | „5 Einträge“ |

- **Speicherschlüssel:** `detail-collapsed:<scope>:<abschnitt>`, wobei `<scope>` die Item-Art bzw. `musician` ist. Lesen und Schreiben stehen in `try/catch`.
- **Aufbau:** Der Abschnittskopf ist eine `<h2>` mit einem `<button aria-expanded aria-controls>` (Disclosure-Muster, mindestens 44 px hoch).
- **Aktionen:** Knöpfe wie „Neue Rechnung“ stehen in einem eigenen Slot rechts im Kopf und sind auch eingeklappt bedienbar.

## Bearbeiten Feld für Feld

### Komponenten

- **`useInlineEdit(save)`:** Composable mit `editingKey`, `savingKey`, `savedKey`, `error` und den Funktionen `start(key)`, `cancel()`, `commit(key, patch)`.
  - Es ist immer nur ein Feld im Bearbeitungsmodus.
  - `commit` ruft `save(patch)` auf.
  - **Erfolg:** Das Feld schließt, und `savedKey` bleibt 2 s gesetzt („Gespeichert“).
  - **Fehler:** Der Fehlertext bleibt am Feld stehen.
- **`InlineField.vue`:** rendert `<dt>` und `<dd>` für eine `detail-grid`-Liste.
  - **Anzeige:** der formatierte Wert und ein Stift-Button mit `aria-label` „„<Label>“ bearbeiten“, mindestens 44 px.
  - **Bearbeiten:** Eingabefeld mit „Speichern“ und „Abbrechen“.
  - **Typen:**
    - `text` und `textarea`
    - `number` (ganzzahlig, `min`/`max`)
    - `date`
    - `select` (mit „—“ für leer, wenn nicht `required`)
    - `bool` (Ja/Nein)
    - `multiselect` (Checkboxen)
    - `tags` (`TagSelect`)
    - `money` (Betrag + Währung)
  - **Tastatur:**
    - Enter speichert; bei `textarea` speichert Strg/⌘+Enter.
    - Escape bricht ab.
    - Beim Start liegt der Fokus im Eingabefeld, danach wieder auf dem Stift-Button.
  - **Prüfungen im Browser:**
    - `required`: Leer ergibt „Pflichtfeld“.
    - `number`: keine gültige Zahl ergibt „Bitte eine ganze Zahl eingeben.“; außerhalb der Grenzen „Mindestens <min>“ bzw. „Höchstens <max>“.
    - `money`: ein Betrag ohne Währung ergibt „Bitte eine Währung wählen.“
  - **Leere optionale Werte** werden als `null` gesendet.
  - **Anzeigeformat:**
    - leer: „—“
    - Datum: `TT.MM.JJJJ`
    - Geld: `de-AT` mit 2 Nachkommastellen und Kürzel
    - `bool`: „Ja“/„Nein“
    - Auswahl: das Label der Option
    - Eigene Anzeige ist über den Slot `display` möglich.

### Felder

- **Items:** Die Felder kommen aus `lib/itemFields.js` → `itemFieldDefs(category, ctx)`. Die Inventarnummer bleibt nur lesbar.

| Art | Felder |
|---|---|
| alle | Menge (Zahl ≥ 1, Pflicht), Hersteller, Eigentümer (Pflicht), Anschaffungsdatum, Anschaffungskosten (money), Notizen (textarea) |
| Instrument | **Typ** (Auswahl, Pflicht; setzt auch `label`), Seriennummer, Baujahr (1800 – aktuelles Jahr + 1), Händler, Behältnis, Besonderheiten (textarea) |
| Kleidung | **Typ** (Auswahl, Pflicht; setzt auch `label`), Größe, Geschlecht |
| Noten | **Titel** (Pflicht), Komponist, Arrangeur, Schwierigkeitsgrad, Gattung (Auswahl, optional), Lagerort |
| Allgemein | **Bezeichnung** (Pflicht), Kategorien (tags, Anlegen erlaubt), Lagerort |

- **Typwechsel bei Instrumenten:** Hat der neue Typ ein anderes Kürzel als das aktuelle `number_prefix`, fragt vorher ein `ConfirmDialog`: „Die Inventarnummer wird neu vergeben: TU-002 → HR-…“. Nach dem Speichern zeigt die Seite die neue Nummer im Titel.
- **Korrekturen an der Anzeige:** „Hersteller“ erscheint nur noch einmal, und „Typ“ wird für Instrumente angezeigt.
- **Musiker:** Vorname und Nachname (Pflicht), Telefon, E-Mail, Adresse, PLZ (Zahl), Ort, Status aktiv (bool), Extern (bool), Register (multiselect → `register_ids`), Notizen (textarea).

## Backend

- **`PUT /api/v1/items/{id}`:** Ungültige Werte ergeben 422 mit der Pydantic-Detail-Liste, wie beim Anlegen. Bisher gab es 500.
- **`ItemUpdateBase`:** `label`, `owner` und `quantity` dürfen nicht leer bzw. `null` gesetzt werden, wenn sie mitgeschickt werden (422, Meldung „Pflichtfeld“).

## Nebenbei

In der Kartenansicht der Item-Listen bekommen die Gruppenüberschriften wieder abgerundete Ecken; das ist ein Rest aus Teilprojekt 3.

## Nicht Teil dieses Teilprojekts

- Rechnungen, Leihen und Fotos inline bearbeiten (dort gibt es eigene Formulare).
- Bearbeiten ohne Netz, rückgängig machen.

## Tests

**Backend:** 422 für Menge 0, leeren und `null`-Eigentümer, leere Bezeichnung; gültige Teil-Updates bleiben 200.

**Frontend:**
- `useSectionCollapse`: Standard offen, Umschalten, Speichern, kaputter Storage.
- `CollapsibleSection`: ARIA, Kurzinfo nur eingeklappt, Aktionen immer sichtbar.
- `useInlineEdit`: nur ein Feld, Erfolg, Fehler, „Gespeichert“ läuft ab.
- `InlineField` für jeden Typ: Anzeige, Prüfung, Tastatur, `null` bei leer.
- `itemFieldDefs`: Felder je Art, Patch für Typ inklusive `label`, Anzeige der Kosten.

**Browser:**
- Item- und Musikerseite bei 390 px, im hellen und dunklen Theme.
- Einklappen bleibt über Items hinweg erhalten.
- An einem Item wird ein Feld geändert und wieder zurückgesetzt, danach wird verglichen, dass alles wie vorher ist. Ebenso an einem Musiker.
