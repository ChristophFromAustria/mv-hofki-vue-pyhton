"""Musician API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from fastapi_filter import FilterDepends
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.api.deps import get_db
from mv_hofki.api.routes._listing import page_response
from mv_hofki.filters.base import PageParams
from mv_hofki.filters.musician import MusicianFilter
from mv_hofki.schemas.musician import (
    MusicianCreate,
    MusicianListRow,
    MusicianRead,
    MusicianUpdate,
)
from mv_hofki.schemas.pagination import PaginatedResponse
from mv_hofki.services import musician as musician_service

router = APIRouter(prefix="/api/v1/musicians", tags=["musicians"])


@router.get("", response_model=PaginatedResponse[MusicianListRow])
async def list_musicians(
    flt: MusicianFilter = FilterDepends(MusicianFilter),
    page: PageParams = Depends(),
    db: AsyncSession = Depends(get_db),
):
    lp = await musician_service.get_list(db, flt, page)
    return page_response(lp, page, [MusicianListRow.model_validate(m) for m in lp.rows])


@router.post("", response_model=MusicianRead, status_code=201)
async def create_musician(data: MusicianCreate, db: AsyncSession = Depends(get_db)):
    return await musician_service.create(db, data)


@router.get("/{musician_id}", response_model=MusicianRead)
async def get_musician(musician_id: int, db: AsyncSession = Depends(get_db)):
    return await musician_service.get_by_id(db, musician_id)


@router.put("/{musician_id}", response_model=MusicianRead)
async def update_musician(
    musician_id: int, data: MusicianUpdate, db: AsyncSession = Depends(get_db)
):
    return await musician_service.update(db, musician_id, data)


@router.delete("/{musician_id}", status_code=204)
async def delete_musician(musician_id: int, db: AsyncSession = Depends(get_db)):
    await musician_service.delete(db, musician_id)
    return Response(status_code=204)
