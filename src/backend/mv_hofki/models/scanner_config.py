"""ScannerConfig ORM model — single-row global pipeline settings."""

from __future__ import annotations

from sqlalchemy import Boolean, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from mv_hofki.db.base import Base


class ScannerConfig(Base):
    __tablename__ = "scanner_config"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Template matching
    confidence_threshold: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.6
    )
    matching_method: Mapped[str] = mapped_column(
        String(30), nullable=False, default="TM_CCOEFF_NORMED"
    )

    # Multi-scale search
    multi_scale_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    multi_scale_range: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.05
    )
    multi_scale_steps: Mapped[int] = mapped_column(Integer, nullable=False, default=3)

    # Edge-based matching
    edge_matching_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    canny_low: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    canny_high: Mapped[int] = mapped_column(Integer, nullable=False, default=150)

    # Staff removal before matching
    staff_removal_before_matching: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    staff_removal_thickness_pct: Mapped[int] = mapped_column(
        Integer, nullable=False, default=100
    )
    staff_removal_symbol_padding: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )

    # Masked template matching
    masked_matching_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    mask_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=200)

    # NMS settings
    nms_iou_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.3)
    nms_method: Mapped[str] = mapped_column(
        String(20), nullable=False, default="standard"
    )

    # Preprocessing
    adaptive_threshold_block_size: Mapped[int] = mapped_column(
        Integer, nullable=False, default=15
    )
    adaptive_threshold_c: Mapped[int] = mapped_column(
        Integer, nullable=False, default=10
    )
    morphology_kernel_size: Mapped[int] = mapped_column(
        Integer, nullable=False, default=2
    )

    # Dewarp (bent staff line correction)
    dewarp_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    dewarp_smoothing: Mapped[int] = mapped_column(Integer, nullable=False, default=50)

    # Deskew
    deskew_method: Mapped[str] = mapped_column(
        String(20), nullable=False, default="projection"
    )

    # Auto-verify
    auto_verify_confidence: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.85
    )
