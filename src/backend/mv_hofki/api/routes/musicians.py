"""Musician API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.api.deps import get_db
from mv_hofki.schemas.musician import MusicianCreate, MusicianRead, MusicianUpdate
from mv_hofki.schemas.pagination import PaginatedResponse
from mv_hofki.services import musician as musician_service

router = APIRouter(prefix="/api/v1/musicians", tags=["musicians"])


@router.get("", response_model=PaginatedResponse[MusicianRead])
async def list_musicians(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    items, total = await musician_service.get_list(
        db, limit=limit, offset=offset, search=search
    )
    return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)


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
