"""SymbolTemplate Pydantic schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, field_validator, model_validator


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


class TemplateCaptureRequest(BaseModel):
    scan_id: int
    x: int
    y: int
    width: int
    height: int
    template_id: int | None = None
    name: str | None = None
    category: str
    musicxml_element: str | None = None
    height_in_lines: float

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str | None) -> str | None:
        if v is not None:
            v = v.strip()
            if not v:
                return None
        return v

    @model_validator(mode="after")
    def require_name_or_template_id(self) -> TemplateCaptureRequest:
        if self.template_id is None and not self.name:
            raise ValueError("Entweder template_id oder name muss angegeben werden")
        return self


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
