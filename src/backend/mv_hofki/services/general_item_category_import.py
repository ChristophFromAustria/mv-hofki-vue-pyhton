"""Apply a reviewed CSV of category assignments to general items (one-off
bulk step; also usable for later mass corrections)."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.models.general_item_category import GeneralItemCategory
from mv_hofki.models.inventory_item import InventoryItem
from mv_hofki.services.general_item_category import set_item_categories

# "A-0001", "A-001", "a-1", "A 1" -> ("A", 1)
_NR_RE = re.compile(r"^\s*([^\W\d_]+)\s*-?\s*0*(\d+)\s*$")


@dataclass
class ProposalRow:
    display_nr: str
    categories: list[str]


@dataclass
class AssignmentReport:
    created_categories: list[str] = field(default_factory=list)
    updated_items: int = 0
    unknown_numbers: list[str] = field(default_factory=list)


def read_proposal(path: Path) -> list[ProposalRow]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh, delimiter=";")
        return [
            ProposalRow(
                display_nr=(row.get("display_nr") or "").strip(),
                categories=[
                    part.strip()
                    for part in (row.get("categories") or "").split("|")
                    if part.strip()
                ],
            )
            for row in reader
            if (row.get("display_nr") or "").strip()
        ]


async def apply_assignments(
    session: AsyncSession, rows: list[ProposalRow]
) -> AssignmentReport:
    report = AssignmentReport()
    by_label = {
        c.label.casefold(): c
        for c in (await session.execute(select(GeneralItemCategory))).scalars()
    }

    for row in rows:
        match = _NR_RE.match(row.display_nr)
        item_id = None
        if match:
            item_id = await session.scalar(
                select(InventoryItem.id).where(
                    InventoryItem.category == "general_item",
                    func.upper(InventoryItem.number_prefix) == match[1].upper(),
                    InventoryItem.inventory_nr == int(match[2]),
                )
            )
        if item_id is None:
            report.unknown_numbers.append(row.display_nr)
            continue

        ids: set[int] = set()
        for label in row.categories:
            category = by_label.get(label.casefold())
            if category is None:
                category = GeneralItemCategory(label=label[:50])
                session.add(category)
                await session.flush()
                by_label[label.casefold()] = category
                report.created_categories.append(category.label)
            ids.add(category.id)
        await set_item_categories(session, item_id, sorted(ids))
        report.updated_items += 1

    await session.commit()
    return report
