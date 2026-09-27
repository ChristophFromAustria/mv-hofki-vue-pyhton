"""GeneralItemCategory Pydantic schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


def _clean_label(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("Bezeichnung darf nicht leer sein")
    return value


class GeneralItemCategoryCreate(BaseModel):
    label: str = Field(max_length=50)

    @field_validator("label")
    @classmethod
    def clean_label(cls, value: str) -> str:
        return _clean_label(value)


class GeneralItemCategoryUpdate(BaseModel):
    label: str | None = Field(None, max_length=50)

    @field_validator("label")
    @classmethod
    def clean_label(cls, value: str | None) -> str | None:
        return None if value is None else _clean_label(value)


class GeneralItemCategoryRef(BaseModel):
    id: int
    label: str

    model_config = {"from_attributes": True}


class GeneralItemCategoryRead(GeneralItemCategoryRef):
    item_count: int = 0


class BulkCategoryUpdate(BaseModel):
    item_ids: list[int] = Field(min_length=1, max_length=500)
    add_ids: list[int] = []
    remove_ids: list[int] = []


class BulkCategoryResult(BaseModel):
    updated: int
