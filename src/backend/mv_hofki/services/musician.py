"""Musician CRUD service."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.filters.base import PageParams, paginate
from mv_hofki.filters.musician import MusicianFilter
from mv_hofki.models.loan import Loan
from mv_hofki.models.musician import Musician
from mv_hofki.schemas.musician import MusicianCreate, MusicianUpdate
from mv_hofki.services import register as register_service


async def get_list(
    session: AsyncSession, flt: MusicianFilter, page: PageParams
) -> tuple[list[Musician], int]:
    query = flt.sort(flt.filter(select(Musician)))
    return await paginate(session, query, page)


async def get_by_id(session: AsyncSession, musician_id: int) -> Musician:
    musician = await session.get(Musician, musician_id)
    if not musician:
        raise HTTPException(status_code=404, detail="Musiker nicht gefunden")
    return musician


async def create(session: AsyncSession, data: MusicianCreate) -> Musician:
    fields = data.model_dump(exclude={"register_ids"})
    musician = Musician(**fields)
    musician.registers = await register_service.get_many(session, data.register_ids)
    session.add(musician)
    await session.commit()
    await session.refresh(musician)
    return musician


async def update(
    session: AsyncSession, musician_id: int, data: MusicianUpdate
) -> Musician:
    musician = await get_by_id(session, musician_id)
    fields = data.model_dump(exclude_unset=True)
    register_ids = fields.pop("register_ids", None)
    for key, value in fields.items():
        setattr(musician, key, value)
    if register_ids is not None:
        musician.registers = await register_service.get_many(session, register_ids)
    await session.commit()
    await session.refresh(musician)
    return musician


async def delete(session: AsyncSession, musician_id: int) -> None:
    musician = await get_by_id(session, musician_id)
    result = await session.execute(
        select(func.count()).where(
            Loan.musician_id == musician_id, Loan.end_date.is_(None)
        )
    )
    if result.scalar_one() > 0:
        raise HTTPException(
            status_code=409,
            detail="Musiker hat aktive Leihen und kann nicht gelöscht werden",
        )
    await session.delete(musician)
    await session.commit()
