"""Instrument CRUD service."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from mv_hofki.models.instrument import Instrument
from mv_hofki.models.instrument_image import InstrumentImage
from mv_hofki.models.instrument_type import InstrumentType
from mv_hofki.models.loan import Loan
from mv_hofki.models.musician import Musician
from mv_hofki.schemas.instrument import (
    ActiveLoanInfo,
    InstrumentCreate,
    InstrumentUpdate,
)


async def _enrich(session: AsyncSession, instruments: list[Instrument]) -> None:
    """Add active_loan and profile_image_url to instruments."""
    if not instruments:
        return
    ids = [i.id for i in instruments]

    # Active loans
    loan_result = await session.execute(
        select(Loan, Musician)
        .join(Musician, Loan.musician_id == Musician.id)
        .where(Loan.instrument_id.in_(ids), Loan.end_date.is_(None))
    )
    loan_map: dict[int, ActiveLoanInfo] = {}
    for loan, musician in loan_result:
        loan_map[loan.instrument_id] = ActiveLoanInfo(
            loan_id=loan.id,
            musician_id=musician.id,
            musician_name=f"{musician.first_name} {musician.last_name}",
            is_extern=musician.is_extern,
            start_date=loan.start_date,
        )

    # Profile images
    img_result = await session.execute(
        select(InstrumentImage).where(
            InstrumentImage.instrument_id.in_(ids), InstrumentImage.is_profile.is_(True)
        )
    )
    img_map: dict[int, str] = {}
    for img in img_result.scalars():
        img_map[img.instrument_id] = (
            f"/uploads/instruments/{img.instrument_id}/{img.filename}"
        )

    for inst in instruments:
        inst.active_loan = loan_map.get(inst.id)  # type: ignore[attr-defined]
        inst.profile_image_url = img_map.get(inst.id)  # type: ignore[attr-defined]


async def get_list(
    session: AsyncSession,
    *,
    limit: int = 50,
    offset: int = 0,
    search: str | None = None,
    type_id: int | None = None,
) -> tuple[list[Instrument], int]:
    query = select(Instrument).options(
        joinedload(Instrument.instrument_type),
        joinedload(Instrument.currency),
    )
    count_query = select(func.count()).select_from(Instrument)

    if type_id is not None:
        query = query.where(Instrument.instrument_type_id == type_id)
        count_query = count_query.where(Instrument.instrument_type_id == type_id)

    if search:
        pattern = f"%{search}%"
        search_filter = or_(
            Instrument.label_addition.ilike(pattern),
            Instrument.manufacturer.ilike(pattern),
            Instrument.serial_nr.ilike(pattern),
            Instrument.notes.ilike(pattern),
            InstrumentType.label.ilike(pattern),
        )
        query = query.join(Instrument.instrument_type).where(search_filter)
        count_query = count_query.join(
            InstrumentType, Instrument.instrument_type_id == InstrumentType.id
        ).where(search_filter)

    total = (await session.execute(count_query)).scalar_one()
    query = query.order_by(Instrument.inventory_nr).limit(limit).offset(offset)
    result = await session.execute(query)
    instruments = list(result.unique().scalars().all())
    await _enrich(session, instruments)
    return instruments, total


async def get_by_id(session: AsyncSession, instrument_id: int) -> Instrument:
    result = await session.execute(
        select(Instrument)
        .options(
            joinedload(Instrument.instrument_type),
            joinedload(Instrument.currency),
        )
        .where(Instrument.id == instrument_id)
    )
    instrument = result.unique().scalar_one_or_none()
    if not instrument:
        raise HTTPException(status_code=404, detail="Instrument nicht gefunden")
    await _enrich(session, [instrument])
    return instrument


async def create(session: AsyncSession, data: InstrumentCreate) -> Instrument:
    # Auto-assign inventory_nr
    result = await session.execute(select(func.max(Instrument.inventory_nr)))
    max_nr = result.scalar_one_or_none() or 0
    instrument = Instrument(**data.model_dump(), inventory_nr=max_nr + 1)
    session.add(instrument)
    await session.commit()
    await session.refresh(instrument, attribute_names=["instrument_type", "currency"])
    await _enrich(session, [instrument])
    return instrument


async def update(
    session: AsyncSession, instrument_id: int, data: InstrumentUpdate
) -> Instrument:
    instrument = await get_by_id(session, instrument_id)
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(instrument, key, value)
    await session.commit()
    await session.refresh(instrument, attribute_names=["instrument_type", "currency"])
    await _enrich(session, [instrument])
    return instrument


async def delete(session: AsyncSession, instrument_id: int) -> None:
    instrument = await get_by_id(session, instrument_id)
    await session.delete(instrument)
    await session.commit()
