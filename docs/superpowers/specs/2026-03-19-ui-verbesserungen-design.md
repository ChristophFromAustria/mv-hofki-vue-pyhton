# UI-Verbesserungen: Modale Formulare, Währung, Kategoriefelder, Rechnungsübersicht

**Datum:** 2026-03-19
**Status:** Entwurf

## Zusammenfassung

Sechs zusammenhängende UI/UX-Verbesserungen für das Inventarsystem:
1. Create/Edit-Formulare als Modal statt eigener Seiten
2. Standardwährung € mit Stift-Icon-Flyout zur Auswahl
3. Kategorie-spezifische Feld-Anpassungen (Label-Dropdown, Titel, Typ-Entfernung)
4. Neue Rechnungs-Übersichtsseite mit Filtern und Summe
5. Lagerort-Feld für Noten und Allgemein
6. Baujahr als Jahres-Dropdown bei Instrumenten

## 1. Modal-Formulare

### Verhalten

- Create/Edit-Formulare werden als **Modal-Dialog** über der aktuellen Seite angezeigt
- **List-Page:** "Neu"-Button öffnet leeres Modal
- **Detail-Page:** "Bearbeiten"-Button öffnet Modal mit vorausgefüllten Daten
- Nach Speichern: Modal schließt, Daten werden neu geladen

### Router-Änderungen

- Routen `/{kategorie}/neu` und `/{kategorie}/:id/bearbeiten` **entfallen**
- `ItemFormPage.vue` wird zu `ItemFormModal.vue` (Komponente, keine Page)
- `ItemFormModal` wird in `ItemListPage.vue` und `ItemDetailPage.vue` eingebunden

### Modal-Design

- Gleicher Stil wie bestehendes `InvoiceModal` (overlay + dialog)
- Breite: `max-width: 700px`
- Scrollbar bei langem Inhalt
- Schließen via X-Button oder Klick auf Overlay

## 2. Währungs-Anzeige & Picker

### Verhalten

- **Standardwährung:** € (Euro), automatisch vorausgewählt bei neuen Items
- Kostenfelder zeigen Währung im Label: **"Anschaffungskosten (€)"**
- Neben dem Label ein **Stift-Icon (SVG)** — Klick öffnet ein Flyout-Panel
- Flyout zeigt verfügbare Währungen als Buttons (€, ATS, $, £)
- Nach Auswahl: Flyout schließt, Label aktualisiert sich sofort
- Gleiches Muster im **InvoiceModal** für "Betrag"

### Umsetzung

Das bestehende Muster aus `InvoiceModal.vue` (currency-edit-btn + currency-picker) wird:
1. Im `ItemFormModal` für Anschaffungskosten angewandt
2. Im `InvoiceModal` beibehalten (bereits vorhanden)

## 3. Kategorie-spezifische Felder

### Instrument

| Feld | Vorher | Nachher |
|------|--------|---------|
| label | Freitext "Bezeichnung" | **Dropdown** befüllt aus `instrument_type` — setzt `label` + `instrument_type_id` gleichzeitig. Label ist **gelockt** auf den Typ-Namen. |
| label_addition | Freitext | **Entfernt** (Spalte aus DB entfernen, bestehende Werte in `particularities` übernehmen) |
| construction_year | Zahl-Input | **Jahres-Dropdown** (1950 bis aktuelles Jahr, Default = aktuelles Jahr) |
| serial_nr, manufacturer, distributor, container, particularities | — | Bleiben unverändert |

**Unterscheidung gleichartiger Instrumente:** Mehrere Instrumente gleichen Typs (z.B. 3x "Klarinette in B") werden in Listen durch `display_nr` (I-001, I-002, I-003) und `manufacturer` unterschieden. Die Kombination aus Typ + display_nr + Hersteller ist ausreichend.

### Kleidung

| Feld | Vorher | Nachher |
|------|--------|---------|
| label | Freitext "Bezeichnung" | **Dropdown** befüllt aus `clothing_type` — setzt `label` + `clothing_type_id` gleichzeitig. Label ist **gelockt** auf den Typ-Namen. |
| size, gender | — | Bleiben unverändert |

**Unterscheidung:** Kleidungsstücke gleichen Typs werden durch `size`, `gender` und `display_nr` unterschieden.

### Noten

| Feld | Vorher | Nachher |
|------|--------|---------|
| label | Freitext "Bezeichnung" | Freitext mit Label **"Titel"** |
| storage_location | — | **Neu:** Freitext "Lagerort" |
| composer, arranger, difficulty, genre | — | Bleiben unverändert |

### Allgemein

| Feld | Vorher | Nachher |
|------|--------|---------|
| label | Freitext "Bezeichnung" | Bleibt Freitext "Bezeichnung" |
| general_item_type | Dropdown (Pflichtfeld) | **Entfernt** (Dropdown, Typ-Tabelle, Seed-Daten, Settings-Seite) |
| storage_location | — | **Neu:** Freitext "Lagerort" |

## 4. Datenbank-Änderungen

### Neue Spalte

- `inventory_item.storage_location` — `VARCHAR(200) NULL`
  - Auf Basis-Tabelle, damit alle Kategorien es technisch nutzen können
  - Frontend zeigt das Feld nur bei Noten und Allgemein an
  - In Schemas: `storage_location` wird auf `ItemCreateBase` definiert (verfügbar für alle Kategorien, Frontend steuert Sichtbarkeit)

### Entfernte Spalte

- `instrument_detail.label_addition` — Spalte entfernen

### Entfernte Tabellen

- `general_item_detail` — Tabelle komplett entfernen (hatte nur `item_id` + `general_item_type_id`)
- `general_item_type` — Lookup-Tabelle entfernen (wird nicht mehr referenziert)

### Migration

Alembic-Migration in einem Schritt:
1. Bestehende `label_addition`-Werte in `particularities` übernehmen (UPDATE ... SET particularities = label_addition WHERE label_addition IS NOT NULL AND particularities IS NULL; bei beiden gesetzt: Konkatenation)
2. `storage_location` auf `inventory_item` hinzufügen
3. `label_addition` von `instrument_detail` entfernen
4. `general_item_detail` und `general_item_type` droppen

## 5. Rechnungs-Übersichtsseite

### Neue Seite: `/rechnungen`

NavBar-Link zwischen "Leihregister" und "Einstellungen".

### Filter

- **Kategorie:** Dropdown (Alle / Instrumente / Kleidung / Allgemein) — Noten sind ausgenommen (haben keine Rechnungen)
- **Zeitraum:** Von-Datum / Bis-Datum (date inputs)
- **Suche:** Freitext (durchsucht Titel, Aussteller)

### Tabelle

| Spalte | Inhalt |
|--------|--------|
| Nr. | invoice_nr |
| Gegenstand | display_nr + label des zugehörigen Items |
| Bezeichnung | Rechnungs-Titel |
| Datum | date_issued |
| Betrag | amount + Währungskürzel |
| Datei | Badge Ja/Nein |

- **Default-Sortierung:** `date_issued DESC`
- Klick auf Zeile → navigiert zur Detail-Ansicht des zugehörigen Items
- Pagination: 50 pro Seite

### Summenzeile

- Am Tabellenende: **Gesamtsumme** der aktuell gefilterten Rechnungen
- `totals_by_currency` bezieht sich auf das **gesamte Filter-Set**, nicht nur die aktuelle Seite
- Bei unterschiedlichen Währungen: Summe pro Währung separat (z.B. "Gesamt: 1.234,50 € · 500 ATS")

### Neuer API-Endpoint

**Datei:** `api/routes/invoices.py` (global, vs. bestehendes `api/routes/item_invoices.py` für per-Item)
**Service:** `services/invoice_overview.py`

```
GET /api/v1/invoices?category=&search=&date_from=&date_to=&limit=50&offset=0
```

Response:
```json
{
  "items": [
    {
      "id": 1,
      "invoice_nr": 1,
      "item_id": 5,
      "item_display_nr": "I-001",
      "item_label": "Querflöte",
      "item_category": "instrument",
      "title": "Reparatur",
      "date_issued": "2026-01-15",
      "amount": 150.00,
      "currency": { "id": 1, "label": "Euro", "abbreviation": "€" },
      "filename": "abc123.pdf",
      "file_url": "/uploads/invoices/5/abc123.pdf"
    }
  ],
  "total": 25,
  "totals_by_currency": [
    { "abbreviation": "€", "total": 1234.50 },
    { "abbreviation": "ATS", "total": 500.00 }
  ]
}
```

## 6. Service-Layer: general_item ohne Detail-Tabelle

Da `general_item_detail` wegfällt, braucht `general_item` keine Detail-Tabelle mehr. Änderungen in `services/inventory_item.py`:

- `CATEGORY_DETAIL_MAP`: Eintrag für `general_item` bekommt `None` als DetailModel
- Guard-Clauses in `create()`, `get_by_id()`, `get_list()`, `update()`, `_build_read_dict()`: wenn `detail_model is None`, Detail-Operationen überspringen
- `_split_fields()`: gibt leeres Dict für Detail-Felder zurück wenn keine Detail-Felder definiert

## 7. Datei-Änderungen Zusammenfassung

### Entfernte Dateien

- `src/backend/mv_hofki/models/general_item_detail.py`
- `src/backend/mv_hofki/models/general_item_type.py`
- `src/backend/mv_hofki/schemas/general_item_type.py`
- `src/backend/mv_hofki/services/general_item_type.py`
- `src/backend/mv_hofki/api/routes/general_item_types.py`
- `src/frontend/src/pages/GeneralItemTypeListPage.vue`
- `src/frontend/src/pages/ItemFormPage.vue` (ersetzt durch ItemFormModal.vue)
- `tests/backend/test_general_item_types.py`

### Neue Dateien

- `src/backend/mv_hofki/services/invoice_overview.py` — Globale Rechnungsabfrage mit Filter + Summen
- `src/backend/mv_hofki/api/routes/invoices.py` — Route für `/api/v1/invoices`
- `src/backend/mv_hofki/schemas/invoice_overview.py` — Schemas für globale Rechnungsresponse
- `src/frontend/src/components/ItemFormModal.vue` — Modal-Formular (ersetzt ItemFormPage.vue)
- `src/frontend/src/pages/InvoiceListPage.vue` — Rechnungsübersicht

### Geänderte Dateien (Backend)

- `models/inventory_item.py` — `storage_location` Spalte hinzufügen
- `models/instrument_detail.py` — `label_addition` Spalte entfernen
- `models/__init__.py` — GeneralItemDetail + GeneralItemType Exports entfernen
- `schemas/inventory_item.py` — `storage_location` in `ItemCreateBase`/`ItemUpdateBase`/`ItemRead`, `label_addition` aus Instrument-Schemas entfernen, `GeneralItemCreate`/`GeneralItemUpdate`/`GeneralItemRead` vereinfachen (kein type_id), `SheetMusicItemCreate`/`SheetMusicItemRead` behalten `storage_location` über Basis-Schema
- `services/inventory_item.py` — `CATEGORY_DETAIL_MAP` anpassen (`general_item` → `None`), Guard-Clauses für Detail-Operationen
- `db/seed.py` — `GENERAL_ITEM_TYPES` Seed-Daten und Import entfernen
- `api/app.py` — `general_item_types` Router entfernen, `invoices` Router hinzufügen

### Geänderte Dateien (Frontend)

- `ItemListPage.vue` — Modal-Integration für Create, Spalten anpassen (Hersteller bei Instrumenten)
- `ItemDetailPage.vue` — Modal-Integration für Edit, Detail-Felder anpassen (kein label_addition, storage_location für Noten/Allgemein, kein general_item_type)
- `InvoiceModal.vue` — Prop `instrumentId` → `itemId` (falls noch nicht geschehen)
- `router.js` — `/neu` und `/bearbeiten` Routen entfernen, `/rechnungen` Route hinzufügen
- `NavBar.vue` — "Rechnungen"-Link hinzufügen, "Gegenstandstypen"-Link entfernen
- `categories.js` — Konfiguration für Label-Typ (dropdown vs. text), labelFieldName
- `LoanListPage.vue` — Falls general_item_type Referenzen vorhanden, entfernen
- `DashboardPage.vue` — Falls general_item_type Referenzen vorhanden, entfernen

### Geänderte Tests

- `tests/backend/test_items.py` — general_item Tests anpassen (kein type_id mehr), label_addition Tests entfernen, storage_location Tests hinzufügen
- `tests/backend/test_item_invoices.py` — Falls Referenzen auf general_item_type
- Neuer Test: `tests/backend/test_invoice_overview.py` — Tests für globalen Rechnungs-Endpoint
