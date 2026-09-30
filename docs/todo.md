# Todo

Aus der Besprechung vom 30.09.2026 (handschriftliche Liste), ergänzt um den
Stand im Code. Keine Umsetzungspläne — Punkte mit „Brainstorming“ brauchen vor
der Umsetzung eine eigene Klärung.

Umfang: **klein** = in einer Sitzung umsetzbar · **mittel** = überschaubar,
aber mehrere Stellen · **groß** = Umbau, vorher Brainstorming.

**Reihenfolge:** zuerst die kleinen Punkte, danach als erstes großes Thema das
allgemeine Suchfeld (16, größter Wunsch).

## Leihregister

1. **Notizen auf Leihregister** — *klein.* Freitextfeld pro Ausleihe.
2. **Wer hat ausgegeben / zurückgenommen** — *mittel.* Bei Ausgabe und Rückgabe
   festhalten, wer sie erfasst hat. Setzt Benutzer voraus (14), mindestens die
   E-Mail aus Cloudflare Access.
3. **Geplantes Rückgabedatum** — *klein.* Soll-Rückgabedatum pro Ausleihe;
   überfällige Ausleihen sichtbar machen.

## Musiker

4. **Musiker direkt anlegen** — *klein.* Eine neue Person direkt im
   Personen-Auswahlfeld (z. B. beim Ausleihen) anlegen, ohne die Seite zu
   verlassen.
5. ~~**Suchumfang umschaltbar**~~ — ✅ erledigt (30.09.2026). *klein.* In Personen-Suchfeldern direkt
   umstellen können: nur aktive / alle Musiker. Heute sucht das Auswahlfeld
   beim Ausleihen fest nur aktive (`fetchMusicianOptions`, `activeOnly`).
6. ~~**Status-Schalter auf der Detailseite**~~ — ✅ erledigt (30.09.2026). *klein.* Die Checkbox „Status“
   (unklar, ob gesetzt = aktiv) wird ein Umschalter „Aktiv/Inaktiv“, direkt in
   der Detailansicht bedienbar und sofort gespeichert, ohne Bearbeiten-Modus.

## Inventar

7. **Inventar-Nr in der URL** — *mittel.* `/instrumente/TR-0006` statt der
   Datenbank-ID. Nach 10 umsetzen; klären, was bei einer Umnummerierung mit
   alten Links passiert.
8. **Inventar-Items kopieren** — *mittel.* Bestehenden Gegenstand als Vorlage
   nehmen; per Checkbox-Menü wählen, welche Werte übernommen werden. Die
   Nummer ist immer neu.
9. **Freigewordene Nummern nie wieder vergeben** — *klein.* Heute ist die
   nächste Nummer „höchste vorhandene + 1“ (`next_inventory_nr`): Lücken in der
   Mitte bleiben frei, aber nach dem Löschen des Stücks mit der *höchsten*
   Nummer (oder dessen Umnummerierung) wird genau diese Nummer wieder vergeben.
   Braucht einen gespeicherten Höchststand pro Präfix.
10. **Vierstellige Inventarnummern** — *klein.* Alle Kategorien auf `XX-0000`,
    solange das System noch nicht im Vollbetrieb ist (bei Kleidung und
    Allgemein sind mehr als 999 Stück pro Typ möglich). Betrifft Anzeige,
    Suche („tr 6“ muss weiter funktionieren) und Import; gespeichert ist die
    Nummer als Zahl, es ist also eine Formatfrage.
11. **Löschen nicht endgültig** — *groß, Brainstorming.* Papierkorb/Archiv mit
    Wiederherstellen statt endgültigem Löschen (heute inkl. Bildern und
    Rechnungen auf der Platte). Zusammen mit 15 und 9 betrachten.

## Druck & Export

12. **Datenblätter drucken / als PDF exportieren** — *groß, Brainstorming.*
    Allgemeines Feature für Datenblätter von Gegenständen, einzeln und für
    ganze Gruppen (z. B. alle Trompeten, eine gefilterte/gruppierte Liste).
    Offen: welche Felder aufs Datenblatt (Foto, aktuelle Ausleihe, Rechnungen …).
13. **QR-Codes für Etiketten** — *groß, Brainstorming.* QR-Code pro Gegenstand,
    als Etikett gedruckt. Hängt an 7 (Linkziel), 10 (Nummernformat) und 12
    (Druck). Offen: Etikettenformat/Drucker, was außer dem QR-Code draufsteht.

## Querschnitt

14. **Berechtigungssystem** — *groß, Brainstorming.* Rollen (z. B. Zeugwart,
    Notenwart, nur lesen). Heute keine Benutzer; Cloudflare Access liefert die
    E-Mail der angemeldeten Person mit.
15. **Event Log** — *groß, Brainstorming.* Wer hat wann was angelegt, geändert,
    verliehen, gelöscht.
16. **Allgemeines Suchfeld** — *groß, Brainstorming, nächstes großes Thema.*
    Eine Suche über alle Bereiche statt nur pro Liste.

## Organisatorisch

17. **Domain** — mit dem Verwalter der offiziellen Vereins-Domain klären, ob sie
    statt der derzeit verwendeten privaten Domain genutzt werden kann.

## Zusammenhänge

- **14 → 2, 15:** ohne Benutzer kein „wer“.
- **11 ↔ 15 ↔ 9:** Papierkorb, Protokoll und nicht wiedervergebene Nummern
  gehören zusammen.
- **10 → 7 → 13:** erst das Nummernformat, dann die URL, dann der QR-Code —
  sonst sind Etiketten mit falschem Format oder Link im Umlauf.
- **12 ↔ 13:** der Etikettendruck ist ein Sonderfall des Druck-Features.
