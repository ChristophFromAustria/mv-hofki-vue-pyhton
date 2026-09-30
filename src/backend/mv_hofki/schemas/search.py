"""Schemas for GET /search (the global search field)."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel

from mv_hofki.schemas.inventory_item import ActiveLoanInfo


class ItemHit(BaseModel):
    id: int
    category: str
    display_nr: str
    label: str
    manufacturer: str | None = None
    notes: str | None = None
    active_loan: ActiveLoanInfo | None = None
    profile_image_url: str | None = None
    # Retired items are found too, marked.
    retired_at: date | None = None
    retired_reason: str | None = None


class MusicianHit(BaseModel):
    id: int
    first_name: str
    last_name: str
    city: str | None = None
    email: str | None = None
    is_active: bool
    is_extern: bool


class InvoiceHit(BaseModel):
    id: int
    title: str
    invoice_issuer: str | None = None
    date_issued: date
    amount: float
    currency: str | None = None
    item_id: int
    item_category: str
    item_display_nr: str
    item_label: str


class ItemGroup(BaseModel):
    category: str
    label: str
    total: int
    hits: list[ItemHit]


class MusicianGroup(BaseModel):
    total: int
    hits: list[MusicianHit]


class InvoiceGroup(BaseModel):
    total: int
    hits: list[InvoiceHit]


class SearchResult(BaseModel):
    query: str
    # The item whose inventory number is exactly the search text ("TR 6").
    exact: ItemHit | None = None
    # Categories in fixed order (instrument, clothing, general_item,
    # sheet_music), only those with hits.
    items: list[ItemGroup] = []
    musicians: MusicianGroup = MusicianGroup(total=0, hits=[])
    invoices: InvoiceGroup = InvoiceGroup(total=0, hits=[])
