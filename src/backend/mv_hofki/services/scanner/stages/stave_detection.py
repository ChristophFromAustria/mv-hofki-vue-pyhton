"""Stave detection stage: find staff line groups via horizontal projection."""

from __future__ import annotations

import numpy as np

from mv_hofki.services.scanner.stages.base import (
    PipelineContext,
    ProcessingStage,
    StaffData,
)


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

        for i, staff_lines in enumerate(staves):
            spacing = np.mean(np.diff(staff_lines))
            margin = int(spacing * 2)
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
        """Group line centers into staves of 5 with consistent spacing."""
        if len(line_centers) < 5:
            return []

        staves: list[list[int]] = []
        used = set()

        i = 0
        while i <= len(line_centers) - 5:
            if i in used:
                i += 1
                continue

            candidate = line_centers[i : i + 5]
            spacings = np.diff(candidate)
            mean_spacing = np.mean(spacings)

            if mean_spacing < 3:
                i += 1
                continue

            # Check spacing consistency
            deviations = np.abs(spacings - mean_spacing) / mean_spacing
            if np.all(deviations < tolerance):
                staves.append(candidate)
                for j in range(i, i + 5):
                    used.add(j)
                i += 5
            else:
                i += 1

        return staves
