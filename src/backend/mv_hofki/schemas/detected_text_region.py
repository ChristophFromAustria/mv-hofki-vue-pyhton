"""DetectedTextRegion Pydantic schemas."""

from __future__ import annotations

from pydantic import BaseModel


class DetectedTextRegionRead(BaseModel):
    id: int
    scan_id: int
    staff_index: int
    x: int
    y: int
    width: int
    height: int
    text: str | None
    confidence: float | None

    model_config = {"from_attributes": True}
