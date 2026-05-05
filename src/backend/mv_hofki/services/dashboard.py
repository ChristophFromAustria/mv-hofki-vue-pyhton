"""Dashboard aggregation service."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.models.instrument_detail import InstrumentDetail
from mv_hofki.models.instrument_type import InstrumentType
from mv_hofki.models.inventory_item import InventoryItem
from mv_hofki.models.loan import Loan
from mv_hofki.models.musician import Musician
from mv_hofki.schemas.dashboard import (
    DashboardStats,
    InstrumentsByType,
    ItemsByCategory,
)

CATEGORY_LABELS = {
    "instrument": "Instrumente",
    "clothing": "Bekleidung",
    "sheet_music": "Noten",
    "general_item": "Allgemein",
}


async def get_stats(session: AsyncSession) -> DashboardStats:
    total_items = (
        await session.execute(select(func.count()).select_from(InventoryItem))
    ).scalar_one()

    total_musicians = (
        await session.execute(select(func.count()).select_from(Musician))
    ).scalar_one()

    active_loans = (
        await session.execute(select(func.count()).where(Loan.end_date.is_(None)))
    ).scalar_one()

    # Instruments by type
    by_type_result = await session.execute(
        select(
            InstrumentType.label,
            InstrumentType.label_short,
            func.count(InstrumentDetail.id).label("instrument_count"),
        )
        .join(
            InstrumentDetail,
            InstrumentDetail.instrument_type_id == InstrumentType.id,
        )
        .group_by(InstrumentType.id, InstrumentType.label, InstrumentType.label_short)
        .order_by(func.count(InstrumentDetail.id).desc())
    )

    instruments_by_type = [
        InstrumentsByType(
            label=row.label,
            label_short=row.label_short,
            count=row._mapping["instrument_count"],  # type: ignore[index]
        )
        for row in by_type_result
    ]

    # Items by category
    by_category_result = await session.execute(
        select(
            InventoryItem.category,
            func.count(InventoryItem.id).label("cat_count"),
        )
        .group_by(InventoryItem.category)
        .order_by(func.count(InventoryItem.id).desc())
    )

    items_by_category = [
        ItemsByCategory(
            category=row.category,
            label=CATEGORY_LABELS.get(row.category, row.category),
            count=row._mapping["cat_count"],  # type: ignore[index]
        )
        for row in by_category_result
    ]

    return DashboardStats(
        total_items=total_items,
        total_musicians=total_musicians,
        active_loans=active_loans,
        instruments_by_type=instruments_by_type,
        items_by_category=items_by_category,
    )
