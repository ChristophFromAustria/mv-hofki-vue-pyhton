"""SheetMusicScan ORM model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mv_hofki.db.base import Base

if TYPE_CHECKING:
    from mv_hofki.models.detected_staff import DetectedStaff
    from mv_hofki.models.scan_part import ScanPart


class SheetMusicScan(Base):
    __tablename__ = "sheet_music_scans"

    id: Mapped[int] = mapped_column(primary_key=True)
    part_id: Mapped[int] = mapped_column(
        ForeignKey("scan_parts.id", ondelete="CASCADE"), nullable=False
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    image_path: Mapped[str] = mapped_column(String(500), nullable=False)
    processed_image_path: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="uploaded")
    adjustments_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )

    part: Mapped[ScanPart] = relationship(back_populates="scans")
    staves: Mapped[list[DetectedStaff]] = relationship(
        back_populates="scan", cascade="all, delete-orphan", lazy="selectin"
    )
