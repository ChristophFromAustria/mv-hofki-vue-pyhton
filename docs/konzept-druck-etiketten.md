# Konzept: Druck/PDF und QR-Etiketten

Todo-Punkte 12 und 13 (`docs/todo.md`). Ergebnis des Brainstormings vom 01.10.2026;
alle drei Phasen am selben Tag umgesetzt.

## Grundsatz

Der **Server erzeugt PDFs**: exakte Maße (wichtig für Etiketten), viele Gegenstände in
einer Datei, gleiches Ergebnis auf jedem Gerät. Am Handy öffnet sich das PDF und wird
von dort gedruckt oder geteilt.

## Einstiegspunkte

- **Gegenstandsseite → „Drucken …“:** Datenblatt oder Etikett für diesen Gegenstand.
- **Liste → „Drucken …“:** Datenblätter, Etiketten oder Inventarliste für **alle gerade
  angezeigten** Gegenstände (aktueller Filter, Suche, Bestand-Filter).

## Datenblatt (A4 hoch, eines pro Gegenstand)

- Kopf: Inventarnummer, Bezeichnung, **QR-Code rechts oben**; darunter die Stammdaten.
- **Checkbox-Menü** für die weiteren Abschnitte: Profilfoto, aktuelle Ausleihe,
  Leihhistorie, Rechnungen (Übersicht ohne Dateien), Notizen. Die letzte Auswahl merkt
  sich der Browser.
- Fußzeile: „MV Hofkirchen · Stand <Datum>“.

## Etiketten

- Inhalt: **QR-Code + Inventarnummer (groß) + „MV Hofkirchen“**.
- Hardware noch offen, daher **Format einstellbar**: Vorlagen für Etikettenrolle (z. B.
  62×29 mm) und gängige A4-Bögen (z. B. 70×37 mm, 3×8), oder eigene Maße in mm (bei Bögen
  mit Spalten/Zeilen/Rändern).
- Bei A4-Bögen **„Beginnen bei Etikett Nr. …“**, damit angebrochene Bögen verwendet
  werden können.

## Inventarliste (A4 quer)

- Tabelle aller angezeigten Gegenstände, **Spalten per Checkbox**, gruppiert wie die
  Liste, mit Anzahl und optional Summe der Anschaffungskosten je Währung (Versicherung,
  Kassaprüfung, Jahreshauptversammlung).

## QR-Code-Adresse

- Der QR-Code enthält `PUBLIC_URL` + `/inventar/<id>` — die id bleibt, auch wenn sich
  die Inventarnummer mit dem Typ ändert; `/inventar/<id>` leitet zur aktuellen Seite.
- `PUBLIC_URL` ist eine Einstellung (`.env`), vorerst **https://inventar.mvhofki.xyz**.
- Solange die endgültige Domain nicht geklärt ist (Todo 17), **keinen Massendruck** von
  Etiketten; Testdrucke sind unkritisch. Alternative: eigene Etiketten-(Sub)Domain, die
  später umgeleitet werden kann.

## Technik

- PDF mit **PyMuPDF** (bereits installiert), QR-Codes mit **segno**, Schrift **DM Sans**
  eingebettet (`src/backend/mv_hofki/assets/fonts`, SIL Open Font License).
- Drucken wird nicht protokolliert.

## Reihenfolge

1. PDF-Grundlage + Datenblatt (einzeln und aus der Liste)
2. Etiketten mit Vorlagen
3. Inventarliste
