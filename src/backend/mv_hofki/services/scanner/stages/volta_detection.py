"""Volta bracket detection: find repeat brackets above staves."""

from __future__ import annotations

import cv2
import numpy as np

from mv_hofki.services.scanner.stages.base import (
    PipelineContext,
    ProcessingStage,
    SymbolData,
)
from mv_hofki.services.scanner.stages.utils import expand_to_connected

# Barline names that indicate a repeat boundary
_REPEAT_BARLINES = {
    "Wiederholung Ende",
    "Wiederholung Anfang",
    "Wiederholung Beidseitig",
}


class VoltaDetectionStage(ProcessingStage):
    """Detect volta brackets above staves using the same Hough + CC-expand
    approach as hairpin detection, constrained to repeat barline areas."""

    name = "volta_detection"

    def process(self, ctx: PipelineContext) -> PipelineContext:
        binary = ctx.processed_image
        if binary is None:
            return ctx

        staves = sorted(ctx.staves, key=lambda s: s.staff_index)

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
        repeat_x_by_staff: dict[int, list[int]] = {}
        for m in ctx.measures:
            if m.end_barline in _REPEAT_BARLINES:
                repeat_x_by_staff.setdefault(m.staff_index, []).append(m.x_start)
                repeat_x_by_staff[m.staff_index].append(m.x_end)

        debug_lines: list[dict] = []
        brackets: list[SymbolData] = []
        volta_group_id = 0

        for staff in staves:
            repeat_xs = repeat_x_by_staff.get(staff.staff_index)
            if not repeat_xs:
                continue

            ls = staff.line_spacing
            top_line = min(staff.line_positions)

            # Region above staff with 1× line_spacing offset
            region_top = staff.y_top
            region_bottom = top_line - int(ls)

            if region_top >= region_bottom:
                continue

            # Hough on full width of region above staff
            # (same approach as hairpin detection)
            region = binary[region_top:region_bottom, :]
            inverted = cv2.bitwise_not(region)

            edges = cv2.Canny(inverted, 50, 150, apertureSize=3)
            min_line_len = int(ls * 3)
            lines = cv2.HoughLinesP(
                edges,
                rho=1,
                theta=np.pi / 180,
                threshold=20,
                minLineLength=min_line_len,
                maxLineGap=10,
            )

            if lines is None:
                continue

            # Collect near-horizontal lines (<=5°)
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

                if angle > 5:
                    continue
                if x1 > x2:
                    x1, y1, x2, y2 = x2, y2, x1, y1
                if (x2 - x1) < min_line_len:
                    continue

                candidates.append((int(x1), int(abs_y1), int(x2), int(abs_y2)))

            # For each candidate: CC-expand, then check if it overlaps
            # with any repeat barline X position
            bottom_line_y = max(staff.line_positions)
            found_boxes: list[tuple[int, int, int, int]] = []

            for x1, y1, x2, y2 in candidates:
                # Skip if midpoint inside an already-found bracket
                mid_x = (x1 + x2) // 2
                if _point_in_any_box_x(mid_x, found_boxes):
                    continue

                # CC-expand to get full bracket extent
                ex = expand_to_connected(
                    binary, x1, y1, x2, y2, region_top, region_bottom
                )
                bx1, by1, bx2, by2 = (
                    int(ex[0]),
                    int(ex[1]),
                    int(ex[2]),
                    int(ex[3]),
                )

                # Must be near a repeat barline X position
                if not _near_repeat(bx1, bx2, repeat_xs, ls):
                    continue

                # Must be wider than tall (bracket-shaped)
                if (bx2 - bx1) < (by2 - by1) * 2:
                    continue

                found_boxes.append((bx1, by1, bx2, by2))

                brackets.append(
                    SymbolData(
                        staff_index=staff.staff_index,
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
                    f"  Volta-Klammer erkannt: System {staff.staff_index}, "
                    f"x={bx1}-{bx2}"
                )

            # Assign volta numbers
            staff_brackets = [b for b in brackets if b.staff_index == staff.staff_index]
            staff_brackets.sort(key=lambda b: b.staff_x_start or b.x)

            if staff_brackets:
                volta_group_id += 1
                for volta_num, bracket in enumerate(staff_brackets, start=1):
                    bx1 = bracket.staff_x_start or bracket.x
                    bx2 = bracket.staff_x_end or (bracket.x + bracket.width)
                    for m in ctx.measures:
                        if m.staff_index != staff.staff_index:
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


def _point_in_any_box_x(x: int, boxes: list[tuple[int, int, int, int]]) -> bool:
    """Check if an X coordinate falls within any box's X range."""
    for bx1, _, bx2, _ in boxes:
        if bx1 <= x <= bx2:
            return True
    return False


def _near_repeat(bx1: int, bx2: int, repeat_xs: list[int], ls: float) -> bool:
    """Check if a bracket's X range overlaps with any repeat barline position."""
    tolerance = int(ls * 2)
    for rx in repeat_xs:
        if bx1 - tolerance <= rx <= bx2 + tolerance:
            return True
    return False
