"""GeneralItemCategory API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.api.deps import get_db
from mv_hofki.schemas.general_item_category import (
    GeneralItemCategoryCreate,
    GeneralItemCategoryRead,
    GeneralItemCategoryUpdate,
)
from mv_hofki.services import general_item_category as category_service

router = APIRouter(
    prefix="/api/v1/general-item-categories", tags=["general-item-categories"]
)


@router.get("", response_model=list[GeneralItemCategoryRead])
async def list_categories(db: AsyncSession = Depends(get_db)):
    return await category_service.get_all(db)


@router.post("", response_model=GeneralItemCategoryRead, status_code=201)
async def create_category(
    data: GeneralItemCategoryCreate, db: AsyncSession = Depends(get_db)
):
    return await category_service.create(db, data)


@router.get("/{category_id}", response_model=GeneralItemCategoryRead)
async def get_category(category_id: int, db: AsyncSession = Depends(get_db)):
    return await category_service.get_by_id(db, category_id)


@router.put("/{category_id}", response_model=GeneralItemCategoryRead)
async def update_category(
    category_id: int,
    data: GeneralItemCategoryUpdate,
    db: AsyncSession = Depends(get_db),
):
    return await category_service.update(db, category_id, data)


@router.delete("/{category_id}", status_code=204)
async def delete_category(category_id: int, db: AsyncSession = Depends(get_db)):
    await category_service.delete(db, category_id)
    return Response(status_code=204)
