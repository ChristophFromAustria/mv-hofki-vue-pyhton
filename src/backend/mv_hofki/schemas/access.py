"""Schemas for Cloudflare Access email management."""

from __future__ import annotations

import re

from pydantic import BaseModel, field_validator


class EmailList(BaseModel):
    emails: list[str]


class EmailAdd(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", v):
            msg = "Ungültige E-Mail-Adresse"
            raise ValueError(msg)
        return v
