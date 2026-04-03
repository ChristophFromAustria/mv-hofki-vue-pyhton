"""Tests for the text masking pipeline stage."""

import cv2
import numpy as np

from mv_hofki.services.scanner.stages.base import PipelineContext, StaffData


def _make_staff_with_text_below():
    """Create a binary image with staff lines and text characters below."""
    img = np.full((300, 800), 255, dtype=np.uint8)

    # Draw 5 staff lines at y=50,60,70,80,90
    for y in [50, 60, 70, 80, 90]:
        img[y : y + 2, 20:780] = 0

    # Draw text-like characters below the staff (y=120..135)
    # Simulate "cresc." — 6 small rectangles spaced horizontally
    for i, x in enumerate([100, 115, 130, 145, 160, 175]):
        cv2.rectangle(img, (x, 120), (x + 8, 135), 0, -1)

    staff = StaffData(
        staff_index=0,
        y_top=20,
        y_bottom=200,
        line_positions=[50, 60, 70, 80, 90],
        line_spacing=10.0,
    )
    return img, staff


def test_text_masking_detects_text_regions():
    from mv_hofki.services.scanner.stages.text_masking import TextMaskingStage

    img, staff = _make_staff_with_text_below()
    ctx = PipelineContext(image=img, processed_image=img.copy(), staves=[staff])

    stage = TextMaskingStage()
    result = stage.process(ctx)

    assert len(result.text_regions) >= 1
    region = result.text_regions[0]
    assert region.staff_index == 0
    assert region.x >= 90
    assert region.x <= 110
    assert region.width > 50


def test_text_masking_whites_out_text_pixels():
    from mv_hofki.services.scanner.stages.text_masking import TextMaskingStage

    img, staff = _make_staff_with_text_below()
    original_black = np.sum(img[110:145, 90:200] == 0)

    ctx = PipelineContext(image=img, processed_image=img.copy(), staves=[staff])
    stage = TextMaskingStage()
    result = stage.process(ctx)

    masked_black = np.sum(result.processed_image[110:145, 90:200] == 0)
    assert masked_black < original_black


def test_text_masking_detects_text_above_staff():
    from mv_hofki.services.scanner.stages.text_masking import TextMaskingStage

    img = np.full((300, 800), 255, dtype=np.uint8)

    # Staff lines at y=100..140
    for y in [100, 110, 120, 130, 140]:
        img[y : y + 2, 20:780] = 0

    # Text above staff (e.g. "1.") at y=60..75
    for x in [200, 215, 230, 245]:
        cv2.rectangle(img, (x, 60), (x + 8, 75), 0, -1)

    staff = StaffData(
        staff_index=0,
        y_top=30,
        y_bottom=250,
        line_positions=[100, 110, 120, 130, 140],
        line_spacing=10.0,
    )
    ctx = PipelineContext(image=img, processed_image=img.copy(), staves=[staff])

    stage = TextMaskingStage()
    result = stage.process(ctx)

    above_regions = [r for r in result.text_regions if r.y < 100]
    assert len(above_regions) >= 1


def test_text_masking_no_false_positives_on_clean_staff():
    from mv_hofki.services.scanner.stages.text_masking import TextMaskingStage

    img = np.full((300, 800), 255, dtype=np.uint8)

    # Only staff lines, no text
    for y in [50, 60, 70, 80, 90]:
        img[y : y + 2, 20:780] = 0

    staff = StaffData(
        staff_index=0,
        y_top=20,
        y_bottom=200,
        line_positions=[50, 60, 70, 80, 90],
        line_spacing=10.0,
    )
    ctx = PipelineContext(image=img, processed_image=img.copy(), staves=[staff])

    stage = TextMaskingStage()
    result = stage.process(ctx)

    assert len(result.text_regions) == 0


def test_text_masking_validate():
    from mv_hofki.services.scanner.stages.text_masking import TextMaskingStage

    stage = TextMaskingStage()

    # No image → False
    ctx = PipelineContext(image=None, processed_image=None)
    assert stage.validate(ctx) is False

    # Image but no staves → False
    img = np.zeros((100, 100), dtype=np.uint8)
    ctx = PipelineContext(image=img, processed_image=img)
    assert stage.validate(ctx) is False

    # Image + staves → True
    staff = StaffData(
        staff_index=0,
        y_top=0,
        y_bottom=100,
        line_positions=[20, 30, 40, 50, 60],
        line_spacing=10.0,
    )
    ctx = PipelineContext(image=img, processed_image=img, staves=[staff])
    assert stage.validate(ctx) is True
