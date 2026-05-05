"""Currency API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.api.deps import get_db
from mv_hofki.schemas.currency import CurrencyCreate, CurrencyRead, CurrencyUpdate
from mv_hofki.services import currency as currency_service

router = APIRouter(prefix="/api/v1/currencies", tags=["currencies"])


@router.get("", response_model=list[CurrencyRead])
async def list_currencies(db: AsyncSession = Depends(get_db)):
    return await currency_service.get_all(db)


@router.post("", response_model=CurrencyRead, status_code=201)
async def create_currency(data: CurrencyCreate, db: AsyncSession = Depends(get_db)):
    return await currency_service.create(db, data)


@router.get("/{currency_id}", response_model=CurrencyRead)
async def get_currency(currency_id: int, db: AsyncSession = Depends(get_db)):
    return await currency_service.get_by_id(db, currency_id)


@router.put("/{currency_id}", response_model=CurrencyRead)
async def update_currency(
    currency_id: int, data: CurrencyUpdate, db: AsyncSession = Depends(get_db)
):
    return await currency_service.update(db, currency_id, data)


@router.delete("/{currency_id}", status_code=204)
async def delete_currency(currency_id: int, db: AsyncSession = Depends(get_db)):
    await currency_service.delete(db, currency_id)
    return Response(status_code=204)
