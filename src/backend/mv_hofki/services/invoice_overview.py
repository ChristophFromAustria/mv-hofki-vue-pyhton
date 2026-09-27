"""Invoice overview service — global listing across all categories."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from mv_hofki.filters.base import PageParams, paginate
from mv_hofki.filters.invoice import InvoiceFilter
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


async def get_list(
    session: AsyncSession, flt: InvoiceFilter, page: PageParams
) -> InvoiceOverviewResponse:
    base = select(ItemInvoice).join(
        InventoryItem, ItemInvoice.item_id == InventoryItem.id
    )
    filtered = flt.filter(base)

    # Totals over every filtered invoice, not only the loaded page.
    rows = filtered.order_by(None).subquery()
    totals_q = (
        select(Currency.abbreviation, func.sum(rows.c.amount))
        .select_from(rows)
        .join(Currency, Currency.id == rows.c.currency_id)
        .group_by(Currency.abbreviation)
        .order_by(Currency.abbreviation)
    )
    totals_by_currency = [
        CurrencyTotal(abbreviation=abbr, total=amount)
        for abbr, amount in (await session.execute(totals_q)).all()
    ]

    invoice_rows, total = await paginate(
        session, flt.sort(filtered), page, options=[joinedload(ItemInvoice.currency)]
    )

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
                    inv_item.number_prefix, inv_item.inventory_nr
                ),
                item_label=inv_item.label,
                item_category=inv_item.category,
                title=inv.title,
                invoice_issuer=inv.invoice_issuer,
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
        limit=page.limit,
        offset=page.offset,
        totals_by_currency=totals_by_currency,
    )
