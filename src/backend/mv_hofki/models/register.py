"""Register (section of the band) and the musician membership table."""

from __future__ import annotations

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Table
from sqlalchemy.orm import Mapped, mapped_column

from mv_hofki.db.base import Base

musician_registers = Table(
    "musician_registers",
    Base.metadata,
    Column(
        "musician_id",
        ForeignKey("musicians.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "register_id",
        ForeignKey("registers.id", ondelete="RESTRICT"),
        primary_key=True,
    ),
)


class Register(Base):
    __tablename__ = "registers"

    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Members of this register normally play a club instrument (not so for
    # percussion, Marketenderinnen, conductor).
    expects_instrument: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
