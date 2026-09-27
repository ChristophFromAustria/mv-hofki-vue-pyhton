"""Generic paginated response schema."""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class GroupCount(BaseModel):
    key: str
    label: str
    count: int


class Grouped(BaseModel):
    """Mixin for list rows: the group a row belongs to when grouping is on."""

    group_key: str | None = None
    group_label: str | None = None


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int
    item_total: int | None = None
    groups: list[GroupCount] | None = None
