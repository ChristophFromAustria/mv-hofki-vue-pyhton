"""GeneralItemType CRUD service — deprecated, table removed."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.schemas.general_item_type import (
    GeneralItemTypeCreate,
    GeneralItemTypeUpdate,
)


async def get_all(session: AsyncSession) -> list:
    return []


async def get_by_id(session: AsyncSession, type_id: int) -> None:
    from fastapi import HTTPException

    raise HTTPException(status_code=404, detail="Allgemeiner Typ nicht gefunden")


async def create(session: AsyncSession, data: GeneralItemTypeCreate) -> None:
    from fastapi import HTTPException

    raise HTTPException(status_code=410, detail="Nicht mehr verfügbar")


async def update(
    session: AsyncSession, type_id: int, data: GeneralItemTypeUpdate
) -> None:
    from fastapi import HTTPException

    raise HTTPException(status_code=410, detail="Nicht mehr verfügbar")


async def delete(session: AsyncSession, type_id: int) -> None:
    from fastapi import HTTPException

    raise HTTPException(status_code=410, detail="Nicht mehr verfügbar")
