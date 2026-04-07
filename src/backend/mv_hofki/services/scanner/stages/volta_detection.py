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

            # Scan region: above staff with 1× line_spacing offset from top line
            region_top = staff.y_top
            region_bottom = top_line - int(ls)

            if region_top >= region_bottom:
                continue

            img_h, img_w = binary.shape[:2]
            staff_measures = measures_by_staff.get(staff_index, [])
            staff_measures.sort(key=lambda m: m.x_start)

            for repeat_m in repeat_measures:
                # Scan exactly one measure before + the repeat measure + one
                # measure after. No further expansion.
                scan_x1 = repeat_m.x_start
                scan_x2 = repeat_m.x_end

                for m in staff_measures:
                    # One measure directly before
                    if m.x_end == repeat_m.x_start or (
                        m.x_end <= repeat_m.x_start
                        and repeat_m.x_start - m.x_end < int(ls)
                    ):
                        scan_x1 = min(scan_x1, m.x_start)
                    # One measure directly after
                    if m.x_start == repeat_m.x_end or (
                        m.x_start >= repeat_m.x_end
                        and m.x_start - repeat_m.x_end < int(ls)
                    ):
                        scan_x2 = max(scan_x2, m.x_end)

                scan_x1 = max(0, scan_x1)
                scan_x2 = min(img_w, scan_x2)

                # Extract scan region
                region = binary[region_top:region_bottom, scan_x1:scan_x2]
                inverted = cv2.bitwise_not(region)

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

                # Collect horizontal lines (<=5°), filter short ones,
                # merge segments on similar Y into single seed lines
                raw_segments: list[tuple[int, int, int, int]] = []
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
                    length = x2 - x1
                    if length < min_line_len:
                        continue

                    raw_segments.append(
                        (
                            scan_x1 + x1,
                            region_top + y1,
                            scan_x1 + x2,
                            region_top + y2,
                        )
                    )

                # Merge segments on similar Y (within 3px) into single seeds
                merged_seeds = _merge_h_segments(raw_segments, y_tolerance=3)

                # CC-expand each merged seed
                bottom_line_y = max(staff.line_positions)
                for sx1, sy1, sx2, sy2 in merged_seeds:
                    ex = expand_to_connected(
                        binary,
                        sx1,
                        sy1,
                        sx2,
                        sy2,
                        region_top,
                        region_bottom,
                    )
                    ex_x1, ex_y1, ex_x2, ex_y2 = (
                        int(ex[0]),
                        int(ex[1]),
                        int(ex[2]),
                        int(ex[3]),
                    )

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

            # NMS: merge overlapping bracket detections on this staff
            staff_brackets = _nms_brackets(
                [b for b in brackets if b.staff_index == staff_index]
            )
            # Remove old staff brackets from list and replace with merged
            brackets = [
                b for b in brackets if b.staff_index != staff_index
            ] + staff_brackets

            # Assign volta numbers
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


def _merge_h_segments(
    segments: list[tuple[int, int, int, int]],
    y_tolerance: int = 3,
) -> list[tuple[int, int, int, int]]:
    """Merge horizontal line segments that sit on similar Y positions.

    Groups segments whose Y-centers are within y_tolerance, then produces
    one merged segment per group spanning the full X range.
    """
    if not segments:
        return []

    # Sort by Y center
    sorted_segs = sorted(segments, key=lambda s: (s[1] + s[3]) / 2)

    groups: list[list[tuple[int, int, int, int]]] = [[sorted_segs[0]]]
    for seg in sorted_segs[1:]:
        prev_y = (groups[-1][-1][1] + groups[-1][-1][3]) / 2
        cur_y = (seg[1] + seg[3]) / 2
        if abs(cur_y - prev_y) <= y_tolerance:
            groups[-1].append(seg)
        else:
            groups.append([seg])

    merged: list[tuple[int, int, int, int]] = []
    for group in groups:
        x1 = min(s[0] for s in group)
        y1 = min(s[1] for s in group)
        x2 = max(s[2] for s in group)
        y2 = max(s[3] for s in group)
        merged.append((x1, y1, x2, y2))

    return merged


def _nms_brackets(
    brackets: list[SymbolData],
) -> list[SymbolData]:
    """Non-maximum suppression: merge overlapping bracket detections.

    Keeps the largest (widest) detection when brackets overlap significantly.
    """
    if not brackets:
        return []

    # Sort by width descending (widest first)
    scored = sorted(brackets, key=lambda b: b.width, reverse=True)

    kept: list[SymbolData] = []
    for det in scored:
        x1 = det.staff_x_start or det.x
        x2 = det.staff_x_end or (det.x + det.width)

        suppressed = False
        for k in kept:
            kx1 = k.staff_x_start or k.x
            kx2 = k.staff_x_end or (k.x + k.width)

            # Check X overlap
            overlap = min(x2, kx2) - max(x1, kx1)
            if overlap > 0:
                smaller_width = min(x2 - x1, kx2 - kx1)
                if smaller_width > 0 and overlap > smaller_width * 0.3:
                    suppressed = True
                    break

        if not suppressed:
            kept.append(det)

    return kept
