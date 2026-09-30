"""InventoryItem CRUD service."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from mv_hofki.core.config import settings
from mv_hofki.filters.base import ListPage, PageParams, fetch_page
from mv_hofki.filters.inventory_item import ItemFilter
from mv_hofki.models.clothing_detail import ClothingDetail
from mv_hofki.models.clothing_type import ClothingType
from mv_hofki.models.instrument_detail import InstrumentDetail
from mv_hofki.models.instrument_type import InstrumentType
from mv_hofki.models.inventory_item import InventoryItem
from mv_hofki.models.item_image import ItemImage
from mv_hofki.models.item_invoice import ItemInvoice
from mv_hofki.models.loan import Loan
from mv_hofki.models.musician import Musician
from mv_hofki.models.sheet_music_detail import SheetMusicDetail
from mv_hofki.schemas.inventory_item import (
    CATEGORY_PREFIXES,
    ActiveLoanInfo,
    format_display_nr,
)
from mv_hofki.services import general_item_category as category_service

UPLOADS_ROOT = Path(settings.PROJECT_ROOT) / "data" / "uploads"

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

    general_ids = [i.id for i in items if i.category == "general_item"]
    cat_map = await category_service.categories_for_items(session, general_ids)

    for item in items:
        item.active_loan = loan_map.get(item.id)  # type: ignore[attr-defined]
        item.profile_image_url = img_map.get(item.id)  # type: ignore[attr-defined]
        if item.category == "general_item":
            item.categories = cat_map.get(item.id, [])  # type: ignore[attr-defined]


async def _get_detail(session: AsyncSession, item_id: int, category: str) -> Any:
    """Fetch the detail record for an item."""
    detail_model, _ = CATEGORY_DETAIL_MAP[category]
    if detail_model is None:
        return None
    query: Any = select(detail_model).where(detail_model.item_id == item_id)  # type: ignore[attr-defined]
    if category in _DETAIL_JOINEDLOAD:
        query = _DETAIL_JOINEDLOAD[category](query)
    # populate_existing: force already identity-mapped rows (e.g. the detail
    # object we just mutated in update()/create(), or one loaded earlier in
    # this session) to refresh from this query's result, so a changed FK's
    # relationship (e.g. instrument_type) isn't served stale.
    query = query.execution_options(populate_existing=True)
    result = await session.execute(query)
    return result.unique().scalar_one_or_none()


def _build_read_dict(item: InventoryItem, detail: Any) -> dict[str, Any]:
    """Build a flat dict suitable for constructing a read schema."""
    d: dict[str, Any] = {
        "id": item.id,
        "category": item.category,
        "inventory_nr": item.inventory_nr,
        "display_nr": format_display_nr(item.number_prefix, item.inventory_nr),
        "label": item.label,
        "quantity": item.quantity,
        "manufacturer": item.manufacturer,
        "acquisition_date": item.acquisition_date,
        "acquisition_cost": item.acquisition_cost,
        "currency_id": item.currency_id,
        "owner": item.owner,
        "notes": item.notes,
        "storage_location": item.storage_location,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
        "currency": item.currency,
        "active_loan": getattr(item, "active_loan", None),
        "profile_image_url": getattr(item, "profile_image_url", None),
    }
    if item.category == "general_item":
        d["categories"] = getattr(item, "categories", [])
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


async def instrument_prefix(session: AsyncSession, instrument_type_id: int) -> str:
    """Number prefix for an instrument: its type's short code."""
    short = await session.scalar(
        select(InstrumentType.label_short).where(
            InstrumentType.id == instrument_type_id
        )
    )
    if short is None:
        raise HTTPException(status_code=400, detail="Instrumententyp nicht gefunden")
    return short.strip().upper()


async def next_inventory_nr(session: AsyncSession, category: str, prefix: str) -> int:
    """Next free number in the sequence of ``prefix`` (numbers are not reused)."""
    max_nr = await session.scalar(
        select(func.max(InventoryItem.inventory_nr)).where(
            InventoryItem.category == category,
            InventoryItem.number_prefix == prefix,
        )
    )
    return (max_nr or 0) + 1


async def create(session: AsyncSession, data: dict[str, Any]) -> dict[str, Any]:
    category = data["category"]
    if category not in CATEGORY_DETAIL_MAP:
        raise HTTPException(status_code=400, detail=f"Ungültige Kategorie: {category}")

    category_ids = data.pop("category_ids", None)
    if category_ids:
        category_ids = await category_service.check_category_ids(session, category_ids)

    base_fields, detail_fields = _split_fields(data, category)

    if category == "instrument":
        prefix = await instrument_prefix(session, detail_fields["instrument_type_id"])
    else:
        prefix = CATEGORY_PREFIXES[category]
    item = InventoryItem(
        **base_fields,
        category=category,
        number_prefix=prefix,
        inventory_nr=await next_inventory_nr(session, category, prefix),
    )
    session.add(item)
    await session.flush()

    # Create detail record (if the category has one)
    detail_model, _ = CATEGORY_DETAIL_MAP[category]
    if detail_model is not None:
        detail = detail_model(item_id=item.id, **detail_fields)
        session.add(detail)

    if category_ids:
        await category_service.set_item_categories(session, item.id, category_ids)
    await session.commit()

    await session.refresh(item)
    detail = await _get_detail(session, item.id, category)
    await _enrich(session, [item])
    return _build_read_dict(item, detail)


def _base_query(category: str) -> Any:
    query: Any = select(InventoryItem).where(InventoryItem.category == category)
    if category == "instrument":
        query = query.outerjoin(
            InstrumentDetail, InstrumentDetail.item_id == InventoryItem.id
        ).outerjoin(
            InstrumentType, InstrumentType.id == InstrumentDetail.instrument_type_id
        )
    elif category == "clothing":
        query = query.outerjoin(
            ClothingDetail, ClothingDetail.item_id == InventoryItem.id
        ).outerjoin(ClothingType, ClothingType.id == ClothingDetail.clothing_type_id)
    elif category == "sheet_music":
        query = query.outerjoin(
            SheetMusicDetail, SheetMusicDetail.item_id == InventoryItem.id
        )
    return query


async def _get_details(
    session: AsyncSession, item_ids: list[int], category: str
) -> dict[int, Any]:
    """Detail rows of many items in one query."""
    detail_model, _ = CATEGORY_DETAIL_MAP[category]
    if detail_model is None or not item_ids:
        return {}
    query: Any = select(detail_model).where(detail_model.item_id.in_(item_ids))  # type: ignore[attr-defined]
    if category in _DETAIL_JOINEDLOAD:
        query = _DETAIL_JOINEDLOAD[category](query)
    result = await session.execute(query)
    return {d.item_id: d for d in result.unique().scalars()}


async def get_list(
    session: AsyncSession,
    *,
    category: str,
    flt: ItemFilter,
    page: PageParams,
) -> ListPage:
    if category not in CATEGORY_DETAIL_MAP:
        raise HTTPException(status_code=400, detail=f"Ungültige Kategorie: {category}")
    flt.bind(category)
    lp = await fetch_page(
        session,
        flt,
        _base_query(category),
        page,
        options=[joinedload(InventoryItem.currency)],
    )
    unique_items = list({i.id: i for i in lp.rows}.values())
    await _enrich(session, unique_items)
    details = await _get_details(session, [i.id for i in unique_items], category)
    lp.rows = [_build_read_dict(i, details.get(i.id)) for i in lp.rows]
    return lp


FACETS: dict[str, dict[str, tuple[Any, Any]]] = {
    "instrument": {"owners": (None, InventoryItem.owner)},
    "clothing": {
        "sizes": (ClothingDetail, ClothingDetail.size),
        "genders": (ClothingDetail, ClothingDetail.gender),
    },
    "sheet_music": {"difficulties": (SheetMusicDetail, SheetMusicDetail.difficulty)},
    "general_item": {},
}


async def get_facets(session: AsyncSession, category: str) -> dict[str, list[str]]:
    """Distinct non-empty values that the list filters offer as choices."""
    if category not in FACETS:
        raise HTTPException(status_code=400, detail=f"Ungültige Kategorie: {category}")
    out: dict[str, list[str]] = {}
    for key, (detail_model, column) in FACETS[category].items():
        query: Any = select(column).distinct().select_from(InventoryItem)
        if detail_model is not None:
            query = query.join(detail_model, detail_model.item_id == InventoryItem.id)
        query = query.where(
            InventoryItem.category == category, column.is_not(None), column != ""
        )
        values = (await session.execute(query)).scalars().all()
        out[key] = sorted(values, key=str.casefold)
    return out


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

    category_ids = data.pop("category_ids", None)
    if category_ids is not None:
        category_ids = await category_service.check_category_ids(session, category_ids)

    base_fields, detail_fields = _split_fields(data, item.category)

    # A new instrument type with another short code moves the item into that
    # code's sequence. Renaming a short code does not: printed labels stay valid.
    new_type_id = detail_fields.get("instrument_type_id")
    if item.category == "instrument" and new_type_id is not None:
        prefix = await instrument_prefix(session, new_type_id)
        if prefix != item.number_prefix:
            item.inventory_nr = await next_inventory_nr(session, item.category, prefix)
            item.number_prefix = prefix

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

    if category_ids is not None:
        await category_service.set_item_categories(session, item.id, category_ids)

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

    # SQLite runs without PRAGMA foreign_keys, so ON DELETE CASCADE does not
    # fire: remove dependent rows explicitly. Otherwise a new item that gets
    # the same id (SQLite reuses the highest rowid) would inherit them.
    await category_service.delete_links_for_items(session, [item_id])
    detail_model, _ = CATEGORY_DETAIL_MAP[item.category]
    dependents: list[Any] = [ItemImage, ItemInvoice, Loan]
    if detail_model is not None:
        dependents.append(detail_model)
    for model in dependents:
        await session.execute(sa_delete(model).where(model.item_id == item_id))
    await session.delete(item)
    await session.commit()

    # Clean up upload directories
    for subdir in ("images", "invoices"):
        item_dir = UPLOADS_ROOT / subdir / str(item_id)
        if item_dir.exists():
            shutil.rmtree(item_dir)
