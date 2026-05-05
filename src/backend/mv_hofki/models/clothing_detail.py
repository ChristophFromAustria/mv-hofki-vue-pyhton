"""ClothingDetail ORM model."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mv_hofki.db.base import Base

if TYPE_CHECKING:
    from mv_hofki.models.clothing_type import ClothingType


class ClothingDetail(Base):
    __tablename__ = "clothing_details"

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(
        ForeignKey("inventory_items.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    clothing_type_id: Mapped[int] = mapped_column(
        ForeignKey("clothing_types.id"), nullable=False
    )
    size: Mapped[str | None] = mapped_column(String(20))
    gender: Mapped[str | None] = mapped_column(String(10))

    clothing_type: Mapped[ClothingType] = relationship(lazy="joined")
