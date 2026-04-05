"""Hairpin detection: find crescendo/decrescendo wedges below staves via Hough."""

from __future__ import annotations

import cv2
import numpy as np

from mv_hofki.services.scanner.stages.base import (
    PipelineContext,
    ProcessingStage,
    SymbolData,
)


class HairpinDetectionStage(ProcessingStage):
    """Detect crescendo/decrescendo hairpins below staff lines using Hough."""

    name = "hairpin_detection"

    def process(self, ctx: PipelineContext) -> PipelineContext:
        binary = ctx.processed_image
        if binary is None:
            return ctx

        staves = sorted(ctx.staves, key=lambda s: s.staff_index)
        hairpins: list[SymbolData] = []
        debug_lines: list[dict] = []

        # Look up template IDs for crescendo/decrescendo from metadata
        display_names: dict[int, str] = ctx.metadata.get("template_display_names", {})
        cresc_id = None
        decresc_id = None
        for tid, name in display_names.items():
            if name == "Crescendo":
                cresc_id = tid
            elif name == "Decrescendo":
                decresc_id = tid

        # Minimum hairpin width in pixels (configurable, default 3× line_spacing)
        hairpin_min_width_factor = ctx.config.get("hairpin_min_width_factor", 3.0)

        for staff in staves:
            bottom_line = max(staff.line_positions)
            region_top = bottom_line + int(staff.line_spacing * 0.5)
            region_bottom = staff.y_bottom

            if region_top >= region_bottom:
                continue

            min_line_length = int(staff.line_spacing * hairpin_min_width_factor)

            region = binary[region_top:region_bottom, :]
            inverted = cv2.bitwise_not(region)

            edges = cv2.Canny(inverted, 50, 150, apertureSize=3)
            lines = cv2.HoughLinesP(
                edges,
                rho=1,
                theta=np.pi / 180,
                threshold=20,
                minLineLength=min_line_length,
                maxLineGap=10,
            )

            if lines is None:
                continue

            # Collect near-horizontal lines (hairpins are very flat, max ±10°)
            candidates: list[tuple[int, int, int, int]] = []
            for line in lines:
                x1, y1, x2, y2 = line[0]
                abs_y1 = region_top + y1
                abs_y2 = region_top + y2
                angle = abs(np.degrees(np.arctan2(y2 - y1, x2 - x1)))

                debug_lines.append(
                    {
                        "x1": int(x1),
                        "y1": int(abs_y1),
                        "x2": int(x2),
                        "y2": int(abs_y2),
                        "staff_index": staff.staff_index,
                    }
                )

                # Keep lines between 1° and 10° (hairpins are slightly angled)
                if 0 <= angle <= 10:
                    # Normalize so x1 < x2
                    if x1 > x2:
                        x1, y1, x2, y2 = x2, y2, x1, y1
                    candidates.append((int(x1), int(abs_y1), int(x2), int(abs_y2)))

            # Find converging line pairs (V-shapes)
            min_y_gap = (staff.line_thickness or 2) * 0
            raw_pairs = _find_hairpin_pairs(
                candidates, staff.line_spacing, min_line_length, min_y_gap
            )

            # Expand each pair to full connected component bounds
            expanded: list[tuple[str, int, int, int, int]] = []
            for hp_type, x_min, y_min, x_max, y_max in raw_pairs:
                ex = _expand_to_connected(
                    binary,
                    x_min,
                    y_min,
                    x_max,
                    y_max,
                    region_top,
                    region_bottom,
                )
                expanded.append((hp_type, *ex))

            # NMS: merge overlapping detections, keep the largest
            merged = _nms_hairpins(expanded)

            bottom_line_y = max(staff.line_positions)
            ls = staff.line_spacing
            min_hitbox_width = int(
                ls * ctx.config.get("hairpin_min_hitbox_width_factor", 3.0)
            )
            for hp_type, x_min, y_min, x_max, y_max in merged:
                if (x_max - x_min) < min_hitbox_width:
                    continue
                conf = _match_hairpin_template(
                    binary, hp_type, x_min, y_min, x_max, y_max
                )
                ctx.log(
                    f"  Hairpin ({hp_type}) Kandidat: "
                    f"System {staff.staff_index}, x={x_min}-{x_max}, "
                    f"conf={conf:.2f}"
                )
                if conf < 0:
                    continue
                template_id = cresc_id if hp_type == "crescendo" else decresc_id
                hairpins.append(
                    SymbolData(
                        staff_index=staff.staff_index,
                        x=x_min,
                        y=y_min,
                        width=x_max - x_min,
                        height=max(y_max - y_min, int(ls // 2)),
                        staff_y_top=round((bottom_line_y - y_min) / ls, 2),
                        staff_y_bottom=round((bottom_line_y - y_max) / ls, 2),
                        staff_x_start=x_min,
                        staff_x_end=x_max,
                        matched_template_id=template_id,
                        confidence=round(conf, 3),
                    )
                )
                ctx.log(
                    f"  Hairpin ({hp_type}) erkannt: "
                    f"System {staff.staff_index}, x={x_min}-{x_max}"
                )

        # Add hairpins to symbols list
        for hp in hairpins:
            hp.sequence_order = len(ctx.symbols)
            ctx.symbols.append(hp)

        ctx.metadata["hairpin_debug_lines"] = debug_lines
        ctx.log(
            f"Hairpin-Erkennung: {len(hairpins)} Crescendo/Decrescendo, "
            f"{len(debug_lines)} Hough-Linien"
        )
        return ctx

    def validate(self, ctx: PipelineContext) -> bool:
        return ctx.processed_image is not None and len(ctx.staves) > 0


_hairpin_templates: list[np.ndarray] | None = None


def _load_hairpin_templates() -> list[np.ndarray]:
    """Load crescendo template images (lazy, cached)."""
    global _hairpin_templates  # noqa: PLW0603
    if _hairpin_templates is not None:
        return _hairpin_templates

    from pathlib import Path

    template_dir = Path(__file__).resolve().parents[4] / "samplefiles" / "crescendo"
    templates = []
    for name in sorted(template_dir.glob("*.png")):
        img = cv2.imread(str(name), cv2.IMREAD_GRAYSCALE)
        if img is not None:
            templates.append(img)
    _hairpin_templates = templates
    return templates


def _match_hairpin_template(
    binary: np.ndarray,
    hp_type: str,
    x_min: int,
    y_min: int,
    x_max: int,
    y_max: int,
) -> float:
    """Match the hitbox region against crescendo templates.

    Returns the best confidence score (0-1). For decrescendo the
    templates are horizontally flipped.
    """
    h_img, w_img = binary.shape[:2]
    x1 = max(0, x_min)
    y1 = max(0, y_min)
    x2 = min(w_img, x_max)
    y2 = min(h_img, y_max)

    if x2 <= x1 or y2 <= y1:
        return 0.0

    roi = binary[y1:y2, x1:x2]
    roi_h, roi_w = roi.shape

    if roi_h < 3 or roi_w < 3:
        return 0.0

    # Binarize ROI — processed image may contain anti-aliased gray values
    _, roi_bin = cv2.threshold(roi, 127, 255, cv2.THRESH_BINARY)

    templates = _load_hairpin_templates()
    if not templates:
        return 0.0

    # Scale template to ROI width but keep some vertical slack so
    # matchTemplate can slide and find the best vertical alignment.
    tpl_h = max(3, int(roi_h * 0.7))
    tpl_w = max(3, int(roi_w * 0.9))

    # Template must be smaller than ROI for sliding
    if tpl_h >= roi_h:
        tpl_h = roi_h - 1
    if tpl_w >= roi_w:
        tpl_w = roi_w - 1

    best_score = 0.0
    for tpl in templates:
        scaled = cv2.resize(tpl, (tpl_w, tpl_h), interpolation=cv2.INTER_AREA)
        _, scaled_bin = cv2.threshold(scaled, 127, 255, cv2.THRESH_BINARY)

        # For decrescendo, flip horizontally
        if hp_type == "decrescendo":
            scaled_bin = cv2.flip(scaled_bin, 1)

        result = cv2.matchTemplate(roi_bin, scaled_bin, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(result)
        if max_val > best_score:
            best_score = max_val

    return best_score


def _find_hairpin_pairs(
    candidates: list[tuple[int, int, int, int]],
    line_spacing: float,
    min_line_length: int = 20,
    min_y_gap: float = 3.0,
) -> list[tuple[str, int, int, int, int]]:
    """Find V-shaped pairs from near-horizontal lines.

    Each candidate is (x1, y1, x2, y2) normalized so x1 < x2.
    A hairpin pair is two lines that:
    - Overlap significantly in X range
    - Have a small Y gap (converge at one end, diverge at the other)
    - The converging end (vertex) has Y values close together
    - The diverging end has Y values further apart

    Returns list of (type, x_min, y_min, x_max, y_max).
    """
    if len(candidates) < 2:
        return []

    max_y_gap = line_spacing * 2
    min_x_overlap_ratio = 0.5
    results: list[tuple[str, int, int, int, int]] = []
    used: set[int] = set()

    for i, (x1a, y1a, x2a, y2a) in enumerate(candidates):
        if i in used:
            continue
        len_a = x2a - x1a
        if len_a < min_line_length:
            continue

        for j, (x1b, y1b, x2b, y2b) in enumerate(candidates):
            if j <= i or j in used:
                continue
            len_b = x2b - x1b
            if len_b < min_line_length:
                continue

            # Check X overlap
            x_overlap = min(x2a, x2b) - max(x1a, x1b)
            min_len = min(len_a, len_b)
            if x_overlap < min_len * min_x_overlap_ratio:
                continue

            # Check Y gap at left and right ends
            # Interpolate Y values at the shared X range
            shared_left = max(x1a, x1b)
            shared_right = min(x2a, x2b)

            def y_at_x(x, x1, y1, x2, y2):
                if x2 == x1:
                    return y1
                return y1 + (y2 - y1) * (x - x1) / (x2 - x1)

            y_a_left = y_at_x(shared_left, x1a, y1a, x2a, y2a)
            y_b_left = y_at_x(shared_left, x1b, y1b, x2b, y2b)
            y_a_right = y_at_x(shared_right, x1a, y1a, x2a, y2a)
            y_b_right = y_at_x(shared_right, x1b, y1b, x2b, y2b)

            gap_left = abs(y_a_left - y_b_left)
            gap_right = abs(y_a_right - y_b_right)

            # Both gaps must be within max_y_gap
            if gap_left > max_y_gap or gap_right > max_y_gap:
                continue

            # The open end must have a minimum gap (avoid matching parallel lines)
            max_gap = max(gap_left, gap_right)
            if max_gap < min_y_gap:
                continue

            # One end should be notably tighter than the other (V-shape)
            min_gap = min(gap_left, gap_right)
            if min_gap > max_gap * 0.9:
                # Too parallel — not a V
                continue

            # Determine type from which end converges
            if gap_left < gap_right:
                hp_type = "crescendo"  # vertex on left, opens right
            else:
                hp_type = "decrescendo"  # vertex on right, opens left

            all_x = [x1a, x2a, x1b, x2b]
            all_y = [y1a, y2a, y1b, y2b]
            results.append(
                (
                    hp_type,
                    min(all_x),
                    min(all_y),
                    max(all_x),
                    max(all_y),
                )
            )
            used.add(i)
            used.add(j)
            break

    return results


def _expand_to_connected(
    binary: np.ndarray,
    x_min: int,
    y_min: int,
    x_max: int,
    y_max: int,
    region_top: int,
    region_bottom: int,
) -> tuple[int, int, int, int]:
    """Expand a bounding box to cover all connected black pixels.

    Uses the full staff below-region for connected component analysis
    so the expansion can reach the full extent of long hairpin symbols.
    """
    h, w = binary.shape[:2]
    roi_y1 = max(0, region_top)
    roi_y2 = min(h, region_bottom)

    roi = binary[roi_y1:roi_y2, :]
    inverted = cv2.bitwise_not(roi)

    num_labels, labels = cv2.connectedComponents(inverted)

    # Find which labels touch the seed box (relative to ROI)
    seed_y1 = max(0, y_min - roi_y1)
    seed_y2 = min(roi_y2 - roi_y1, y_max - roi_y1)
    seed_x1 = max(0, x_min)
    seed_x2 = min(w, x_max)

    if seed_y1 >= seed_y2 or seed_x1 >= seed_x2:
        return x_min, y_min, x_max, y_max

    seed_region = labels[seed_y1:seed_y2, seed_x1:seed_x2]
    touching_labels = set(np.unique(seed_region)) - {0}

    if not touching_labels:
        return x_min, y_min, x_max, y_max

    # Find the bounding box of all pixels with those labels
    mask = np.isin(labels, list(touching_labels))
    coords = cv2.findNonZero(mask.astype(np.uint8))
    if coords is None:
        return x_min, y_min, x_max, y_max

    rx, ry, rw, rh = cv2.boundingRect(coords)
    return rx, roi_y1 + ry, rx + rw, roi_y1 + ry + rh


def _nms_hairpins(
    detections: list[tuple[str, int, int, int, int]],
) -> list[tuple[str, int, int, int, int]]:
    """Non-maximum suppression: merge overlapping hairpin detections.

    When multiple detections overlap significantly, keep the one with
    the largest area (= best expanded bounds).
    """
    if not detections:
        return []

    # Sort by area descending (largest first)
    scored = sorted(
        detections,
        key=lambda d: (d[3] - d[1]) * (d[4] - d[2]),
        reverse=True,
    )

    kept: list[tuple[str, int, int, int, int]] = []
    for det in scored:
        _, x1, y1, x2, y2 = det
        area = (x2 - x1) * (y2 - y1)
        if area <= 0:
            continue

        suppressed = False
        for k_det in kept:
            _, kx1, ky1, kx2, ky2 = k_det
            # Compute overlap
            ox1 = max(x1, kx1)
            oy1 = max(y1, ky1)
            ox2 = min(x2, kx2)
            oy2 = min(y2, ky2)
            if ox1 < ox2 and oy1 < oy2:
                overlap_area = (ox2 - ox1) * (oy2 - oy1)
                # Suppress if >30% of the smaller detection overlaps
                if overlap_area > area * 0.3:
                    suppressed = True
                    break

        if not suppressed:
            kept.append(det)

    return kept
