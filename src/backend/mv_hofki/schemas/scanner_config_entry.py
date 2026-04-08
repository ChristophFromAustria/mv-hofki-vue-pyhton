"""Pydantic schemas for scanner config entries."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ConfigEntryRead(BaseModel):
    key: str
    value: int | float | bool | str
    default_value: int | float | bool | str
    is_modified: bool
    type: str
    label: str
    group_path: str | None
    min: float | None
    max: float | None
    step: float | None
    options: list[dict[str, str]] | None
    sort_order: int


class ConfigResponse(BaseModel):
    entries: list[ConfigEntryRead]


class ConfigUpdate(BaseModel):
    values: dict[str, Any]


class ConfigReset(BaseModel):
    keys: list[str] = []
