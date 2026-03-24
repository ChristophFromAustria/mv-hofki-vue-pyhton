"""Staff line removal stage (optional)."""

from __future__ import annotations

import numpy as np

from mv_hofki.services.scanner.stages.base import PipelineContext, ProcessingStage


class StaffRemovalStage(ProcessingStage):
    """Remove horizontal staff lines, preserving vertical components."""

    name = "staff_removal"

    def process(self, ctx: PipelineContext) -> PipelineContext:
        assert ctx.image is not None
        img = ctx.image.copy()

        for staff in ctx.staves:
            for line_y in staff.line_positions:
                self._remove_line(img, line_y, line_thickness=3)

        ctx.image = img
        return ctx

    def validate(self, ctx: PipelineContext) -> bool:
        return ctx.image is not None and len(ctx.staves) > 0

    @staticmethod
    def _remove_line(img: np.ndarray, y: int, line_thickness: int = 3) -> None:
        """Remove a horizontal line at y, preserving vertical crossings."""
        h, w = img.shape[:2]
        y_start = max(0, y - line_thickness // 2)
        y_end = min(h, y + line_thickness // 2 + 1)

        for x in range(w):
            # Check if this column has a vertical component crossing the line
            above_black = False
            below_black = False

            check_range = line_thickness + 2
            if y_start - check_range >= 0:
                above_black = bool(np.any(img[y_start - check_range : y_start, x] == 0))
            if y_end + check_range < h:
                below_black = bool(np.any(img[y_end : y_end + check_range, x] == 0))

            # Only remove if no vertical component crosses here
            if not (above_black and below_black):
                img[y_start:y_end, x] = 255
