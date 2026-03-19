"""Dashboard Pydantic schemas."""

from __future__ import annotations

from pydantic import BaseModel


class InstrumentsByType(BaseModel):
    label: str
    label_short: str
    count: int


class ItemsByCategory(BaseModel):
    category: str
    label: str
    count: int


class DashboardStats(BaseModel):
    total_items: int
    total_musicians: int
    active_loans: int
    instruments_by_type: list[InstrumentsByType]
    items_by_category: list[ItemsByCategory]
