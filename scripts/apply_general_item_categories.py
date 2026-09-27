#!/usr/bin/env python
"""Apply a reviewed category proposal to the general items.

Usage (inside the devcontainer, from the project root):

    PYTHONPATH=src/backend python scripts/apply_general_item_categories.py \
        data/general_item_categories_proposal.csv

CSV: ``display_nr;label;storage_location;categories`` (``;`` separated, categories
joined with ``|``; an empty cell removes all categories of that item). Missing
categories are created. Each listed item's categories are replaced; nothing else
changes. The database is copied to data/backups/ first.
"""

from __future__ import annotations

import argparse
import asyncio
import shutil
from datetime import datetime
from pathlib import Path

from mv_hofki.core.config import settings
from mv_hofki.db.engine import async_session_factory
from mv_hofki.services.general_item_category_import import (
    apply_assignments,
    read_proposal,
)

ROOT = Path(settings.PROJECT_ROOT)
DB_FILE = ROOT / "data" / "mv_hofki.db"


def _backup() -> Path:
    target = ROOT / "data" / "backups"
    target.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = target / f"mv_hofki-{stamp}-vor-kategorien.db"
    shutil.copy2(DB_FILE, dest)
    return dest


async def _run(csv_path: Path) -> None:
    rows = read_proposal(csv_path)
    print(f"{len(rows)} Zeilen gelesen, Sicherung: {_backup()}")
    async with async_session_factory() as session:
        report = await apply_assignments(session, rows)
    print(f"Gegenstände aktualisiert: {report.updated_items}")
    print(
        f"Neue Kategorien ({len(report.created_categories)}): "
        f"{', '.join(report.created_categories) or '—'}"
    )
    if report.unknown_numbers:
        print(f"Unbekannte Nummern: {', '.join(report.unknown_numbers)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("csv", type=Path)
    asyncio.run(_run(parser.parse_args().csv))


if __name__ == "__main__":
    main()
