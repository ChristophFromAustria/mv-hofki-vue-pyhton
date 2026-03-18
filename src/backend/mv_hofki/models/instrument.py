"""Instrument ORM model."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mv_hofki.db.base import Base

if TYPE_CHECKING:
    from mv_hofki.models.currency import Currency
    from mv_hofki.models.instrument_type import InstrumentType


class Instrument(Base):
    __tablename__ = "instruments"

    id: Mapped[int] = mapped_column(primary_key=True)
    inventory_nr: Mapped[int] = mapped_column(Integer, nullable=False)
    label_addition: Mapped[str | None] = mapped_column(String(100))
    manufacturer: Mapped[str | None] = mapped_column(String(100))
    serial_nr: Mapped[str | None] = mapped_column(String(100))
    construction_year: Mapped[date | None] = mapped_column(Date)
    acquisition_date: Mapped[date | None] = mapped_column(Date)
    acquisition_cost: Mapped[float | None] = mapped_column(Float)
    currency_id: Mapped[int] = mapped_column(
        ForeignKey("currencies.id"), nullable=False
    )
    distributor: Mapped[str | None] = mapped_column(String(100))
    container: Mapped[str | None] = mapped_column(String(100))
    particularities: Mapped[str | None] = mapped_column(String(100))
    owner: Mapped[str] = mapped_column(String(100), nullable=False)
    notes: Mapped[str | None] = mapped_column(String(100))
    instrument_type_id: Mapped[int] = mapped_column(
        ForeignKey("instrument_types.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    instrument_type: Mapped[InstrumentType] = relationship(lazy="joined")
    currency: Mapped[Currency] = relationship(lazy="joined")
