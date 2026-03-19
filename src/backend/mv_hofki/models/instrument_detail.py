"""InstrumentDetail ORM model."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mv_hofki.db.base import Base

if TYPE_CHECKING:
    from mv_hofki.models.instrument_type import InstrumentType


class InstrumentDetail(Base):
    __tablename__ = "instrument_details"

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(
        ForeignKey("inventory_items.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    instrument_type_id: Mapped[int] = mapped_column(
        ForeignKey("instrument_types.id"), nullable=False
    )
    label_addition: Mapped[str | None] = mapped_column(String(100))
    serial_nr: Mapped[str | None] = mapped_column(String(100))
    construction_year: Mapped[int | None] = mapped_column(Integer)
    distributor: Mapped[str | None] = mapped_column(String(100))
    container: Mapped[str | None] = mapped_column(String(100))
    particularities: Mapped[str | None] = mapped_column(String(500))

    instrument_type: Mapped[InstrumentType] = relationship(lazy="joined")
