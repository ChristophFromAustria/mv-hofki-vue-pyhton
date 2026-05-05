"""SheetMusicDetail ORM model."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mv_hofki.db.base import Base

if TYPE_CHECKING:
    from mv_hofki.models.sheet_music_genre import SheetMusicGenre


class SheetMusicDetail(Base):
    __tablename__ = "sheet_music_details"

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(
        ForeignKey("inventory_items.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    composer: Mapped[str | None] = mapped_column(String(100))
    arranger: Mapped[str | None] = mapped_column(String(100))
    difficulty: Mapped[str | None] = mapped_column(String(50))
    genre_id: Mapped[int | None] = mapped_column(
        ForeignKey("sheet_music_genres.id"), nullable=True
    )

    genre: Mapped[SheetMusicGenre | None] = relationship(lazy="joined")
