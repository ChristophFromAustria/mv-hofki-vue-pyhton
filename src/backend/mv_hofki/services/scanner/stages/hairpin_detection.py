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

        for staff in staves:
            bottom_line = max(staff.line_positions)
            region_top = bottom_line
            region_bottom = staff.y_bottom

            if region_top >= region_bottom:
                continue

            region = binary[region_top:region_bottom, :]
            inverted = cv2.bitwise_not(region)

            edges = cv2.Canny(inverted, 50, 150, apertureSize=3)
            lines = cv2.HoughLinesP(
                edges,
                rho=1,
                theta=np.pi / 180,
                threshold=20,
                minLineLength=20,
                maxLineGap=10,
            )

            if lines is None:
                continue

            # Collect near-horizontal lines (hairpins are very flat, 0-15°)
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

                # Keep lines up to 15° (hairpins are nearly horizontal)
                if angle <= 15:
                    # Normalize so x1 < x2
                    if x1 > x2:
                        x1, y1, x2, y2 = x2, y2, x1, y1
                    candidates.append((int(x1), int(abs_y1), int(x2), int(abs_y2)))

            # Find converging line pairs (V-shapes)
            found = _find_hairpin_pairs(candidates, staff.line_spacing)
            for hp_type, x_min, y_min, x_max, y_max in found:
                # Expand hitbox to cover all connected black pixels
                x_min, y_min, x_max, y_max = _expand_to_connected(
                    binary, x_min, y_min, x_max, y_max
                )

                template_id = cresc_id if hp_type == "crescendo" else decresc_id
                bottom_line_y = max(staff.line_positions)
                ls = staff.line_spacing
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
                        confidence=0.8,
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


def _find_hairpin_pairs(
    candidates: list[tuple[int, int, int, int]],
    line_spacing: float,
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
        if len_a < 20:
            continue

        for j, (x1b, y1b, x2b, y2b) in enumerate(candidates):
            if j <= i or j in used:
                continue
            len_b = x2b - x1b
            if len_b < 20:
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

            # One end should be notably tighter than the other (V-shape)
            min_gap = min(gap_left, gap_right)
            max_gap = max(gap_left, gap_right)
            if max_gap < 3 or min_gap > max_gap * 0.7:
                # Too parallel or too similar — not a V
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
    padding: int = 2,
) -> tuple[int, int, int, int]:
    """Expand a bounding box to cover all connected black pixels.

    Takes the initial Hough-based hitbox as a seed region, finds all
    connected components that touch it, and returns the expanded bounds.
    This ensures both inner and outer contours of thick hairpin lines
    are fully enclosed.
    """
    h, w = binary.shape[:2]

    # Add padding around the seed box to catch nearby pixels
    roi_y1 = max(0, y_min - padding * 5)
    roi_y2 = min(h, y_max + padding * 5)
    roi_x1 = max(0, x_min - padding * 5)
    roi_x2 = min(w, x_max + padding * 5)

    roi = binary[roi_y1:roi_y2, roi_x1:roi_x2]
    # Invert: black pixels (ink) become white (foreground) for connectedComponents
    inverted = cv2.bitwise_not(roi)

    num_labels, labels = cv2.connectedComponents(inverted)

    # Find which labels touch the seed box (relative to ROI)
    seed_y1 = y_min - roi_y1
    seed_y2 = y_max - roi_y1
    seed_x1 = x_min - roi_x1
    seed_x2 = x_max - roi_x1

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

    # Convert back to absolute coordinates
    abs_x_min = roi_x1 + rx
    abs_y_min = roi_y1 + ry
    abs_x_max = roi_x1 + rx + rw
    abs_y_max = roi_y1 + ry + rh

    return abs_x_min, abs_y_min, abs_x_max, abs_y_max
