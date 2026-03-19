"""GeneralItemType CRUD service."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.models.general_item_detail import GeneralItemDetail
from mv_hofki.models.general_item_type import GeneralItemType
from mv_hofki.schemas.general_item_type import (
    GeneralItemTypeCreate,
    GeneralItemTypeUpdate,
)


async def get_all(session: AsyncSession) -> list[GeneralItemType]:
    result = await session.execute(
        select(GeneralItemType).order_by(GeneralItemType.label)
    )
    return list(result.scalars().all())


async def get_by_id(session: AsyncSession, type_id: int) -> GeneralItemType:
    obj = await session.get(GeneralItemType, type_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Allgemeiner Typ nicht gefunden")
    return obj


async def create(session: AsyncSession, data: GeneralItemTypeCreate) -> GeneralItemType:
    obj = GeneralItemType(**data.model_dump())
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return obj


async def update(
    session: AsyncSession, type_id: int, data: GeneralItemTypeUpdate
) -> GeneralItemType:
    obj = await get_by_id(session, type_id)
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(obj, key, value)
    await session.commit()
    await session.refresh(obj)
    return obj


async def delete(session: AsyncSession, type_id: int) -> None:
    obj = await get_by_id(session, type_id)
    result = await session.execute(
        select(func.count()).where(GeneralItemDetail.general_item_type_id == type_id)
    )
    if result.scalar_one() > 0:
        raise HTTPException(
            status_code=409,
            detail="Typ wird verwendet und kann nicht gelöscht werden",
        )
    await session.delete(obj)
    await session.commit()
