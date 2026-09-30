"""SheetMusicGenre lookup ORM model."""

from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from mv_hofki.db.base import Base
from mv_hofki.db.soft_delete import SoftDeleteMixin


class SheetMusicGenre(SoftDeleteMixin, Base):
    __tablename__ = "sheet_music_genres"

    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
