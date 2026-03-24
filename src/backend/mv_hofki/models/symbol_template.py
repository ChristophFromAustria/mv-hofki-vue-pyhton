"""SymbolTemplate ORM model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mv_hofki.db.base import Base

if TYPE_CHECKING:
    from mv_hofki.models.symbol_variant import SymbolVariant


class SymbolTemplate(Base):
    __tablename__ = "symbol_templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    musicxml_element: Mapped[str | None] = mapped_column(Text)
    lilypond_token: Mapped[str | None] = mapped_column(String(50))
    is_seed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    variants: Mapped[list[SymbolVariant]] = relationship(
        back_populates="template", cascade="all, delete-orphan", lazy="selectin"
    )
