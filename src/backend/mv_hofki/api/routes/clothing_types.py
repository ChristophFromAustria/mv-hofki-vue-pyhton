"""ClothingType API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.api.deps import get_db
from mv_hofki.schemas.clothing_type import (
    ClothingTypeCreate,
    ClothingTypeRead,
    ClothingTypeUpdate,
)
from mv_hofki.services import clothing_type as clothing_type_service

router = APIRouter(prefix="/api/v1/clothing-types", tags=["clothing-types"])


@router.get("", response_model=list[ClothingTypeRead])
async def list_clothing_types(db: AsyncSession = Depends(get_db)):
    return await clothing_type_service.get_all(db)


@router.post("", response_model=ClothingTypeRead, status_code=201)
async def create_clothing_type(
    data: ClothingTypeCreate, db: AsyncSession = Depends(get_db)
):
    return await clothing_type_service.create(db, data)


@router.get("/{type_id}", response_model=ClothingTypeRead)
async def get_clothing_type(type_id: int, db: AsyncSession = Depends(get_db)):
    return await clothing_type_service.get_by_id(db, type_id)


@router.put("/{type_id}", response_model=ClothingTypeRead)
async def update_clothing_type(
    type_id: int, data: ClothingTypeUpdate, db: AsyncSession = Depends(get_db)
):
    return await clothing_type_service.update(db, type_id, data)


@router.delete("/{type_id}", status_code=204)
async def delete_clothing_type(type_id: int, db: AsyncSession = Depends(get_db)):
    await clothing_type_service.delete(db, type_id)
    return Response(status_code=204)
