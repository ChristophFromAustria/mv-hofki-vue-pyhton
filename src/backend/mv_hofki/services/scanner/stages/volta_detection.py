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

        # Group repeat barlines by staff
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

            top_line = min(staff.line_positions)
            region_top = staff.y_top
            region_bottom = top_line

            if region_top >= region_bottom:
                continue

            h, w = binary.shape[:2]
            region = binary[region_top:region_bottom, :]
            inverted = cv2.bitwise_not(region)

            # Run Hough for debug info
            edges = cv2.Canny(inverted, 50, 150, apertureSize=3)
            min_line_len = int(staff.line_spacing * 2)
            lines = cv2.HoughLinesP(
                edges,
                rho=1,
                theta=np.pi / 180,
                threshold=15,
                minLineLength=min_line_len,
                maxLineGap=10,
            )

            if lines is not None:
                for line in lines:
                    x1, y1, x2, y2 = line[0]
                    debug_lines.append(
                        {
                            "x1": int(x1),
                            "y1": int(region_top + y1),
                            "x2": int(x2),
                            "y2": int(region_top + y2),
                            "staff_index": staff_index,
                        }
                    )

            # Use connected components to find bracket shapes
            num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(inverted)

            bottom_line_y = max(staff.line_positions)
            ls = staff.line_spacing
            min_width = int(ls * 2)

            for lbl in range(1, num_labels):
                cc_x = int(stats[lbl, cv2.CC_STAT_LEFT])
                cc_y = int(stats[lbl, cv2.CC_STAT_TOP])
                cc_w = int(stats[lbl, cv2.CC_STAT_WIDTH])
                cc_h = int(stats[lbl, cv2.CC_STAT_HEIGHT])

                # Filter: must be wide enough to be a bracket
                if cc_w < min_width:
                    continue

                # Filter: must be wider than tall (bracket-shaped)
                if cc_w < cc_h * 2:
                    continue

                # Convert to absolute coordinates
                abs_y = region_top + cc_y
                abs_y2 = abs_y + cc_h

                brackets.append(
                    SymbolData(
                        staff_index=staff_index,
                        x=cc_x,
                        y=abs_y,
                        width=cc_w,
                        height=max(cc_h, int(ls // 2)),
                        staff_y_top=round((bottom_line_y - abs_y) / ls, 2),
                        staff_y_bottom=round((bottom_line_y - abs_y2) / ls, 2),
                        staff_x_start=cc_x,
                        staff_x_end=cc_x + cc_w,
                        matched_template_id=bracket_id,
                        confidence=0.8,
                    )
                )

                ctx.log(
                    f"  Volta-Klammer erkannt: System {staff_index}, "
                    f"x={cc_x}-{cc_x + cc_w}"
                )

            # Assign volta numbers to measures under brackets
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
                        # Measure overlaps with bracket X range
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
