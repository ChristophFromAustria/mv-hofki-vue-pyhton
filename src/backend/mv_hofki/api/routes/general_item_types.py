"""GeneralItemType API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.api.deps import get_db
from mv_hofki.schemas.general_item_type import (
    GeneralItemTypeCreate,
    GeneralItemTypeRead,
    GeneralItemTypeUpdate,
)
from mv_hofki.services import general_item_type as general_item_type_service

router = APIRouter(prefix="/api/v1/general-item-types", tags=["general-item-types"])


@router.get("", response_model=list[GeneralItemTypeRead])
async def list_general_item_types(db: AsyncSession = Depends(get_db)):
    return await general_item_type_service.get_all(db)


@router.post("", response_model=GeneralItemTypeRead, status_code=201)
async def create_general_item_type(
    data: GeneralItemTypeCreate, db: AsyncSession = Depends(get_db)
):
    return await general_item_type_service.create(db, data)


@router.get("/{type_id}", response_model=GeneralItemTypeRead)
async def get_general_item_type(type_id: int, db: AsyncSession = Depends(get_db)):
    return await general_item_type_service.get_by_id(db, type_id)


@router.put("/{type_id}", response_model=GeneralItemTypeRead)
async def update_general_item_type(
    type_id: int, data: GeneralItemTypeUpdate, db: AsyncSession = Depends(get_db)
):
    return await general_item_type_service.update(db, type_id, data)


@router.delete("/{type_id}", status_code=204)
async def delete_general_item_type(type_id: int, db: AsyncSession = Depends(get_db)):
    await general_item_type_service.delete(db, type_id)
    return Response(status_code=204)
