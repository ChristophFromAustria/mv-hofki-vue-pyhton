"""Deskew algorithms for staff line straightening.

Two strategies are available:
- ``deskew_hough``: Morphologically enhanced Hough line detection.
- ``deskew_projection``: Two-pass angle sweep maximising horizontal projection
  sharpness — more robust for staff-line-heavy sheet music.

Both accept a binary image (0 = black, 255 = white) and return a rotated copy.
"""

from __future__ import annotations

import cv2
import numpy as np


def _rotate(img: np.ndarray, angle_deg: float) -> np.ndarray:
    """Rotate *img* by *angle_deg* around its center, padding with white."""
    h, w = img.shape[:2]
    center = (w // 2, h // 2)
    matrix = cv2.getRotationMatrix2D(center, angle_deg, 1.0)
    return cv2.warpAffine(img, matrix, (w, h), flags=cv2.INTER_LINEAR, borderValue=255)


# ---------------------------------------------------------------------------
# Strategy A – Improved Hough
# ---------------------------------------------------------------------------


def deskew_hough(img: np.ndarray) -> np.ndarray:
    """Detect skew via morphologically filtered Hough lines and correct it.

    Improvements over the legacy deskew:
    * A long horizontal morphological closing emphasises staff lines and
      suppresses note heads, stems and text before edge detection.
    * Line length is weighted when computing the median angle so that
      short spurious segments have less influence.
    """
    # Emphasise horizontal structures with a wide closing kernel
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (80, 1))
    enhanced = cv2.morphologyEx(img, cv2.MORPH_CLOSE, kernel)

    edges = cv2.Canny(enhanced, 50, 150, apertureSize=3)
    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180,
        threshold=80,
        minLineLength=60,
        maxLineGap=10,
    )

    if lines is None:
        return img

    angles: list[float] = []
    weights: list[float] = []
    for line in lines:
        x1, y1, x2, y2 = line[0]
        angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))
        if abs(angle) < 5:
            length = np.hypot(x2 - x1, y2 - y1)
            angles.append(angle)
            weights.append(length)

    if not angles:
        return img

    # Weighted median: sort by angle, pick the value at cumulative-weight midpoint
    order = np.argsort(angles)
    sorted_angles = np.array(angles)[order]
    sorted_weights = np.array(weights)[order]
    cum = np.cumsum(sorted_weights)
    mid = cum[-1] / 2.0
    idx = int(np.searchsorted(cum, mid))
    median_angle = float(sorted_angles[idx])

    if abs(median_angle) < 0.05:
        return img

    return _rotate(img, median_angle)


# ---------------------------------------------------------------------------
# Strategy B – Projection-based angle sweep
# ---------------------------------------------------------------------------


def _projection_sharpness(img: np.ndarray, angle: float) -> float:
    """Return peak value of horizontal projection after rotating by *angle*."""
    rotated = _rotate(img, angle)
    projection = np.sum(rotated == 0, axis=1).astype(float)
    return float(projection.max())


def deskew_projection(img: np.ndarray) -> np.ndarray:
    """Find the rotation angle that maximises horizontal projection sharpness.

    Pass 1: coarse sweep from -3 to +3 degrees in 0.1-degree steps.
    Pass 2: fine sweep +/- 0.15 degrees around the best coarse angle in
    0.02-degree steps.
    """
    if np.all(img == 255):
        return img

    # Coarse pass
    coarse_angles = np.arange(-3.0, 3.05, 0.1)
    best_angle = 0.0
    best_score = -1.0
    for a in coarse_angles:
        score = _projection_sharpness(img, a)
        if score > best_score:
            best_score = score
            best_angle = float(a)

    # Fine pass
    fine_angles = np.arange(best_angle - 0.15, best_angle + 0.16, 0.02)
    for a in fine_angles:
        score = _projection_sharpness(img, a)
        if score > best_score:
            best_score = score
            best_angle = float(a)

    if abs(best_angle) < 0.02:
        return img

    return _rotate(img, best_angle)
