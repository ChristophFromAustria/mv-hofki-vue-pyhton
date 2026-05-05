"""ClothingType Pydantic schemas."""

from __future__ import annotations

from pydantic import BaseModel


class ClothingTypeCreate(BaseModel):
    label: str


class ClothingTypeUpdate(BaseModel):
    label: str | None = None


class ClothingTypeRead(BaseModel):
    id: int
    label: str

    model_config = {"from_attributes": True}
