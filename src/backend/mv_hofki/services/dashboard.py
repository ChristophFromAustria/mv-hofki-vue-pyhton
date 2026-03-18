"""Dashboard aggregation service."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.models.instrument import Instrument
from mv_hofki.models.instrument_type import InstrumentType
from mv_hofki.models.loan import Loan
from mv_hofki.models.musician import Musician
from mv_hofki.schemas.dashboard import DashboardStats, InstrumentsByType


async def get_stats(session: AsyncSession) -> DashboardStats:
    total_instruments = (
        await session.execute(select(func.count()).select_from(Instrument))
    ).scalar_one()

    total_musicians = (
        await session.execute(select(func.count()).select_from(Musician))
    ).scalar_one()

    active_loans = (
        await session.execute(select(func.count()).where(Loan.end_date.is_(None)))
    ).scalar_one()

    by_type_result = await session.execute(
        select(
            InstrumentType.label,
            InstrumentType.label_short,
            func.count(Instrument.id).label("instrument_count"),
        )
        .join(Instrument, Instrument.instrument_type_id == InstrumentType.id)
        .group_by(InstrumentType.id, InstrumentType.label, InstrumentType.label_short)
        .order_by(func.count(Instrument.id).desc())
    )

    instruments_by_type = [
        InstrumentsByType(
            label=row.label,
            label_short=row.label_short,
            count=row._mapping["instrument_count"],  # type: ignore[index]
        )
        for row in by_type_result
    ]

    return DashboardStats(
        total_instruments=total_instruments,
        total_musicians=total_musicians,
        active_loans=active_loans,
        instruments_by_type=instruments_by_type,
    )
