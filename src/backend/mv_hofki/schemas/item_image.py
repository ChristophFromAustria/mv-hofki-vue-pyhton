"""ItemImage Pydantic schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ItemImageRead(BaseModel):
    id: int
    item_id: int
    filename: str
    is_profile: bool
    created_at: datetime
    url: str

    model_config = {"from_attributes": True}
