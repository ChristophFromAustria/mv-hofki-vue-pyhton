"""ScanPart ORM model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mv_hofki.db.base import Base

if TYPE_CHECKING:
    from mv_hofki.models.scan_project import ScanProject
    from mv_hofki.models.sheet_music_scan import SheetMusicScan


class ScanPart(Base):
    __tablename__ = "scan_parts"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("scan_projects.id", ondelete="CASCADE"), nullable=False
    )
    part_name: Mapped[str] = mapped_column(String(200), nullable=False)
    part_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    clef_hint: Mapped[str | None] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    project: Mapped[ScanProject] = relationship(back_populates="parts")
    scans: Mapped[list[SheetMusicScan]] = relationship(
        back_populates="part", cascade="all, delete-orphan", lazy="selectin"
    )
