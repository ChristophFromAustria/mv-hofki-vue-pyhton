"""Volta bracket detection: find 1st/2nd ending brackets above staves."""

from __future__ import annotations

import cv2
import numpy as np

from mv_hofki.services.scanner.stages.base import (
    MeasureData,
    PipelineContext,
    ProcessingStage,
    StaffData,
)

_REPEAT_END_NAMES = {"Wiederholung Ende", "Wiederholung Beidseitig"}


class VoltaDetectionStage(ProcessingStage):
    """Detect volta brackets by finding horizontal lines above staves."""

    name = "volta_detection"

    def process(self, ctx: PipelineContext) -> PipelineContext:
        binary = ctx.processed_image
        if binary is None:
            return ctx

        staff_map = {s.staff_index: s for s in ctx.staves}
        measures_by_staff: dict[int, list[MeasureData]] = {}
        for m in ctx.measures:
            measures_by_staff.setdefault(m.staff_index, []).append(m)

        group_id = 1

        for staff_index in sorted(staff_map.keys()):
            staff = staff_map[staff_index]
            staff_measures = measures_by_staff.get(staff_index, [])
            if not staff_measures:
                continue

            brackets = self._find_brackets(binary, staff, staff_measures)
            if not brackets:
                continue

            self._assign_volta_numbers(brackets, staff_measures, group_id)
            group_id += len(brackets)

        ctx.log(
            f"Volta-Erkennung: "
            f"{sum(1 for m in ctx.measures if m.volta_number is not None)} "
            f"Takte mit Volta-Klammern"
        )
        return ctx

    def _find_brackets(
        self,
        binary: np.ndarray,
        staff: StaffData,
        measures: list[MeasureData],
    ) -> list[tuple[int, int]]:
        """Find horizontal line segments in the volta region above the staff.

        Uses probabilistic Hough line detection on the region 1-3
        line-spacings above the staff.  Hough tolerates slightly angled,
        thin, or gapped lines much better than morphological opening.

        Returns list of (x_start, x_end) for each detected bracket.
        """
        ls = staff.line_spacing
        region_top = max(0, int(staff.y_top - 3 * ls))
        region_bottom = max(0, int(staff.y_top - ls))
        if region_top >= region_bottom or region_bottom <= 0:
            return []

        region = binary[region_top:region_bottom, :]
        inverted = cv2.bitwise_not(region)

        avg_measure_width = int(
            sum(m.x_end - m.x_start for m in measures) / max(len(measures), 1)
        )
        # Use a low minLineLength so Hough finds fragments of broken/angled
        # lines.  We filter by total width after merging segments.
        min_line_length = max(int(ls), 20)

        # Edge detection + probabilistic Hough
        edges = cv2.Canny(inverted, 50, 150, apertureSize=3)
        lines = cv2.HoughLinesP(
            edges,
            rho=1,
            theta=np.pi / 180,
            threshold=30,
            minLineLength=min_line_length,
            maxLineGap=max(int(ls * 0.3), 5),
        )

        if lines is None:
            return []

        # Filter: keep only near-horizontal lines (within ~7 degrees)
        segments: list[tuple[int, int]] = []
        for line in lines:
            x1, y1, x2, y2 = line[0]
            angle = abs(np.degrees(np.arctan2(y2 - y1, x2 - x1)))
            if angle <= 7:
                seg_start = min(x1, x2)
                seg_end = max(x1, x2)
                segments.append((seg_start, seg_end))

        if not segments:
            return []

        # Merge overlapping/close segments into brackets
        segments.sort(key=lambda s: s[0])
        merged: list[tuple[int, int]] = [segments[0]]
        for seg_start, seg_end in segments[1:]:
            prev_start, prev_end = merged[-1]
            # Merge if overlapping or within one line_spacing gap
            if seg_start <= prev_end + int(ls):
                merged[-1] = (prev_start, max(prev_end, seg_end))
            else:
                merged.append((seg_start, seg_end))

        # Filter: minimum width = half average measure width
        min_width = avg_measure_width // 2
        brackets = [(s, e) for s, e in merged if (e - s) >= min_width]

        return brackets

    def _assign_volta_numbers(
        self,
        brackets: list[tuple[int, int]],
        measures: list[MeasureData],
        start_group_id: int,
    ) -> None:
        """Assign volta_number and volta_group_id to measures under brackets."""
        repeat_end_positions: list[int] = []
        for m in measures:
            if m.end_barline in _REPEAT_END_NAMES:
                repeat_end_positions.append(m.x_end)

        current_group = start_group_id

        for bx_start, bx_end in brackets:
            volta_num = 1
            for rep_x in repeat_end_positions:
                if bx_start >= rep_x:
                    volta_num = 2
                    break

            for m in measures:
                overlap = min(m.x_end, bx_end) - max(m.x_start, bx_start)
                measure_width = m.x_end - m.x_start
                if measure_width > 0 and overlap > measure_width * 0.3:
                    m.volta_number = volta_num
                    m.volta_group_id = current_group

            current_group += 1

        # Merge adjacent volta 1/2 into the same group
        volta1_groups = set()
        volta2_groups = set()
        for m in measures:
            if m.volta_number == 1 and m.volta_group_id is not None:
                volta1_groups.add(m.volta_group_id)
            elif m.volta_number == 2 and m.volta_group_id is not None:
                volta2_groups.add(m.volta_group_id)

        if volta1_groups and volta2_groups:
            v1_id = min(volta1_groups)
            for m in measures:
                if m.volta_number == 2 and m.volta_group_id in volta2_groups:
                    m.volta_group_id = v1_id

    def validate(self, ctx: PipelineContext) -> bool:
        return ctx.processed_image is not None and len(ctx.measures) > 0
