"""ScanPart Pydantic schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, field_validator


class ScanPartCreate(BaseModel):
    part_name: str
    part_order: int = 0
    clef_hint: str | None = None

    @field_validator("part_name")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Darf nicht leer sein")
        return v.strip()

    @field_validator("clef_hint")
    @classmethod
    def valid_clef(cls, v: str | None) -> str | None:
        if v is not None and v not in ("treble", "bass"):
            raise ValueError("Muss 'treble' oder 'bass' sein")
        return v


class ScanPartUpdate(BaseModel):
    part_name: str | None = None
    part_order: int | None = None
    clef_hint: str | None = None


class ScanPartRead(BaseModel):
    id: int
    project_id: int
    part_name: str
    part_order: int
    clef_hint: str | None
    created_at: datetime
    scan_count: int = 0
    completed_count: int = 0

    model_config = {"from_attributes": True}
