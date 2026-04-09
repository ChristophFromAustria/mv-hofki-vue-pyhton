"""Tests for sliding window template matching stage."""

import cv2
import numpy as np

from mv_hofki.services.scanner.stages.base import PipelineContext, StaffData
from mv_hofki.services.scanner.stages.template_matching import TemplateMatchingStage


def _make_staff(line_spacing=20):
    """Create a staff with known line spacing."""
    return StaffData(
        staff_index=0,
        y_top=10,
        y_bottom=10 + int(line_spacing * 8),
        line_positions=[10 + int(line_spacing * i) for i in range(5)],
        line_spacing=float(line_spacing),
    )


def test_template_matching_finds_exact_match():
    """A template placed in the image should be found."""
    spacing = 20
    staff = _make_staff(spacing)

    # Create a blank image
    img = np.full((200, 400), 255, dtype=np.uint8)

    # Create a "symbol" — a filled circle
    symbol = np.full((40, 20), 255, dtype=np.uint8)
    cv2.circle(symbol, (10, 20), 8, 0, -1)

    # Place it at position (100, 30) in the image
    img[30:70, 100:120] = symbol

    # The template is the same circle, declared as 2 lines high
    template_img = symbol.copy()
    height_in_lines = 2.0

    stage = TemplateMatchingStage(
        variant_images=[template_img],
        variant_template_ids=[42],
        variant_heights=[height_in_lines],
    )

    ctx = PipelineContext(
        image=img, staves=[staff], config={"confidence_threshold": 0.5}
    )
    result = stage.process(ctx)

    assert len(result.symbols) > 0
    # Should find a match near x=100
    xs = [s.x for s in result.symbols]
    assert any(95 <= x <= 125 for x in xs), f"Expected match near x=100, got {xs}"


def test_template_matching_respects_threshold():
    """No matches should be found if confidence threshold is very high."""
    spacing = 20
    staff = _make_staff(spacing)
    img = np.full((200, 400), 255, dtype=np.uint8)
    # Add some random noise
    rng = np.random.RandomState(42)
    noise = rng.randint(200, 255, img.shape, dtype=np.uint8)
    img = np.minimum(img, noise)

    template = np.full((40, 20), 255, dtype=np.uint8)
    cv2.circle(template, (10, 20), 8, 0, -1)

    stage = TemplateMatchingStage(
        variant_images=[template],
        variant_template_ids=[1],
        variant_heights=[2.0],
    )

    ctx = PipelineContext(
        image=img, staves=[staff], config={"confidence_threshold": 0.99}
    )
    result = stage.process(ctx)
    assert len(result.symbols) == 0


def test_template_matching_returns_staff_positions():
    """Detections include correct staff_y_top and staff_y_bottom."""
    spacing = 20
    staff = _make_staff(spacing)

    img = np.full((200, 400), 255, dtype=np.uint8)
    symbol = np.full((40, 20), 255, dtype=np.uint8)
    cv2.circle(symbol, (10, 20), 8, 0, -1)
    img[30:70, 100:120] = symbol

    stage = TemplateMatchingStage(
        variant_images=[symbol.copy()],
        variant_template_ids=[42],
        variant_heights=[2.0],
    )
    ctx = PipelineContext(
        image=img, staves=[staff], config={"confidence_threshold": 0.5}
    )
    result = stage.process(ctx)

    assert len(result.symbols) > 0
    sym = result.symbols[0]
    assert sym.staff_y_top is not None
    assert sym.staff_y_bottom is not None
    # Bottom line is at y=90 (line_positions[4]=10+20*4=90)
    # Symbol y ≈ 30, so staff_y_top ≈ (90-30)/20 = 3.0
    assert 2.0 <= sym.staff_y_top <= 4.0


def test_template_matching_scales_template():
    """Template should be scaled based on height_in_lines and staff spacing."""
    stage = TemplateMatchingStage(
        variant_images=[],
        variant_template_ids=[],
        variant_heights=[],
    )
    template = np.full((40, 20), 255, dtype=np.uint8)
    # height_in_lines=4, spacing=10 → target height=40 (same size, no scale)
    scaled = stage._scale_template(template, height_in_lines=4.0, line_spacing=10.0)
    assert scaled.shape[0] == 40

    # height_in_lines=4, spacing=20 → target height=80
    scaled2 = stage._scale_template(template, height_in_lines=4.0, line_spacing=20.0)
    assert scaled2.shape[0] == 80
    assert scaled2.shape[1] == 40  # width scales proportionally


def test_template_categories_splits_into_zones():
    """Templates are split by category: dynamics → below_staff, others → staff."""
    stage = TemplateMatchingStage(
        variant_images=[],
        variant_template_ids=[1, 2, 3],
        variant_heights=[],
        template_categories={1: "note", 2: "dynamic", 3: "barline"},
    )
    staff_indices, below_staff_indices = stage._split_by_zone()
    assert staff_indices == [0, 2]
    assert below_staff_indices == [1]


def test_below_staff_region_with_next_staff():
    """below_staff region goes from bottom_line - 1*ls to next staff's top line."""
    staff = StaffData(
        staff_index=0,
        y_top=10,
        y_bottom=170,
        line_positions=[50, 70, 90, 110, 130],
        line_spacing=20.0,
    )
    next_staff = StaffData(
        staff_index=1,
        y_top=210,
        y_bottom=370,
        line_positions=[250, 270, 290, 310, 330],
        line_spacing=20.0,
    )
    y_start, y_end = TemplateMatchingStage._compute_below_staff_region(
        staff, next_staff, img_height=500
    )
    # y_start = max(line_positions) - 1 * line_spacing = 130 - 20 = 110
    assert y_start == 110
    # y_end = min(next_staff.line_positions) = 250
    assert y_end == 250


def test_below_staff_region_last_staff():
    """For the last staff, below_staff region extends to page bottom."""
    staff = StaffData(
        staff_index=0,
        y_top=10,
        y_bottom=170,
        line_positions=[50, 70, 90, 110, 130],
        line_spacing=20.0,
    )
    y_start, y_end = TemplateMatchingStage._compute_below_staff_region(
        staff, None, img_height=500
    )
    assert y_start == 110
    assert y_end == 500


def test_below_staff_region_clamps_to_zero():
    """y_start should not go below 0 for staves near the top."""
    staff = StaffData(
        staff_index=0,
        y_top=0,
        y_bottom=100,
        line_positions=[5, 15, 25, 35, 45],
        line_spacing=10.0,
    )
    y_start, y_end = TemplateMatchingStage._compute_below_staff_region(
        staff, None, img_height=200
    )
    # y_start = max(5,15,25,35,45) - 10 = 35, no clamping needed here
    assert y_start == 35
    assert y_end == 200


def test_dynamic_template_scans_below_staff_region():
    """A dynamic symbol placed between two staves is found via below_staff zone."""
    spacing = 20
    # Two staves: staff 0 lines at y=50..130, staff 1 lines at y=250..330
    staff0 = StaffData(
        staff_index=0,
        y_top=10,
        y_bottom=170,
        line_positions=[50, 70, 90, 110, 130],
        line_spacing=float(spacing),
    )
    staff1 = StaffData(
        staff_index=1,
        y_top=210,
        y_bottom=370,
        line_positions=[250, 270, 290, 310, 330],
        line_spacing=float(spacing),
    )

    img = np.full((500, 400), 255, dtype=np.uint8)

    # Place a dynamic symbol at y=180 (below staff0, above staff1)
    # This is OUTSIDE staff0.y_bottom=170 so it would NOT be found
    # without the below_staff zone.
    symbol = np.full((30, 40), 255, dtype=np.uint8)
    cv2.rectangle(symbol, (5, 5), (35, 25), 0, -1)
    img[180:210, 100:140] = symbol

    stage = TemplateMatchingStage(
        variant_images=[symbol.copy()],
        variant_template_ids=[50],
        variant_heights=[1.5],
        template_categories={50: "dynamic"},
    )
    ctx = PipelineContext(
        image=img,
        staves=[staff0, staff1],
        config={"confidence_threshold": 0.5},
        metadata={"template_categories": {50: "dynamic"}},
    )
    result = stage.process(ctx)

    # Should find the dynamic between the staves
    assert len(result.symbols) > 0
    dynamic_hits = [s for s in result.symbols if s.matched_template_id == 50]
    assert len(dynamic_hits) > 0
    # Should be assigned to staff 0
    assert dynamic_hits[0].staff_index == 0
    # y should be near 180
    assert any(170 <= s.y <= 215 for s in dynamic_hits)


def test_non_dynamic_not_scanned_in_below_staff_region():
    """Non-dynamic templates only scan the staff region, not below_staff."""
    spacing = 20
    staff0 = StaffData(
        staff_index=0,
        y_top=10,
        y_bottom=170,
        line_positions=[50, 70, 90, 110, 130],
        line_spacing=float(spacing),
    )

    img = np.full((500, 400), 255, dtype=np.uint8)

    # Place a note-like symbol at y=180 — outside staff region
    symbol = np.full((30, 40), 255, dtype=np.uint8)
    cv2.rectangle(symbol, (5, 5), (35, 25), 0, -1)
    img[180:210, 100:140] = symbol

    stage = TemplateMatchingStage(
        variant_images=[symbol.copy()],
        variant_template_ids=[1],
        variant_heights=[1.5],
        template_categories={1: "note"},
    )
    ctx = PipelineContext(
        image=img,
        staves=[staff0],
        config={"confidence_threshold": 0.5},
        metadata={"template_categories": {1: "note"}},
    )
    result = stage.process(ctx)

    # Should NOT find anything — symbol is outside staff region
    note_hits = [s for s in result.symbols if 170 <= s.y <= 215]
    assert len(note_hits) == 0
