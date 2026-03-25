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
        variant_line_spacings: list[float | None] | None = None,
        confidence_threshold: float = 0.6,
    ) -> None:
        self._variant_images = variant_images
        self._variant_template_ids = variant_template_ids
        self._variant_heights = variant_heights
        self._variant_line_spacings = variant_line_spacings or [None] * len(
            variant_images
        )
        self._confidence_threshold = confidence_threshold

    def process(self, ctx: PipelineContext) -> PipelineContext:
        assert ctx.image is not None
        img = ctx.image
        if len(img.shape) == 3:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        raw_detections: list[SymbolData] = []

        for staff in ctx.staves:
            region = img[staff.y_top : staff.y_bottom, :]

            for i, tmpl_img in enumerate(self._variant_images):
                template_id = self._variant_template_ids[i]
                height_in_lines = self._variant_heights[i]
                source_ls = self._variant_line_spacings[i]

                scaled = self._scale_template(
                    tmpl_img,
                    height_in_lines,
                    staff.line_spacing,
                    source_line_spacing=source_ls,
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
                    raw_detections.append(
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

        # Apply NMS: keep best detection per overlap region,
        # store alternatives from different templates
        ctx.symbols = self._nms_with_alternatives(raw_detections)

        # Sort by staff, then left to right
        ctx.symbols.sort(key=lambda s: (s.staff_index, s.x))
        for i, sym in enumerate(ctx.symbols):
            sym.sequence_order = i

        return ctx

    @staticmethod
    def _iou(a: SymbolData, b: SymbolData) -> float:
        """Intersection over union of two bounding boxes."""
        x1 = max(a.x, b.x)
        y1 = max(a.y, b.y)
        x2 = min(a.x + a.width, b.x + b.width)
        y2 = min(a.y + a.height, b.y + b.height)
        inter = max(0, x2 - x1) * max(0, y2 - y1)
        if inter == 0:
            return 0.0
        area_a = a.width * a.height
        area_b = b.width * b.height
        return inter / (area_a + area_b - inter)

    def _nms_with_alternatives(
        self, detections: list[SymbolData], iou_threshold: float = 0.3
    ) -> list[SymbolData]:
        """Non-maximum suppression keeping top hit and alternatives."""
        # Sort by confidence descending
        detections.sort(key=lambda d: d.confidence or 0, reverse=True)
        kept: list[SymbolData] = []
        suppressed = [False] * len(detections)

        for i, det in enumerate(detections):
            if suppressed[i]:
                continue
            # This detection is the best for its region
            kept.append(det)
            # Check remaining detections for overlap
            for j in range(i + 1, len(detections)):
                if suppressed[j]:
                    continue
                if self._iou(det, detections[j]) >= iou_threshold:
                    suppressed[j] = True
                    # Add as alternative if from a different template
                    other = detections[j]
                    if other.matched_template_id != det.matched_template_id:
                        # Avoid duplicate template alternatives
                        existing_ids = {a[0] for a in det.alternatives}
                        if other.matched_template_id not in existing_ids:
                            det.alternatives.append(
                                (other.matched_template_id or 0, other.confidence or 0)
                            )
        return kept

    def validate(self, ctx: PipelineContext) -> bool:
        return ctx.image is not None and len(ctx.staves) > 0

    @staticmethod
    def _scale_template(
        template: np.ndarray,
        height_in_lines: float,
        line_spacing: float,
        source_line_spacing: float | None = None,
    ) -> np.ndarray | None:
        """Scale template to match the target staff's line spacing.

        If source_line_spacing is known, scale by the ratio of target
        to source line spacing (px-per-line-space matching).
        Otherwise fall back to height_in_lines * line_spacing.
        """
        if source_line_spacing and source_line_spacing > 0:
            scale = line_spacing / source_line_spacing
        else:
            target_height = int(height_in_lines * line_spacing)
            if target_height < 3:
                return None
            h = template.shape[0]
            scale = target_height / h

        h, w = template.shape[:2]
        target_height = max(3, int(h * scale))
        target_width = max(1, int(w * scale))

        if len(template.shape) == 3:
            template = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)

        scaled = cv2.resize(
            template, (target_width, target_height), interpolation=cv2.INTER_AREA
        )
        return scaled
