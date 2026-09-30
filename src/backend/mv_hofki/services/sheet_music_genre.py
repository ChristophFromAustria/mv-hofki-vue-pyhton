"""SheetMusicGenre CRUD service."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.db.soft_delete import utcnow
from mv_hofki.models.sheet_music_detail import SheetMusicDetail
from mv_hofki.models.sheet_music_genre import SheetMusicGenre
from mv_hofki.schemas.sheet_music_genre import (
    SheetMusicGenreCreate,
    SheetMusicGenreUpdate,
)
from mv_hofki.services.lookup_names import ensure_label_free


async def get_all(session: AsyncSession) -> list[SheetMusicGenre]:
    result = await session.execute(
        select(SheetMusicGenre).order_by(SheetMusicGenre.label)
    )
    return list(result.scalars().all())


async def get_by_id(session: AsyncSession, genre_id: int) -> SheetMusicGenre:
    obj = await session.get(SheetMusicGenre, genre_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Genre nicht gefunden")
    return obj


async def create(session: AsyncSession, data: SheetMusicGenreCreate) -> SheetMusicGenre:
    await ensure_label_free(session, SheetMusicGenre, data.label, what="Gattung")
    obj = SheetMusicGenre(**data.model_dump())
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return obj


async def update(
    session: AsyncSession, genre_id: int, data: SheetMusicGenreUpdate
) -> SheetMusicGenre:
    obj = await get_by_id(session, genre_id)
    if data.label is not None:
        await ensure_label_free(
            session, SheetMusicGenre, data.label, what="Gattung", exclude_id=genre_id
        )
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(obj, key, value)
    await session.commit()
    await session.refresh(obj)
    return obj


async def delete(session: AsyncSession, genre_id: int) -> None:
    obj = await get_by_id(session, genre_id)
    result = await session.execute(
        select(func.count()).where(SheetMusicDetail.genre_id == genre_id)
    )
    if result.scalar_one() > 0:
        raise HTTPException(
            status_code=409,
            detail="Genre wird verwendet und kann nicht gelöscht werden",
        )
    obj.deleted_at = utcnow()  # to the trash
    await session.commit()
