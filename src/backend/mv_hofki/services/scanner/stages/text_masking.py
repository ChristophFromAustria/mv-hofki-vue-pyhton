"""Text masking: detect and remove text regions before Hough-based stages."""

from __future__ import annotations

import cv2
import numpy as np

from mv_hofki.services.scanner.stages.base import (
    PipelineContext,
    ProcessingStage,
    StaffData,
    TextRegionData,
)


class TextMaskingStage(ProcessingStage):
    """Detect text-like regions around staves and mask them in the binary image."""

    name = "text_masking"

    def process(self, ctx: PipelineContext) -> PipelineContext:
        binary = ctx.processed_image
        if binary is None:
            return ctx

        staves = sorted(ctx.staves, key=lambda s: s.staff_index)

        for staff in staves:
            regions = _scan_staff_regions(binary, staff)
            ctx.text_regions.extend(regions)

        # Mask detected text regions in the binary image
        for region in ctx.text_regions:
            y1 = region.y
            y2 = region.y + region.height
            x1 = region.x
            x2 = region.x + region.width
            binary[y1:y2, x1:x2] = 255

        ctx.log(
            f"Text-Maskierung: {len(ctx.text_regions)} Textregionen "
            f"in {len(staves)} Systemen erkannt"
        )
        return ctx

    def validate(self, ctx: PipelineContext) -> bool:
        return ctx.processed_image is not None and len(ctx.staves) > 0


def _scan_staff_regions(
    binary: np.ndarray,
    staff: StaffData,
) -> list[TextRegionData]:
    """Scan above and below a staff for text-like regions."""
    results: list[TextRegionData] = []

    top_line = min(staff.line_positions)
    bottom_line = max(staff.line_positions)

    # Region above: y_top to top staff line
    if staff.y_top < top_line:
        above = _detect_text_regions(
            binary,
            staff.y_top,
            top_line,
            staff.line_spacing,
            staff.staff_index,
        )
        results.extend(above)

    # Region below: bottom staff line to y_bottom
    if bottom_line < staff.y_bottom:
        below = _detect_text_regions(
            binary,
            bottom_line,
            staff.y_bottom,
            staff.line_spacing,
            staff.staff_index,
        )
        results.extend(below)

    return results


def _detect_text_regions(
    binary: np.ndarray,
    region_top: int,
    region_bottom: int,
    line_spacing: float,
    staff_index: int,
) -> list[TextRegionData]:
    """Find text-like clusters in a horizontal strip of the binary image.

    Text characters are small connected components clustered horizontally.
    We identify them by size relative to line_spacing and group adjacent ones.
    """
    h, w = binary.shape[:2]
    region_top = max(0, region_top)
    region_bottom = min(h, region_bottom)

    if region_top >= region_bottom:
        return []

    region = binary[region_top:region_bottom, :]
    inverted = cv2.bitwise_not(region)

    rh, rw = inverted.shape[:2]
    if rh == 0 or rw == 0:
        return []

    num_labels, _labels, stats, _ = cv2.connectedComponentsWithStats(
        inverted, connectivity=8
    )

    # Thresholds derived from staff line spacing
    max_char_size = line_spacing * 2.0
    min_char_size = max(2, line_spacing * 0.15)

    # Collect bounding boxes of character-sized components
    char_boxes: list[tuple[int, int, int, int]] = []
    for label_idx in range(1, num_labels):  # skip background
        bx = stats[label_idx, cv2.CC_STAT_LEFT]
        by = stats[label_idx, cv2.CC_STAT_TOP]
        bw = stats[label_idx, cv2.CC_STAT_WIDTH]
        bh = stats[label_idx, cv2.CC_STAT_HEIGHT]

        if (
            min_char_size <= bw <= max_char_size
            and min_char_size <= bh <= max_char_size
        ):
            # Reject very elongated components (likely line fragments)
            aspect = max(bw, bh) / max(min(bw, bh), 1)
            if aspect < 5:
                char_boxes.append((bx, by, bx + bw, by + bh))

    if len(char_boxes) < 3:
        return []

    # Sort by x and cluster horizontally adjacent characters
    char_boxes.sort(key=lambda b: b[0])
    merge_gap = line_spacing * 1.0
    clusters: list[list[tuple[int, int, int, int]]] = [[char_boxes[0]]]

    for box in char_boxes[1:]:
        prev = clusters[-1][-1]
        h_gap = box[0] - prev[2]
        v_overlap = min(box[3], prev[3]) - max(box[1], prev[1])
        if h_gap <= merge_gap and v_overlap > 0:
            clusters[-1].append(box)
        else:
            clusters.append([box])

    # Convert clusters with >= 3 characters to TextRegionData
    padding = int(line_spacing * 0.3)
    results: list[TextRegionData] = []

    for cluster in clusters:
        if len(cluster) < 3:
            continue
        cx1 = max(0, min(b[0] for b in cluster) - padding)
        cy1 = max(0, min(b[1] for b in cluster) - padding)
        cx2 = min(rw, max(b[2] for b in cluster) + padding)
        cy2 = min(rh, max(b[3] for b in cluster) + padding)

        results.append(
            TextRegionData(
                staff_index=staff_index,
                x=cx1,
                y=region_top + cy1,
                width=cx2 - cx1,
                height=cy2 - cy1,
            )
        )

    return results
