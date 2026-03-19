"""SheetMusicGenre API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.api.deps import get_db
from mv_hofki.schemas.sheet_music_genre import (
    SheetMusicGenreCreate,
    SheetMusicGenreRead,
    SheetMusicGenreUpdate,
)
from mv_hofki.services import sheet_music_genre as genre_service

router = APIRouter(prefix="/api/v1/sheet-music-genres", tags=["sheet-music-genres"])


@router.get("", response_model=list[SheetMusicGenreRead])
async def list_genres(db: AsyncSession = Depends(get_db)):
    return await genre_service.get_all(db)


@router.post("", response_model=SheetMusicGenreRead, status_code=201)
async def create_genre(data: SheetMusicGenreCreate, db: AsyncSession = Depends(get_db)):
    return await genre_service.create(db, data)


@router.get("/{genre_id}", response_model=SheetMusicGenreRead)
async def get_genre(genre_id: int, db: AsyncSession = Depends(get_db)):
    return await genre_service.get_by_id(db, genre_id)


@router.put("/{genre_id}", response_model=SheetMusicGenreRead)
async def update_genre(
    genre_id: int, data: SheetMusicGenreUpdate, db: AsyncSession = Depends(get_db)
):
    return await genre_service.update(db, genre_id, data)


@router.delete("/{genre_id}", status_code=204)
async def delete_genre(genre_id: int, db: AsyncSession = Depends(get_db)):
    await genre_service.delete(db, genre_id)
    return Response(status_code=204)
