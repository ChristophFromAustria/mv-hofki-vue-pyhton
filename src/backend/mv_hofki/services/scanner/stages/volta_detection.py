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

        # Group measures by staff for lookup
        measures_by_staff: dict[int, list] = {}
        for m in ctx.measures:
            measures_by_staff.setdefault(m.staff_index, []).append(m)

        # Find repeat barlines
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

            # Scan region: above staff with 1× line_spacing offset from top line
            region_top = staff.y_top
            region_bottom = top_line - int(ls)

            if region_top >= region_bottom:
                continue

            img_h, img_w = binary.shape[:2]
            staff_measures = measures_by_staff.get(staff_index, [])
            staff_measures.sort(key=lambda m: m.x_start)

            # Build scan ranges: for each repeat barline, scan from the
            # previous repeat/staff-start to the next repeat/staff-end.
            # This captures both volta 1 (before) and volta 2 (after).
            repeat_measures.sort(key=lambda m: m.x_start)
            scan_ranges: list[tuple[int, int]] = []

            for repeat_m in repeat_measures:
                # Find measure before: go back until another repeat or staff start
                scan_x1 = repeat_m.x_start
                for m in reversed(staff_measures):
                    if m.x_end <= repeat_m.x_start:
                        scan_x1 = m.x_start
                        if m.end_barline in _REPEAT_BARLINES:
                            break

                # Find measure after: go forward until another repeat or staff end
                scan_x2 = repeat_m.x_end
                for m in staff_measures:
                    if m.x_start >= repeat_m.x_end:
                        scan_x2 = m.x_end
                        if m.end_barline in _REPEAT_BARLINES:
                            break

                scan_x1 = max(0, scan_x1)
                scan_x2 = min(img_w, scan_x2)
                scan_ranges.append((scan_x1, scan_x2))

            # Deduplicate overlapping ranges
            merged_ranges: list[tuple[int, int]] = []
            for sx1, sx2 in sorted(scan_ranges):
                if merged_ranges and sx1 <= merged_ranges[-1][1]:
                    merged_ranges[-1] = (
                        merged_ranges[-1][0],
                        max(merged_ranges[-1][1], sx2),
                    )
                else:
                    merged_ranges.append((sx1, sx2))

            for scan_x1, scan_x2 in merged_ranges:
                # Extract the scan region (restricted X range)
                region = binary[region_top:region_bottom, scan_x1:scan_x2]
                inverted = cv2.bitwise_not(region)

                edges = cv2.Canny(inverted, 50, 150, apertureSize=3)
                min_line_len = int(ls * 2)
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

                # Collect all near-horizontal lines (<=5°), convert to abs
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

                    if angle <= 5:
                        if x1 > x2:
                            x1, y1, x2, y2 = x2, y2, x1, y1
                        h_lines.append(
                            (
                                scan_x1 + x1,
                                region_top + y1,
                                scan_x1 + x2,
                                region_top + y2,
                            )
                        )

                # Expand each horizontal line via CC, deduplicate results
                used_labels: set[tuple[int, int, int, int]] = set()
                for lx1, ly1, lx2, ly2 in h_lines:
                    ex = expand_to_connected(
                        binary,
                        lx1,
                        ly1,
                        lx2,
                        ly2,
                        region_top,
                        region_bottom,
                    )
                    ex_key = (int(ex[0]), int(ex[1]), int(ex[2]), int(ex[3]))

                    # Skip if we already found this exact expanded box
                    if ex_key in used_labels:
                        continue
                    used_labels.add(ex_key)

                    ex_x1, ex_y1, ex_x2, ex_y2 = ex_key

                    bottom_line_y = max(staff.line_positions)

                    brackets.append(
                        SymbolData(
                            staff_index=staff_index,
                            x=ex_x1,
                            y=ex_y1,
                            width=ex_x2 - ex_x1,
                            height=max(ex_y2 - ex_y1, int(ls // 2)),
                            staff_y_top=round((bottom_line_y - ex_y1) / ls, 2),
                            staff_y_bottom=round((bottom_line_y - ex_y2) / ls, 2),
                            staff_x_start=ex_x1,
                            staff_x_end=ex_x2,
                            matched_template_id=bracket_id,
                            confidence=0.8,
                        )
                    )

                    ctx.log(
                        f"  Volta-Klammer erkannt: System {staff_index}, "
                        f"x={ex_x1}-{ex_x2}"
                    )

            # Assign volta numbers: match bracket hitbox against measures
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
