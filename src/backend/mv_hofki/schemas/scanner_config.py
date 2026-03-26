"""ScannerConfig Pydantic schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ScannerConfigRead(BaseModel):
    """Full scanner config — returned by GET."""

    confidence_threshold: float
    matching_method: str
    multi_scale_enabled: bool
    multi_scale_range: float
    multi_scale_steps: int
    edge_matching_enabled: bool
    canny_low: int
    canny_high: int
    staff_removal_before_matching: bool
    masked_matching_enabled: bool
    mask_threshold: int
    nms_iou_threshold: float
    nms_method: str
    adaptive_threshold_block_size: int
    adaptive_threshold_c: int
    morphology_kernel_size: int
    auto_verify_confidence: float

    model_config = {"from_attributes": True}


class ScannerConfigUpdate(BaseModel):
    """Partial update — all fields optional.

    Used for both save and per-request override.
    """

    confidence_threshold: float | None = Field(None, ge=0.0, le=1.0)
    matching_method: str | None = Field(
        None, pattern="^TM_(CCOEFF|CCORR|SQDIFF)_NORMED$"
    )
    multi_scale_enabled: bool | None = None
    multi_scale_range: float | None = Field(None, gt=0.0, le=0.5)
    multi_scale_steps: int | None = Field(None, ge=1, le=20)
    edge_matching_enabled: bool | None = None
    canny_low: int | None = Field(None, ge=0, le=500)
    canny_high: int | None = Field(None, ge=0, le=500)
    staff_removal_before_matching: bool | None = None
    masked_matching_enabled: bool | None = None
    mask_threshold: int | None = Field(None, ge=0, le=255)
    nms_iou_threshold: float | None = Field(None, ge=0.0, le=1.0)
    nms_method: str | None = Field(None, pattern="^(standard|dilate)$")
    adaptive_threshold_block_size: int | None = Field(None, ge=3, le=99)
    adaptive_threshold_c: int | None = Field(None, ge=0, le=50)
    morphology_kernel_size: int | None = Field(None, ge=1, le=10)
    auto_verify_confidence: float | None = Field(None, ge=0.0, le=1.0)
