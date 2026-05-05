"""ScanProject ORM model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mv_hofki.db.base import Base

if TYPE_CHECKING:
    from mv_hofki.models.scan_part import ScanPart


class ScanProject(Base):
    __tablename__ = "scan_projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    composer: Mapped[str | None] = mapped_column(String(200))
    category: Mapped[str | None] = mapped_column(String(100))
    catalog_number: Mapped[int | None] = mapped_column()
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )

    parts: Mapped[list[ScanPart]] = relationship(
        back_populates="project", cascade="all, delete-orphan", lazy="selectin"
    )
