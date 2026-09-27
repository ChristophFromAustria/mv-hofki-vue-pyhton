"""Filter for GET /invoices."""

from __future__ import annotations

from datetime import date
from typing import Literal

from mv_hofki.filters.base import ListFilter
from mv_hofki.models.inventory_item import InventoryItem
from mv_hofki.models.item_invoice import ItemInvoice


class InvoiceFilter(ListFilter):
    item_category: (
        Literal["instrument", "clothing", "sheet_music", "general_item"] | None
    ) = None
    date_issued__gte: date | None = None
    date_issued__lte: date | None = None
    currency_id: int | None = None

    class Constants(ListFilter.Constants):
        model = ItemInvoice
        search_model_fields = ["title", "invoice_issuer"]
        columns = {"item_category": InventoryItem.category}
        sort_fields = {
            "date_issued": [ItemInvoice.date_issued],
            "amount": [ItemInvoice.amount],
            "invoice_issuer": [ItemInvoice.invoice_issuer],
        }
        default_sort = ["-date_issued"]
