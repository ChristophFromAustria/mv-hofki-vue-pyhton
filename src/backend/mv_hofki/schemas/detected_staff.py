"""DetectedStaff Pydantic schemas."""

from __future__ import annotations

from pydantic import BaseModel


class DetectedStaffRead(BaseModel):
    id: int
    scan_id: int
    staff_index: int
    y_top: int
    y_bottom: int
    line_positions_json: str
    line_spacing: float
    line_thickness: int | None
    clef: str | None
    key_signature: str | None
    time_signature: str | None
    symbol_count: int = 0
    verified_count: int = 0

    model_config = {"from_attributes": True}


class DetectedStaffUpdate(BaseModel):
    clef: str | None = None
    key_signature: str | None = None
    time_signature: str | None = None
