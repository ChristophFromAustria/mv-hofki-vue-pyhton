"""InventoryItem API routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.api.deps import get_db
from mv_hofki.schemas.inventory_item import (
    ClothingItemCreate,
    ClothingItemRead,
    ClothingItemUpdate,
    GeneralItemCreate,
    GeneralItemRead,
    GeneralItemUpdate,
    InstrumentItemCreate,
    InstrumentItemRead,
    InstrumentItemUpdate,
    SheetMusicItemCreate,
    SheetMusicItemRead,
    SheetMusicItemUpdate,
)
from mv_hofki.schemas.pagination import PaginatedResponse
from mv_hofki.services import inventory_item as item_service

router = APIRouter(prefix="/api/v1/items", tags=["items"])

_CREATE_SCHEMAS: dict[str, type] = {
    "instrument": InstrumentItemCreate,
    "clothing": ClothingItemCreate,
    "sheet_music": SheetMusicItemCreate,
    "general_item": GeneralItemCreate,
}

_UPDATE_SCHEMAS: dict[str, type] = {
    "instrument": InstrumentItemUpdate,
    "clothing": ClothingItemUpdate,
    "sheet_music": SheetMusicItemUpdate,
    "general_item": GeneralItemUpdate,
}

_READ_SCHEMAS: dict[str, type] = {
    "instrument": InstrumentItemRead,
    "clothing": ClothingItemRead,
    "sheet_music": SheetMusicItemRead,
    "general_item": GeneralItemRead,
}


def _to_read(data: dict[str, Any]) -> dict[str, Any]:
    """Construct the category-specific read schema from a flat dict."""
    category = data["category"]
    schema_cls = _READ_SCHEMAS.get(category)
    if schema_cls:
        return schema_cls(**data).model_dump(mode="json")  # type: ignore[no-any-return]
    return data


@router.get("")
async def list_items(
    category: str = Query(
        ..., description="Category: instrument, clothing, sheet_music, general_item"
    ),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    items, total = await item_service.get_list(
        db, category=category, search=search, limit=limit, offset=offset
    )
    return PaginatedResponse(
        items=[_to_read(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", status_code=201)
async def create_item(body: dict[str, Any], db: AsyncSession = Depends(get_db)):
    from fastapi import HTTPException
    from pydantic import ValidationError

    category = body.get("category")
    if not category or category not in _CREATE_SCHEMAS:
        raise HTTPException(status_code=400, detail=f"Ungültige Kategorie: {category}")

    # Validate with category-specific schema
    schema_cls = _CREATE_SCHEMAS[category]
    try:
        validated = schema_cls(**body)
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail=[
                {"loc": e["loc"], "msg": e["msg"], "type": e["type"]}
                for e in exc.errors()
            ],
        ) from exc
    result = await item_service.create(db, validated.model_dump())
    return _to_read(result)


@router.get("/{item_id}")
async def get_item(item_id: int, db: AsyncSession = Depends(get_db)):
    result = await item_service.get_by_id(db, item_id)
    return _to_read(result)


@router.put("/{item_id}")
async def update_item(
    item_id: int, body: dict[str, Any], db: AsyncSession = Depends(get_db)
):
    # First fetch item to know its category
    current = await item_service.get_by_id(db, item_id)
    category = current["category"]
    schema_cls = _UPDATE_SCHEMAS.get(category)
    if schema_cls:
        validated = schema_cls(**body)
        update_data = validated.model_dump(exclude_unset=True)
    else:
        update_data = body

    result = await item_service.update(db, item_id, update_data)
    return _to_read(result)


@router.delete("/{item_id}", status_code=204)
async def delete_item(item_id: int, db: AsyncSession = Depends(get_db)):
    await item_service.delete(db, item_id)
    return Response(status_code=204)
