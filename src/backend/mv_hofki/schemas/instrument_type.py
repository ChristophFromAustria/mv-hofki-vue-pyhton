"""InstrumentType Pydantic schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class InstrumentTypeCreate(BaseModel):
    label: str
    label_short: str


class InstrumentTypeUpdate(BaseModel):
    label: str | None = None
    label_short: str | None = None


class InstrumentTypeRead(BaseModel):
    id: int
    label: str
    label_short: str
    created_at: datetime

    model_config = {"from_attributes": True}
