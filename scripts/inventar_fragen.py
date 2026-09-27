#!/usr/bin/env python
"""Write the open-questions list and the list of unclear instruments.

Usage (inside the devcontainer, from the project root):

    PYTHONPATH=src/backend python scripts/inventar_fragen.py

Reads the extraction (samplefiles/inventar_scans/_extraktion), builds the same
import plan as scripts/inventar_import.py and writes

* OFFENE_FRAGEN.md – everything still to be clarified, grouped: name matches
  with the scheduling app, active musicians without an instrument, questions per
  folder (answered ones are left out);
* UNKLARE_INSTRUMENTE.md – instruments that are not (or only doubtfully) in the
  inventory, each with every reference in the old records and the questions.
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import date
from pathlib import Path

from mv_hofki.core.config import settings
from mv_hofki.db.engine import async_session_factory
from mv_hofki.services.inventar_import import (
    UNCLEAR_OWNER,
    _describe_source,
    _page_index,
    active_without_instrument,
    build_plan,
    load_register_labels,
    load_short_codes,
)

ROOT = Path(settings.PROJECT_ROOT) / "samplefiles" / "inventar_scans"
SRC = ROOT / "_extraktion"
ORDER = [
    "Klarinette", "Bassklarinette", "Querfloete", "Saxophon", "Oboe", "Fagott",
    "Fluegelhorn", "Trompete", "Tenorhorn", "Zugposaune", "Tuba", "Waldhorn",
    "Schlagwerk", "Allgemeines_Inventar",
]  # fmt: skip

# Possible married names: same first name, different surname, same register.
# Not merged automatically – asked.
MARRIED_NAME_HINTS = [
    ("Cornelia Auinger", "Cornelia (Conny) Pichler", "Horn WH 2/WH 5"),
    ("Elisa Keplinger", "Elisa Schörgendorfer", "Horn WH 4"),
    ("Marion Zehetner", "Marion Oegger", "Tenorhorn TE 2"),
    ("Teresa Huemer-Baumgartner", "Theresa Anzengruber", "Tuba TU 3 (seit 2008)"),
]


def _open(q: dict) -> bool:
    return not q.get("antwort") or str(q["antwort"]).startswith(("Offen", "Teilweise"))


def _sources(inst: dict, folder: str, pages: dict[str, str]) -> list[str]:
    out = []
    for s in inst.get("quellen", []):
        page = s.split("#")[0]
        full = s if "/" in page else f"{folder}/{s}"
        out.append(_describe_source(full, pages))
    return out


def unclear_md(plan, pages) -> str:
    lines = [
        "# Unklare Instrumente",
        "",
        f"Stand {date.today():%d.%m.%Y}. Instrumente, die in den Altdaten vorkommen, "
        "deren Existenz, Identität oder Eigentum aber offen ist. Seitenbilder: "
        "`_extraktion/<Ordner>/seiten/` bzw. `_extraktion/_gesamt/seiten/`.",
        "",
        "## A. Nicht importiert (bis zur Klärung)",
        "",
    ]
    for zf in sorted(SRC.glob("*/zusammenfuehrung.json")):
        folder = zf.parent.name
        d = json.loads(zf.read_text())
        for inst in d.get("instrumente", []):
            if inst.get("import") is not False or inst.get("dublette_von"):
                continue
            desc = ", ".join(
                str(inst[k]) for k in ("typ", "hersteller", "modell") if inst.get(k)
            )
            sn = f", SN {inst['seriennummer']}" if inst.get("seriennummer") else ""
            lines.append(f"### {folder}/{inst['id']} – {desc}{sn}")
            lines.append("")
            lines.append(f"- **Grund:** {inst.get('import_grund')}")
            if inst.get("notiz"):
                lines.append(f"- **Notiz:** {inst['notiz']}")
            loans = [x for x in d["leihen"] if x["instrument"] == inst["id"]]
            people = {m["id"]: m for m in d["musiker"]}
            for x in loans:
                m = people.get(x["musiker"], {})
                who = f"{m.get('vorname') or ''} {m.get('nachname') or ''}".strip()
                lines.append(
                    f"- **Spieler:** {who} {x.get('von') or '?'}–{x.get('bis') or ''}"
                )
            lines.append("- **Fundstellen:**")
            lines += [f"  - {s}" for s in _sources(inst, folder, pages)]
            qs = [
                q
                for q in d.get("offene_fragen", [])
                if inst["id"] in (q.get("betrifft") or []) and _open(q)
            ]
            if qs:
                lines.append("- **Zu klären:**")
                lines += [f"  - {folder} {q['id']}: {q['frage']}" for q in qs]
            lines.append("")

    lines += [
        "## B. Nur aus Kaufbuchungen bekannt – kein passendes Instrument im Bestand",
        "",
    ]
    zu = json.loads((SRC / "_gesamt" / "beleg_zuordnung.json").read_text())
    for n in zu.get("nicht_zugeordnet", []):
        if n.get("kategorie") != "fehlendes_instrument":
            continue
        lines.append(f"- **{n['text']}** – {_describe_source(n['quelle'], pages)}")
        lines.append(f"  - {n.get('grund')}")
        lines.append(
            "  - Zu klären: Gibt es das Instrument noch (verkauft, verschollen, "
            "nicht gescannt)? Falls vorhanden: Inventarnummer, Seriennummer, Spieler."
        )
    lines += [
        "",
        "## C. Importiert, aber unsicher",
        "",
        "| Nr. | Instrument | Grund | Fundstellen |",
        "|---|---|---|---|",
    ]
    for i in sorted(plan.items, key=lambda x: (x.prefix, x.inventory_nr or 0)):
        reasons = []
        if i.owner == UNCLEAR_OWNER:
            reasons.append("Eigentum unklar")
        if "Nur aus Kaufbuchung bekannt" in i.notes:
            reasons.append("nur aus Kaufbuchung bekannt")
        if "Datenlage: offen" in i.notes:
            reasons.append("Datenlage offen")
        if not reasons:
            continue
        refs = "; ".join(s.split(" – ")[0] for s in i.sources)
        lines.append(f"| {i.display_nr} | {i.label} | {', '.join(reasons)} | {refs} |")
    return "\n".join(lines) + "\n"


def questions_md(plan) -> str:
    lines = [
        "# Offene Fragen zur Inventar-Digitalisierung",
        "",
        f"Stand {date.today():%d.%m.%Y}. Antworten bitte mit Ordner + ID "
        "(z. B. „Tuba Q3: …“). Unklare Instrumente stehen gesammelt in "
        "`UNKLARE_INSTRUMENTE.md`.",
        "",
        "## Musiker: Namensabgleich Termin-App ↔ Unterlagen (bitte bestätigen)",
        "",
        "Diese Namen wurden automatisch zusammengelegt:",
        "",
    ]
    lines += [
        f"- **M-{n}** „{x['termin_app']}“ = „{x['unterlagen']}“ ({x['art']})"
        for n, x in enumerate(plan.name_matches, 1)
    ]
    lines += [
        "",
        "Mögliche neue Nachnamen (Heirat) – **nicht** zusammengelegt:",
        "",
    ]
    lines += [
        f"- **H-{n}** Ist „{a}“ (Termin-App) dieselbe Person wie „{b}“ ({where})?"
        for n, (a, b, where) in enumerate(MARRIED_NAME_HINTS, 1)
    ]
    lines += [
        "",
        "## Aktive Musiker ohne erfasstes Instrument",
        "",
        "Laut Termin-App aktiv in einem Register mit Leihinstrument, aber in den "
        "Unterlagen ohne aktive Leihe und ohne Privatinstrument. Welches Instrument "
        "spielen sie (Inventarnummer oder privat)?",
        "",
    ]
    lines += [
        f"- **I-{n}** {m.first_name} {m.last_name} ({', '.join(m.registers)})"
        for n, m in enumerate(active_without_instrument(plan), 1)
    ]
    lines.append("")
    beleg = SRC / "_gesamt" / "beleg_fragen.json"
    if beleg.exists():
        lines += ["## Belegliste – unsichere Zuordnungen", ""]
        lines += [
            f"- **B-{n}** {q}"
            for n, q in enumerate(json.loads(beleg.read_text()), 1)
            if not q.startswith("Vereinskauf ohne Instrument")
        ]
        lines.append("")
    for folder in ORDER:
        path = SRC / folder / "zusammenfuehrung.json"
        if not path.exists():
            continue
        qs = [
            q for q in json.loads(path.read_text()).get("offene_fragen", []) if _open(q)
        ]
        if not qs:
            continue
        lines += [f"## {folder}", ""]
        for q in qs:
            b = ", ".join(q.get("betrifft") or [])
            lines.append(f"- **{q['id']}**{' (' + b + ')' if b else ''}: {q['frage']}")
        lines.append("")
    return "\n".join(lines) + "\n"


async def main() -> int:
    async with async_session_factory() as db:
        plan = build_plan(
            SRC,
            await load_short_codes(db),
            date.today(),
            active_list=ROOT / "aktive_musiker",
            register_labels=await load_register_labels(db),
        )
    pages = _page_index(SRC)
    (SRC / "UNKLARE_INSTRUMENTE.md").write_text(
        unclear_md(plan, pages), encoding="utf-8"
    )
    text = questions_md(plan)
    (SRC / "OFFENE_FRAGEN.md").write_text(text, encoding="utf-8")
    count = sum(1 for x in text.splitlines() if x.startswith("- **"))
    print(f"OFFENE_FRAGEN.md: {count} Fragen")
    print("UNKLARE_INSTRUMENTE.md geschrieben")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
