"""Text masking: detect and remove text regions via EasyOCR."""

from __future__ import annotations

import numpy as np

from mv_hofki.services.scanner.stages.base import (
    PipelineContext,
    ProcessingStage,
    TextRegionData,
)


class TextMaskingStage(ProcessingStage):
    """Detect text regions via EasyOCR and mask them in the binary image."""

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
        # EasyOCR uses 0-1 confidence, config is 0-100
        min_conf_normalized = min_confidence / 100.0

        results = _run_easyocr(binary)

        for bbox, text, conf in results:
            text = text.strip()
            if conf < min_conf_normalized or not text:
                continue

            # EasyOCR returns bbox as [[x1,y1],[x2,y1],[x2,y2],[x1,y2]]
            xs = [int(p[0]) for p in bbox]
            ys = [int(p[1]) for p in bbox]
            x = min(xs)
            y = min(ys)
            w = max(xs) - x
            h = max(ys) - y

            # Skip regions overlapping with staff lines (except "Trio")
            if _overlaps_staff_lines(y, y + h, staff_line_ranges):
                if text.lower() != "trio":
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
                    confidence=round(conf * 100, 1),
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


# Lazy-initialized EasyOCR reader (model loading is expensive)
_reader = None


def _get_reader():  # type: ignore[no-untyped-def]
    """Get or create the EasyOCR reader singleton."""
    global _reader  # noqa: PLW0603
    if _reader is None:
        import easyocr  # type: ignore[import-not-found]

        _reader = easyocr.Reader(["de", "en"], gpu=False)
    return _reader


def _run_easyocr(binary: np.ndarray) -> list:  # type: ignore[type-arg]
    """Run EasyOCR on the full image and return detections.

    Each result is (bbox, text, confidence) where bbox is
    [[x1,y1],[x2,y1],[x2,y2],[x1,y2]].
    """
    reader = _get_reader()
    result: list = reader.readtext(binary)
    return result
