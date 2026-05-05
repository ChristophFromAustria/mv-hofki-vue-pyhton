"""SheetMusicGenre Pydantic schemas."""

from __future__ import annotations

from pydantic import BaseModel


class SheetMusicGenreCreate(BaseModel):
    label: str


class SheetMusicGenreUpdate(BaseModel):
    label: str | None = None


class SheetMusicGenreRead(BaseModel):
    id: int
    label: str

    model_config = {"from_attributes": True}
