"""DetectedMeasure Pydantic schemas."""

from __future__ import annotations

from pydantic import BaseModel


class DetectedMeasureRead(BaseModel):
    id: int
    scan_id: int
    staff_id: int
    staff_index: int
    measure_number_in_staff: int
    global_measure_number: int
    x_start: int
    x_end: int
    end_barline: str | None

    model_config = {"from_attributes": True}
