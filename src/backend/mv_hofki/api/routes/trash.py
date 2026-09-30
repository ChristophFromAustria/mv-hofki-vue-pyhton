"""Papierkorb API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.api.deps import get_db
from mv_hofki.schemas.trash import TrashEntry
from mv_hofki.services import trash as trash_service

router = APIRouter(prefix="/api/v1/trash", tags=["trash"])


@router.get("", response_model=list[TrashEntry])
async def list_trash(db: AsyncSession = Depends(get_db)):
    return await trash_service.list_trash(db)


@router.post("/{kind}/{obj_id}/restore", status_code=204)
async def restore(kind: str, obj_id: int, db: AsyncSession = Depends(get_db)):
    await trash_service.restore(db, kind, obj_id)
    return Response(status_code=204)


@router.delete("/{kind}/{obj_id}", status_code=204)
async def purge(kind: str, obj_id: int, db: AsyncSession = Depends(get_db)):
    """Delete for good (with files)."""
    await trash_service.purge(db, kind, obj_id)
    return Response(status_code=204)
