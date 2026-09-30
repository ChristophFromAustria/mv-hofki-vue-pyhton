"""Inventory numbers that were given out once and must never be given again."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from mv_hofki.db.base import Base


class RetiredInventoryNumber(Base):
    """A number freed by deleting or renumbering an item. New numbers of the
    same sequence (category + prefix) skip it, so a printed label never points
    at a different item."""

    __tablename__ = "retired_inventory_numbers"

    category: Mapped[str] = mapped_column(String(20), primary_key=True)
    number_prefix: Mapped[str] = mapped_column(String(10), primary_key=True)
    inventory_nr: Mapped[int] = mapped_column(Integer, primary_key=True)
    retired_at: Mapped[datetime] = mapped_column(server_default=func.now())
