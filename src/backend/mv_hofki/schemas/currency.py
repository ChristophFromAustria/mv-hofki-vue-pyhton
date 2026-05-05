"""Currency Pydantic schemas."""

from __future__ import annotations

from pydantic import BaseModel


class CurrencyCreate(BaseModel):
    label: str
    abbreviation: str


class CurrencyUpdate(BaseModel):
    label: str | None = None
    abbreviation: str | None = None


class CurrencyRead(BaseModel):
    id: int
    label: str
    abbreviation: str

    model_config = {"from_attributes": True}
