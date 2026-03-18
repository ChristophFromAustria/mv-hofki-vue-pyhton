"""InstrumentInvoice ORM model."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, Float, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mv_hofki.db.base import Base

if TYPE_CHECKING:
    from mv_hofki.models.currency import Currency
    from mv_hofki.models.instrument import Instrument


class InstrumentInvoice(Base):
    __tablename__ = "instrument_invoices"

    id: Mapped[int] = mapped_column(primary_key=True)
    instrument_id: Mapped[int] = mapped_column(
        ForeignKey("instruments.id"), nullable=False
    )
    amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency_id: Mapped[int] = mapped_column(
        ForeignKey("currencies.id"), nullable=False
    )
    date_issued: Mapped[date | None] = mapped_column(Date, nullable=True)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    invoice_nr: Mapped[str | None] = mapped_column(String(100), nullable=True)
    invoice_issuer: Mapped[str | None] = mapped_column(String(100), nullable=True)
    issuer_address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    instrument: Mapped[Instrument] = relationship(lazy="joined")
    currency: Mapped[Currency] = relationship(lazy="joined")
