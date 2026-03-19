"""GeneralItemType Pydantic schemas."""

from __future__ import annotations

from pydantic import BaseModel


class GeneralItemTypeCreate(BaseModel):
    label: str


class GeneralItemTypeUpdate(BaseModel):
    label: str | None = None


class GeneralItemTypeRead(BaseModel):
    id: int
    label: str

    model_config = {"from_attributes": True}
