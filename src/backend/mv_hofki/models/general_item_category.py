"""GeneralItemCategory lookup ORM model and its item link table."""

from __future__ import annotations

from sqlalchemy import Column, ForeignKey, Integer, String, Table
from sqlalchemy.orm import Mapped, mapped_column

from mv_hofki.db.base import Base

# Many-to-many: a general item can carry several categories. SQLite runs without
# PRAGMA foreign_keys, so the services delete links explicitly.
general_item_category_links = Table(
    "general_item_category_links",
    Base.metadata,
    Column(
        "item_id",
        Integer,
        ForeignKey("inventory_items.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "category_id",
        Integer,
        ForeignKey("general_item_categories.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class GeneralItemCategory(Base):
    __tablename__ = "general_item_categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
