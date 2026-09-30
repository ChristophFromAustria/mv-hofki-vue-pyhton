"""Musician Pydantic schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from mv_hofki.schemas.pagination import Grouped
from mv_hofki.schemas.register import RegisterRef


class MusicianCreate(BaseModel):
    first_name: str
    last_name: str
    phone: str | None = None
    email: str | None = None
    street_address: str | None = None
    postal_code: int | None = None
    city: str | None = None
    is_extern: bool = False
    is_active: bool = True
    notes: str | None = Field(None, max_length=10_000)
    register_ids: list[int] = []

    @field_validator("first_name", "last_name")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Darf nicht leer sein")
        return v.strip()


class MusicianUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    email: str | None = None
    street_address: str | None = None
    postal_code: int | None = None
    city: str | None = None
    is_extern: bool | None = None
    is_active: bool | None = None
    notes: str | None = Field(None, max_length=10_000)
    register_ids: list[int] | None = None

    @field_validator("first_name", "last_name")
    @classmethod
    def not_empty(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("Darf nicht leer sein")
        return v.strip() if v else v


class MusicianRead(BaseModel):
    id: int
    first_name: str
    last_name: str
    phone: str | None
    email: str | None
    street_address: str | None
    postal_code: int | None
    city: str | None
    is_extern: bool
    is_active: bool
    notes: str | None
    registers: list[RegisterRef] = []
    created_at: datetime
    # Set while the musician is in the trash (seen in loans of their history).
    deleted_at: datetime | None = None

    model_config = {"from_attributes": True}


class MusicianListRow(MusicianRead, Grouped):
    pass
