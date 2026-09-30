"""InstrumentType CRUD service."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.db.soft_delete import utcnow
from mv_hofki.models.instrument_detail import InstrumentDetail
from mv_hofki.models.instrument_type import InstrumentType
from mv_hofki.schemas.instrument_type import InstrumentTypeCreate, InstrumentTypeUpdate
from mv_hofki.services.lookup_names import ensure_label_free


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
    await ensure_label_free(session, InstrumentType, data.label, what="Instrumententyp")
    instrument_type = InstrumentType(**data.model_dump())
    session.add(instrument_type)
    await session.commit()
    await session.refresh(instrument_type)
    return instrument_type


async def update(
    session: AsyncSession, type_id: int, data: InstrumentTypeUpdate
) -> InstrumentType:
    instrument_type = await get_by_id(session, type_id)
    if data.label is not None:
        await ensure_label_free(
            session,
            InstrumentType,
            data.label,
            what="Instrumententyp",
            exclude_id=type_id,
        )
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
    instrument_type.deleted_at = utcnow()  # to the trash
    await session.commit()
