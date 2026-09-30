# Konzept: Allgemeines Suchfeld

Todo-Punkt 16 (`docs/todo.md`). Ergebnis des Brainstormings vom 30.09.2026;
umgesetzt am selben Tag (`GlobalSearch.vue`, `SearchPage.vue`, `GET /api/v1/search`).

## Bedienung

- **Desktop:** Suchfeld in der Kopfzeile, auch per **Strg+K** oder **/** erreichbar.
- **Handy:** Lupen-Symbol in der Kopfzeile öffnet die Suche im Vollbild.
- Beim Tippen: **Popup mit den besten Treffern je Bereich** (höchstens 3), darunter
  „Alle *n* Treffer anzeigen“ → Seite **`/suche`** mit allen Treffern.
- Vollständig per Tastatur: ↑/↓ wählen, Enter öffnen, Esc schließen.
- **Eindeutige Inventarnummer + Enter** (z. B. „TR 6“) springt direkt zur Detailseite.
- Suche ab 2 Zeichen; Inventarnummern schon ab einem Zeichen („A 1“).

## Umfang

| Bereich | Durchsuchte Felder |
|---|---|
| Inventar (Instrumente, Kleidung, Allgemein, Noten) | Bezeichnung, Hersteller, Notizen, Inv.-Nr., Person der laufenden Ausleihe |
| Musiker | Vorname, Nachname, E-Mail, Ort — inaktive werden gefunden und markiert |
| Rechnungen | Titel, Aussteller (die Rechnungsnummer zählt pro Gegenstand 1, 2, 3 … und wäre als globaler Treffer nur Rauschen) |

Noten-Scans sind vorerst nicht dabei.

## Treffer

- Jeder Treffer zeigt seinen **Status**: Verfügbar / Ausgeliehen an … / Überfällig.
  Aktionen (Ausleihen, Zurückgeben) bleiben auf der Detailseite.
- Suchbegriffe sind **markiert**; liegt der Treffer in einem nicht angezeigten Feld,
  steht die Fundstelle darunter („Treffer in Notizen: …“) — wie in den Listen.
- **Feste Reihenfolge:** exakter Inv.-Nr.-Treffer ganz oben, dann Instrumente →
  Kleidung → Allgemein → Noten → Musiker → Rechnungen. Innerhalb eines Bereichs
  Treffer in der Bezeichnung vor Treffern in anderen Feldern.
- Keine „zuletzt gesucht“-Liste in der ersten Version.

## Wie gesucht wird

- **Mehrere Wörter:** jedes Wort muss in irgendeinem Feld vorkommen
  („trompete yamaha“ findet Yamaha-Trompeten). Gilt auch für die Listensuchen.
- **Tolerant:** Groß-/Kleinschreibung egal, **ü = ue = u**, ö/ä ebenso, **ß = ss**,
  andere Akzente werden ignoriert. Behebt nebenbei, dass SQLite `LIKE` nur bei
  ASCII Groß/Klein ignoriert („müller“ fand „MÜLLER“ nicht).

## Technik

- Backend: eine SQLite-Funktion `fold()` (auf jeder Verbindung registriert)
  vereinfacht Text; Suchfelder und Suchwörter werden gleich gefaltet und mit
  `LIKE` verglichen. Die Feldlisten der bestehenden Filter werden wiederverwendet.
- Neuer Endpunkt `GET /api/v1/search?q=…&limit=…` liefert die Bereiche mit Treffern,
  Gesamtzahl je Bereich und einen exakten Inv.-Nr.-Treffer.
- Frontend: `lib/highlight.js` faltet genauso und bildet die Positionen auf den
  Originaltext zurück, damit „mueller“ genau „Müller“ markiert.
