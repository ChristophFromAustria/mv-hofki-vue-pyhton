"""Musician ORM model."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mv_hofki.db.base import Base
from mv_hofki.db.soft_delete import SoftDeleteMixin
from mv_hofki.models.register import Register, musician_registers


class Musician(SoftDeleteMixin, Base):
    __tablename__ = "musicians"
    # Never reuse the id of a musician deleted for good (event history).
    __table_args__ = {"sqlite_autoincrement": True}

    id: Mapped[int] = mapped_column(primary_key=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(100))
    email: Mapped[str | None] = mapped_column(String(100))
    street_address: Mapped[str | None] = mapped_column(String(100))
    postal_code: Mapped[int | None] = mapped_column(Integer)
    city: Mapped[str | None] = mapped_column(String(100))
    is_extern: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    registers: Mapped[list[Register]] = relationship(
        secondary=musician_registers, lazy="selectin", order_by=Register.sort_order
    )
