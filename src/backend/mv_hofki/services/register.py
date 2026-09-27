"""Register CRUD service."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.models.register import Register, musician_registers
from mv_hofki.schemas.register import RegisterCreate, RegisterUpdate


async def get_all(session: AsyncSession) -> list[Register]:
    result = await session.execute(
        select(Register).order_by(Register.sort_order, Register.label)
    )
    return list(result.scalars().all())


async def get_by_id(session: AsyncSession, register_id: int) -> Register:
    obj = await session.get(Register, register_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Register nicht gefunden")
    return obj


async def get_many(session: AsyncSession, ids: list[int]) -> list[Register]:
    """Registers for ``ids``; 400 if any id is unknown."""
    if not ids:
        return []
    result = await session.execute(select(Register).where(Register.id.in_(ids)))
    found = list(result.scalars().all())
    if len(found) != len(set(ids)):
        raise HTTPException(status_code=400, detail="Unbekanntes Register")
    return found


async def create(session: AsyncSession, data: RegisterCreate) -> Register:
    obj = Register(**data.model_dump())
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return obj


async def update(
    session: AsyncSession, register_id: int, data: RegisterUpdate
) -> Register:
    obj = await get_by_id(session, register_id)
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(obj, key, value)
    await session.commit()
    await session.refresh(obj)
    return obj


async def delete(session: AsyncSession, register_id: int) -> None:
    obj = await get_by_id(session, register_id)
    in_use = await session.scalar(
        select(func.count()).where(musician_registers.c.register_id == register_id)
    )
    if in_use:
        raise HTTPException(
            status_code=409,
            detail="Register hat Mitglieder und kann nicht gelöscht werden",
        )
    await session.delete(obj)
    await session.commit()
