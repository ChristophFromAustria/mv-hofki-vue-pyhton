"""Template matching stage: sliding window with cv2.matchTemplate."""

from __future__ import annotations

import logging
from typing import Any

import cv2
import numpy as np

from mv_hofki.services.scanner.stages.base import (
    PipelineContext,
    ProcessingStage,
    StaffData,
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

    _BELOW_STAFF_CATEGORY = "dynamic"

    def __init__(
        self,
        variant_images: list[np.ndarray],
        variant_template_ids: list[int],
        variant_heights: list[float],
        variant_line_spacings: list[float] | None = None,
        template_display_names: dict[int, str] | None = None,
        template_categories: dict[int, str] | None = None,
        variant_ids: list[int] | None = None,
        template_min_confidence: dict[int, float] | None = None,
        template_confidence_weight: dict[int, float] | None = None,
        template_merge_overlapping: set[int] | None = None,
    ) -> None:
        self._variant_images = variant_images
        self._variant_template_ids = variant_template_ids
        self._variant_ids = variant_ids or []
        self._variant_heights = variant_heights
        self._variant_line_spacings = variant_line_spacings or [0.0] * len(
            variant_images
        )
        self._template_display_names = template_display_names or {}
        self._template_categories = template_categories or {}
        # Per-template overrides. A template without an entry uses the
        # global confidence_threshold / a weight of 1.0 / no merging.
        self._template_min_confidence = template_min_confidence or {}
        self._template_confidence_weight = template_confidence_weight or {}
        self._template_merge_overlapping = template_merge_overlapping or set()

    def _split_by_zone(self) -> tuple[list[int], list[int]]:
        """Split variant indices into staff and below_staff groups."""
        staff_indices: list[int] = []
        below_staff_indices: list[int] = []
        for i, tid in enumerate(self._variant_template_ids):
            cat = self._template_categories.get(tid, "")
            if cat == self._BELOW_STAFF_CATEGORY:
                below_staff_indices.append(i)
            else:
                staff_indices.append(i)
        return staff_indices, below_staff_indices

    @staticmethod
    def _compute_below_staff_region(
        staff: StaffData,
        next_staff: StaffData | None,
        img_height: int,
    ) -> tuple[int, int]:
        """Compute the vertical region for below-staff matching (dynamics).

        Returns (y_start, y_end) where:
        - y_start = bottom staff line minus 1 × line_spacing
        - y_end = top line of next staff, or image height if last staff
        """
        bottom_line = max(staff.line_positions)
        y_start = max(0, int(bottom_line - staff.line_spacing))
        if next_staff is not None:
            y_end = min(next_staff.line_positions)
        else:
            y_end = img_height
        return y_start, y_end

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
        staff_indices, below_staff_indices = self._split_by_zone()

        for si, staff in enumerate(ctx.staves):
            next_staff = ctx.staves[si + 1] if si + 1 < len(ctx.staves) else None

            # --- Zone 1: staff region (all non-dynamic templates) ---
            if staff_indices:
                region = img[staff.y_top : staff.y_bottom, :]
                edge_region: np.ndarray | None = None
                if edge_img is not None:
                    edge_region = edge_img[staff.y_top : staff.y_bottom, :]

                raw_detections.extend(
                    self._match_templates_in_region(
                        region=region,
                        edge_region=edge_region,
                        staff=staff,
                        template_indices=staff_indices,
                        region_y_offset=staff.y_top,
                        confidence_threshold=confidence_threshold,
                        cv_method=cv_method,
                        is_sqdiff=is_sqdiff,
                        multi_scale_enabled=multi_scale_enabled,
                        multi_scale_range=multi_scale_range,
                        multi_scale_steps=multi_scale_steps,
                        edge_matching_enabled=edge_matching_enabled,
                        canny_low=canny_low,
                        canny_high=canny_high,
                        masked_matching_enabled=masked_matching_enabled,
                        mask_threshold=mask_threshold,
                    )
                )

            # --- Zone 2: below_staff region (dynamic templates only) ---
            # bs_start may overlap the staff bounding box (intentional — catches
            # dynamics at the lower staff boundary).  No double-detection risk
            # because staff_indices and below_staff_indices are mutually exclusive.
            if below_staff_indices:
                bs_start, bs_end = self._compute_below_staff_region(
                    staff, next_staff, img.shape[0]
                )
                if bs_end > bs_start:
                    bs_region = img[bs_start:bs_end, :]
                    bs_edge_region: np.ndarray | None = None
                    if edge_img is not None:
                        bs_edge_region = edge_img[bs_start:bs_end, :]

                    raw_detections.extend(
                        self._match_templates_in_region(
                            region=bs_region,
                            edge_region=bs_edge_region,
                            staff=staff,
                            template_indices=below_staff_indices,
                            region_y_offset=bs_start,
                            confidence_threshold=confidence_threshold,
                            cv_method=cv_method,
                            is_sqdiff=is_sqdiff,
                            multi_scale_enabled=multi_scale_enabled,
                            multi_scale_range=multi_scale_range,
                            multi_scale_steps=multi_scale_steps,
                            edge_matching_enabled=edge_matching_enabled,
                            canny_low=canny_low,
                            canny_high=canny_high,
                            masked_matching_enabled=masked_matching_enabled,
                            mask_threshold=mask_threshold,
                        )
                    )

        # Read NMS config
        nms_method: str = str(self._cfg(ctx, "nms_method", "standard"))
        nms_iou_threshold: float = float(self._cfg(ctx, "nms_iou_threshold", 0.3))

        if nms_method == "dilate":
            ctx.symbols = self._nms_dilate(raw_detections)
        else:
            ctx.symbols = self._nms_with_alternatives(raw_detections, nms_iou_threshold)

        if self._template_merge_overlapping:
            ctx.symbols = self._merge_overlapping_same_template(
                ctx.symbols, self._template_merge_overlapping, ctx.staves
            )

        # Sort by staff, then left to right
        ctx.symbols.sort(key=lambda s: (s.staff_index, s.x))
        for i, sym in enumerate(ctx.symbols):
            sym.sequence_order = i

        return ctx

    # ------------------------------------------------------------------
    # Region matching
    # ------------------------------------------------------------------

    def _match_templates_in_region(
        self,
        *,
        region: np.ndarray,
        edge_region: np.ndarray | None,
        staff: StaffData,
        template_indices: list[int],
        region_y_offset: int,
        confidence_threshold: float,
        cv_method: int,
        is_sqdiff: bool,
        multi_scale_enabled: bool,
        multi_scale_range: float,
        multi_scale_steps: int,
        edge_matching_enabled: bool,
        canny_low: int,
        canny_high: int,
        masked_matching_enabled: bool,
        mask_threshold: int,
    ) -> list[SymbolData]:
        """Match templates against a single image region.

        This is the inner matching loop extracted from *process()* so it
        can be reused for different regions (e.g. staff zone vs.
        below-staff zone).
        """
        detections: list[SymbolData] = []
        bottom_line_y = max(staff.line_positions)

        for i in template_indices:
            tmpl_img = self._variant_images[i]
            template_id = self._variant_template_ids[i]
            variant_id = self._variant_ids[i] if self._variant_ids else None
            # Effective threshold and weight for this template. The weight is
            # applied to the raw score *before* the threshold so that every
            # stored confidence is >= the threshold the user configured.
            tmpl_threshold = self._template_min_confidence.get(
                template_id, confidence_threshold
            )
            tmpl_weight = self._template_confidence_weight.get(template_id, 1.0)
            raw_threshold = tmpl_threshold / tmpl_weight if tmpl_weight > 0 else 1.01
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
                    mask = np.where(scaled < mask_threshold, 255, 0).astype(np.uint8)
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
                    locations = np.where(result <= (1 - raw_threshold))
                else:
                    locations = np.where(result >= raw_threshold)

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
                    confidence = min(1.0, confidence * tmpl_weight)
                    abs_y = int(region_y_offset + pt_y)
                    sym_h = int(scaled.shape[0])
                    sym_w = int(scaled.shape[1])
                    sym_x = int(pt_x)
                    detections.append(
                        SymbolData(
                            staff_index=staff.staff_index,
                            x=sym_x,
                            y=abs_y,
                            width=sym_w,
                            height=sym_h,
                            staff_y_top=round(
                                (bottom_line_y - abs_y) / staff.line_spacing, 2
                            ),
                            staff_y_bottom=round(
                                (bottom_line_y - (abs_y + sym_h)) / staff.line_spacing,
                                2,
                            ),
                            staff_x_start=sym_x,
                            staff_x_end=sym_x + sym_w,
                            matched_template_id=template_id,
                            matched_variant_id=variant_id,
                            confidence=confidence,
                        )
                    )

        return detections

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
    def _merge_overlapping_same_template(
        detections: list[SymbolData],
        merge_template_ids: set[int],
        staves: list[StaffData] | None = None,
        min_vertical_overlap: float = 0.5,
    ) -> list[SymbolData]:
        """Merge overlapping hits of the same template into one bounding box.

        Wide symbols (e.g. a long half rest bar) can produce several hits of
        a narrower template that survive NMS because their IoU stays below
        the suppression threshold. For templates that opted in, hits on the
        same staff whose boxes overlap horizontally and share at least
        *min_vertical_overlap* of the smaller height are unioned into one
        detection carrying the best confidence and the merged alternatives.
        """
        merged: list[SymbolData] = []
        staff_map = {st.staff_index: st for st in (staves or [])}
        # Highest confidence first so the survivor keeps the best score.
        pending = sorted(detections, key=lambda d: d.confidence or 0, reverse=True)
        consumed = [False] * len(pending)

        for i, det in enumerate(pending):
            if consumed[i]:
                continue
            consumed[i] = True
            if det.matched_template_id not in merge_template_ids:
                merged.append(det)
                continue

            # Grow the union box until no further candidate overlaps it.
            changed = True
            while changed:
                changed = False
                for j, other in enumerate(pending):
                    if (
                        consumed[j]
                        or other.matched_template_id != det.matched_template_id
                    ):
                        continue
                    if other.staff_index != det.staff_index:
                        continue
                    if not TemplateMatchingStage._overlaps_for_merge(
                        det, other, min_vertical_overlap
                    ):
                        continue
                    consumed[j] = True
                    changed = True
                    TemplateMatchingStage._absorb(det, other)
            staff = staff_map.get(det.staff_index)
            if staff is not None and staff.line_spacing > 0:
                bottom = max(staff.line_positions)
                det.staff_y_top = round((bottom - det.y) / staff.line_spacing, 2)
                det.staff_y_bottom = round(
                    (bottom - (det.y + det.height)) / staff.line_spacing, 2
                )
            merged.append(det)
        return merged

    @staticmethod
    def _overlaps_for_merge(
        a: SymbolData, b: SymbolData, min_vertical_overlap: float
    ) -> bool:
        x_overlap = min(a.x + a.width, b.x + b.width) - max(a.x, b.x)
        if x_overlap <= 0:
            return False
        y_overlap = min(a.y + a.height, b.y + b.height) - max(a.y, b.y)
        min_h = min(a.height, b.height)
        return min_h > 0 and y_overlap / min_h >= min_vertical_overlap

    @staticmethod
    def _absorb(target: SymbolData, other: SymbolData) -> None:
        """Extend *target* to the union of both boxes and merge alternatives."""
        x1 = min(target.x, other.x)
        y1 = min(target.y, other.y)
        x2 = max(target.x + target.width, other.x + other.width)
        y2 = max(target.y + target.height, other.y + other.height)
        target.x, target.y = x1, y1
        target.width, target.height = x2 - x1, y2 - y1
        target.staff_x_start = x1
        target.staff_x_end = x2
        target.confidence = max(target.confidence or 0, other.confidence or 0)
        best: dict[int, float] = {tid: conf for tid, conf in target.alternatives}
        for tid, conf in other.alternatives:
            if tid != target.matched_template_id and conf > best.get(tid, -1.0):
                best[tid] = conf
        target.alternatives = sorted(best.items(), key=lambda a: a[1], reverse=True)

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
