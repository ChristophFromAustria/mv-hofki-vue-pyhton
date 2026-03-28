"""ScanProject Pydantic schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, field_validator


class ScanProjectCreate(BaseModel):
    name: str
    composer: str | None = None
    notes: str | None = None

    @field_validator("name")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Darf nicht leer sein")
        return v.strip()


class ScanProjectUpdate(BaseModel):
    name: str | None = None
    composer: str | None = None
    notes: str | None = None

    @field_validator("name")
    @classmethod
    def not_empty(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("Darf nicht leer sein")
        return v.strip() if v else v


class ScanProjectRead(BaseModel):
    id: int
    name: str
    composer: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
    part_count: int = 0
    scan_count: int = 0
    status_uploaded: int = 0
    status_review: int = 0
    status_processing: int = 0

    model_config = {"from_attributes": True}
