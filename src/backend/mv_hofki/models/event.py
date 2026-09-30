"""Event log: one row per change (docs/konzept-papierkorb-protokoll.md)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from mv_hofki.db.base import Base


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        Index("ix_events_item_id", "item_id"),
        Index("ix_events_musician_id", "musician_id"),
        Index("ix_events_at", "at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # UTC, like every server_default=func.now() in this schema.
    at: Mapped[datetime] = mapped_column(server_default=func.now())
    # Cloudflare Access e-mail; None when unknown (no tunnel, CLI).
    actor: Mapped[str | None] = mapped_column(String(200))
    # web | ki-import | import | system
    source: Mapped[str] = mapped_column(String(20), default="web")
    # item | musician | loan | invoice | image | instrument_type | ...
    entity_type: Mapped[str] = mapped_column(String(30))
    entity_id: Mapped[int | None] = mapped_column(Integer)
    # Label at the time of the event ("TR-0006 Trompete"), kept when it changes.
    entity_label: Mapped[str] = mapped_column(String(300))
    # created | updated | deleted | loaned | returned | ...
    action: Mapped[str] = mapped_column(String(30))
    # [{"field", "label", "old", "new"}] for updates, else None.
    changes: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)
    # Free text for events that are not about one row (e.g. an import).
    summary: Mapped[str | None] = mapped_column(String(300))
    # The item / musician the event concerns, for their history.
    item_id: Mapped[int | None] = mapped_column(Integer)
    musician_id: Mapped[int | None] = mapped_column(Integer)
