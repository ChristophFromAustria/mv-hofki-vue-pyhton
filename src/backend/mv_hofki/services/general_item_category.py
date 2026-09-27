"""GeneralItemCategory CRUD and the links between general items and categories."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import delete as sa_delete
from sqlalchemy import func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.models.general_item_category import (
    GeneralItemCategory,
)
from mv_hofki.models.general_item_category import (
    general_item_category_links as links,
)
from mv_hofki.models.inventory_item import InventoryItem
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


async def check_category_ids(session: AsyncSession, ids: list[int]) -> list[int]:
    """Deduplicated, sorted ids; 422 if any id is unknown."""
    wanted = sorted(set(ids))
    if not wanted:
        return []
    found = set(
        (
            await session.execute(
                select(GeneralItemCategory.id).where(GeneralItemCategory.id.in_(wanted))
            )
        ).scalars()
    )
    missing = [i for i in wanted if i not in found]
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"Unbekannte Kategorie: {', '.join(str(i) for i in missing)}",
        )
    return wanted


async def set_item_categories(
    session: AsyncSession, item_id: int, ids: list[int]
) -> None:
    """Replace an item's categories. ``ids`` must come from check_category_ids."""
    await session.execute(sa_delete(links).where(links.c.item_id == item_id))
    if ids:
        await session.execute(
            insert(links), [{"item_id": item_id, "category_id": i} for i in ids]
        )


async def categories_for_items(
    session: AsyncSession, item_ids: list[int]
) -> dict[int, list[dict]]:
    """{item_id: [{id, label}, ...]} sorted by label, one query for all items."""
    if not item_ids:
        return {}
    result = await session.execute(
        select(links.c.item_id, GeneralItemCategory.id, GeneralItemCategory.label)
        .join(GeneralItemCategory, GeneralItemCategory.id == links.c.category_id)
        .where(links.c.item_id.in_(item_ids))
    )
    out: dict[int, list[dict]] = {}
    for item_id, cat_id, label in result.all():
        out.setdefault(item_id, []).append({"id": cat_id, "label": label})
    for cats in out.values():
        cats.sort(key=lambda c: _sort_key(c["label"]))
    return out


async def delete_links_for_items(
    session: AsyncSession, item_ids: list[int] | None
) -> None:
    """Remove the category links of the given items (all links if None)."""
    stmt = sa_delete(links)
    if item_ids is not None:
        stmt = stmt.where(links.c.item_id.in_(item_ids))
    await session.execute(stmt)


async def bulk_update(
    session: AsyncSession,
    item_ids: list[int],
    add_ids: list[int],
    remove_ids: list[int],
) -> int:
    """Add/remove categories on many general items in one transaction."""
    if not add_ids and not remove_ids:
        raise HTTPException(status_code=422, detail="Keine Kategorien angegeben")
    if set(add_ids) & set(remove_ids):
        raise HTTPException(
            status_code=422,
            detail="Kategorie kann nicht gleichzeitig hinzugefügt und entfernt werden",
        )
    wanted = sorted(set(item_ids))
    found = set(
        (
            await session.execute(
                select(InventoryItem.id).where(
                    InventoryItem.id.in_(wanted),
                    InventoryItem.category == "general_item",
                )
            )
        ).scalars()
    )
    bad = [i for i in wanted if i not in found]
    if bad:
        raise HTTPException(
            status_code=422,
            detail=f"Nur allgemeine Gegenstände: {', '.join(str(i) for i in bad)}",
        )
    add = await check_category_ids(session, add_ids)
    remove = await check_category_ids(session, remove_ids)
    if remove:
        await session.execute(
            sa_delete(links).where(
                links.c.item_id.in_(wanted), links.c.category_id.in_(remove)
            )
        )
    if add:
        existing = set(
            (
                await session.execute(
                    select(links.c.item_id, links.c.category_id).where(
                        links.c.item_id.in_(wanted), links.c.category_id.in_(add)
                    )
                )
            ).all()
        )
        new = [
            {"item_id": i, "category_id": c}
            for i in wanted
            for c in add
            if (i, c) not in existing
        ]
        if new:
            await session.execute(insert(links), new)
    await session.commit()
    return len(wanted)
