"""Invoice overview service — global listing across all categories."""

from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from mv_hofki.models.currency import Currency
from mv_hofki.models.inventory_item import InventoryItem
from mv_hofki.models.item_invoice import ItemInvoice
from mv_hofki.schemas.currency import CurrencyRead
from mv_hofki.schemas.inventory_item import format_display_nr
from mv_hofki.schemas.invoice_overview import (
    CurrencyTotal,
    InvoiceOverviewItem,
    InvoiceOverviewResponse,
)


def _build_filters(
    category: str | None,
    search: str | None,
    date_from: date | None,
    date_to: date | None,
):
    """Return a list of SQLAlchemy filter expressions."""
    filters = []
    if category:
        filters.append(InventoryItem.category == category)
    if search:
        term = f"%{search}%"
        filters.append(
            ItemInvoice.title.ilike(term) | ItemInvoice.invoice_issuer.ilike(term)
        )
    if date_from:
        filters.append(ItemInvoice.date_issued >= date_from)
    if date_to:
        filters.append(ItemInvoice.date_issued <= date_to)
    return filters


async def get_list(
    session: AsyncSession,
    *,
    category: str | None = None,
    search: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 50,
    offset: int = 0,
) -> InvoiceOverviewResponse:
    filters = _build_filters(category, search, date_from, date_to)

    # Base query joining InventoryItem
    base_q = (
        select(ItemInvoice)
        .join(InventoryItem, ItemInvoice.item_id == InventoryItem.id)
        .options(joinedload(ItemInvoice.currency))
        .where(*filters)
    )

    # Count query
    count_q = (
        select(func.count())
        .select_from(ItemInvoice)
        .join(InventoryItem, ItemInvoice.item_id == InventoryItem.id)
        .where(*filters)
    )
    total = (await session.execute(count_q)).scalar_one()

    # Totals-by-currency query (full filtered set, no pagination)
    totals_q = (
        select(Currency.abbreviation, func.sum(ItemInvoice.amount))
        .select_from(ItemInvoice)
        .join(InventoryItem, ItemInvoice.item_id == InventoryItem.id)
        .join(Currency, ItemInvoice.currency_id == Currency.id)
        .where(*filters)
        .group_by(Currency.abbreviation)
    )
    totals_rows = (await session.execute(totals_q)).all()
    totals_by_currency = [
        CurrencyTotal(abbreviation=abbr, total=total_amount)
        for abbr, total_amount in totals_rows
    ]

    # Paginated items query
    items_q = (
        base_q.order_by(ItemInvoice.date_issued.desc().nulls_last())
        .limit(limit)
        .offset(offset)
    )
    invoice_rows = (await session.execute(items_q)).unique().scalars().all()

    # Fetch InventoryItem data for each invoice (need category + inventory_nr + label)
    item_ids = list({inv.item_id for inv in invoice_rows})
    item_map: dict[int, InventoryItem] = {}
    if item_ids:
        items_result = await session.execute(
            select(InventoryItem).where(InventoryItem.id.in_(item_ids))
        )
        item_map = {item.id: item for item in items_result.scalars().all()}

    items: list[InvoiceOverviewItem] = []
    for inv in invoice_rows:
        inv_item = item_map.get(inv.item_id)
        if inv_item is None:
            continue
        file_url = (
            f"/uploads/invoices/{inv.item_id}/{inv.filename}" if inv.filename else None
        )
        items.append(
            InvoiceOverviewItem(
                id=inv.id,
                invoice_nr=inv.invoice_nr,
                item_id=inv.item_id,
                item_display_nr=format_display_nr(
                    inv_item.category, inv_item.inventory_nr
                ),
                item_label=inv_item.label,
                item_category=inv_item.category,
                title=inv.title,
                date_issued=inv.date_issued,
                amount=inv.amount,
                currency=CurrencyRead.model_validate(inv.currency),
                filename=inv.filename,
                file_url=file_url,
                created_at=inv.created_at,
            )
        )

    return InvoiceOverviewResponse(
        items=items,
        total=total,
        totals_by_currency=totals_by_currency,
    )
