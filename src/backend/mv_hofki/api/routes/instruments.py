"""Instrument API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.api.deps import get_db
from mv_hofki.schemas.instrument import (
    InstrumentCreate,
    InstrumentRead,
    InstrumentUpdate,
)
from mv_hofki.schemas.pagination import PaginatedResponse
from mv_hofki.services import instrument as instrument_service

router = APIRouter(prefix="/api/v1/instruments", tags=["instruments"])


@router.get("", response_model=PaginatedResponse[InstrumentRead])
async def list_instruments(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    search: str | None = None,
    type_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    items, total = await instrument_service.get_list(
        db, limit=limit, offset=offset, search=search, type_id=type_id
    )
    return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)


@router.post("", response_model=InstrumentRead, status_code=201)
async def create_instrument(data: InstrumentCreate, db: AsyncSession = Depends(get_db)):
    return await instrument_service.create(db, data)


@router.get("/{instrument_id}", response_model=InstrumentRead)
async def get_instrument(instrument_id: int, db: AsyncSession = Depends(get_db)):
    return await instrument_service.get_by_id(db, instrument_id)


@router.put("/{instrument_id}", response_model=InstrumentRead)
async def update_instrument(
    instrument_id: int, data: InstrumentUpdate, db: AsyncSession = Depends(get_db)
):
    return await instrument_service.update(db, instrument_id, data)


@router.delete("/{instrument_id}", status_code=204)
async def delete_instrument(instrument_id: int, db: AsyncSession = Depends(get_db)):
    await instrument_service.delete(db, instrument_id)
    return Response(status_code=204)
