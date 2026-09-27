"""Turn a ListPage into a PaginatedResponse."""

from __future__ import annotations

from typing import Any

from mv_hofki.filters.base import ListPage, PageParams
from mv_hofki.schemas.pagination import GroupCount, PaginatedResponse


def page_response(
    lp: ListPage, page: PageParams, items: list[Any]
) -> PaginatedResponse:
    """``items`` are the converted rows in the order of ``lp.rows``; group
    fields are attached when grouping is on (dicts or Grouped models)."""
    if lp.row_groups is not None:
        for item, (key, label) in zip(items, lp.row_groups):
            if isinstance(item, dict):
                item["group_key"], item["group_label"] = key, label
            else:
                item.group_key, item.group_label = key, label
    groups = None if lp.groups is None else [GroupCount(**g) for g in lp.groups]
    return PaginatedResponse(
        items=items,
        total=lp.total,
        limit=page.limit,
        offset=page.offset,
        item_total=lp.item_total,
        groups=groups,
    )
