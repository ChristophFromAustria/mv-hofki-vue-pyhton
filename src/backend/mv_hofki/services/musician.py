"""Musician CRUD service."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.models.loan import Loan
from mv_hofki.models.musician import Musician
from mv_hofki.schemas.musician import MusicianCreate, MusicianUpdate


async def get_list(
    session: AsyncSession,
    *,
    limit: int = 50,
    offset: int = 0,
    search: str | None = None,
) -> tuple[list[Musician], int]:
    query = select(Musician)
    count_query = select(func.count()).select_from(Musician)

    if search:
        pattern = f"%{search}%"
        search_filter = or_(
            Musician.first_name.ilike(pattern),
            Musician.last_name.ilike(pattern),
            Musician.email.ilike(pattern),
            Musician.city.ilike(pattern),
        )
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    total = (await session.execute(count_query)).scalar_one()
    query = (
        query.order_by(Musician.last_name, Musician.first_name)
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(query)
    return list(result.scalars().all()), total


async def get_by_id(session: AsyncSession, musician_id: int) -> Musician:
    musician = await session.get(Musician, musician_id)
    if not musician:
        raise HTTPException(status_code=404, detail="Musiker nicht gefunden")
    return musician


async def create(session: AsyncSession, data: MusicianCreate) -> Musician:
    musician = Musician(**data.model_dump())
    session.add(musician)
    await session.commit()
    await session.refresh(musician)
    return musician


async def update(
    session: AsyncSession, musician_id: int, data: MusicianUpdate
) -> Musician:
    musician = await get_by_id(session, musician_id)
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(musician, key, value)
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
