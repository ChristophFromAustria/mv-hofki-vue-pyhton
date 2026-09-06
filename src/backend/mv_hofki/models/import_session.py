"""ImportSession ORM model: one KI-Import run from upload to import."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mv_hofki.db.base import Base

if TYPE_CHECKING:
    from mv_hofki.models.import_page import ImportPage

# uploaded  -> files added, nothing analysed yet
# analyzing -> extraction running
# review    -> extraction finished (at least one page), user is correcting
# importing -> import running (guards against double submission)
# imported  -> data written to the inventory
# error     -> every page failed / analysis aborted
IMPORT_SESSION_STATUSES = (
    "uploaded",
    "analyzing",
    "review",
    "importing",
    "imported",
    "error",
)


class ImportSession(Base):
    __tablename__ = "import_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="uploaded")
    model: Mapped[str | None] = mapped_column(String(100))
    archive_dir: Mapped[str | None] = mapped_column(String(500))
    draft_json: Mapped[str | None] = mapped_column(Text)
    import_result_json: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )

    pages: Mapped[list[ImportPage]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="ImportPage.page_index",
    )
