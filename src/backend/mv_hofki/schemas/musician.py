"""Musician Pydantic schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, field_validator


class MusicianCreate(BaseModel):
    first_name: str
    last_name: str
    phone: str | None = None
    email: str | None = None
    street_address: str | None = None
    postal_code: int | None = None
    city: str | None = None
    is_extern: bool = False
    notes: str | None = None

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
    notes: str | None = None

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
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
