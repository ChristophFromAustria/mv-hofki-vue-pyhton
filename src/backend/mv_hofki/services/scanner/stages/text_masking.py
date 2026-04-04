"""Text masking: detect and remove text regions via Tesseract OCR."""

from __future__ import annotations

import cv2
import numpy as np
import pytesseract  # type: ignore[import-not-found]
from pytesseract import Output  # type: ignore[import-not-found]

from mv_hofki.services.scanner.stages.base import (
    PipelineContext,
    ProcessingStage,
    TextRegionData,
)


class TextMaskingStage(ProcessingStage):
    """Detect text regions via Tesseract and mask them in the binary image."""

    name = "text_masking"

    def process(self, ctx: PipelineContext) -> PipelineContext:
        binary = ctx.processed_image
        if binary is None:
            return ctx

        staves = sorted(ctx.staves, key=lambda s: s.staff_index)
        staff_centers = [
            (s.staff_index, float(np.mean(s.line_positions))) for s in staves
        ]

        # Build staff line ranges for overlap filtering
        staff_line_ranges = [
            (min(s.line_positions), max(s.line_positions)) for s in staves
        ]

        min_confidence = ctx.config.get("text_masking_min_confidence", 30)

        data = _run_tesseract(binary)

        for i in range(len(data["text"])):
            conf = float(data["conf"][i])
            text = data["text"][i].strip()
            if conf < min_confidence or not text:
                continue

            x = int(data["left"][i])
            y = int(data["top"][i])
            w = int(data["width"][i])
            h = int(data["height"][i])

            # Skip regions overlapping with staff lines
            region_top = y
            region_bottom = y + h
            if _overlaps_staff_lines(region_top, region_bottom, staff_line_ranges):
                continue

            # Assign to nearest staff
            center_y = y + h / 2
            staff_idx = min(staff_centers, key=lambda sc: abs(sc[1] - center_y))[0]

            ctx.text_regions.append(
                TextRegionData(
                    staff_index=staff_idx,
                    x=x,
                    y=y,
                    width=w,
                    height=h,
                    text=text,
                    confidence=conf,
                )
            )

        # Mask detected text regions in the binary image
        for region in ctx.text_regions:
            binary[
                region.y : region.y + region.height,
                region.x : region.x + region.width,
            ] = 255

        ctx.log(
            f"Text-Maskierung: {len(ctx.text_regions)} Textregionen "
            f"in {len(staves)} Systemen erkannt"
        )
        return ctx

    def validate(self, ctx: PipelineContext) -> bool:
        return ctx.processed_image is not None and len(ctx.staves) > 0


def _overlaps_staff_lines(
    region_top: int,
    region_bottom: int,
    staff_line_ranges: list[tuple[int, int]],
) -> bool:
    """Check if a region's Y range overlaps with any staff's line area."""
    for line_top, line_bottom in staff_line_ranges:
        if region_top < line_bottom and region_bottom > line_top:
            return True
    return False


def _run_tesseract(binary: np.ndarray) -> dict:
    """Run Tesseract on the full image and return word-level data."""
    inverted = cv2.bitwise_not(binary)
    result: dict = pytesseract.image_to_data(
        inverted, lang="deu", config="--psm 6", output_type=Output.DICT
    )
    return result
