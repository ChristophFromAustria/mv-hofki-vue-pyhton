"""InstrumentType CRUD service."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.models.instrument_detail import InstrumentDetail
from mv_hofki.models.instrument_type import InstrumentType
from mv_hofki.schemas.instrument_type import InstrumentTypeCreate, InstrumentTypeUpdate


async def get_all(session: AsyncSession) -> list[InstrumentType]:
    result = await session.execute(
        select(InstrumentType).order_by(InstrumentType.label)
    )
    return list(result.scalars().all())


async def get_by_id(session: AsyncSession, type_id: int) -> InstrumentType:
    instrument_type = await session.get(InstrumentType, type_id)
    if not instrument_type:
        raise HTTPException(status_code=404, detail="Instrumententyp nicht gefunden")
    return instrument_type


async def create(session: AsyncSession, data: InstrumentTypeCreate) -> InstrumentType:
    instrument_type = InstrumentType(**data.model_dump())
    session.add(instrument_type)
    await session.commit()
    await session.refresh(instrument_type)
    return instrument_type


async def update(
    session: AsyncSession, type_id: int, data: InstrumentTypeUpdate
) -> InstrumentType:
    instrument_type = await get_by_id(session, type_id)
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(instrument_type, key, value)
    await session.commit()
    await session.refresh(instrument_type)
    return instrument_type


async def delete(session: AsyncSession, type_id: int) -> None:
    instrument_type = await get_by_id(session, type_id)
    result = await session.execute(
        select(func.count()).where(InstrumentDetail.instrument_type_id == type_id)
    )
    if result.scalar_one() > 0:
        raise HTTPException(
            status_code=409,
            detail=(
                "Instrumententyp wird von Instrumenten verwendet"
                " und kann nicht gelöscht werden"
            ),
        )
    await session.delete(instrument_type)
    await session.commit()
