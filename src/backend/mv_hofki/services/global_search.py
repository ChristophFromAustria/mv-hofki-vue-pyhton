"""The global search: one search text over items, musicians and invoices.

Uses the same tolerant, word-wise conditions as the list searches
(filters/text_search.py), so a hit here is a hit in the matching list.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import ColumnElement, Select, case, func, literal, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from mv_hofki.filters.inventory_item import (
    CATEGORY_LABELS,
    display_nr_condition,
    item_search_clause,
)
from mv_hofki.filters.text_search import search_words, words_clause
from mv_hofki.models.inventory_item import InventoryItem
from mv_hofki.models.item_invoice import ItemInvoice
from mv_hofki.models.musician import Musician
from mv_hofki.schemas.inventory_item import format_display_nr
from mv_hofki.schemas.search import (
    InvoiceGroup,
    InvoiceHit,
    ItemGroup,
    ItemHit,
    MusicianGroup,
    MusicianHit,
    SearchResult,
)
from mv_hofki.services.inventory_item import enrich_items

# Fixed order of the item groups (see docs/konzept-allgemeine-suche.md).
ITEM_CATEGORIES = ("instrument", "clothing", "general_item", "sheet_music")
MIN_LENGTH = 2


def _item_hit(item: InventoryItem) -> ItemHit:
    return ItemHit(
        id=item.id,
        category=item.category,
        display_nr=format_display_nr(item.number_prefix, item.inventory_nr),
        label=item.label,
        manufacturer=item.manufacturer,
        notes=item.notes,
        active_loan=getattr(item, "active_loan", None),
        profile_image_url=getattr(item, "profile_image_url", None),
    )


async def _count(session: AsyncSession, query: Select) -> int:
    return (
        await session.scalar(select(func.count()).select_from(query.subquery()))
    ) or 0


def _label_first(text: str) -> ColumnElement[Any]:
    """0 for items with every search word in the label, else 1."""
    in_label = words_clause(text, [InventoryItem.label])
    return literal(0) if in_label is None else case((in_label, 0), else_=1)


async def _items(
    session: AsyncSession, text: str, limit: int
) -> tuple[list[ItemGroup], ItemHit | None]:
    clause = item_search_clause(text)
    groups: list[ItemGroup] = []
    if clause is not None:
        for category in ITEM_CATEGORIES:
            query = select(InventoryItem).where(
                InventoryItem.category == category, clause
            )
            total = await _count(session, query)
            if not total:
                continue
            rows = list(
                (
                    await session.execute(
                        query.order_by(
                            _label_first(text),
                            InventoryItem.number_prefix,
                            InventoryItem.inventory_nr,
                        ).limit(limit)
                    )
                ).scalars()
            )
            await enrich_items(session, rows)
            groups.append(
                ItemGroup(
                    category=category,
                    label=CATEGORY_LABELS[category],
                    total=total,
                    hits=[_item_hit(i) for i in rows],
                )
            )

    exact: ItemHit | None = None
    nr = display_nr_condition(text)
    if nr is not None:
        found = list(
            (await session.execute(select(InventoryItem).where(nr).limit(2))).scalars()
        )
        # Prefixes are unique per category only; jump only when unambiguous.
        if len(found) == 1:
            await enrich_items(session, found)
            exact = _item_hit(found[0])
    return groups, exact


async def _musicians(session: AsyncSession, text: str, limit: int) -> MusicianGroup:
    clause = words_clause(
        text,
        [Musician.first_name, Musician.last_name, Musician.email, Musician.city],
    )
    if clause is None:
        return MusicianGroup(total=0, hits=[])
    query = select(Musician).where(clause)
    total = await _count(session, query)
    rows = (
        await session.execute(
            query.order_by(
                Musician.is_active.desc(), Musician.last_name, Musician.first_name
            ).limit(limit)
        )
    ).scalars()
    return MusicianGroup(
        total=total,
        hits=[
            MusicianHit(
                id=m.id,
                first_name=m.first_name,
                last_name=m.last_name,
                city=m.city,
                email=m.email,
                is_active=m.is_active,
                is_extern=m.is_extern,
            )
            for m in rows
        ],
    )


async def _invoices(session: AsyncSession, text: str, limit: int) -> InvoiceGroup:
    clause = words_clause(text, [ItemInvoice.title, ItemInvoice.invoice_issuer])
    if clause is None:
        return InvoiceGroup(total=0, hits=[])
    query = select(ItemInvoice).where(clause)
    total = await _count(session, query)
    rows = (
        await session.execute(
            select(ItemInvoice, InventoryItem)
            .join(InventoryItem, InventoryItem.id == ItemInvoice.item_id)
            .options(joinedload(ItemInvoice.currency))
            .where(clause)
            .order_by(ItemInvoice.date_issued.desc(), ItemInvoice.id.desc())
            .limit(limit)
        )
    ).all()
    return InvoiceGroup(
        total=total,
        hits=[
            InvoiceHit(
                id=inv.id,
                title=inv.title,
                invoice_issuer=inv.invoice_issuer,
                date_issued=inv.date_issued,
                amount=inv.amount,
                currency=inv.currency.abbreviation if inv.currency else None,
                item_id=item.id,
                item_category=item.category,
                item_display_nr=format_display_nr(
                    item.number_prefix, item.inventory_nr
                ),
                item_label=item.label,
            )
            for inv, item in rows
        ],
    )


async def search(session: AsyncSession, text: str, limit: int) -> SearchResult:
    """Hits of ``text`` in every area, at most ``limit`` per group. Texts
    shorter than MIN_LENGTH find nothing, unless they are an inventory
    number ("A 1")."""
    text = text.strip()
    result = SearchResult(query=text)
    is_number = display_nr_condition(text) is not None
    if not search_words(text) or (len(text) < MIN_LENGTH and not is_number):
        return result
    result.items, result.exact = await _items(session, text, limit)
    result.musicians = await _musicians(session, text, limit)
    result.invoices = await _invoices(session, text, limit)
    return result
