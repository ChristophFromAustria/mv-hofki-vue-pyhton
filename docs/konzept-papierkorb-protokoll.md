# Konzept: Protokoll, Papierkorb, Ausgeschieden

Todo-Punkte 11 und 15 (`docs/todo.md`), deckt nebenbei Punkt 2 ab. Ergebnis des
Brainstormings vom 30.09.2026. Umsetzung in drei Phasen, in dieser Reihenfolge —
alle drei am 30.09.2026 umgesetzt.

## Phase 1 — Protokoll (Event Log)

- **Vollständig:** Anlegen, jede Feldänderung mit **Alt → Neu** (Fremdschlüssel als
  Klartext, z. B. „Typ: Trompete → Flügelhorn“), Ausleihe und Rückgabe, Bilder,
  Rechnungen, Kategorien und Register, Papierkorb, Wiederherstellen, endgültiges
  Löschen, Ausscheiden. Musiker, Gegenstände, Ausleihen, Rechnungen, Bilder und
  Stammdaten.
- **Wer:** E-Mail aus dem Cloudflare-Access-Header
  (`Cf-Access-Authenticated-User-Email`); ohne Tunnel „unbekannt“. Importe tragen die
  Quelle „KI-Import“, automatische Vorgänge „System“. Damit ist Todo 2 („wer hat
  ausgegeben / zurückgenommen“) erfüllt.
- **Nur lesen** — kein Rückgängig aus dem Protokoll.
- **Anzeige:**
  - Dashboard: die **neuesten 10 Einträge** mit Link „Ganzes Protokoll“.
  - **Verlauf** (aufklappbar) auf Gegenstands- und Musikerseiten.
  - Seite **Protokoll**, filterbar nach Bereich, Person, Aktion und Zeitraum.
- Das Protokoll beginnt leer (kein rückwirkendes Nachtragen) und wird nicht geleert.
  Importe: ein Ereignis pro angelegtem Datensatz (Quelle „KI-Import“).
- **Technik:** Änderungen werden zentral beim Speichern (SQLAlchemy-Flush) erfasst,
  nicht in jedem Service einzeln — so kann keine Änderung vergessen werden.

## Phase 2 — Papierkorb

- **Löschen verschiebt in den Papierkorb:** Gegenstände (mit Bildern, Rechnungen,
  Leihhistorie), Musiker (mit Leihhistorie; in alten Ausleihen „im Papierkorb“
  markiert), einzelne Rechnungen und Bilder, Stammdaten (Typen, Register,
  Kategorien, Gattungen, Währungen).
- Inventarnummern gelöschter Gegenstände bleiben gesperrt.
- Seite **Papierkorb:** was, wann, von wem; **Wiederherstellen** und **Endgültig
  löschen** (mit Bestätigung).
- **Nach 90 Tagen automatisch endgültig gelöscht** (inkl. Dateien); geprüft beim
  Serverstart und danach täglich, protokolliert als „System“.
- Stammdaten, die noch verwendet werden, lassen sich wie bisher nicht löschen.
  Wer einen Namen neu anlegt, der im Papierkorb liegt, bekommt den Hinweis, ihn
  dort wiederherzustellen.
- **Technik:** Spalte `deleted_at`; gelöschte Zeilen werden in allen Abfragen
  automatisch ausgeblendet (zentraler Filter), nur Papierkorb und
  Nummernvergabe sehen sie.

## Phase 3 — Ausgeschieden

- Für Gegenstände, die real weg sind: **Grund** (Verkauft, Verloren/gestohlen,
  Verschrottet/defekt, An Eigentümer zurückgegeben, Sonstiges), **Datum**, **Notiz**.
- Nur ohne offene Ausleihe; „Wieder in Bestand“ macht es rückgängig.
- Bleiben mit Historie und Nummer erhalten, erscheinen aber nicht in den normalen
  Listen (Filter **Bestand / Ausgeschieden / Alle**), nicht im Ausleihen-Picker und
  nicht in den Bestandszahlen; die Detailseite zeigt einen deutlichen Hinweis, die
  globale Suche findet sie mit Kennzeichnung.
