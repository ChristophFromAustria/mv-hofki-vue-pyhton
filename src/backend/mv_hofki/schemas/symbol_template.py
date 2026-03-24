"""SymbolTemplate Pydantic schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, field_validator


class SymbolTemplateCreate(BaseModel):
    category: str
    name: str
    display_name: str
    musicxml_element: str | None = None
    lilypond_token: str | None = None


class TemplateCaptureRequest(BaseModel):
    scan_id: int
    x: int
    y: int
    width: int
    height: int
    name: str
    category: str
    musicxml_element: str | None = None
    height_in_lines: float

    @field_validator("name")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Darf nicht leer sein")
        return v.strip()


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
