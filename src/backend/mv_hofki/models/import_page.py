"""ImportPage ORM model: one rendered page of an import session."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mv_hofki.db.base import Base

if TYPE_CHECKING:
    from mv_hofki.models.import_session import ImportSession

# uploaded -> analyzing -> done | error
IMPORT_PAGE_STATUSES = ("uploaded", "analyzing", "done", "error")


class ImportPage(Base):
    __tablename__ = "import_pages"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("import_sessions.id", ondelete="CASCADE"), nullable=False
    )
    page_index: Mapped[int] = mapped_column(Integer, nullable=False)  # within session
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_page: Mapped[int] = mapped_column(Integer, nullable=False)  # within file
    image_path: Mapped[str] = mapped_column(String(500), nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="uploaded")
    raw_json: Mapped[str | None] = mapped_column(Text)  # model output as returned
    extraction_json: Mapped[str | None] = mapped_column(Text)  # validated, px boxes
    error: Mapped[str | None] = mapped_column(Text)
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    session: Mapped[ImportSession] = relationship(back_populates="pages")
