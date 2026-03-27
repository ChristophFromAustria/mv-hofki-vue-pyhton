"""Tests for new template matching features."""

import cv2
import numpy as np

from mv_hofki.services.scanner.stages.base import PipelineContext, StaffData
from mv_hofki.services.scanner.stages.template_matching import TemplateMatchingStage


def _make_staff(line_spacing=20):
    return StaffData(
        staff_index=0,
        y_top=10,
        y_bottom=10 + int(line_spacing * 8),
        line_positions=[10 + int(line_spacing * i) for i in range(5)],
        line_spacing=float(line_spacing),
    )


def _make_image_with_symbol(img_shape=(200, 400), symbol_pos=(100, 30)):
    """Create a white image with a filled circle symbol."""
    img = np.full(img_shape, 255, dtype=np.uint8)
    symbol = np.full((40, 20), 255, dtype=np.uint8)
    cv2.circle(symbol, (10, 20), 8, 0, -1)
    x, y = symbol_pos
    img[y : y + 40, x : x + 20] = symbol
    return img, symbol.copy()


def _run_stage(config: dict, variant_line_spacings=None):
    """Helper: build stage + context and run process()."""
    img, symbol = _make_image_with_symbol()
    staff = _make_staff(20)
    stage = TemplateMatchingStage(
        variant_images=[symbol],
        variant_template_ids=[1],
        variant_heights=[2.0],
        variant_line_spacings=variant_line_spacings,
    )
    base_config: dict = {"confidence_threshold": 0.5}
    base_config.update(config)
    ctx = PipelineContext(image=img, staves=[staff], config=base_config)
    return stage.process(ctx)


# ------------------------------------------------------------------
# Edge matching
# ------------------------------------------------------------------


def test_edge_matching_finds_symbol():
    result = _run_stage({"edge_matching_enabled": True})
    assert len(result.symbols) > 0
    xs = [s.x for s in result.symbols]
    assert any(90 <= x <= 130 for x in xs), f"Expected match near x=100, got {xs}"


# ------------------------------------------------------------------
# Multi-scale search
# ------------------------------------------------------------------


def test_multi_scale_finds_slightly_misscaled_symbol():
    """With multi-scale enabled, a slight mismatch in line spacing is handled."""
    result = _run_stage(
        {
            "multi_scale_enabled": True,
            "multi_scale_range": 0.1,
            "multi_scale_steps": 5,
            "confidence_threshold": 0.4,
        },
        variant_line_spacings=[19.0],
    )
    assert len(result.symbols) > 0
    xs = [s.x for s in result.symbols]
    assert any(90 <= x <= 130 for x in xs), f"Expected match near x=100, got {xs}"


def test_multi_scale_disabled_uses_single_scale():
    """Even without multi-scale, exact-match templates are found."""
    result = _run_stage({"multi_scale_enabled": False})
    assert len(result.symbols) > 0
    xs = [s.x for s in result.symbols]
    assert any(90 <= x <= 130 for x in xs), f"Expected match near x=100, got {xs}"


# ------------------------------------------------------------------
# Masked matching
# ------------------------------------------------------------------


def test_masked_matching_finds_symbol():
    result = _run_stage(
        {
            "masked_matching_enabled": True,
            "mask_threshold": 200,
            "confidence_threshold": 0.9,
            "matching_method": "TM_CCORR_NORMED",
        }
    )
    assert len(result.symbols) > 0
    xs = [s.x for s in result.symbols]
    assert any(90 <= x <= 130 for x in xs), f"Expected match near x=100, got {xs}"


# ------------------------------------------------------------------
# Dilate NMS
# ------------------------------------------------------------------


def test_dilate_nms_finds_symbol():
    result = _run_stage({"nms_method": "dilate"})
    assert len(result.symbols) > 0
    xs = [s.x for s in result.symbols]
    assert any(90 <= x <= 130 for x in xs), f"Expected match near x=100, got {xs}"


def test_dilate_nms_suppresses_duplicates():
    """Low threshold produces many raw hits — dilate NMS collapses them."""
    result = _run_stage({"nms_method": "dilate", "confidence_threshold": 0.3})
    # With dilate NMS, nearby detections should be collapsed
    assert len(result.symbols) >= 1
    # All surviving detections should be spatially distinct
    for i, a in enumerate(result.symbols):
        for b in result.symbols[i + 1 :]:
            if a.staff_index == b.staff_index:
                dist = ((a.x - b.x) ** 2 + (a.y - b.y) ** 2) ** 0.5
                # They should not be extremely close (within half-template-width)
                assert dist >= a.width / 2.0 or dist >= b.width / 2.0


# ------------------------------------------------------------------
# Matching method variants
# ------------------------------------------------------------------


def test_matching_method_sqdiff():
    result = _run_stage(
        {"matching_method": "TM_SQDIFF_NORMED", "confidence_threshold": 0.5}
    )
    assert len(result.symbols) > 0
    xs = [s.x for s in result.symbols]
    assert any(90 <= x <= 130 for x in xs), f"Expected match near x=100, got {xs}"


def test_matching_method_ccorr():
    result = _run_stage(
        {"matching_method": "TM_CCORR_NORMED", "confidence_threshold": 0.5}
    )
    assert len(result.symbols) > 0
    xs = [s.x for s in result.symbols]
    assert any(90 <= x <= 130 for x in xs), f"Expected match near x=100, got {xs}"


# ------------------------------------------------------------------
# NMS IoU threshold
# ------------------------------------------------------------------


def test_nms_iou_threshold_affects_suppression():
    """A very high IoU threshold keeps more overlapping detections."""
    # Two symbols placed close together (slight overlap)
    img = np.full((200, 400), 255, dtype=np.uint8)
    symbol = np.full((40, 20), 255, dtype=np.uint8)
    cv2.circle(symbol, (10, 20), 8, 0, -1)
    # Place at x=100 and x=112 (12px apart, 20px wide → significant overlap)
    img[30:70, 100:120] = symbol
    img[30:70, 112:132] = symbol

    staff = _make_staff(20)
    template = symbol.copy()

    # Low IoU threshold → aggressive suppression → fewer detections
    stage = TemplateMatchingStage(
        variant_images=[template],
        variant_template_ids=[1],
        variant_heights=[2.0],
    )
    ctx_low = PipelineContext(
        image=img.copy(),
        staves=[staff],
        config={"confidence_threshold": 0.5, "nms_iou_threshold": 0.1},
    )
    result_low = stage.process(ctx_low)

    # High IoU threshold → relaxed suppression → more detections
    stage2 = TemplateMatchingStage(
        variant_images=[template],
        variant_template_ids=[1],
        variant_heights=[2.0],
    )
    ctx_high = PipelineContext(
        image=img.copy(),
        staves=[staff],
        config={"confidence_threshold": 0.5, "nms_iou_threshold": 0.95},
    )
    result_high = stage2.process(ctx_high)

    # With high threshold, more detections should survive
    assert len(result_high.symbols) >= len(result_low.symbols)


# ------------------------------------------------------------------
# Staff removal before matching
# ------------------------------------------------------------------


def test_staff_removal_before_matching_config():
    """Verify staff removal stage exists and can process."""
    from mv_hofki.services.scanner.stages.staff_removal import StaffRemovalStage

    img = np.full((200, 400), 255, dtype=np.uint8)
    # Draw staff lines
    for i in range(5):
        y = 30 + i * 20
        img[y : y + 2, 20:380] = 0

    staff = StaffData(
        staff_index=0,
        y_top=0,
        y_bottom=180,
        line_positions=[30, 50, 70, 90, 110],
        line_spacing=20.0,
    )
    ctx = PipelineContext(image=img.copy(), staves=[staff])
    stage = StaffRemovalStage()
    result = stage.process(ctx)

    # Lines should be mostly removed
    for line_y in [30, 50, 70, 90, 110]:
        row_black_after = np.sum(result.image[line_y : line_y + 2, :] == 0)
        row_black_before = np.sum(img[line_y : line_y + 2, :] == 0)
        assert row_black_after < row_black_before
