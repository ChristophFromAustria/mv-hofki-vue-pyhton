"""Template matching stage: sliding window with cv2.matchTemplate."""

from __future__ import annotations

import cv2
import numpy as np

from mv_hofki.services.scanner.stages.base import (
    PipelineContext,
    ProcessingStage,
    SymbolData,
)


class TemplateMatchingStage(ProcessingStage):
    """Find symbols using scaled template matching across each staff region."""

    name = "template_matching"

    def __init__(
        self,
        variant_images: list[np.ndarray],
        variant_template_ids: list[int],
        variant_heights: list[float],
        confidence_threshold: float = 0.6,
    ) -> None:
        self._variant_images = variant_images
        self._variant_template_ids = variant_template_ids
        self._variant_heights = variant_heights
        self._confidence_threshold = confidence_threshold

    def process(self, ctx: PipelineContext) -> PipelineContext:
        assert ctx.image is not None
        img = ctx.image
        if len(img.shape) == 3:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        for staff in ctx.staves:
            region = img[staff.y_top : staff.y_bottom, :]

            for i, tmpl_img in enumerate(self._variant_images):
                template_id = self._variant_template_ids[i]
                height_in_lines = self._variant_heights[i]

                scaled = self._scale_template(
                    tmpl_img, height_in_lines, staff.line_spacing
                )
                if scaled is None:
                    continue

                # Skip if template is larger than the region
                if (
                    scaled.shape[0] > region.shape[0]
                    or scaled.shape[1] > region.shape[1]
                ):
                    continue

                # Run template matching
                result = cv2.matchTemplate(region, scaled, cv2.TM_CCOEFF_NORMED)

                # Find all locations above threshold
                locations = np.where(result >= self._confidence_threshold)

                for pt_y, pt_x in zip(locations[0], locations[1]):
                    confidence = float(result[pt_y, pt_x])
                    ctx.symbols.append(
                        SymbolData(
                            staff_index=staff.staff_index,
                            x=int(pt_x),
                            y=int(staff.y_top + pt_y),
                            width=int(scaled.shape[1]),
                            height=int(scaled.shape[0]),
                            position_on_staff=None,
                            matched_template_id=template_id,
                            confidence=confidence,
                        )
                    )

        # Sort by staff, then left to right
        ctx.symbols.sort(key=lambda s: (s.staff_index, s.x))
        for i, sym in enumerate(ctx.symbols):
            sym.sequence_order = i

        return ctx

    def validate(self, ctx: PipelineContext) -> bool:
        return ctx.image is not None and len(ctx.staves) > 0

    @staticmethod
    def _scale_template(
        template: np.ndarray,
        height_in_lines: float,
        line_spacing: float,
    ) -> np.ndarray | None:
        """Scale template to match the staff's line spacing."""
        target_height = int(height_in_lines * line_spacing)
        if target_height < 3:
            return None

        h, w = template.shape[:2]
        scale = target_height / h
        target_width = max(1, int(w * scale))

        if len(template.shape) == 3:
            template = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)

        scaled = cv2.resize(
            template, (target_width, target_height), interpolation=cv2.INTER_AREA
        )
        return scaled
