"""DetectedSymbol ORM model."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mv_hofki.db.base import Base

if TYPE_CHECKING:
    from mv_hofki.models.detected_staff import DetectedStaff
    from mv_hofki.models.symbol_template import SymbolTemplate


class DetectedSymbol(Base):
    __tablename__ = "detected_symbols"

    id: Mapped[int] = mapped_column(primary_key=True)
    staff_id: Mapped[int] = mapped_column(
        ForeignKey("detected_staves.id", ondelete="CASCADE"), nullable=False
    )
    x: Mapped[int] = mapped_column(Integer, nullable=False)
    y: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    snippet_path: Mapped[str | None] = mapped_column(String(500))
    position_on_staff: Mapped[int | None] = mapped_column(Integer)
    sequence_order: Mapped[int] = mapped_column(Integer, nullable=False)
    matched_symbol_id: Mapped[int | None] = mapped_column(
        ForeignKey("symbol_templates.id", ondelete="SET NULL")
    )
    confidence: Mapped[float | None] = mapped_column(Float)
    user_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    user_corrected_symbol_id: Mapped[int | None] = mapped_column(
        ForeignKey("symbol_templates.id", ondelete="SET NULL")
    )
    alternatives_json: Mapped[str | None] = mapped_column(String(2000))
    filtered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    filter_reason: Mapped[str | None] = mapped_column(String(200))

    staff: Mapped[DetectedStaff] = relationship(back_populates="symbols")
    matched_symbol: Mapped[SymbolTemplate | None] = relationship(
        foreign_keys=[matched_symbol_id], lazy="joined"
    )
    corrected_symbol: Mapped[SymbolTemplate | None] = relationship(
        foreign_keys=[user_corrected_symbol_id], lazy="joined"
    )
