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
| label | Freitext "Bezeichnung" | **Dropdown** befüllt aus `instrument_type` — setzt `label` + `instrument_type_id` gleichzeitig |
| label_addition | Freitext | **Entfernt** |
| construction_year | Zahl-Input | **Jahres-Dropdown** (1900 bis aktuelles Jahr, Default = aktuelles Jahr) |
| serial_nr, manufacturer, distributor, container, particularities | — | Bleiben unverändert |

### Kleidung

| Feld | Vorher | Nachher |
|------|--------|---------|
| label | Freitext "Bezeichnung" | **Dropdown** befüllt aus `clothing_type` — setzt `label` + `clothing_type_id` gleichzeitig |
| size, gender | — | Bleiben unverändert |

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
  - Verwendet von Noten und Allgemein, ignoriert von Instrument und Kleidung
  - Auf Basis-Tabelle statt Detail-Tabelle, weil `general_item_detail` komplett entfällt

### Entfernte Spalte

- `instrument_detail.label_addition` — Spalte entfernen

### Entfernte Tabelle

- `general_item_detail` — Tabelle komplett entfernen (hatte nur `item_id` + `general_item_type_id`)
- `general_item_type` — Lookup-Tabelle entfernen (wird nicht mehr referenziert)

### Migration

- Alembic-Migration: `storage_location` auf `inventory_item` hinzufügen, `label_addition` von `instrument_detail` entfernen, `general_item_detail` und `general_item_type` droppen

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

Klick auf Zeile → navigiert zur Detail-Ansicht des zugehörigen Items.

### Summenzeile

- Am Tabellenende: **Gesamtsumme** der aktuell gefilterten Rechnungen
- Bei unterschiedlichen Währungen: Summe pro Währung separat (z.B. "Gesamt: 1.234,50 € · 500 ATS")

### Neuer API-Endpoint

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

## 6. Backend-Änderungen Zusammenfassung

### Entfernte Dateien

- `models/general_item_detail.py`
- `models/general_item_type.py`
- `schemas/general_item_type.py`
- `services/general_item_type.py`
- `api/routes/general_item_types.py`
- `pages/GeneralItemTypeListPage.vue`

### Geänderte Dateien (Backend)

- `models/inventory_item.py` — `storage_location` hinzufügen
- `models/instrument_detail.py` — `label_addition` entfernen
- `models/__init__.py` — GeneralItemDetail + GeneralItemType Exports entfernen
- `schemas/inventory_item.py` — storage_location in Schemas, label_addition entfernen, GeneralItemCreate vereinfachen (kein type_id mehr)
- `services/inventory_item.py` — CATEGORY_DETAIL_MAP anpassen (general_item hat keine Detail-Tabelle mehr), storage_location handling
- `db/seed.py` — GENERAL_ITEM_TYPES Seed-Daten entfernen
- `api/app.py` — general_item_types Router entfernen, invoices Router hinzufügen
- Neuer Service + Route für globale Rechnungsabfrage

### Geänderte Dateien (Frontend)

- `ItemFormModal.vue` (neu, ersetzt ItemFormPage.vue)
- `ItemListPage.vue` — Modal-Integration, angepasste Felder
- `ItemDetailPage.vue` — Modal-Integration, angepasste Detail-Anzeige
- `InvoiceListPage.vue` (neu)
- `router.js` — /neu und /bearbeiten Routen entfernen, /rechnungen hinzufügen
- `NavBar.vue` — Rechnungen-Link, Gegenstandstypen-Link entfernen
- `categories.js` — Konfiguration anpassen
