"""PDF output: data sheets (labels and inventory lists follow)."""

from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi_filter import FilterDepends
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.api.deps import get_db
from mv_hofki.filters.inventory_item import CATEGORY_LABELS, ItemFilter
from mv_hofki.services import inventory_item as item_service
from mv_hofki.services.printing import datasheet

router = APIRouter(prefix="/api/v1/print", tags=["print"])

MAX_ITEMS = 300


def _pdf(data: bytes, filename: str) -> Response:
    # inline: opens in the browser's PDF viewer, from there print or save.
    return Response(
        content=data,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"inline; filename*=UTF-8''{quote(filename)}",
            "Cache-Control": "no-store",
        },
    )


async def _items(
    db: AsyncSession, category: str, item_id: int | None, flt: ItemFilter
) -> tuple[list[int], str]:
    """The items to print: one (item_id) or all the list shows for the filters."""
    if item_id is not None:
        item = await item_service.get_by_id(db, item_id)
        return [item_id], item["display_nr"]
    ids = await item_service.filtered_ids(
        db, category=category, flt=flt, limit=MAX_ITEMS
    )
    if not ids:
        raise HTTPException(
            status_code=422, detail="Keine Gegenstände für diese Filter"
        )
    return ids, CATEGORY_LABELS.get(category, category)


@router.get("/datasheets")
async def datasheets(
    category: str,
    item_id: int | None = None,
    sections: str = Query("", description="photo,loan,loan_history,invoices,notes"),
    flt: ItemFilter = FilterDepends(ItemFilter),
    db: AsyncSession = Depends(get_db),
):
    chosen = {s for s in sections.split(",") if s in datasheet.SECTIONS}
    ids, name = await _items(db, category, item_id, flt)
    data = await datasheet.render(db, ids, chosen)
    return _pdf(data, f"Datenblatt {name}.pdf")
