"""Shared utilities for scanner pipeline stages."""

from __future__ import annotations

import cv2
import numpy as np


def expand_to_connected(
    binary: np.ndarray,
    x_min: int,
    y_min: int,
    x_max: int,
    y_max: int,
    region_top: int,
    region_bottom: int,
) -> tuple[int, int, int, int]:
    """Expand a bounding box to cover all connected black pixels.

    Uses the specified region for connected component analysis
    so the expansion can reach the full extent of connected symbols.

    Parameters
    ----------
    binary : grayscale image (0=black, 255=white)
    x_min, y_min, x_max, y_max : seed bounding box (absolute coords)
    region_top, region_bottom : Y limits for CC analysis (absolute coords)

    Returns (x_min, y_min, x_max, y_max) of expanded box.
    """
    h, w = binary.shape[:2]
    roi_y1 = max(0, region_top)
    roi_y2 = min(h, region_bottom)

    roi = binary[roi_y1:roi_y2, :]
    inverted = cv2.bitwise_not(roi)

    _, labels = cv2.connectedComponents(inverted)

    # Find which labels touch the seed box (relative to ROI)
    seed_y1 = max(0, y_min - roi_y1)
    seed_y2 = min(roi_y2 - roi_y1, y_max - roi_y1)
    seed_x1 = max(0, x_min)
    seed_x2 = min(w, x_max)

    if seed_y1 >= seed_y2 or seed_x1 >= seed_x2:
        return x_min, y_min, x_max, y_max

    seed_region = labels[seed_y1:seed_y2, seed_x1:seed_x2]
    touching_labels = set(np.unique(seed_region)) - {0}

    if not touching_labels:
        return x_min, y_min, x_max, y_max

    # Find the bounding box of all pixels with those labels
    mask = np.isin(labels, list(touching_labels))
    coords = cv2.findNonZero(mask.astype(np.uint8))
    if coords is None:
        return x_min, y_min, x_max, y_max

    rx, ry, rw, rh = cv2.boundingRect(coords)
    return rx, roi_y1 + ry, rx + rw, roi_y1 + ry + rh
