"""ClothingType lookup ORM model."""

from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from mv_hofki.db.base import Base


class ClothingType(Base):
    __tablename__ = "clothing_types"

    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
