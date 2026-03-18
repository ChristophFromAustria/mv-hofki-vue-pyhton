"""InstrumentType API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.api.deps import get_db
from mv_hofki.schemas.instrument_type import (
    InstrumentTypeCreate,
    InstrumentTypeRead,
    InstrumentTypeUpdate,
)
from mv_hofki.services import instrument_type as instrument_type_service

router = APIRouter(prefix="/api/v1/instrument-types", tags=["instrument-types"])


@router.get("", response_model=list[InstrumentTypeRead])
async def list_instrument_types(db: AsyncSession = Depends(get_db)):
    return await instrument_type_service.get_all(db)


@router.post("", response_model=InstrumentTypeRead, status_code=201)
async def create_instrument_type(
    data: InstrumentTypeCreate, db: AsyncSession = Depends(get_db)
):
    return await instrument_type_service.create(db, data)


@router.get("/{type_id}", response_model=InstrumentTypeRead)
async def get_instrument_type(type_id: int, db: AsyncSession = Depends(get_db)):
    return await instrument_type_service.get_by_id(db, type_id)


@router.put("/{type_id}", response_model=InstrumentTypeRead)
async def update_instrument_type(
    type_id: int, data: InstrumentTypeUpdate, db: AsyncSession = Depends(get_db)
):
    return await instrument_type_service.update(db, type_id, data)


@router.delete("/{type_id}", status_code=204)
async def delete_instrument_type(type_id: int, db: AsyncSession = Depends(get_db)):
    await instrument_type_service.delete(db, type_id)
    return Response(status_code=204)
