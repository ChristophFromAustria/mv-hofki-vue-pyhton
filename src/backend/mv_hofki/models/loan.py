"""Loan ORM model."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mv_hofki.db.base import Base

if TYPE_CHECKING:
    from mv_hofki.models.inventory_item import InventoryItem
    from mv_hofki.models.musician import Musician


class Loan(Base):
    __tablename__ = "loan_register"

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(
        ForeignKey("inventory_items.id", ondelete="CASCADE"), nullable=False
    )
    musician_id: Mapped[int] = mapped_column(ForeignKey("musicians.id"), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    item: Mapped[InventoryItem] = relationship(lazy="joined")
    musician: Mapped[Musician] = relationship(lazy="joined")
