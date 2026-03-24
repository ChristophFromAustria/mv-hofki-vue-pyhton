"""Symbol segmentation stage: find bounding boxes via connected components."""

from __future__ import annotations

import cv2
import numpy as np

from mv_hofki.services.scanner.stages.base import (
    PipelineContext,
    ProcessingStage,
    SymbolData,
)


class SegmentationStage(ProcessingStage):
    """Detect symbol regions using connected component analysis."""

    name = "segmentation"

    def process(self, ctx: PipelineContext) -> PipelineContext:
        assert ctx.image is not None
        img = ctx.image
        if len(img.shape) == 3:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Invert so symbols are white (for connectedComponents)
        inverted = cv2.bitwise_not(img)

        for staff in ctx.staves:
            # Crop to staff region
            region = inverted[staff.y_top : staff.y_bottom, :]
            symbols = self._find_symbols_in_region(region, staff, ctx.image.shape[1])
            ctx.symbols.extend(symbols)

        # Sort all symbols by staff index, then left to right
        ctx.symbols.sort(key=lambda s: (s.staff_index, s.x))

        # Assign sequence order
        for i, sym in enumerate(ctx.symbols):
            sym.sequence_order = i

        return ctx

    def validate(self, ctx: PipelineContext) -> bool:
        return ctx.image is not None and len(ctx.staves) > 0

    def _find_symbols_in_region(
        self,
        region: np.ndarray,
        staff,
        image_width: int,
    ) -> list[SymbolData]:
        """Find connected components in a staff region."""
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
            region, connectivity=8
        )

        min_area = int(staff.line_spacing * 2)
        max_area = int(staff.line_spacing * staff.line_spacing * 20)
        symbols = []

        for label_id in range(1, num_labels):  # skip background (0)
            x = stats[label_id, cv2.CC_STAT_LEFT]
            y = stats[label_id, cv2.CC_STAT_TOP]
            w = stats[label_id, cv2.CC_STAT_WIDTH]
            h = stats[label_id, cv2.CC_STAT_HEIGHT]
            area = stats[label_id, cv2.CC_STAT_AREA]

            if area < min_area or area > max_area:
                continue

            # Skip very wide components (likely line remnants)
            if w > image_width * 0.5:
                continue

            abs_y = staff.y_top + y
            center_y = abs_y + h // 2

            # Determine position on staff (line/space index)
            position = self._get_staff_position(center_y, staff.line_positions)

            # Extract snippet from original region
            snippet = region[y : y + h, x : x + w]

            symbols.append(
                SymbolData(
                    staff_index=staff.staff_index,
                    x=x,
                    y=abs_y,
                    width=w,
                    height=h,
                    snippet=snippet.copy(),
                    position_on_staff=position,
                )
            )

        return symbols

    @staticmethod
    def _get_staff_position(center_y: int, line_positions: list[int]) -> int:
        """Map a y-coordinate to a staff position index.

        Lines are even indices (0, 2, 4, 6, 8), spaces are odd (1, 3, 5, 7).
        Position 0 = top line, position 8 = bottom line.
        Negative = above staff, >8 = below staff.
        """
        if not line_positions:
            return 0

        spacing = (line_positions[-1] - line_positions[0]) / 4.0
        half_space = spacing / 2.0

        for i, line_y in enumerate(line_positions):
            if abs(center_y - line_y) < half_space:
                return i * 2  # on a line

        # Check spaces between lines
        for i in range(len(line_positions) - 1):
            mid = (line_positions[i] + line_positions[i + 1]) / 2.0
            if abs(center_y - mid) < half_space:
                return i * 2 + 1  # in a space

        # Above or below staff
        if center_y < line_positions[0]:
            return -1
        return 9
