"""Register Pydantic schemas."""

from __future__ import annotations

from pydantic import BaseModel, field_validator


class RegisterCreate(BaseModel):
    label: str
    sort_order: int = 0
    expects_instrument: bool = True

    @field_validator("label")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Darf nicht leer sein")
        return v.strip()


class RegisterUpdate(BaseModel):
    label: str | None = None
    sort_order: int | None = None
    expects_instrument: bool | None = None


class RegisterRead(BaseModel):
    id: int
    label: str
    sort_order: int
    expects_instrument: bool

    model_config = {"from_attributes": True}


class RegisterRef(BaseModel):
    id: int
    label: str

    model_config = {"from_attributes": True}
