#!/usr/bin/env python
"""Import the digitised paper inventory into the database.

Usage (inside the devcontainer, from the project root):

    # dry run: write the report, change nothing
    PYTHONPATH=src/backend python scripts/inventar_import.py

    # replace ALL instruments, musicians, loans, invoices and images
    PYTHONPATH=src/backend python scripts/inventar_import.py --ersetzen

The source is samplefiles/inventar_scans/_extraktion (per-folder
zusammenfuehrung.json, _gesamt/musiker.json, fotos/). Both runs write
IMPORT_BERICHT.md and import_bericht.json next to the sources: what would be /
was created, every assumption made, and everything left out. ``--ersetzen``
first copies the database to data/backups/ and runs everything in one
transaction.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import sys
from collections import Counter
from datetime import date, datetime
from pathlib import Path

from mv_hofki.core.config import settings
from mv_hofki.db.engine import async_session_factory
from mv_hofki.services.inventar_import import (
    Plan,
    apply_plan,
    build_plan,
    load_short_codes,
    wipe_inventory,
)

ROOT = Path(settings.PROJECT_ROOT)
DEFAULT_SOURCE = ROOT / "samplefiles" / "inventar_scans" / "_extraktion"
UPLOADS = ROOT / "data" / "uploads"
DB_FILE = ROOT / "data" / "mv_hofki.db"


def _report_md(plan: Plan, applied: bool, result: dict | None) -> str:
    by_type = Counter(i.type_label for i in plan.items)
    names = {m.key: f"{m.last_name} {m.first_name}".strip() for m in plan.musicians}
    nr_of = {i.key: i.display_nr for i in plan.items}
    lines = [
        f"# Inventar-Import – {'durchgeführt' if applied else 'Probelauf'}",
        "",
        f"Stand {datetime.now():%d.%m.%Y %H:%M}.",
        "",
        f"- Instrumente: {len(plan.items)}",
        f"- Musiker: {len(plan.musicians)}",
        f"- Leihen: {len(plan.loans)} (davon aktiv: "
        f"{sum(1 for x in plan.loans if x.end is None)})",
        f"- Belege: {len(plan.invoices)}",
        f"- Fotos: {sum(len(i.photos) for i in plan.items)}",
        f"- Hinweise: {len(plan.warnings)}, nicht übernommen: {len(plan.skipped)}",
        "",
        "## Instrumente",
        "",
        "| Nr. | Papier | Typ | Bezeichnung | Seriennr. | Eigentümer | Lager | Fotos |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for i in sorted(plan.items, key=lambda x: (x.prefix, x.inventory_nr or 0)):
        lines.append(
            f"| {i.display_nr} | {i.paper_nr or ''} | {i.type_label} | {i.label} | "
            f"{i.serial_nr or ''} | {i.owner} | {i.storage_location or ''} | "
            f"{len(i.photos)} |"
        )
    lines += [
        "",
        "Nach Typ: " + ", ".join(f"{k} {v}" for k, v in sorted(by_type.items())),
        "",
    ]
    lines += ["## Aktive Leihen", "", "| Nr. | Musiker | seit |", "|---|---|---|"]
    for x in sorted(plan.loans, key=lambda x: nr_of[x.item_key]):
        if x.end is None:
            lines.append(
                f"| {nr_of[x.item_key]} | {names[x.musician_key]} "
                f"| {x.start:%d.%m.%Y} |"
            )
    lines += ["", "## Hinweise (Annahmen)", ""]
    lines += [f"- `{w['wo']}`: {w['text']}" for w in plan.warnings]
    lines += ["", "## Nicht übernommen", ""]
    lines += [f"- `{s['wo']}`: {s['text']}" for s in plan.skipped]
    return "\n".join(lines) + "\n"


def _report_json(plan: Plan, result: dict | None) -> dict:
    ids = {r["key"]: r["id"] for r in (result or {}).get("items", [])}
    return {
        "items": [
            {
                "key": i.key,
                "id": ids.get(i.key),
                "display_nr": i.display_nr,
                "paper_nr": i.paper_nr,
                "type": i.type_label,
                "label": i.label,
                "owner": i.owner,
                "storage_location": i.storage_location,
                "sources": i.sources,
                "photos": [str(p["path"]) for p in i.photos],
            }
            for i in plan.items
        ],
        "musicians": [
            {
                "key": m.key,
                "name": f"{m.first_name} {m.last_name}".strip(),
                "refs": m.refs,
            }
            for m in plan.musicians
        ],
        "loans": [
            {
                "item": x.item_key,
                "musician": x.musician_key,
                "start": x.start.isoformat(),
                "end": x.end.isoformat() if x.end else None,
                "sources": x.sources,
            }
            for x in plan.loans
        ],
        "warnings": plan.warnings,
        "skipped": plan.skipped,
    }


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--quelle", type=Path, default=DEFAULT_SOURCE)
    ap.add_argument(
        "--ersetzen",
        action="store_true",
        help="alle Instrumente, Musiker, Leihen, Belege und Bilder ersetzen",
    )
    args = ap.parse_args()

    async with async_session_factory() as db:
        plan = build_plan(args.quelle, await load_short_codes(db), date.today())
        result = None
        if args.ersetzen:
            backup = (
                ROOT
                / "data"
                / "backups"
                / f"mv_hofki_{datetime.now():%Y-%m-%d_%H%M%S}.db"
            )
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(DB_FILE, backup)
            print(f"Sicherung: {backup}")
            # old image/invoice files move into the backup; restored on failure
            aside = backup.with_suffix(".uploads")
            moved = []
            for sub in ("images", "invoices"):
                if (UPLOADS / sub).exists():
                    aside.mkdir(parents=True, exist_ok=True)
                    shutil.move(UPLOADS / sub, aside / sub)
                    moved.append(sub)
            try:
                print("Gelöscht:", await wipe_inventory(db))
                result = await apply_plan(db, plan, UPLOADS)
                await db.commit()
            except Exception:
                await db.rollback()
                for sub in ("images", "invoices"):
                    shutil.rmtree(UPLOADS / sub, ignore_errors=True)
                for sub in moved:
                    shutil.move(aside / sub, UPLOADS / sub)
                print(
                    "Fehler – Datenbank und Upload-Ordner unverändert.", file=sys.stderr
                )
                raise
            print(f"Alte Upload-Dateien: {aside}")

    (args.quelle / "IMPORT_BERICHT.md").write_text(
        _report_md(plan, args.ersetzen, result), encoding="utf-8"
    )
    (args.quelle / "import_bericht.json").write_text(
        json.dumps(_report_json(plan, result), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(
        f"{'Importiert' if args.ersetzen else 'Probelauf'}: "
        f"{len(plan.items)} Instrumente, {len(plan.musicians)} Musiker, "
        f"{len(plan.loans)} Leihen, {len(plan.invoices)} Belege, "
        f"{sum(len(i.photos) for i in plan.items)} Fotos; "
        f"{len(plan.warnings)} Hinweise, {len(plan.skipped)} nicht übernommen."
    )
    print(f"Bericht: {args.quelle / 'IMPORT_BERICHT.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
