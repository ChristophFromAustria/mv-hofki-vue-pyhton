"""Text masking: detect and remove text regions before Hough-based stages."""

from __future__ import annotations

import cv2
import numpy as np
import pytesseract  # type: ignore[import-not-found]

from mv_hofki.services.scanner.stages.base import (
    PipelineContext,
    ProcessingStage,
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

        # Use average line_spacing across all staves for thresholds
        avg_spacing = sum(s.line_spacing for s in staves) / len(staves)

        # Scan the entire image globally
        h = binary.shape[0]
        raw_regions = _detect_text_regions(binary, 0, h, avg_spacing, staff_index=0)

        # Assign each region to the nearest staff
        staff_centers = [
            (s.staff_index, float(np.mean(s.line_positions))) for s in staves
        ]
        for region in raw_regions:
            region_center_y = region.y + region.height / 2
            closest_idx = min(
                staff_centers, key=lambda sc: abs(sc[1] - region_center_y)
            )[0]
            region.staff_index = closest_idx
            region.text = _ocr_region(binary, region)
            ctx.text_regions.append(region)

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


def _ocr_region(binary: np.ndarray, region: TextRegionData) -> str | None:
    """Run Tesseract OCR on a text region and return recognized text."""
    y1 = region.y
    y2 = region.y + region.height
    x1 = region.x
    x2 = region.x + region.width

    snippet = binary[y1:y2, x1:x2]
    # Invert: tesseract expects black text on white background
    snippet = cv2.bitwise_not(snippet)

    text = pytesseract.image_to_string(snippet, lang="deu", config="--psm 7").strip()
    return text if text else None


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
    max_char_size = line_spacing * 3.0
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

    if not char_boxes:
        return []

    # Group into horizontal bands by Y-center, then cluster within each band.
    # This prevents note heads at different Y positions from splitting text clusters.
    band_height = line_spacing * 1.5
    char_boxes.sort(key=lambda b: (b[1] + b[3]) / 2)

    bands: list[list[tuple[int, int, int, int]]] = [[char_boxes[0]]]
    for box in char_boxes[1:]:
        prev_center = (bands[-1][-1][1] + bands[-1][-1][3]) / 2
        cur_center = (box[1] + box[3]) / 2
        if abs(cur_center - prev_center) <= band_height:
            bands[-1].append(box)
        else:
            bands.append([box])

    # Within each band, sort by X and cluster horizontally
    merge_gap = line_spacing * 1.0
    clusters: list[list[tuple[int, int, int, int]]] = []

    for band in bands:
        band.sort(key=lambda b: b[0])
        current_cluster: list[tuple[int, int, int, int]] = [band[0]]
        for box in band[1:]:
            prev = current_cluster[-1]
            h_gap = box[0] - prev[2]
            v_overlap = min(box[3], prev[3]) - max(box[1], prev[1])
            if h_gap <= merge_gap and v_overlap > 0:
                current_cluster.append(box)
            else:
                clusters.append(current_cluster)
                current_cluster = [box]
        clusters.append(current_cluster)

    # Convert qualifying clusters to TextRegionData.
    # Clusters with >= 3 characters are always accepted.
    # Single/double-component clusters are accepted only if each component
    # is large enough (>= 0.5 * line_spacing) to avoid catching note dots.
    min_solo_size = line_spacing * 0.5
    padding = int(line_spacing * 0.3)
    results: list[TextRegionData] = []

    for cluster in clusters:
        if len(cluster) < 3:
            # Accept small clusters only if components are large enough
            all_large = all(
                (b[2] - b[0]) >= min_solo_size and (b[3] - b[1]) >= min_solo_size
                for b in cluster
            )
            if not all_large:
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
