"""Invoice overview Pydantic schemas."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel

from mv_hofki.schemas.currency import CurrencyRead


class InvoiceOverviewItem(BaseModel):
    id: int
    invoice_nr: int
    item_id: int
    item_display_nr: str
    item_label: str
    item_category: str
    title: str
    date_issued: date
    amount: float
    currency: CurrencyRead
    filename: str | None
    file_url: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class CurrencyTotal(BaseModel):
    abbreviation: str
    total: float


class InvoiceOverviewResponse(BaseModel):
    items: list[InvoiceOverviewItem]
    total: int
    totals_by_currency: list[CurrencyTotal]
