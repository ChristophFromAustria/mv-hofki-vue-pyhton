"""Filter for GET /loans."""

from __future__ import annotations

from datetime import date
from typing import Literal

from sqlalchemy import ColumnElement, Select, and_, case, literal, or_

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


def overdue_condition(today: date | None = None) -> ColumnElement[bool]:
    """Open loans whose planned return day has passed."""
    return and_(
        Loan.end_date.is_(None),
        Loan.due_date.is_not(None),
        Loan.due_date < (today or date.today()),
    )


class LoanFilter(ListFilter):
    active: bool | None = None
    item_category: Literal["instrument", "clothing", "general_item"] | None = None
    musician_id: int | None = None
    item_id: int | None = None
    overdue: bool | None = None

    class Constants(ListFilter.Constants):
        model = Loan
        columns = {"item_category": InventoryItem.category}
        sort_fields = {
            "start_date": [Loan.start_date],
            "end_date": [Loan.end_date],
            "due_date": [Loan.due_date],
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
            # "today" is evaluated per query, see group_spec.
            "status": None,
        }

    def group_spec(self) -> GroupSpec | None:
        if self.group_by == "status":
            overdue = overdue_condition()
            open_ = Loan.end_date.is_(None)
            return GroupSpec(
                key=case(
                    (overdue, "ueberfaellig"), (open_, "offen"), else_="zurueckgegeben"
                ),
                label=case(
                    (overdue, "Überfällig"), (open_, "Offen"), else_="Zurückgegeben"
                ),
                order=case((overdue, 0), (open_, 1), else_=2),
                empty_label="—",
            )
        return super().group_spec()

    def filter_overdue(self, query: Select, value: bool) -> Select:
        condition = overdue_condition()
        return query.where(condition if value else ~condition)

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
            Loan.notes.ilike(pattern),
        ]
        nr = display_nr_condition(value)
        if nr is not None:
            conditions.append(nr)
        return or_(*conditions)
