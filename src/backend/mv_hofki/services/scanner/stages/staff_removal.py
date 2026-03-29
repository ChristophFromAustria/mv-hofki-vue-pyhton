"""Staff line removal stage (optional).

Removes only the "empty" segments of staves — stretches where no musical
symbols exist between or near the five staff lines.  The algorithm evaluates
each column across the full staff region: if the only black pixels present
belong to the staff lines themselves, the entire column (all 5 lines plus
margin) is erased.  Where symbols are present, all lines are kept.
"""

from __future__ import annotations

import numpy as np

from mv_hofki.services.scanner.stages.base import PipelineContext, ProcessingStage


class StaffRemovalStage(ProcessingStage):
    """Remove empty staff segments, preserving all lines where symbols exist."""

    name = "staff_removal"

    def process(self, ctx: PipelineContext) -> PipelineContext:
        assert ctx.image is not None
        img = ctx.image.copy()

        thickness_pct = ctx.config.get("staff_removal_thickness_pct", 100)
        symbol_padding = ctx.config.get("staff_removal_symbol_padding", 0)

        for staff in ctx.staves:
            measured = self._measure_thickness(img, staff.line_positions)
            effective = max(1, int(measured * thickness_pct / 100))
            staff.line_thickness = int(measured)
            ctx.log(
                f"  System {staff.staff_index}: Liniendicke={measured}px, "
                f"effektiv={effective}px ({thickness_pct}%), "
                f"Abstand={staff.line_spacing:.0f}px"
            )
            self._remove_empty_staff_segments(
                img,
                staff.line_positions,
                line_spacing=staff.line_spacing,
                line_thickness=effective,
                symbol_padding=symbol_padding,
            )

        ctx.image = img
        ctx.processed_image = img.copy()
        return ctx

    def validate(self, ctx: PipelineContext) -> bool:
        return ctx.image is not None and len(ctx.staves) > 0

    @staticmethod
    def _measure_line_thickness(
        img: np.ndarray, line_y: int, search: int = 15
    ) -> np.ndarray:
        """Measure the black-pixel run crossing *line_y* at every column.

        Returns an array of shape (w,) with the thickness per column.
        Columns without black pixels near the line get thickness 0.
        """
        h, w = img.shape[:2]
        y_lo = max(0, line_y - search)
        y_hi = min(h, line_y + search)
        centre_idx = line_y - y_lo

        region = img[y_lo:y_hi, :]  # (region_h, w)
        is_black = region == 0

        # For each column find the contiguous run of black pixels closest to
        # the expected centre.  Vectorising the full run-detection is awkward,
        # so we iterate columns but keep it in a tight loop.
        thicknesses = np.zeros(w, dtype=np.int32)
        for x in range(w):
            col = is_black[:, x]
            black_idx = np.where(col)[0]
            if len(black_idx) == 0:
                continue
            # Group into contiguous runs
            splits = np.where(np.diff(black_idx) > 1)[0] + 1
            runs = np.split(black_idx, splits)
            # Pick run whose midpoint is closest to the expected centre
            best_run = min(runs, key=lambda r: abs((r[0] + r[-1]) / 2 - centre_idx))
            thicknesses[x] = best_run[-1] - best_run[0] + 1

        return thicknesses

    @staticmethod
    def _measure_thickness(img: np.ndarray, line_positions: list[int]) -> int:
        """Measure staff-line thickness across all 5 lines.

        For each line, measure the black-pixel run at every column, then
        discard the top 10 % of values (symbols inflating the measurement)
        and take the maximum of what remains.  The final thickness is the
        median across all 5 lines.
        """
        per_line: list[int] = []
        for line_y in line_positions:
            col_thick = StaffRemovalStage._measure_line_thickness(img, line_y)
            # Only consider columns that actually have a measurement
            valid = col_thick[col_thick > 0]
            if len(valid) == 0:
                continue
            # Sort ascending, drop the top 10 % (symbol outliers)
            valid.sort()
            cutoff = int(len(valid) * 0.9)
            trimmed = valid[:cutoff] if cutoff > 0 else valid
            per_line.append(int(trimmed[-1]))  # max after trimming

        if not per_line:
            return 3
        per_line.sort()
        return per_line[len(per_line) // 2]

    @staticmethod
    def _remove_empty_staff_segments(
        img: np.ndarray,
        line_positions: list[int],
        line_spacing: float,
        line_thickness: int,
        symbol_padding: int = 0,
    ) -> None:
        """Erase columns of the staff region where only line pixels exist.

        *symbol_padding* keeps that many extra pixels of staff lines intact
        on each side of a symbol, so lines don't end abruptly at the symbol
        edge.
        """
        h, w = img.shape[:2]
        half_t = line_thickness // 2 + 1

        margin = int(line_spacing * 0.5)
        region_top = max(0, line_positions[0] - margin)
        region_bot = min(h, line_positions[-1] + margin)

        region_h = region_bot - region_top
        line_mask = np.zeros(region_h, dtype=bool)
        for ly in line_positions:
            local_top = max(0, ly - half_t - region_top)
            local_bot = min(region_h, ly + half_t + 1 - region_top)
            line_mask[local_top:local_bot] = True

        region = img[region_top:region_bot, :]
        is_black = region == 0

        symbol_pixels = is_black & ~line_mask[:, np.newaxis]
        symbol_count = np.count_nonzero(symbol_pixels, axis=0)

        has_symbol = symbol_count > 0  # shape (w,)

        # Expand symbol columns by *symbol_padding* pixels in each direction
        if symbol_padding > 0:
            protected = has_symbol.copy()
            for shift in range(1, symbol_padding + 1):
                if shift < w:
                    protected[shift:] |= has_symbol[:-shift]  # pad right
                    protected[:-shift] |= has_symbol[shift:]  # pad left
            is_empty = ~protected
        else:
            is_empty = ~has_symbol

        # Erase contiguous empty runs
        run_start: int | None = None
        for x in range(w):
            if not is_empty[x]:
                if run_start is not None:
                    img[region_top:region_bot, run_start:x] = 255
                run_start = None
            else:
                if run_start is None:
                    run_start = x

        if run_start is not None:
            img[region_top:region_bot, run_start:w] = 255
