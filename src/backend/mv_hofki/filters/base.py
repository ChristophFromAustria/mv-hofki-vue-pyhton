"""Shared plumbing for list endpoints.

``ListFilter`` builds on fastapi-filter's SQLAlchemy ``Filter`` (query syntax
``field__op=value``, ``order_by=-a,b``, list parsing, OpenAPI docs) and adds the
project's conventions:

* ``Constants.columns`` maps a public field name to any column, also one of a
  joined table; unmapped names use the model's attribute of the same name.
* A method ``filter_<field name>(query, value)`` handles a field itself.
* ``search_clause(value)`` builds the ``search`` condition.
* ``Constants.sort_fields`` defines the public sort keys (one key may sort by
  several columns); ``order_by`` is validated against them. NULLs always sort
  last and the model's ``id`` is always the final key, so paging is stable.
* ``Constants.group_fields`` defines optional grouping (see ``fetch_page``).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, cast

from fastapi import Query
from fastapi_filter.contrib.sqlalchemy import Filter
from pydantic import ValidationInfo, field_validator
from sqlalchemy import ColumnElement, Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.filters.text_search import words_clause

MAX_LIMIT = 200


def _ilike(column: Any, value: str) -> ColumnElement[bool]:
    return cast(
        "ColumnElement[bool]", column.ilike(value if "%" in value else f"%{value}%")
    )


_OPERATORS: dict[str, Callable[[Any, Any], ColumnElement[bool]]] = {
    "neq": lambda col, v: col != v,
    "gt": lambda col, v: col > v,
    "gte": lambda col, v: col >= v,
    "lt": lambda col, v: col < v,
    "lte": lambda col, v: col <= v,
    "in": lambda col, v: col.in_(v),
    "not_in": lambda col, v: col.not_in(v),
    "isnull": lambda col, v: col.is_(None) if v else col.is_not(None),
    "ilike": _ilike,
}


class PageParams:
    """``limit``/``offset`` query parameters of every list endpoint."""

    def __init__(
        self,
        limit: int = Query(50, ge=1, le=MAX_LIMIT),
        offset: int = Query(0, ge=0),
    ):
        self.limit = limit
        self.offset = offset


@dataclass(frozen=True)
class GroupSpec:
    """How a list groups its rows. ``key``/``label``/``order`` are SQL
    expressions (``order`` defaults to ``label``); ``join`` adds the outer joins
    they need. With ``multi`` a row repeats once per group, e.g. an item with
    several categories; rows without one form the ``empty_label`` group."""

    key: Any
    label: Any
    empty_label: str
    order: Any = None
    join: Callable[[Select], Select] | None = None
    multi: bool = False


@dataclass
class ListPage:
    rows: list[Any]
    total: int
    item_total: int
    row_groups: list[tuple[str, str]] | None = None
    groups: list[dict[str, Any]] | None = None


class ListFilter(Filter):
    search: str | None = None
    order_by: list[str] | None = None
    group_by: str | None = None

    class Constants(Filter.Constants):  # type: ignore[misc]
        columns: dict[str, Any] = {}
        sort_fields: dict[str, list[Any]] = {}
        default_sort: list[str] = []
        group_fields: dict[str, GroupSpec | None] = {}

    # Replaces fastapi-filter's validator of the same name, which only accepts
    # attributes of the model as sort keys.
    @field_validator("*", mode="before", check_fields=False)
    @classmethod
    def validate_order_by(cls, value: Any, field: ValidationInfo) -> Any:
        if field.field_name != cls.Constants.ordering_field_name:
            return value
        if not value:
            return None
        if isinstance(value, str):
            value = value.split(",")
        keys = [v.strip() for v in value if v and v.strip()]
        seen: set[str] = set()
        for key in keys:
            name = key.lstrip("+-")
            if name not in cls.Constants.sort_fields:
                raise ValueError(f"„{name}“ ist kein gültiger Sortierschlüssel.")
            if name in seen:
                raise ValueError(f"Sortierschlüssel „{name}“ ist doppelt angegeben.")
            seen.add(name)
        return keys or None

    @field_validator("group_by")
    @classmethod
    def validate_group_by(cls, value: str | None) -> str | None:
        if not value:
            return None
        if value not in cls.Constants.group_fields:
            raise ValueError(f"„{value}“ ist keine gültige Gruppierung.")
        return value

    def group_spec(self) -> GroupSpec | None:
        if not self.group_by:
            return None
        return self.Constants.group_fields[self.group_by]

    def column(self, field: str) -> Any:
        if field in self.Constants.columns:
            return self.Constants.columns[field]
        return getattr(self.Constants.model, field)

    def sort_columns(self, key: str) -> list[Any]:
        return self.Constants.sort_fields[key]

    def search_clause(self, value: str) -> ColumnElement[bool] | None:
        """Every word in one of ``Constants.search_model_fields`` (tolerant,
        see ``filters/text_search.py``)."""
        fields = getattr(self.Constants, "search_model_fields", [])
        if not fields:
            return None
        return words_clause(value, [self.column(f) for f in fields])

    def filter(self, query: Select) -> Select:  # type: ignore[override]
        for name, value in self.filtering_fields:
            if name == "group_by":
                continue
            if name == self.Constants.search_field_name:
                clause = self.search_clause(value)
                if clause is not None:
                    query = query.where(clause)
                continue
            handler = getattr(self, f"filter_{name}", None)
            if handler is not None:
                query = handler(query, value)
                continue
            field, _, op = name.partition("__")
            column = self.column(field)
            query = query.where(
                _OPERATORS[op](column, value) if op else column == value
            )
        return query

    def sort(self, query: Select) -> Select:  # type: ignore[override]
        for key in self.order_by or self.Constants.default_sort:
            descending = key.startswith("-")
            for col in self.sort_columns(key.lstrip("+-")):
                ordered = col.desc() if descending else col.asc()
                query = query.order_by(ordered.nulls_last())
        return query.order_by(self.Constants.model.id)


async def paginate(
    session: AsyncSession,
    query: Select,
    page: PageParams,
    *,
    options: Sequence[Any] = (),
) -> tuple[list[Any], int]:
    """(rows of one page, total of the filtered query). Loader ``options`` are
    applied to the page query only, not to the count."""
    total = await session.scalar(
        select(func.count()).select_from(query.order_by(None).subquery())
    )
    result = await session.execute(
        query.options(*options).limit(page.limit).offset(page.offset)
    )
    return list(result.unique().scalars().all()), total or 0


def _key(value: Any) -> str:
    return "" if value is None else str(value)


async def fetch_page(
    session: AsyncSession,
    flt: ListFilter,
    query: Select,
    page: PageParams,
    *,
    options: Sequence[Any] = (),
) -> ListPage:
    """Filter, optionally group, sort and page ``query`` (a select of the
    filter's model). See ``GroupSpec`` for grouping."""
    filtered = flt.filter(query)
    distinct = filtered.order_by(None).subquery()
    item_total = (
        await session.scalar(select(func.count(func.distinct(distinct.c.id)))) or 0
    )
    spec = flt.group_spec()
    if spec is None:
        rows, total = await paginate(session, flt.sort(filtered), page, options=options)
        return ListPage(rows=rows, total=total, item_total=item_total)

    order = spec.order if spec.order is not None else spec.label
    grouped = spec.join(filtered) if spec.join else filtered
    grouped = grouped.add_columns(
        spec.key.label("group_key"),
        spec.label.label("group_label"),
        order.label("group_order"),
    )

    sub = grouped.order_by(None).subquery()
    total = await session.scalar(select(func.count()).select_from(sub)) or 0
    count_rows = await session.execute(
        select(sub.c.group_key, sub.c.group_label, func.count(func.distinct(sub.c.id)))
        .group_by(sub.c.group_key, sub.c.group_label, sub.c.group_order)
        .order_by(
            sub.c.group_order.asc().nulls_last(), sub.c.group_key.asc().nulls_last()
        )
    )
    groups = [
        {
            "key": _key(key),
            "label": spec.empty_label if key is None else str(label),
            "count": count,
        }
        for key, label, count in count_rows.all()
    ]

    ordered = flt.sort(
        grouped.order_by(order.asc().nulls_last(), spec.key.asc().nulls_last())
    )
    result = await session.execute(
        ordered.options(*options).limit(page.limit).offset(page.offset)
    )
    raw_rows = result.unique().all()
    return ListPage(
        rows=[r[0] for r in raw_rows],
        total=total,
        item_total=item_total,
        row_groups=[
            (
                _key(r.group_key),
                spec.empty_label if r.group_key is None else str(r.group_label),
            )
            for r in raw_rows
        ],
        groups=groups,
    )
