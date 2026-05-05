"""Loan CRUD service."""

from __future__ import annotations

from datetime import date

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from mv_hofki.models.inventory_item import InventoryItem
from mv_hofki.models.loan import Loan
from mv_hofki.schemas.loan import LoanCreate, LoanUpdate

LOANABLE_CATEGORIES = {"instrument", "clothing", "general_item"}


async def get_list(
    session: AsyncSession,
    *,
    active: bool | None = None,
    item_id: int | None = None,
    musician_id: int | None = None,
) -> list[Loan]:
    query = select(Loan).options(
        joinedload(Loan.item),
        joinedload(Loan.musician),
    )
    if active is True:
        query = query.where(Loan.end_date.is_(None))
    elif active is False:
        query = query.where(Loan.end_date.is_not(None))

    if item_id is not None:
        query = query.where(Loan.item_id == item_id)
    if musician_id is not None:
        query = query.where(Loan.musician_id == musician_id)

    query = query.order_by(Loan.start_date.desc())
    result = await session.execute(query)
    return list(result.unique().scalars().all())


async def get_by_id(session: AsyncSession, loan_id: int) -> Loan:
    result = await session.execute(
        select(Loan)
        .options(joinedload(Loan.item), joinedload(Loan.musician))
        .where(Loan.id == loan_id)
    )
    loan = result.unique().scalar_one_or_none()
    if not loan:
        raise HTTPException(status_code=404, detail="Leihe nicht gefunden")
    return loan


async def create(session: AsyncSession, data: LoanCreate) -> Loan:
    # Validate item exists and is loanable
    item_result = await session.execute(
        select(InventoryItem).where(InventoryItem.id == data.item_id)
    )
    item = item_result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Gegenstand nicht gefunden")
    if item.category not in LOANABLE_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail="Dieser Gegenstand kann nicht ausgeliehen werden",
        )

    # Check for active loan
    result = await session.execute(
        select(func.count()).where(
            Loan.item_id == data.item_id,
            Loan.end_date.is_(None),
        )
    )
    if result.scalar_one() > 0:
        raise HTTPException(
            status_code=409,
            detail="Gegenstand ist bereits ausgeliehen",
        )
    loan = Loan(**data.model_dump())
    session.add(loan)
    await session.commit()
    return await get_by_id(session, loan.id)


async def update(session: AsyncSession, loan_id: int, data: LoanUpdate) -> Loan:
    loan = await get_by_id(session, loan_id)
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(loan, key, value)
    await session.commit()
    return await get_by_id(session, loan_id)


async def return_item(
    session: AsyncSession, loan_id: int, end_date: date | None = None
) -> Loan:
    loan = await get_by_id(session, loan_id)
    if loan.end_date is not None:
        raise HTTPException(
            status_code=409, detail="Gegenstand wurde bereits zurückgegeben"
        )
    loan.end_date = end_date or date.today()
    await session.commit()
    return await get_by_id(session, loan_id)
