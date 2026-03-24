"""SymbolTemplate Pydantic schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class SymbolTemplateCreate(BaseModel):
    category: str
    name: str
    display_name: str
    musicxml_element: str | None = None
    lilypond_token: str | None = None


class SymbolTemplateRead(BaseModel):
    id: int
    category: str
    name: str
    display_name: str
    musicxml_element: str | None
    lilypond_token: str | None
    is_seed: bool
    created_at: datetime
    variant_count: int = 0

    model_config = {"from_attributes": True}
