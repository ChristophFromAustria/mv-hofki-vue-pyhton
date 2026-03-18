"""InstrumentInvoice Pydantic schemas."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel

from mv_hofki.schemas.currency import CurrencyRead


class InstrumentInvoiceCreate(BaseModel):
    amount: float | None = None
    currency_id: int
    date_issued: date | None = None
    description: str | None = None
    invoice_nr: str | None = None
    invoice_issuer: str | None = None
    issuer_address: str | None = None


class InstrumentInvoiceUpdate(BaseModel):
    amount: float | None = None
    currency_id: int | None = None
    date_issued: date | None = None
    description: str | None = None
    invoice_nr: str | None = None
    invoice_issuer: str | None = None
    issuer_address: str | None = None


class InstrumentInvoiceRead(BaseModel):
    id: int
    instrument_id: int
    amount: float | None
    currency_id: int
    date_issued: date | None
    description: str | None
    invoice_nr: str | None
    invoice_issuer: str | None
    issuer_address: str | None
    filename: str | None
    file_url: str | None = None
    created_at: datetime
    currency: CurrencyRead

    model_config = {"from_attributes": True}
