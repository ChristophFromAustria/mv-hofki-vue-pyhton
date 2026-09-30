"""Unique labels of master data, including rows in the trash."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.db.soft_delete import with_deleted


async def ensure_label_free(
    session: AsyncSession,
    model: Any,
    label: str,
    *,
    what: str,
    exclude_id: int | None = None,
) -> None:
    """409 if another row (also a trashed one) has this label — compared
    case-insensitively, umlauts too. Labels are unique in the database, so a
    trashed row blocks the name until it is restored or deleted for good."""
    wanted = label.strip().casefold()
    rows = await session.execute(
        with_deleted(select(model.id, model.label, model.deleted_at))
    )
    for other_id, other_label, deleted_at in rows.all():
        if other_id == exclude_id or other_label.strip().casefold() != wanted:
            continue
        if deleted_at is not None:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"{what} „{other_label}“ liegt im Papierkorb – "
                    "dort wiederherstellen"
                ),
            )
        raise HTTPException(status_code=409, detail=f"{what} existiert bereits")
