"""Currency CRUD service."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.models.currency import Currency
from mv_hofki.models.inventory_item import InventoryItem
from mv_hofki.schemas.currency import CurrencyCreate, CurrencyUpdate


async def get_all(session: AsyncSession) -> list[Currency]:
    result = await session.execute(select(Currency).order_by(Currency.label))
    return list(result.scalars().all())


async def get_by_id(session: AsyncSession, currency_id: int) -> Currency:
    currency = await session.get(Currency, currency_id)
    if not currency:
        raise HTTPException(status_code=404, detail="Währung nicht gefunden")
    return currency


async def create(session: AsyncSession, data: CurrencyCreate) -> Currency:
    currency = Currency(**data.model_dump())
    session.add(currency)
    await session.commit()
    await session.refresh(currency)
    return currency


async def update(
    session: AsyncSession, currency_id: int, data: CurrencyUpdate
) -> Currency:
    currency = await get_by_id(session, currency_id)
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(currency, key, value)
    await session.commit()
    await session.refresh(currency)
    return currency


async def delete(session: AsyncSession, currency_id: int) -> None:
    currency = await get_by_id(session, currency_id)
    result = await session.execute(
        select(func.count()).where(InventoryItem.currency_id == currency_id)
    )
    if result.scalar_one() > 0:
        raise HTTPException(
            status_code=409,
            detail=(
                "Währung wird von Gegenständen verwendet"
                " und kann nicht gelöscht werden"
            ),
        )
    await session.delete(currency)
    await session.commit()
