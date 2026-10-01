"""InventoryItem API routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, Response
from fastapi_filter import FilterDepends
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.api.deps import get_db
from mv_hofki.api.routes._listing import page_response
from mv_hofki.filters.base import PageParams
from mv_hofki.filters.inventory_item import ItemFilter
from mv_hofki.schemas.general_item_category import (
    BulkCategoryResult,
    BulkCategoryUpdate,
)
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
    ItemRetire,
    SheetMusicItemCreate,
    SheetMusicItemRead,
    SheetMusicItemUpdate,
)
from mv_hofki.services import general_item_category as category_service
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
    flt: ItemFilter = FilterDepends(ItemFilter),
    page: PageParams = Depends(),
    db: AsyncSession = Depends(get_db),
):
    lp = await item_service.get_list(db, category=category, flt=flt, page=page)
    return page_response(lp, page, [_to_read(item) for item in lp.rows])


@router.get("/facets")
async def item_facets(category: str = Query(...), db: AsyncSession = Depends(get_db)):
    return await item_service.get_facets(db, category)


@router.post("/bulk-categories", response_model=BulkCategoryResult)
async def bulk_categories(data: BulkCategoryUpdate, db: AsyncSession = Depends(get_db)):
    updated = await category_service.bulk_update(
        db, data.item_ids, data.add_ids, data.remove_ids
    )
    return BulkCategoryResult(updated=updated)


@router.post("", status_code=201)
async def create_item(body: dict[str, Any], db: AsyncSession = Depends(get_db)):
    from fastapi import HTTPException
    from pydantic import ValidationError

    category = body.get("category")
    if not category or category not in _CREATE_SCHEMAS:
        raise HTTPException(status_code=400, detail=f"Ungültige Kategorie: {category}")

    if "category_ids" in body and category != "general_item":
        raise HTTPException(
            status_code=422,
            detail="Kategorien gibt es nur für allgemeine Gegenstände",
        )

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


@router.get("/by-number/{display_nr}")
async def get_item_by_number(
    display_nr: str, category: str, db: AsyncSession = Depends(get_db)
):
    return _to_read(await item_service.get_by_number(db, category, display_nr))


@router.get("/{item_id}")
async def get_item(item_id: int, db: AsyncSession = Depends(get_db)):
    result = await item_service.get_by_id(db, item_id)
    return _to_read(result)


@router.put("/{item_id}")
async def update_item(
    item_id: int, body: dict[str, Any], db: AsyncSession = Depends(get_db)
):
    from fastapi import HTTPException
    from pydantic import ValidationError

    # First fetch item to know its category
    current = await item_service.get_by_id(db, item_id)
    category = current["category"]

    if "category_ids" in body and category != "general_item":
        raise HTTPException(
            status_code=422,
            detail="Kategorien gibt es nur für allgemeine Gegenstände",
        )

    schema_cls = _UPDATE_SCHEMAS.get(category)
    if schema_cls:
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
        update_data = validated.model_dump(exclude_unset=True)
    else:
        update_data = body

    result = await item_service.update(db, item_id, update_data)
    return _to_read(result)


@router.post("/{item_id}/retire")
async def retire_item(
    item_id: int, data: ItemRetire, db: AsyncSession = Depends(get_db)
):
    return _to_read(await item_service.retire(db, item_id, data))


@router.post("/{item_id}/reinstate")
async def reinstate_item(item_id: int, db: AsyncSession = Depends(get_db)):
    return _to_read(await item_service.reinstate(db, item_id))


@router.delete("/{item_id}", status_code=204)
async def delete_item(item_id: int, db: AsyncSession = Depends(get_db)):
    await item_service.delete(db, item_id)
    return Response(status_code=204)
