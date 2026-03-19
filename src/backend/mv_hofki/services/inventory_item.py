"""InventoryItem CRUD service."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from mv_hofki.core.config import settings
from mv_hofki.models.clothing_detail import ClothingDetail
from mv_hofki.models.instrument_detail import InstrumentDetail
from mv_hofki.models.inventory_item import InventoryItem
from mv_hofki.models.item_image import ItemImage
from mv_hofki.models.loan import Loan
from mv_hofki.models.musician import Musician
from mv_hofki.models.sheet_music_detail import SheetMusicDetail
from mv_hofki.schemas.inventory_item import ActiveLoanInfo, format_display_nr

CATEGORY_PREFIXES = {
    "instrument": "I",
    "clothing": "K",
    "sheet_music": "N",
    "general_item": "A",
}
LOANABLE_CATEGORIES = {"instrument", "clothing", "general_item"}
INVOICEABLE_CATEGORIES = {"instrument", "clothing", "general_item"}

CATEGORY_DETAIL_MAP: dict[str, tuple[type | None, set[str]]] = {
    "instrument": (
        InstrumentDetail,
        {
            "instrument_type_id",
            "serial_nr",
            "construction_year",
            "distributor",
            "container",
            "particularities",
        },
    ),
    "clothing": (ClothingDetail, {"clothing_type_id", "size", "gender"}),
    "sheet_music": (
        SheetMusicDetail,
        {"composer", "arranger", "difficulty", "genre_id"},
    ),
    "general_item": (None, set()),
}

_DETAIL_JOINEDLOAD = {
    "instrument": lambda q: q.options(
        joinedload(InstrumentDetail.instrument_type),
    ),
    "clothing": lambda q: q.options(
        joinedload(ClothingDetail.clothing_type),
    ),
    "sheet_music": lambda q: q.options(
        joinedload(SheetMusicDetail.genre),
    ),
}


def _split_fields(
    data: dict[str, Any], category: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Split input data into base item fields and detail fields."""
    detail_model, detail_field_names = CATEGORY_DETAIL_MAP[category]
    base_fields: dict[str, Any] = {}
    detail_fields: dict[str, Any] = {}
    for key, value in data.items():
        if key == "category":
            continue
        if key in detail_field_names:
            detail_fields[key] = value
        else:
            base_fields[key] = value
    return base_fields, detail_fields


async def _enrich(session: AsyncSession, items: list[InventoryItem]) -> None:
    """Add active_loan and profile_image_url to items."""
    if not items:
        return
    ids = [i.id for i in items]

    # Active loans
    loan_result = await session.execute(
        select(Loan, Musician)
        .join(Musician, Loan.musician_id == Musician.id)
        .where(Loan.item_id.in_(ids), Loan.end_date.is_(None))
    )
    loan_map: dict[int, ActiveLoanInfo] = {}
    for loan, musician in loan_result:
        loan_map[loan.item_id] = ActiveLoanInfo(
            loan_id=loan.id,
            musician_id=musician.id,
            musician_name=f"{musician.first_name} {musician.last_name}",
            is_extern=musician.is_extern,
            start_date=loan.start_date,
        )

    # Profile images
    img_result = await session.execute(
        select(ItemImage).where(
            ItemImage.item_id.in_(ids), ItemImage.is_profile.is_(True)
        )
    )
    img_map: dict[int, str] = {}
    for img in img_result.scalars():
        img_map[img.item_id] = f"/uploads/images/{img.item_id}/{img.filename}"

    for item in items:
        item.active_loan = loan_map.get(item.id)  # type: ignore[attr-defined]
        item.profile_image_url = img_map.get(item.id)  # type: ignore[attr-defined]


async def _get_detail(session: AsyncSession, item_id: int, category: str) -> Any:
    """Fetch the detail record for an item."""
    detail_model, _ = CATEGORY_DETAIL_MAP[category]
    if detail_model is None:
        return None
    query: Any = select(detail_model).where(detail_model.item_id == item_id)  # type: ignore[attr-defined]
    if category in _DETAIL_JOINEDLOAD:
        query = _DETAIL_JOINEDLOAD[category](query)
    result = await session.execute(query)
    return result.unique().scalar_one_or_none()


def _build_read_dict(item: InventoryItem, detail: Any) -> dict[str, Any]:
    """Build a flat dict suitable for constructing a read schema."""
    d: dict[str, Any] = {
        "id": item.id,
        "category": item.category,
        "inventory_nr": item.inventory_nr,
        "display_nr": format_display_nr(item.category, item.inventory_nr),
        "label": item.label,
        "manufacturer": item.manufacturer,
        "acquisition_date": item.acquisition_date,
        "acquisition_cost": item.acquisition_cost,
        "currency_id": item.currency_id,
        "owner": item.owner,
        "notes": item.notes,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
        "currency": item.currency,
        "active_loan": getattr(item, "active_loan", None),
        "profile_image_url": getattr(item, "profile_image_url", None),
    }
    if detail:
        _, detail_field_names = CATEGORY_DETAIL_MAP[item.category]
        for field_name in detail_field_names:
            d[field_name] = getattr(detail, field_name, None)
        # Add relationship objects
        if item.category == "instrument":
            d["instrument_type"] = getattr(detail, "instrument_type", None)
        elif item.category == "clothing":
            d["clothing_type"] = getattr(detail, "clothing_type", None)
        elif item.category == "sheet_music":
            d["genre"] = getattr(detail, "genre", None)
    return d


async def create(session: AsyncSession, data: dict[str, Any]) -> dict[str, Any]:
    category = data["category"]
    if category not in CATEGORY_DETAIL_MAP:
        raise HTTPException(status_code=400, detail=f"Ungültige Kategorie: {category}")

    base_fields, detail_fields = _split_fields(data, category)

    # Auto-assign inventory_nr per category
    result = await session.execute(
        select(func.max(InventoryItem.inventory_nr)).where(
            InventoryItem.category == category
        )
    )
    max_nr = result.scalar_one_or_none() or 0

    item = InventoryItem(**base_fields, category=category, inventory_nr=max_nr + 1)
    session.add(item)
    await session.flush()

    # Create detail record (if the category has one)
    detail_model, _ = CATEGORY_DETAIL_MAP[category]
    if detail_model is not None:
        detail = detail_model(item_id=item.id, **detail_fields)
        session.add(detail)
    await session.commit()

    await session.refresh(item)
    detail = await _get_detail(session, item.id, category)
    await _enrich(session, [item])
    return _build_read_dict(item, detail)


async def get_list(
    session: AsyncSession,
    *,
    category: str,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    if category not in CATEGORY_DETAIL_MAP:
        raise HTTPException(status_code=400, detail=f"Ungültige Kategorie: {category}")

    query = (
        select(InventoryItem)
        .options(joinedload(InventoryItem.currency))
        .where(InventoryItem.category == category)
    )
    count_query = (
        select(func.count())
        .select_from(InventoryItem)
        .where(InventoryItem.category == category)
    )

    if search:
        pattern = f"%{search}%"
        search_filter = or_(
            InventoryItem.label.ilike(pattern),
            InventoryItem.manufacturer.ilike(pattern),
            InventoryItem.notes.ilike(pattern),
        )
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    total = (await session.execute(count_query)).scalar_one()
    query = query.order_by(InventoryItem.inventory_nr).limit(limit).offset(offset)
    result = await session.execute(query)
    items = list(result.unique().scalars().all())
    await _enrich(session, items)

    # Fetch details for all items
    read_items: list[dict[str, Any]] = []
    for item in items:
        detail = await _get_detail(session, item.id, category)
        read_items.append(_build_read_dict(item, detail))

    return read_items, total


async def get_by_id(session: AsyncSession, item_id: int) -> dict[str, Any]:
    result = await session.execute(
        select(InventoryItem)
        .options(joinedload(InventoryItem.currency))
        .where(InventoryItem.id == item_id)
    )
    item = result.unique().scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Gegenstand nicht gefunden")

    await _enrich(session, [item])
    detail = await _get_detail(session, item.id, item.category)
    return _build_read_dict(item, detail)


async def update(
    session: AsyncSession, item_id: int, data: dict[str, Any]
) -> dict[str, Any]:
    result = await session.execute(
        select(InventoryItem)
        .options(joinedload(InventoryItem.currency))
        .where(InventoryItem.id == item_id)
    )
    item = result.unique().scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Gegenstand nicht gefunden")

    base_fields, detail_fields = _split_fields(data, item.category)

    # Update base fields
    for key, value in base_fields.items():
        setattr(item, key, value)

    # Update detail fields
    if detail_fields:
        detail_model, _ = CATEGORY_DETAIL_MAP[item.category]
        if detail_model is not None:
            detail_result = await session.execute(  # type: ignore[var-annotated]
                select(detail_model).where(detail_model.item_id == item_id)  # type: ignore[attr-defined]
            )
            detail = detail_result.scalar_one_or_none()
            if detail:
                for key, value in detail_fields.items():
                    setattr(detail, key, value)

    await session.commit()
    await session.refresh(item)
    detail = await _get_detail(session, item.id, item.category)
    await _enrich(session, [item])
    return _build_read_dict(item, detail)


async def delete(session: AsyncSession, item_id: int) -> None:
    result = await session.execute(
        select(InventoryItem).where(InventoryItem.id == item_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Gegenstand nicht gefunden")

    await session.delete(item)
    await session.commit()

    # Clean up upload directories
    uploads_root = Path(settings.PROJECT_ROOT) / "data" / "uploads"
    for subdir in ("images", "invoices"):
        item_dir = uploads_root / subdir / str(item_id)
        if item_dir.exists():
            shutil.rmtree(item_dir)
