"""Filter for GET /loans."""

from __future__ import annotations

from typing import Literal

from sqlalchemy import ColumnElement, Select, case, literal, or_

from mv_hofki.filters.base import GroupSpec, ListFilter
from mv_hofki.filters.inventory_item import display_nr_condition
from mv_hofki.models.inventory_item import InventoryItem
from mv_hofki.models.loan import Loan
from mv_hofki.models.musician import Musician

_CATEGORY_LABEL = case(
    (InventoryItem.category == "instrument", "Instrumente"),
    (InventoryItem.category == "clothing", "Kleidung"),
    else_="Allgemein",
)
_CATEGORY_ORDER = case(
    (InventoryItem.category == "instrument", 0),
    (InventoryItem.category == "clothing", 1),
    else_=2,
)
_MUSICIAN_LABEL = Musician.last_name + literal(" ") + Musician.first_name


class LoanFilter(ListFilter):
    active: bool | None = None
    item_category: Literal["instrument", "clothing", "general_item"] | None = None
    musician_id: int | None = None
    item_id: int | None = None

    class Constants(ListFilter.Constants):
        model = Loan
        columns = {"item_category": InventoryItem.category}
        sort_fields = {
            "start_date": [Loan.start_date],
            "end_date": [Loan.end_date],
        }
        default_sort = ["-start_date"]
        group_fields = {
            "musician": GroupSpec(
                key=Musician.id, label=_MUSICIAN_LABEL, empty_label="—"
            ),
            "item_category": GroupSpec(
                key=InventoryItem.category,
                label=_CATEGORY_LABEL,
                order=_CATEGORY_ORDER,
                empty_label="—",
            ),
            "status": GroupSpec(
                key=case((Loan.end_date.is_(None), "offen"), else_="zurueckgegeben"),
                label=case((Loan.end_date.is_(None), "Offen"), else_="Zurückgegeben"),
                order=case((Loan.end_date.is_(None), 0), else_=1),
                empty_label="—",
            ),
        }

    def filter_active(self, query: Select, value: bool) -> Select:
        return query.where(
            Loan.end_date.is_(None) if value else Loan.end_date.is_not(None)
        )

    def search_clause(self, value: str) -> ColumnElement[bool] | None:
        value = value.strip()
        if not value:
            return None
        pattern = f"%{value}%"
        conditions: list[ColumnElement[bool]] = [
            InventoryItem.label.ilike(pattern),
            Musician.first_name.ilike(pattern),
            Musician.last_name.ilike(pattern),
        ]
        nr = display_nr_condition(value)
        if nr is not None:
            conditions.append(nr)
        return or_(*conditions)
