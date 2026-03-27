"""Stave detection stage: find staff line groups via horizontal projection."""

from __future__ import annotations

import numpy as np

from mv_hofki.services.scanner.stages.base import (
    PipelineContext,
    ProcessingStage,
    StaffData,
)


def _find_best_staff(
    line_centers: list[int],
    start: int,
    used: set[int],
    tolerance: float,
    max_window: int = 10,
    ref_spacing: float = 0.0,
) -> tuple[list[int], list[int]] | None:
    """Find the best 5-line staff starting from *start*, skipping false candidates.

    Searches combinations of 5 unused lines within a window of *max_window*
    candidates.  When *ref_spacing* > 0 (learned from earlier staves),
    candidates whose mean spacing deviates >50% from the reference are
    rejected.  Returns ``(indices, positions)`` for the best group, or
    ``None`` if no valid staff is found.
    """
    n = len(line_centers)
    end = min(n, start + max_window)

    # Collect available (unused) indices in the window
    available = [j for j in range(start, end) if j not in used]
    if len(available) < 5:
        return None

    best_score: tuple[int, float] | None = None  # (first_index, deviation_sum)
    best_result: tuple[list[int], list[int]] | None = None

    from itertools import combinations

    for combo in combinations(available, 5):
        positions = [line_centers[j] for j in combo]
        spacings = np.diff(positions).astype(float)
        mean_spacing = spacings.mean()

        if mean_spacing < 3:
            continue

        # Reject groups whose spacing is far from the reference
        if ref_spacing > 0 and abs(mean_spacing - ref_spacing) / ref_spacing > 0.5:
            continue

        deviations = np.abs(spacings - mean_spacing) / mean_spacing
        if not np.all(deviations < tolerance):
            continue

        # Prefer groups starting closest to `start`, then lowest deviation
        score = (combo[0], float(deviations.sum()))
        if best_score is None or score < best_score:
            best_score = score
            best_result = (list(combo), positions)

    return best_result


class StaveDetectionStage(ProcessingStage):
    """Detect groups of 5 horizontal lines that form musical staves."""

    name = "stave_detection"

    def process(self, ctx: PipelineContext) -> PipelineContext:
        img = ctx.processed_image if ctx.processed_image is not None else ctx.image
        assert img is not None

        # Horizontal projection: sum black pixels per row
        # (assuming binary image: 0=black, 255=white)
        binary = img if len(img.shape) == 2 else img[:, :, 0]
        projection = np.sum(binary == 0, axis=1).astype(float)

        # Find line candidates: rows with high density of black pixels
        threshold = projection.max() * 0.3
        line_rows = np.where(projection > threshold)[0]

        if len(line_rows) == 0:
            return ctx

        # Group consecutive rows into line centers
        line_centers = self._group_consecutive(line_rows)

        # Group line centers into staves (groups of 5 with consistent spacing)
        staves = self._group_into_staves(line_centers)

        # Filter out staves with anomalous spacing (e.g. false groups
        # spanning two real staves).  Use the median spacing across all
        # candidates as reference.
        if len(staves) >= 2:
            all_spacings = [float(np.mean(np.diff(s))) for s in staves]
            median_spacing = float(np.median(all_spacings))
            staves = [
                s
                for s in staves
                if abs(float(np.mean(np.diff(s))) - median_spacing) / median_spacing
                < 0.5
            ]

        for i, staff_lines in enumerate(staves):
            spacing = np.mean(np.diff(staff_lines))
            # Extend region by the full staff height (4× line spacing)
            # to catch symbols above/below the lines
            margin = int(spacing * 4)
            ctx.staves.append(
                StaffData(
                    staff_index=i,
                    y_top=max(0, staff_lines[0] - margin),
                    y_bottom=min(img.shape[0], staff_lines[-1] + margin),
                    line_positions=[int(y) for y in staff_lines],
                    line_spacing=float(spacing),
                )
            )

        return ctx

    def validate(self, ctx: PipelineContext) -> bool:
        return (ctx.processed_image is not None) or (ctx.image is not None)

    @staticmethod
    def _group_consecutive(rows: np.ndarray, max_gap: int = 3) -> list[int]:
        """Group consecutive row indices and return their centers."""
        groups: list[list[int]] = []
        current: list[int] = [rows[0]]

        for r in rows[1:]:
            if r - current[-1] <= max_gap:
                current.append(r)
            else:
                groups.append(current)
                current = [r]
        groups.append(current)

        return [int(np.mean(g)) for g in groups]

    @staticmethod
    def _group_into_staves(
        line_centers: list[int], tolerance: float = 0.3
    ) -> list[list[int]]:
        """Group line centers into staves of 5 with consistent spacing.

        Uses a sliding-window approach that can skip false line candidates
        by trying all 5-element combinations within a local window.
        """
        if len(line_centers) < 5:
            return []

        staves: list[list[int]] = []
        used: set[int] = set()
        n = len(line_centers)
        ref_spacing: float = 0.0  # learned from first valid staff

        i = 0
        while i < n:
            if i in used:
                i += 1
                continue

            best = _find_best_staff(
                line_centers, i, used, tolerance, ref_spacing=ref_spacing
            )
            if best is not None:
                indices, candidate = best
                staves.append(candidate)
                used.update(indices)
                if ref_spacing == 0.0:
                    ref_spacing = float(np.mean(np.diff(candidate)))
                i = max(indices) + 1
            else:
                i += 1

        return staves
