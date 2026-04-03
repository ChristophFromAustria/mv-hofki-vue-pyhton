"""Volta bracket detection: Hough line scan on inter-staff regions."""

from __future__ import annotations

import cv2
import numpy as np

from mv_hofki.services.scanner.stages.base import PipelineContext, ProcessingStage


class VoltaDetectionStage(ProcessingStage):
    """Run Hough line detection between staves and store results for debugging."""

    name = "volta_detection"

    def process(self, ctx: PipelineContext) -> PipelineContext:
        binary = ctx.processed_image
        if binary is None:
            return ctx

        staves = sorted(ctx.staves, key=lambda s: s.staff_index)
        debug_lines: list[dict] = []

        for staff in staves:
            # Region above the top staff line but within the staff scan area
            # y_top = upper boundary of scan region
            # min(line_positions) = actual top staff line
            # Volta brackets sit between these two
            top_line = min(staff.line_positions)
            region_top = staff.y_top
            region_bottom = top_line

            if region_top >= region_bottom or region_bottom <= 0:
                continue

            region = binary[region_top:region_bottom, :]
            inverted = cv2.bitwise_not(region)

            edges = cv2.Canny(inverted, 50, 150, apertureSize=3)
            lines = cv2.HoughLinesP(
                edges,
                rho=1,
                theta=np.pi / 180,
                threshold=20,
                minLineLength=30,
                maxLineGap=15,
            )

            if lines is None:
                continue

            for line in lines:
                x1, y1, x2, y2 = line[0]
                debug_lines.append(
                    {
                        "x1": int(x1),
                        "y1": int(region_top + y1),
                        "x2": int(x2),
                        "y2": int(region_top + y2),
                        "staff_index": staff.staff_index,
                    }
                )

        ctx.metadata["volta_debug_lines"] = debug_lines
        ctx.log(f"Volta-Hough: {len(debug_lines)} Linien gefunden")
        return ctx

    def validate(self, ctx: PipelineContext) -> bool:
        return ctx.processed_image is not None and len(ctx.staves) > 0
