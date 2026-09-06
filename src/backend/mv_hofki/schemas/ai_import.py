"""Pydantic schemas for the KI-Import API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ImportSessionCreate(BaseModel):
    title: str | None = None


class ImportPageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    page_index: int
    source_name: str
    source_page: int
    image_url: str
    width: int
    height: int
    status: str
    extraction: dict[str, Any] | None = None
    error: str | None = None
    duration_seconds: float | None = None


class ImportSessionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str | None
    status: str
    model: str | None
    page_count: int
    created_at: datetime
    updated_at: datetime


class ImportSessionRead(ImportSessionSummary):
    error: str | None = None
    draft: dict[str, Any] | None = None
    import_result: dict[str, Any] | None = None
    pages: list[ImportPageRead] = Field(default_factory=list)


class ImportDraftUpdate(BaseModel):
    draft: dict[str, Any]
