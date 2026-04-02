"""DetectedMeasure ORM model."""

from __future__ import annotations

from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from mv_hofki.db.base import Base


class DetectedMeasure(Base):
    __tablename__ = "detected_measures"

    id: Mapped[int] = mapped_column(primary_key=True)
    scan_id: Mapped[int] = mapped_column(
        ForeignKey("sheet_music_scans.id", ondelete="CASCADE"), nullable=False
    )
    staff_id: Mapped[int] = mapped_column(
        ForeignKey("detected_staves.id", ondelete="CASCADE"), nullable=False
    )
    staff_index: Mapped[int] = mapped_column(Integer, nullable=False)
    measure_number_in_staff: Mapped[int] = mapped_column(Integer, nullable=False)
    global_measure_number: Mapped[int] = mapped_column(Integer, nullable=False)
    x_start: Mapped[int] = mapped_column(Integer, nullable=False)
    x_end: Mapped[int] = mapped_column(Integer, nullable=False)
