"""Template matching stage: sliding window with cv2.matchTemplate."""

from __future__ import annotations

import logging
from typing import Any

import cv2
import numpy as np

from mv_hofki.services.scanner.stages.base import (
    PipelineContext,
    ProcessingStage,
    SymbolData,
)

logger = logging.getLogger(__name__)

# Cap raw hits per variant+staff to avoid O(n²) NMS on false positives.
_MAX_HITS_PER_VARIANT = 500

# Map config strings to OpenCV constants.
_METHOD_MAP = {
    "TM_CCOEFF_NORMED": cv2.TM_CCOEFF_NORMED,
    "TM_CCORR_NORMED": cv2.TM_CCORR_NORMED,
    "TM_SQDIFF_NORMED": cv2.TM_SQDIFF_NORMED,
}


class TemplateMatchingStage(ProcessingStage):
    """Find symbols using scaled template matching across each staff region."""

    name = "template_matching"

    def __init__(
        self,
        variant_images: list[np.ndarray],
        variant_template_ids: list[int],
        variant_heights: list[float],
        variant_line_spacings: list[float] | None = None,
        template_display_names: dict[int, str] | None = None,
    ) -> None:
        self._variant_images = variant_images
        self._variant_template_ids = variant_template_ids
        self._variant_heights = variant_heights
        self._variant_line_spacings = variant_line_spacings or [0.0] * len(
            variant_images
        )
        self._template_display_names = template_display_names or {}

    # ------------------------------------------------------------------
    # Config helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _cfg(ctx: PipelineContext, key: str, default: Any) -> Any:
        return ctx.config.get(key, default)

    # ------------------------------------------------------------------
    # Public pipeline interface
    # ------------------------------------------------------------------

    def process(self, ctx: PipelineContext) -> PipelineContext:  # noqa: C901
        assert ctx.image is not None
        ctx.metadata["template_display_names"] = self._template_display_names
        img = ctx.image
        if len(img.shape) == 3:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Read config with defaults
        confidence_threshold: float = float(self._cfg(ctx, "confidence_threshold", 0.6))
        matching_method_str: str = str(
            self._cfg(ctx, "matching_method", "TM_CCOEFF_NORMED")
        )
        multi_scale_enabled: bool = bool(self._cfg(ctx, "multi_scale_enabled", False))
        multi_scale_range: float = float(self._cfg(ctx, "multi_scale_range", 0.05))
        multi_scale_steps: int = int(self._cfg(ctx, "multi_scale_steps", 3))
        edge_matching_enabled: bool = bool(
            self._cfg(ctx, "edge_matching_enabled", False)
        )
        canny_low: int = int(self._cfg(ctx, "canny_low", 50))
        canny_high: int = int(self._cfg(ctx, "canny_high", 150))
        masked_matching_enabled: bool = bool(
            self._cfg(ctx, "masked_matching_enabled", False)
        )
        mask_threshold: int = int(self._cfg(ctx, "mask_threshold", 200))

        cv_method = _METHOD_MAP.get(matching_method_str, cv2.TM_CCOEFF_NORMED)
        is_sqdiff = cv_method == cv2.TM_SQDIFF_NORMED

        # Precompute full-image edge map if requested
        edge_img: np.ndarray | None = None
        if edge_matching_enabled:
            edge_img = cv2.Canny(img, canny_low, canny_high)

        raw_detections: list[SymbolData] = []

        for staff in ctx.staves:
            region = img[staff.y_top : staff.y_bottom, :]
            edge_region: np.ndarray | None = None
            if edge_img is not None:
                edge_region = edge_img[staff.y_top : staff.y_bottom, :]

            for i, tmpl_img in enumerate(self._variant_images):
                template_id = self._variant_template_ids[i]
                height_in_lines = self._variant_heights[i]
                source_ls = self._variant_line_spacings[i]

                base_scale = self._compute_scale(
                    tmpl_img, height_in_lines, staff.line_spacing, source_ls
                )
                if base_scale is None:
                    continue

                # Determine scales to try
                if multi_scale_enabled and multi_scale_steps > 1:
                    scales = np.linspace(
                        base_scale * (1 - multi_scale_range),
                        base_scale * (1 + multi_scale_range),
                        multi_scale_steps,
                    ).tolist()
                else:
                    scales = [base_scale]

                for scale in scales:
                    scaled = self._apply_scale(tmpl_img, scale)
                    if scaled is None:
                        continue

                    # Skip if template is larger than the region
                    if (
                        scaled.shape[0] > region.shape[0]
                        or scaled.shape[1] > region.shape[1]
                    ):
                        continue

                    # Choose images and method for matching
                    match_region = region
                    match_template = scaled
                    method_to_use = cv_method
                    mask: np.ndarray | None = None

                    # Per-iteration sqdiff flag — may differ from outer
                    # is_sqdiff when masked matching overrides the method.
                    iter_sqdiff = is_sqdiff

                    if edge_matching_enabled and edge_region is not None:
                        match_region = edge_region
                        match_template = cv2.Canny(scaled, canny_low, canny_high)
                    elif masked_matching_enabled:
                        # Build foreground mask from the template
                        mask = np.where(scaled < mask_threshold, 255, 0).astype(
                            np.uint8
                        )
                        # Force TM_SQDIFF — OpenCV masks only work
                        # reliably with TM_SQDIFF / TM_CCORR (not normed)
                        method_to_use = cv2.TM_SQDIFF

                    # Run template matching
                    if mask is not None:
                        result = cv2.matchTemplate(
                            match_region, match_template, method_to_use, mask=mask
                        )
                        # TM_SQDIFF (unnormalized) — convert to 0-1
                        # confidence where 1=perfect match.
                        rmin = result.min()
                        rmax = result.max()
                        if rmax > rmin:
                            result = 1.0 - (result - rmin) / (rmax - rmin)
                        else:
                            result = np.ones_like(result)
                        iter_sqdiff = False  # already normalised as confidence
                    else:
                        result = cv2.matchTemplate(
                            match_region, match_template, method_to_use
                        )

                    # Threshold logic (inverted for SQDIFF_NORMED)
                    if iter_sqdiff:
                        locations = np.where(result <= (1 - confidence_threshold))
                    else:
                        locations = np.where(result >= confidence_threshold)

                    n_hits = len(locations[0])

                    if n_hits > _MAX_HITS_PER_VARIANT:
                        logger.warning(
                            "Variant tid=%d on staff %d produced %d hits "
                            "(cap=%d), keeping top %d by confidence",
                            template_id,
                            staff.staff_index,
                            n_hits,
                            _MAX_HITS_PER_VARIANT,
                            _MAX_HITS_PER_VARIANT,
                        )
                        confidences = result[locations]
                        if iter_sqdiff:
                            # Lower is better for SQDIFF
                            top_indices = np.argpartition(
                                confidences, _MAX_HITS_PER_VARIANT
                            )[:_MAX_HITS_PER_VARIANT]
                        else:
                            top_indices = np.argpartition(
                                confidences, -_MAX_HITS_PER_VARIANT
                            )[-_MAX_HITS_PER_VARIANT:]
                        locations = (
                            locations[0][top_indices],
                            locations[1][top_indices],
                        )

                    for pt_y, pt_x in zip(locations[0], locations[1]):
                        score = float(result[pt_y, pt_x])
                        confidence = (1.0 - score) if iter_sqdiff else score
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

        # Read NMS config
        nms_method: str = str(self._cfg(ctx, "nms_method", "standard"))
        nms_iou_threshold: float = float(self._cfg(ctx, "nms_iou_threshold", 0.3))

        if nms_method == "dilate":
            ctx.symbols = self._nms_dilate(raw_detections)
        else:
            ctx.symbols = self._nms_with_alternatives(raw_detections, nms_iou_threshold)

        # Sort by staff, then left to right
        ctx.symbols.sort(key=lambda s: (s.staff_index, s.x))
        for i, sym in enumerate(ctx.symbols):
            sym.sequence_order = i

        return ctx

    # ------------------------------------------------------------------
    # Scale helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_scale(
        template: np.ndarray,
        height_in_lines: float,
        line_spacing: float,
        source_line_spacing: float = 0.0,
    ) -> float | None:
        """Compute the scale factor for a template given spacings."""
        if source_line_spacing and source_line_spacing > 0:
            return line_spacing / source_line_spacing

        target_height = int(height_in_lines * line_spacing)
        if target_height < 3:
            return None
        h: int = template.shape[0]
        return float(target_height / h)

    @staticmethod
    def _apply_scale(template: np.ndarray, scale: float) -> np.ndarray | None:
        """Resize *template* by *scale*, returning a grayscale image."""
        h, w = template.shape[:2]
        target_height = max(3, int(h * scale))
        target_width = max(1, int(w * scale))

        tmpl = template
        if len(tmpl.shape) == 3:
            tmpl = cv2.cvtColor(tmpl, cv2.COLOR_BGR2GRAY)

        return cv2.resize(
            tmpl, (target_width, target_height), interpolation=cv2.INTER_AREA
        )

    @staticmethod
    def _scale_template(
        template: np.ndarray,
        height_in_lines: float,
        line_spacing: float,
        source_line_spacing: float = 0.0,
    ) -> np.ndarray | None:
        """Scale template to match the target staff's line spacing.

        If source_line_spacing is known, scale by the ratio of target
        to source line spacing (px-per-line-space matching).
        Otherwise fall back to height_in_lines * line_spacing.

        Kept for backward compatibility — delegates to _compute_scale
        and _apply_scale.
        """
        scale = TemplateMatchingStage._compute_scale(
            template, height_in_lines, line_spacing, source_line_spacing
        )
        if scale is None:
            return None
        return TemplateMatchingStage._apply_scale(template, scale)

    # ------------------------------------------------------------------
    # NMS variants
    # ------------------------------------------------------------------

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

    @staticmethod
    def _nms_with_alternatives(
        detections: list[SymbolData], iou_threshold: float = 0.3
    ) -> list[SymbolData]:
        """Non-maximum suppression keeping top hit and alternatives."""
        detections.sort(key=lambda d: d.confidence or 0, reverse=True)
        kept: list[SymbolData] = []
        suppressed = [False] * len(detections)

        for i, det in enumerate(detections):
            if suppressed[i]:
                continue
            kept.append(det)
            for j in range(i + 1, len(detections)):
                if suppressed[j]:
                    continue
                if TemplateMatchingStage._iou(det, detections[j]) >= iou_threshold:
                    suppressed[j] = True
                    other = detections[j]
                    if other.matched_template_id != det.matched_template_id:
                        existing_ids = {a[0] for a in det.alternatives}
                        if other.matched_template_id not in existing_ids:
                            det.alternatives.append(
                                (other.matched_template_id or 0, other.confidence or 0)
                            )
        return kept

    @staticmethod
    def _nms_dilate(detections: list[SymbolData]) -> list[SymbolData]:
        """Proximity-based NMS: suppress detections within half-template-width."""
        detections.sort(key=lambda d: d.confidence or 0, reverse=True)
        kept: list[SymbolData] = []
        suppressed = [False] * len(detections)

        for i, det in enumerate(detections):
            if suppressed[i]:
                continue
            kept.append(det)
            suppression_distance = det.width / 2.0
            cx_i = det.x + det.width / 2.0
            cy_i = det.y + det.height / 2.0

            for j in range(i + 1, len(detections)):
                if suppressed[j]:
                    continue
                other = detections[j]
                cx_j = other.x + other.width / 2.0
                cy_j = other.y + other.height / 2.0
                dist = ((cx_i - cx_j) ** 2 + (cy_i - cy_j) ** 2) ** 0.5
                if dist < suppression_distance:
                    suppressed[j] = True
                    if other.matched_template_id != det.matched_template_id:
                        existing_ids = {a[0] for a in det.alternatives}
                        if other.matched_template_id not in existing_ids:
                            det.alternatives.append(
                                (other.matched_template_id or 0, other.confidence or 0)
                            )
        return kept

    def validate(self, ctx: PipelineContext) -> bool:
        return ctx.image is not None and len(ctx.staves) > 0
