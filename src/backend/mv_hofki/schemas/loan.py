"""Loan Pydantic schemas."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator

from mv_hofki.schemas.inventory_item import ItemRead
from mv_hofki.schemas.musician import MusicianRead
from mv_hofki.schemas.pagination import Grouped

LOAN_NOTES_MAX = 1000


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


class LoanCreate(BaseModel):
    item_id: int
    musician_id: int
    start_date: date
    notes: str | None = Field(None, max_length=LOAN_NOTES_MAX)

    _notes = field_validator("notes")(_blank_to_none)


class LoanUpdate(BaseModel):
    start_date: date | None = None
    end_date: date | None = None
    notes: str | None = Field(None, max_length=LOAN_NOTES_MAX)

    _notes = field_validator("notes")(_blank_to_none)


class LoanReturn(BaseModel):
    end_date: date | None = None


class LoanRead(BaseModel):
    id: int
    item_id: int
    musician_id: int
    start_date: date
    end_date: date | None
    notes: str | None = None
    created_at: datetime
    item: ItemRead
    musician: MusicianRead

    model_config = {"from_attributes": True}


class LoanListRow(LoanRead, Grouped):
    pass
