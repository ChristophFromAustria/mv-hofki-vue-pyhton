"""Instrument Pydantic schemas."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel

from mv_hofki.schemas.currency import CurrencyRead
from mv_hofki.schemas.instrument_type import InstrumentTypeRead


class InstrumentCreate(BaseModel):
    inventory_nr: int
    label_addition: str | None = None
    manufacturer: str | None = None
    serial_nr: str | None = None
    construction_year: date | None = None
    acquisition_date: date | None = None
    acquisition_cost: float | None = None
    currency_id: int
    distributor: str | None = None
    container: str | None = None
    particularities: str | None = None
    owner: str
    notes: str | None = None
    instrument_type_id: int


class InstrumentUpdate(BaseModel):
    inventory_nr: int | None = None
    label_addition: str | None = None
    manufacturer: str | None = None
    serial_nr: str | None = None
    construction_year: date | None = None
    acquisition_date: date | None = None
    acquisition_cost: float | None = None
    currency_id: int | None = None
    distributor: str | None = None
    container: str | None = None
    particularities: str | None = None
    owner: str | None = None
    notes: str | None = None
    instrument_type_id: int | None = None


class InstrumentRead(BaseModel):
    id: int
    inventory_nr: int
    label_addition: str | None
    manufacturer: str | None
    serial_nr: str | None
    construction_year: date | None
    acquisition_date: date | None
    acquisition_cost: float | None
    currency_id: int
    distributor: str | None
    container: str | None
    particularities: str | None
    owner: str
    notes: str | None
    instrument_type_id: int
    created_at: datetime
    instrument_type: InstrumentTypeRead
    currency: CurrencyRead

    model_config = {"from_attributes": True}
