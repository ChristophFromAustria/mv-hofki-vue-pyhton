"""Loan Pydantic schemas."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel

from mv_hofki.schemas.instrument import InstrumentRead
from mv_hofki.schemas.musician import MusicianRead


class LoanCreate(BaseModel):
    instrument_id: int
    musician_id: int
    start_date: date


class LoanUpdate(BaseModel):
    start_date: date | None = None
    end_date: date | None = None


class LoanRead(BaseModel):
    id: int
    instrument_id: int
    musician_id: int
    start_date: date
    end_date: date | None
    created_at: datetime
    instrument: InstrumentRead
    musician: MusicianRead

    model_config = {"from_attributes": True}
