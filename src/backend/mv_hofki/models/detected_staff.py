"""DetectedStaff ORM model."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mv_hofki.db.base import Base

if TYPE_CHECKING:
    from mv_hofki.models.detected_symbol import DetectedSymbol
    from mv_hofki.models.sheet_music_scan import SheetMusicScan


class DetectedStaff(Base):
    __tablename__ = "detected_staves"

    id: Mapped[int] = mapped_column(primary_key=True)
    scan_id: Mapped[int] = mapped_column(
        ForeignKey("sheet_music_scans.id", ondelete="CASCADE"), nullable=False
    )
    staff_index: Mapped[int] = mapped_column(Integer, nullable=False)
    y_top: Mapped[int] = mapped_column(Integer, nullable=False)
    y_bottom: Mapped[int] = mapped_column(Integer, nullable=False)
    line_positions_json: Mapped[str] = mapped_column(Text, nullable=False)
    line_spacing: Mapped[float] = mapped_column(Float, nullable=False)
    clef: Mapped[str | None] = mapped_column(String(20))
    key_signature: Mapped[str | None] = mapped_column(String(50))
    time_signature: Mapped[str | None] = mapped_column(String(20))

    scan: Mapped[SheetMusicScan] = relationship(back_populates="staves")
    symbols: Mapped[list[DetectedSymbol]] = relationship(
        back_populates="staff", cascade="all, delete-orphan", lazy="selectin"
    )
