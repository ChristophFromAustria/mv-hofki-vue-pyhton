"""SymbolTemplate Pydantic schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SymbolTemplateCreate(BaseModel):
    category: str
    name: str
    display_name: str
    musicxml_element: str | None = None
    lilypond_token: str | None = None


class SymbolTemplateUpdate(BaseModel):
    display_name: str | None = None
    musicxml_element: str | None = None
    lilypond_token: str | None = None
    # Matching parameters; None resets to the global scanner config value.
    min_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    confidence_weight: float | None = Field(default=None, gt=0.0, le=2.0)
    merge_overlapping: bool | None = None


class VariantCropRequest(BaseModel):
    x: int
    y: int
    width: int
    height: int


class SymbolTemplateRead(BaseModel):
    id: int
    category: str
    name: str
    display_name: str
    musicxml_element: str | None
    lilypond_token: str | None
    is_seed: bool
    min_confidence: float | None = None
    confidence_weight: float | None = None
    merge_overlapping: bool = False
    created_at: datetime
    variant_count: int = 0

    model_config = {"from_attributes": True}
