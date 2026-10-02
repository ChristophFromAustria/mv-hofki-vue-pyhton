"""ItemImage Pydantic schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ItemImageRead(BaseModel):
    id: int
    item_id: int
    filename: str
    is_profile: bool
    kind: str
    caption: str | None
    created_at: datetime
    url: str
    # Edited: the original can be restored.
    has_original: bool = False

    model_config = {"from_attributes": True}
