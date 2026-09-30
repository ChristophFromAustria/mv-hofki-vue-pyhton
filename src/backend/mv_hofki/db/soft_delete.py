"""Soft delete (Papierkorb): rows with ``deleted_at`` set are hidden.

Models that can go to the trash inherit ``SoftDeleteMixin``. A listener on
every ORM query adds ``deleted_at IS NULL`` for all of them — in the main
entity, joins, subqueries and aliases — so no list, count or search can show
a trashed row by accident. Loading a relationship of a visible row (a loan's
musician, an item's type) is not filtered: history keeps pointing at what it
pointed at.

Queries that must see trashed rows (the trash itself, inventory number
allocation, the loan list with trashed musicians) opt out with
``.execution_options(include_deleted=True)``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, event
from sqlalchemy.orm import (
    Mapped,
    ORMExecuteState,
    Session,
    mapped_column,
    with_loader_criteria,
)

INCLUDE_DELETED = "include_deleted"


def utcnow() -> datetime:
    """Naive UTC, like SQLite's CURRENT_TIMESTAMP used everywhere else."""
    return datetime.now(UTC).replace(tzinfo=None)


class SoftDeleteMixin:
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)


@event.listens_for(Session, "do_orm_execute")
def _hide_deleted(state: ORMExecuteState) -> None:
    if (
        not state.is_select
        or state.is_relationship_load
        or state.is_column_load
        or state.execution_options.get(INCLUDE_DELETED, False)
    ):
        return
    state.statement = state.statement.options(
        with_loader_criteria(
            SoftDeleteMixin,
            lambda cls: cls.deleted_at.is_(None),
            include_aliases=True,
        )
    )


def with_deleted(query: Any) -> Any:
    return query.execution_options(**{INCLUDE_DELETED: True})
