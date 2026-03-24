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
    created_at: datetime

    model_config = {"from_attributes": True}
