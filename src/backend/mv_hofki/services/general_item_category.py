"""GeneralItemCategory CRUD and the links between general items and categories."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.models.general_item_category import (
    GeneralItemCategory,
)
from mv_hofki.models.general_item_category import (
    general_item_category_links as links,
)
from mv_hofki.schemas.general_item_category import (
    GeneralItemCategoryCreate,
    GeneralItemCategoryUpdate,
)


def _sort_key(label: str) -> str:
    return label.casefold()


def _as_dict(category: GeneralItemCategory, item_count: int) -> dict:
    return {"id": category.id, "label": category.label, "item_count": item_count}


async def _get(session: AsyncSession, category_id: int) -> GeneralItemCategory:
    obj = await session.get(GeneralItemCategory, category_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Kategorie nicht gefunden")
    return obj


async def _item_count(session: AsyncSession, category_id: int) -> int:
    return (
        await session.scalar(
            select(func.count())
            .select_from(links)
            .where(links.c.category_id == category_id)
        )
        or 0
    )


async def _ensure_unique(
    session: AsyncSession, label: str, exclude_id: int | None = None
) -> None:
    # Compared in Python: SQLite's lower() leaves umlauts alone.
    rows = await session.execute(
        select(GeneralItemCategory.id, GeneralItemCategory.label)
    )
    wanted = label.casefold()
    for other_id, other_label in rows.all():
        if other_id != exclude_id and other_label.casefold() == wanted:
            raise HTTPException(status_code=409, detail="Kategorie existiert bereits")


async def get_all(session: AsyncSession) -> list[dict]:
    result = await session.execute(
        select(GeneralItemCategory, func.count(links.c.item_id))
        .outerjoin(links, links.c.category_id == GeneralItemCategory.id)
        .group_by(GeneralItemCategory.id)
    )
    rows = [_as_dict(category, count) for category, count in result.all()]
    return sorted(rows, key=lambda r: _sort_key(r["label"]))


async def get_by_id(session: AsyncSession, category_id: int) -> dict:
    obj = await _get(session, category_id)
    return _as_dict(obj, await _item_count(session, category_id))


async def create(session: AsyncSession, data: GeneralItemCategoryCreate) -> dict:
    await _ensure_unique(session, data.label)
    obj = GeneralItemCategory(label=data.label)
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return _as_dict(obj, 0)


async def update(
    session: AsyncSession, category_id: int, data: GeneralItemCategoryUpdate
) -> dict:
    obj = await _get(session, category_id)
    if data.label is not None:
        await _ensure_unique(session, data.label, exclude_id=category_id)
        obj.label = data.label
    await session.commit()
    await session.refresh(obj)
    return _as_dict(obj, await _item_count(session, category_id))


async def delete(session: AsyncSession, category_id: int) -> None:
    obj = await _get(session, category_id)
    await session.execute(sa_delete(links).where(links.c.category_id == category_id))
    await session.delete(obj)
    await session.commit()
