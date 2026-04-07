"""Volta bracket detection: find repeat brackets above staves."""

from __future__ import annotations

import cv2
import numpy as np

from mv_hofki.services.scanner.stages.base import (
    PipelineContext,
    ProcessingStage,
    SymbolData,
)

# Barline names that indicate a repeat boundary
_REPEAT_BARLINES = {
    "Wiederholung Ende",
    "Wiederholung Anfang",
    "Wiederholung Beidseitig",
}


class VoltaDetectionStage(ProcessingStage):
    """Detect volta brackets above staves by seeding from repeat barlines."""

    name = "volta_detection"

    def process(self, ctx: PipelineContext) -> PipelineContext:
        binary = ctx.processed_image
        if binary is None:
            return ctx

        staves = sorted(ctx.staves, key=lambda s: s.staff_index)
        staff_map = {s.staff_index: s for s in staves}

        # Look up template ID for "Wiederholungs Klammer"
        display_names: dict[int, str] = ctx.metadata.get("template_display_names", {})
        bracket_id: int | None = None
        for tid, name in display_names.items():
            if name == "Wiederholungs Klammer":
                bracket_id = tid
                break

        # Group measures by staff
        measures_by_staff: dict[int, list] = {}
        for m in ctx.measures:
            measures_by_staff.setdefault(m.staff_index, []).append(m)

        # Find repeat barlines by staff
        repeat_measures_by_staff: dict[int, list] = {}
        for m in ctx.measures:
            if m.end_barline in _REPEAT_BARLINES:
                repeat_measures_by_staff.setdefault(m.staff_index, []).append(m)

        debug_lines: list[dict] = []
        brackets: list[SymbolData] = []
        volta_group_id = 0

        for staff_index, repeat_measures in repeat_measures_by_staff.items():
            staff = staff_map.get(staff_index)
            if staff is None:
                continue

            ls = staff.line_spacing
            top_line = min(staff.line_positions)
            min_line_len = int(ls * 2)

            # Scan region: above staff with 1× line_spacing offset
            region_top = staff.y_top
            region_bottom = top_line - int(ls)

            if region_top >= region_bottom:
                continue

            img_h, img_w = binary.shape[:2]
            staff_measures = measures_by_staff.get(staff_index, [])
            staff_measures.sort(key=lambda m: m.x_start)

            # Binarize the scan region once (handle anti-aliased gray values)
            region_bin = binary[region_top:region_bottom, :].copy()
            cv2.threshold(region_bin, 127, 255, cv2.THRESH_BINARY, region_bin)

            for repeat_m in repeat_measures:
                # Scan exactly one measure before + after the repeat
                scan_x1 = repeat_m.x_start
                scan_x2 = repeat_m.x_end

                for m in staff_measures:
                    if m.x_end == repeat_m.x_start or (
                        m.x_end <= repeat_m.x_start
                        and repeat_m.x_start - m.x_end < int(ls)
                    ):
                        scan_x1 = min(scan_x1, m.x_start)
                    if m.x_start == repeat_m.x_end or (
                        m.x_start >= repeat_m.x_end
                        and m.x_start - repeat_m.x_end < int(ls)
                    ):
                        scan_x2 = max(scan_x2, m.x_end)

                scan_x1 = max(0, scan_x1)
                scan_x2 = min(img_w, scan_x2)

                # Run Hough on scan region
                scan_region = region_bin[:, scan_x1:scan_x2]
                inverted = cv2.bitwise_not(scan_region)
                edges = cv2.Canny(inverted, 50, 150, apertureSize=3)
                lines = cv2.HoughLinesP(
                    edges,
                    rho=1,
                    theta=np.pi / 180,
                    threshold=15,
                    minLineLength=min_line_len,
                    maxLineGap=10,
                )

                if lines is None:
                    continue

                # Collect horizontal lines (<=5°, >= 2× line_spacing)
                # in absolute coordinates
                h_lines: list[tuple[int, int, int, int]] = []
                for line in lines:
                    x1, y1, x2, y2 = line[0]
                    angle = abs(np.degrees(np.arctan2(y2 - y1, x2 - x1)))

                    debug_lines.append(
                        {
                            "x1": int(scan_x1 + x1),
                            "y1": int(region_top + y1),
                            "x2": int(scan_x1 + x2),
                            "y2": int(region_top + y2),
                            "staff_index": staff_index,
                        }
                    )

                    if angle > 5:
                        continue
                    if x1 > x2:
                        x1, y1, x2, y2 = x2, y2, x1, y1
                    if (x2 - x1) < min_line_len:
                        continue

                    h_lines.append(
                        (
                            scan_x1 + x1,
                            region_top + y1,
                            scan_x1 + x2,
                            region_top + y2,
                        )
                    )

                # Process each Hough line: flood-fill from it to find
                # the full bracket, skip lines inside already-found brackets
                bottom_line_y = max(staff.line_positions)
                found_boxes: list[tuple[int, int, int, int]] = []

                for lx1, ly1, lx2, ly2 in h_lines:
                    # Skip if this line is inside an already-found bracket
                    mid_x = (lx1 + lx2) // 2
                    mid_y = (ly1 + ly2) // 2
                    if _point_in_any_box(mid_x, mid_y, found_boxes):
                        continue

                    # Flood-fill expansion from the Hough line seed
                    box = _flood_expand(region_bin, lx1, ly1, lx2, ly2, region_top)
                    bx1, by1, bx2, by2 = box

                    # Must be wider than tall (bracket-shaped)
                    if (bx2 - bx1) < (by2 - by1) * 2:
                        continue

                    found_boxes.append(box)

                    brackets.append(
                        SymbolData(
                            staff_index=staff_index,
                            x=bx1,
                            y=by1,
                            width=bx2 - bx1,
                            height=max(by2 - by1, int(ls // 2)),
                            staff_y_top=round((bottom_line_y - by1) / ls, 2),
                            staff_y_bottom=round((bottom_line_y - by2) / ls, 2),
                            staff_x_start=bx1,
                            staff_x_end=bx2,
                            matched_template_id=bracket_id,
                            confidence=0.8,
                        )
                    )

                    ctx.log(
                        f"  Volta-Klammer erkannt: System {staff_index}, "
                        f"x={bx1}-{bx2}"
                    )

            # Assign volta numbers
            staff_brackets = [b for b in brackets if b.staff_index == staff_index]
            staff_brackets.sort(key=lambda b: b.staff_x_start or b.x)

            if staff_brackets:
                volta_group_id += 1
                for volta_num, bracket in enumerate(staff_brackets, start=1):
                    bx1 = bracket.staff_x_start or bracket.x
                    bx2 = bracket.staff_x_end or (bracket.x + bracket.width)
                    for m in ctx.measures:
                        if m.staff_index != staff_index:
                            continue
                        if m.x_start < bx2 and m.x_end > bx1:
                            m.volta_number = volta_num
                            m.volta_group_id = volta_group_id

        # Add brackets to symbols list
        for b in brackets:
            b.sequence_order = len(ctx.symbols)
            ctx.symbols.append(b)

        ctx.metadata["volta_debug_lines"] = debug_lines
        ctx.log(
            f"Volta-Erkennung: {len(brackets)} Klammern, "
            f"{len(debug_lines)} Hough-Linien"
        )
        return ctx

    def validate(self, ctx: PipelineContext) -> bool:
        return ctx.processed_image is not None and len(ctx.staves) > 0


def _point_in_any_box(x: int, y: int, boxes: list[tuple[int, int, int, int]]) -> bool:
    """Check if a point falls inside any of the given bounding boxes."""
    for bx1, by1, bx2, by2 in boxes:
        if bx1 <= x <= bx2 and by1 <= y <= by2:
            return True
    return False


def _flood_expand(
    region_bin: np.ndarray,
    lx1: int,
    ly1: int,
    lx2: int,
    ly2: int,
    region_top: int,
) -> tuple[int, int, int, int]:
    """Expand from a Hough line seed by following all connected black pixels.

    Uses cv2.floodFill on a white copy where black pixels are passable.
    Seeds from multiple points along the Hough line to ensure we catch
    the full bracket even if the line has small gaps.

    Returns (x_min, y_min, x_max, y_max) in absolute image coordinates.
    """
    rh, rw = region_bin.shape[:2]

    # Create a mask for floodFill (needs 2px border)
    # We flood-fill on the inverted image: black pixels become white (255),
    # white becomes black (0). FloodFill fills connected white regions.
    inverted = cv2.bitwise_not(region_bin)

    # Use a tolerance to bridge small gray gaps
    filled = inverted.copy()
    mask = np.zeros((rh + 2, rw + 2), dtype=np.uint8)

    # Convert Hough line coords to region-relative
    rel_y1 = ly1 - region_top
    rel_y2 = ly2 - region_top

    # Seed from multiple points along the Hough line
    num_seeds = max(3, (lx2 - lx1) // 20)
    for i in range(num_seeds + 1):
        t = i / max(num_seeds, 1)
        sx = int(lx1 + t * (lx2 - lx1))
        sy = int(rel_y1 + t * (rel_y2 - rel_y1))

        sx = max(0, min(rw - 1, sx))
        sy = max(0, min(rh - 1, sy))

        # Only seed if the pixel is white in inverted (= black in original)
        if inverted[sy, sx] > 0:
            mask[:] = 0
            cv2.floodFill(
                filled,
                mask,
                (sx, sy),
                128,
                loDiff=(30,),
                upDiff=(30,),
            )

    # Find all pixels that were filled (value 128)
    filled_mask = (filled == 128).astype(np.uint8)
    coords = cv2.findNonZero(filled_mask)

    if coords is None:
        # Fallback: return the Hough line bounds
        return lx1, ly1, lx2, max(ly1, ly2)

    rx, ry, rw_box, rh_box = cv2.boundingRect(coords)
    return (
        int(rx),
        int(region_top + ry),
        int(rx + rw_box),
        int(region_top + ry + rh_box),
    )
