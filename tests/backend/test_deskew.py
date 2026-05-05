"""Tests for deskew algorithms."""

import cv2
import numpy as np

from mv_hofki.services.scanner.deskew import deskew_hough, deskew_projection


def _make_tilted_staff_image(
    angle_deg: float, width: int = 800, height: int = 400
) -> np.ndarray:
    """Create a synthetic binary image with 5 tilted staff lines."""
    img = np.full((height, width), 255, dtype=np.uint8)
    center = (width // 2, height // 2)
    matrix = cv2.getRotationMatrix2D(center, -angle_deg, 1.0)

    # Draw 5 horizontal lines at even spacing
    line_ys = [150, 170, 190, 210, 230]
    straight = np.full((height, width), 255, dtype=np.uint8)
    for y in line_ys:
        cv2.line(straight, (0, y), (width, y), 0, 2)

    # Rotate to introduce tilt
    img = cv2.warpAffine(straight, matrix, (width, height), borderValue=255)
    return img


def test_deskew_hough_corrects_tilt():
    img = _make_tilted_staff_image(2.0)
    corrected = deskew_hough(img)
    proj_before = np.sum(img == 0, axis=1).astype(float)
    proj_after = np.sum(corrected == 0, axis=1).astype(float)
    assert proj_after.max() > proj_before.max()


def test_deskew_hough_no_change_when_straight():
    img = _make_tilted_staff_image(0.0)
    corrected = deskew_hough(img)
    diff = np.abs(img.astype(float) - corrected.astype(float))
    assert diff.mean() < 1.0


def test_deskew_projection_corrects_tilt():
    img = _make_tilted_staff_image(2.0)
    corrected = deskew_projection(img)
    proj_before = np.sum(img == 0, axis=1).astype(float)
    proj_after = np.sum(corrected == 0, axis=1).astype(float)
    assert proj_after.max() > proj_before.max()


def test_deskew_projection_corrects_negative_tilt():
    img = _make_tilted_staff_image(-1.5)
    corrected = deskew_projection(img)
    proj_before = np.sum(img == 0, axis=1).astype(float)
    proj_after = np.sum(corrected == 0, axis=1).astype(float)
    assert proj_after.max() > proj_before.max()


def test_deskew_projection_no_change_when_straight():
    img = _make_tilted_staff_image(0.0)
    corrected = deskew_projection(img)
    diff = np.abs(img.astype(float) - corrected.astype(float))
    assert diff.mean() < 1.0


def test_deskew_projection_handles_blank_image():
    blank = np.full((200, 400), 255, dtype=np.uint8)
    result = deskew_projection(blank)
    assert result.shape == blank.shape


def test_deskew_hough_handles_blank_image():
    blank = np.full((200, 400), 255, dtype=np.uint8)
    result = deskew_hough(blank)
    assert result.shape == blank.shape
