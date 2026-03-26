"""SheetMusicScan Pydantic schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class SheetMusicScanRead(BaseModel):
    id: int
    part_id: int
    page_number: int
    original_filename: str
    image_path: str
    processed_image_path: str | None
    corrected_image_path: str | None
    status: str
    adjustments_json: str | None
    pipeline_config_json: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SheetMusicScanUpdate(BaseModel):
    page_number: int | None = None
    adjustments_json: str | None = None
    pipeline_config_json: str | None = None


class ScanStatusRead(BaseModel):
    status: str
    current_stage: str | None = None
    progress: float | None = None
