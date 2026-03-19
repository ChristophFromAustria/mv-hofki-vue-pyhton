"""ClothingType CRUD service."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.models.clothing_detail import ClothingDetail
from mv_hofki.models.clothing_type import ClothingType
from mv_hofki.schemas.clothing_type import ClothingTypeCreate, ClothingTypeUpdate


async def get_all(session: AsyncSession) -> list[ClothingType]:
    result = await session.execute(select(ClothingType).order_by(ClothingType.label))
    return list(result.scalars().all())


async def get_by_id(session: AsyncSession, type_id: int) -> ClothingType:
    obj = await session.get(ClothingType, type_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Bekleidungstyp nicht gefunden")
    return obj


async def create(session: AsyncSession, data: ClothingTypeCreate) -> ClothingType:
    obj = ClothingType(**data.model_dump())
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return obj


async def update(
    session: AsyncSession, type_id: int, data: ClothingTypeUpdate
) -> ClothingType:
    obj = await get_by_id(session, type_id)
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(obj, key, value)
    await session.commit()
    await session.refresh(obj)
    return obj


async def delete(session: AsyncSession, type_id: int) -> None:
    obj = await get_by_id(session, type_id)
    result = await session.execute(
        select(func.count()).where(ClothingDetail.clothing_type_id == type_id)
    )
    if result.scalar_one() > 0:
        raise HTTPException(
            status_code=409,
            detail="Bekleidungstyp wird verwendet und kann nicht gelöscht werden",
        )
    await session.delete(obj)
    await session.commit()
