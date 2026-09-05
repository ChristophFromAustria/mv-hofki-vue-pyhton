"""SymbolVariant Pydantic schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class SymbolVariantRead(BaseModel):
    id: int
    template_id: int
    image_path: str
    source: str
    usage_count: int
    height_in_lines: float | None
    source_line_spacing: float
    anchor_dx: float | None = None
    anchor_dy: float | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class VariantAnchorUpdate(BaseModel):
    """Manual anchor correction in image pixels; None resets to default."""

    anchor_dx: float | None = None
    anchor_dy: float | None = None
