"""GeneralItemDetail ORM model."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mv_hofki.db.base import Base

if TYPE_CHECKING:
    from mv_hofki.models.general_item_type import GeneralItemType


class GeneralItemDetail(Base):
    __tablename__ = "general_item_details"

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(
        ForeignKey("inventory_items.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    general_item_type_id: Mapped[int] = mapped_column(
        ForeignKey("general_item_types.id"), nullable=False
    )

    general_item_type: Mapped[GeneralItemType] = relationship(lazy="joined")
