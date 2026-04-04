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

MIN_CONFIDENCE = 30


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

        data = _run_tesseract(binary)

        for i in range(len(data["text"])):
            conf = float(data["conf"][i])
            text = data["text"][i].strip()
            if conf < MIN_CONFIDENCE or not text:
                continue

            x = int(data["left"][i])
            y = int(data["top"][i])
            w = int(data["width"][i])
            h = int(data["height"][i])

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


def _run_tesseract(binary: np.ndarray) -> dict:
    """Run Tesseract on the full image and return word-level data."""
    inverted = cv2.bitwise_not(binary)
    result: dict = pytesseract.image_to_data(
        inverted, lang="deu", config="--psm 6", output_type=Output.DICT
    )
    return result
