"""Tests for dynamic filter and dynamic masking stage."""

import numpy as np

from mv_hofki.services.scanner.stages.base import PipelineContext, StaffData, SymbolData
from mv_hofki.services.scanner.stages.dynamic_masking import DynamicMaskingStage
from mv_hofki.services.scanner.stages.post_matching import PostMatchingStage


def _make_ctx(symbols, template_categories=None):
    staves = [
        StaffData(
            staff_index=0,
            y_top=50,
            y_bottom=200,
            line_positions=[100, 125, 150, 175, 200],
            line_spacing=25.0,
        )
    ]
    img = np.full((300, 600), 255, dtype=np.uint8)
    ctx = PipelineContext(
        image=img,
        processed_image=img.copy(),
        staves=staves,
        symbols=symbols,
        metadata={
            "template_categories": template_categories or {},
            "template_display_names": {},
        },
        config={},
    )
    return ctx


def test_dynamic_below_staff_not_filtered():
    """A dynamic below the staff (staff_y_top < 1) should be kept."""
    sym = SymbolData(
        staff_index=0,
        x=100,
        y=210,
        width=30,
        height=20,
        matched_template_id=50,
        confidence=0.7,
        staff_y_top=-0.4,  # below bottom line
    )
    ctx = _make_ctx([sym], {50: "dynamic"})
    PostMatchingStage().process(ctx)
    assert sym.filtered is False


def test_dynamic_above_staff_filtered():
    """A dynamic with staff_y_top > 1 should be filtered."""
    sym = SymbolData(
        staff_index=0,
        x=100,
        y=140,
        width=30,
        height=20,
        matched_template_id=50,
        confidence=0.7,
        staff_y_top=2.4,  # well above bottom line
    )
    ctx = _make_ctx([sym], {50: "dynamic"})
    PostMatchingStage().process(ctx)
    assert sym.filtered is True
    assert sym.filter_reason == "dynamic_position_above_staff"


def test_dynamic_at_boundary_not_filtered():
    """A dynamic at exactly staff_y_top=1 should NOT be filtered."""
    sym = SymbolData(
        staff_index=0,
        x=100,
        y=175,
        width=30,
        height=20,
        matched_template_id=50,
        confidence=0.7,
        staff_y_top=1.0,
    )
    ctx = _make_ctx([sym], {50: "dynamic"})
    PostMatchingStage().process(ctx)
    assert sym.filtered is False


def test_non_dynamic_not_affected():
    """Non-dynamic symbols should not be affected by the dynamic filter."""
    sym = SymbolData(
        staff_index=0,
        x=100,
        y=140,
        width=30,
        height=20,
        matched_template_id=1,
        confidence=0.7,
        staff_y_top=2.4,
    )
    ctx = _make_ctx([sym], {1: "note"})
    PostMatchingStage().process(ctx)
    assert sym.filtered is False


def test_dynamic_masking_erases_unfiltered():
    """DynamicMaskingStage should erase unfiltered dynamic hitboxes."""
    sym = SymbolData(
        staff_index=0,
        x=100,
        y=210,
        width=30,
        height=20,
        matched_template_id=50,
        confidence=0.7,
        staff_y_top=-0.4,
    )
    ctx = _make_ctx([sym], {50: "dynamic"})
    # Draw some black in the hitbox area
    ctx.processed_image[210:230, 100:130] = 0

    DynamicMaskingStage().process(ctx)

    # Hitbox area should now be white
    assert np.all(ctx.processed_image[210:230, 100:130] == 255)


def test_dynamic_masking_skips_filtered():
    """DynamicMaskingStage should NOT erase filtered dynamic hitboxes."""
    sym = SymbolData(
        staff_index=0,
        x=100,
        y=140,
        width=30,
        height=20,
        matched_template_id=50,
        confidence=0.7,
        staff_y_top=2.4,
        filtered=True,
        filter_reason="dynamic_position_above_staff",
    )
    ctx = _make_ctx([sym], {50: "dynamic"})
    # Draw some black in the hitbox area
    ctx.processed_image[140:160, 100:130] = 0

    DynamicMaskingStage().process(ctx)

    # Hitbox area should still have black (not masked)
    assert np.any(ctx.processed_image[140:160, 100:130] == 0)
