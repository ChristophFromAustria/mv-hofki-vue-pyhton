"""PDF output: data sheets, labels and inventory lists."""

from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi_filter import FilterDepends
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.api.deps import get_db
from mv_hofki.core.config import settings
from mv_hofki.filters.inventory_item import CATEGORY_LABELS, ItemFilter
from mv_hofki.services import inventory_item as item_service
from mv_hofki.services.printing import datasheet, inventory_list, labels

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


@router.get("/label-presets")
async def label_presets():
    """The label formats offered in the print dialog (sizes in mm), and the
    address the QR codes point to."""
    return {
        "public_url": settings.PUBLIC_URL,
        "presets": [
            {"key": key, "label": label, **vars(layout), "per_page": layout.per_page}
            for key, (label, layout) in labels.PRESETS.items()
        ],
    }


@router.get("/labels")
async def label_sheet(
    category: str,
    item_id: int | None = None,
    template: str = "roll-62x29",
    start: int = Query(1, ge=1),
    logo: bool = True,
    frame: bool = False,
    # template=custom: sizes in mm; cols/rows 0 = roll (page = label)
    width: float = 62,
    height: float = 29,
    cols: int = Query(0, ge=0, le=20),
    rows: int = Query(0, ge=0, le=40),
    margin_left: float = Query(0, ge=0),
    margin_top: float = Query(0, ge=0),
    gap_x: float = Query(0, ge=0),
    gap_y: float = Query(0, ge=0),
    flt: ItemFilter = FilterDepends(ItemFilter),
    db: AsyncSession = Depends(get_db),
):
    if template == "custom":
        layout = labels.custom_layout(
            width, height, cols, rows, margin_left, margin_top, gap_x, gap_y
        )
    elif template in labels.PRESETS:
        layout = labels.PRESETS[template][1]
    else:
        raise HTTPException(status_code=422, detail=f"Unbekanntes Format: {template}")
    ids, name = await _items(db, category, item_id, flt)
    numbers = await item_service.display_numbers(db, ids)
    items = [labels.LabelItem(i, numbers[i]) for i in ids if i in numbers]
    data = labels.render(items, layout, start=start, logo=logo, frame=frame)
    return _pdf(data, f"Etiketten {name}.pdf")


@router.get("/inventory-list")
async def inventory_list_pdf(
    category: str,
    columns: str = Query("", description="comma-separated column keys"),
    totals: bool = False,
    flt: ItemFilter = FilterDepends(ItemFilter),
    db: AsyncSession = Depends(get_db),
):
    """The items the list shows (its filters, order and grouping) as a table."""
    data = await inventory_list.render(
        db,
        category=category,
        flt=flt,
        columns=[c for c in columns.split(",") if c],
        totals=totals,
    )
    return _pdf(data, f"Inventarliste {CATEGORY_LABELS.get(category, category)}.pdf")


@router.get("/inventory-list/columns")
async def inventory_list_columns(category: str):
    """The columns the dialog offers for a category, in order."""
    keys = inventory_list.CATEGORY_COLUMNS.get(category)
    if keys is None:
        raise HTTPException(status_code=400, detail=f"Ungültige Kategorie: {category}")
    return [{"key": k, "label": inventory_list.column_label(category, k)} for k in keys]
