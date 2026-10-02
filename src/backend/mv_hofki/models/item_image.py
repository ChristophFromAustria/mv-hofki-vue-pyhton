"""ItemImage ORM model."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from mv_hofki.db.base import Base
from mv_hofki.db.soft_delete import SoftDeleteMixin


class ItemImage(SoftDeleteMixin, Base):
    __tablename__ = "item_images"

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(
        ForeignKey("inventory_items.id", ondelete="CASCADE"), nullable=False
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    is_profile: Mapped[bool] = mapped_column(Boolean, default=False)
    # "foto" = picture of the instrument, "scan" = scanned paperwork page
    kind: Mapped[str] = mapped_column(
        String(20), nullable=False, default="foto", server_default="foto"
    )
    caption: Mapped[str | None] = mapped_column(String(300))
    # Set once the image is edited: the untouched upload, kept for restoring.
    original_filename: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
