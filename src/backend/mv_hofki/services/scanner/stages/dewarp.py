"""Dewarp stage: straighten curved staff lines via column-wise remapping."""

from __future__ import annotations

import logging

import cv2
import numpy as np

from mv_hofki.services.scanner.stages.base import PipelineContext, ProcessingStage

logger = logging.getLogger(__name__)


class DewarpStage(ProcessingStage):
    """Straighten bent staff lines using staff-line-guided piecewise dewarping.

    For each detected staff, the actual curved path of every staff line is
    traced across the image.  A per-column vertical displacement map is built
    so that each line moves to its median y-position (i.e. perfectly straight).
    Displacements between and beyond staves are interpolated smoothly.

    The stage replaces ``ctx.image`` with the dewarped result and updates
    ``ctx.staves`` with the new (straight) line positions.
    """

    name = "dewarp"

    # ── public interface ──────────────────────────────────────────────

    def process(self, ctx: PipelineContext) -> PipelineContext:
        assert ctx.image is not None

        img = ctx.image
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            gray = img

        smoothing = int(ctx.config.get("dewarp_smoothing", 50))

        # 1. Build a horizontal-line mask to isolate staff lines
        staff_mask = self._extract_staff_mask(gray)

        # 2. Trace each staff line as a curved path y(x)
        all_paths: list[np.ndarray] = []
        all_targets: list[float] = []

        for staff in ctx.staves:
            # Search band = half the line spacing so adjacent lines don't interfere
            band = max(3, int(staff.line_spacing * 0.4))
            for line_y in staff.line_positions:
                path = self._trace_line(
                    staff_mask,
                    line_y,
                    gray.shape[1],
                    smoothing,
                    search_band=band,
                )
                all_paths.append(path)
                all_targets.append(float(np.median(path)))

        if len(all_paths) < 2:
            ctx.log("Dewarp: zu wenige Linien erkannt, übersprungen")
            return ctx

        # 3. Build remap arrays
        map_x, map_y = self._build_remap(all_paths, all_targets, gray.shape)

        # 4. Apply remap
        dewarped = cv2.remap(
            img,
            map_x,
            map_y,
            cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=255,
        )
        ctx.image = dewarped

        # Also dewarp the processed (binary) image if present
        if ctx.processed_image is not None:
            ctx.processed_image = cv2.remap(
                ctx.processed_image,
                map_x,
                map_y,
                cv2.INTER_LINEAR,
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=255,
            )

        # 5. Update stave positions to the straight target values
        path_idx = 0
        for staff in ctx.staves:
            new_positions = []
            for _ in staff.line_positions:
                new_positions.append(int(round(all_targets[path_idx])))
                path_idx += 1
            staff.line_positions = new_positions
            spacing = (
                float(np.mean(np.diff(new_positions)))
                if len(new_positions) > 1
                else staff.line_spacing
            )
            staff.line_spacing = spacing
            margin = int(spacing * 4)
            staff.y_top = max(0, new_positions[0] - margin)
            staff.y_bottom = min(img.shape[0], new_positions[-1] + margin)

        max_displacement = max(
            float(np.max(np.abs(p - t))) for p, t in zip(all_paths, all_targets)
        )
        ctx.log(
            f"Dewarp: {len(all_paths)} Linien begradigt, "
            f"max. Verschiebung {max_displacement:.1f} px"
        )
        return ctx

    def validate(self, ctx: PipelineContext) -> bool:
        return ctx.image is not None and len(ctx.staves) > 0

    # ── internals ─────────────────────────────────────────────────────

    @staticmethod
    def _extract_staff_mask(gray: np.ndarray) -> np.ndarray:
        """Isolate horizontal staff lines with morphological opening."""
        # Binary: staff lines are black (0) on white (255)
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        # Wide horizontal kernel keeps only long horizontal structures
        k_width = max(gray.shape[1] // 6, 40)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (k_width, 1))
        return cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)

    @staticmethod
    def _trace_line(
        staff_mask: np.ndarray,
        approx_y: int,
        width: int,
        smoothing: int,
        search_band: int = 15,
    ) -> np.ndarray:
        """Trace a staff line's y-position at each x-coordinate.

        Looks for white pixels in ``staff_mask`` within ±search_band of
        ``approx_y`` and takes the centroid.  The result is smoothed with
        a moving average to fill gaps and reduce noise.
        """
        h = staff_mask.shape[0]
        path = np.full(width, float(approx_y), dtype=np.float32)

        y_lo = max(0, approx_y - search_band)
        y_hi = min(h, approx_y + search_band)

        for x in range(width):
            col = staff_mask[y_lo:y_hi, x]
            hits = np.where(col > 0)[0]
            if len(hits) > 0:
                path[x] = y_lo + hits.mean()

        # Smooth with a uniform (box) filter to handle small gaps
        if smoothing > 1:
            kernel = np.ones(smoothing) / smoothing
            path = np.convolve(path, kernel, mode="same").astype(np.float32)
            # Fix edges where convolution has boundary effects
            half = smoothing // 2
            path[:half] = path[half]
            path[-half:] = path[-half - 1]

        return path

    @staticmethod
    def _build_remap(
        paths: list[np.ndarray],
        targets: list[float],
        img_shape: tuple[int, ...],
    ) -> tuple[np.ndarray, np.ndarray]:
        """Build ``cv2.remap`` arrays from staff line paths and target positions.

        For each column *x*, the detected paths give control points mapping
        ``target_y → source_y``.  Displacements are interpolated for all rows
        so that the full image is smoothly warped.
        """
        h, w = img_shape[:2]

        map_x = np.tile(np.arange(w, dtype=np.float32), (h, 1))
        map_y = np.tile(np.arange(h, dtype=np.float32).reshape(-1, 1), (1, w))

        tgt = np.array(targets, dtype=np.float32)
        sort_idx = np.argsort(tgt)
        tgt_sorted = tgt[sort_idx]

        for x in range(w):
            src_sorted = np.array([paths[i][x] for i in sort_idx], dtype=np.float32)
            # displacement = source_y - target_y at each control point
            displacements = src_sorted - tgt_sorted

            # Interpolate displacement for every row in this column
            # Clamp (extrapolate flat) beyond the outermost staff lines
            col_disp = np.interp(
                np.arange(h, dtype=np.float32),
                tgt_sorted,
                displacements,
            )
            map_y[:, x] += col_disp

        return map_x, map_y
