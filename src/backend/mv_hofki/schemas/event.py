"""Event log schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, field_serializer


class EventRead(BaseModel):
    id: int
    at: datetime
    actor: str | None
    source: str
    entity_type: str
    entity_id: int | None
    entity_label: str
    action: str
    changes: list[dict[str, Any]] | None = None
    summary: str | None = None
    item_id: int | None = None
    musician_id: int | None = None

    model_config = {"from_attributes": True}

    @field_serializer("at")
    def _utc(self, value: datetime) -> str:
        # Stored as naive UTC (SQLite CURRENT_TIMESTAMP); say so explicitly.
        return value.isoformat() + ("Z" if value.tzinfo is None else "")
