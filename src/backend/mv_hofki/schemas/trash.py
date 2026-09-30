"""Papierkorb schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, field_serializer


class TrashEntry(BaseModel):
    kind: str
    kind_label: str
    id: int
    label: str
    # The item an invoice or image belongs to.
    context: str | None = None
    deleted_at: datetime
    purge_at: datetime
    # E-mail, or "ki-import"/"system"; None = unknown.
    deleted_by: str | None = None

    @field_serializer("deleted_at", "purge_at")
    def _utc(self, value: datetime) -> str:
        return value.isoformat() + ("Z" if value.tzinfo is None else "")
