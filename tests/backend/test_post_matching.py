"""Tests for the post-matching stage."""

import numpy as np

from mv_hofki.services.scanner.stages.base import PipelineContext, StaffData, SymbolData
from mv_hofki.services.scanner.stages.post_matching import PostMatchingStage
from mv_hofki.services.scanner.stages.template_matching import TemplateMatchingStage


def test_symbol_data_has_filter_fields():
    """SymbolData should have filtered and filter_reason fields."""
    sym = SymbolData(staff_index=0, x=10, y=20, width=5, height=40)
    assert sym.filtered is False
    assert sym.filter_reason is None


def test_template_matching_exposes_display_names():
    """TemplateMatchingStage should store display names in ctx.metadata."""
    staff = StaffData(
        staff_index=0,
        y_top=10,
        y_bottom=170,
        line_positions=[10, 30, 50, 70, 90],
        line_spacing=20.0,
    )
    img = np.full((200, 400), 255, dtype=np.uint8)
    display_names = {42: "Einfacher Taktstrich"}

    stage = TemplateMatchingStage(
        variant_images=[],
        variant_template_ids=[],
        variant_heights=[],
        variant_line_spacings=[],
        template_display_names=display_names,
    )

    ctx = PipelineContext(image=img, staves=[staff], config={})
    result = stage.process(ctx)
    assert result.metadata["template_display_names"] == {42: "Einfacher Taktstrich"}


def _make_ctx(symbols, staves=None, display_names=None, categories=None):
    """Helper to create a PipelineContext for post-matching tests."""
    if staves is None:
        staves = [
            StaffData(
                staff_index=0,
                y_top=100,
                y_bottom=200,
                line_positions=[100, 125, 150, 175, 200],
                line_spacing=25.0,
            )
        ]
    metadata = {"template_display_names": display_names or {}}
    if categories is not None:
        metadata["template_categories"] = categories
    ctx = PipelineContext(
        image=np.full((400, 600), 255, dtype=np.uint8),
        staves=staves,
        symbols=symbols,
        metadata=metadata,
        config={},
    )
    return ctx


def test_barline_position_filter_marks_outside_staff():
    """A barline far outside the staff region should be filtered."""
    sym = SymbolData(
        staff_index=0,
        x=50,
        y=10,
        width=5,
        height=40,
        matched_template_id=1,
        confidence=0.8,
    )
    ctx = _make_ctx(
        symbols=[sym],
        display_names={1: "Einfacher Taktstrich"},
    )
    stage = PostMatchingStage()
    result = stage.process(ctx)
    assert result.symbols[0].filtered is True
    assert result.symbols[0].filter_reason == "barline_position_outside_staff"


def test_barline_position_filter_keeps_inside_staff():
    """A barline within the staff region should not be filtered."""
    sym = SymbolData(
        staff_index=0,
        x=50,
        y=120,
        width=5,
        height=60,
        matched_template_id=1,
        confidence=0.8,
    )
    ctx = _make_ctx(
        symbols=[sym],
        display_names={1: "Einfacher Taktstrich"},
    )
    stage = PostMatchingStage()
    result = stage.process(ctx)
    assert result.symbols[0].filtered is False


def test_barline_overlap_with_priority_symbol():
    """A barline overlapping a priority symbol should be filtered."""
    barline = SymbolData(
        staff_index=0,
        x=100,
        y=100,
        width=5,
        height=100,
        matched_template_id=1,
        confidence=0.9,
    )
    note = SymbolData(
        staff_index=0,
        x=98,
        y=110,
        width=20,
        height=50,
        matched_template_id=2,
        confidence=0.7,
    )
    ctx = _make_ctx(
        symbols=[barline, note],
        display_names={1: "Einfacher Taktstrich", 2: "Viertelnote"},
    )
    stage = PostMatchingStage()
    result = stage.process(ctx)
    assert result.symbols[0].filtered is True  # barline filtered
    assert "Viertelnote" in result.symbols[0].filter_reason
    assert result.symbols[1].filtered is False  # note kept


def test_barline_overlap_with_repeat_symbol():
    """A barline overlapping a repeat sign should be filtered."""
    barline = SymbolData(
        staff_index=0,
        x=100,
        y=100,
        width=5,
        height=100,
        matched_template_id=1,
        confidence=0.95,
    )
    repeat = SymbolData(
        staff_index=0,
        x=98,
        y=100,
        width=15,
        height=100,
        matched_template_id=3,
        confidence=0.6,
    )
    ctx = _make_ctx(
        symbols=[barline, repeat],
        display_names={1: "Einfacher Taktstrich", 3: "Wiederholung Ende"},
    )
    stage = PostMatchingStage()
    result = stage.process(ctx)
    assert (
        result.symbols[0].filtered is True
    )  # barline filtered even with higher confidence
    assert result.symbols[1].filtered is False


def test_barline_overlap_non_priority_lower_confidence_filtered():
    """When overlapping a non-priority symbol, the lower confidence is filtered."""
    barline = SymbolData(
        staff_index=0,
        x=100,
        y=100,
        width=5,
        height=100,
        matched_template_id=1,
        confidence=0.6,
    )
    other = SymbolData(
        staff_index=0,
        x=102,
        y=110,
        width=10,
        height=30,
        matched_template_id=4,
        confidence=0.8,
    )
    ctx = _make_ctx(
        symbols=[barline, other],
        display_names={1: "Einfacher Taktstrich", 4: "Staccato"},
    )
    stage = PostMatchingStage()
    result = stage.process(ctx)
    assert result.symbols[0].filtered is True  # barline has lower confidence
    assert result.symbols[0].filter_reason == "overlap_lower_confidence"
    assert result.symbols[1].filtered is False


def test_no_overlap_no_filter():
    """Non-overlapping symbols should not be filtered."""
    barline = SymbolData(
        staff_index=0,
        x=100,
        y=100,
        width=5,
        height=100,
        matched_template_id=1,
        confidence=0.8,
    )
    note = SymbolData(
        staff_index=0,
        x=200,
        y=110,
        width=20,
        height=50,
        matched_template_id=2,
        confidence=0.7,
    )
    ctx = _make_ctx(
        symbols=[barline, note],
        display_names={1: "Einfacher Taktstrich", 2: "Viertelnote"},
    )
    stage = PostMatchingStage()
    result = stage.process(ctx)
    assert result.symbols[0].filtered is False
    assert result.symbols[1].filtered is False


def test_post_matching_validate_with_no_symbols():
    """PostMatchingStage.validate should return False with no symbols."""
    ctx = PipelineContext(
        image=np.full((200, 400), 255, dtype=np.uint8),
        staves=[],
        symbols=[],
        metadata={},
        config={},
    )
    stage = PostMatchingStage()
    assert stage.validate(ctx) is False


def test_post_matching_validate_with_symbols():
    """PostMatchingStage.validate should return True with symbols."""
    ctx = _make_ctx(
        symbols=[SymbolData(staff_index=0, x=10, y=100, width=5, height=40)],
        display_names={},
    )
    stage = PostMatchingStage()
    assert stage.validate(ctx) is True


def test_barline_filter_ignores_non_barline_symbols():
    """Non-barline symbols should not be affected by the barline filter."""
    note = SymbolData(
        staff_index=0,
        x=50,
        y=10,
        width=20,
        height=40,
        matched_template_id=2,
        confidence=0.8,
    )
    ctx = _make_ctx(
        symbols=[note],
        display_names={2: "Viertelnote"},
    )
    stage = PostMatchingStage()
    result = stage.process(ctx)
    assert result.symbols[0].filtered is False


def test_barline_position_at_boundary():
    """A barline right at the line_spacing boundary should NOT be filtered."""
    # line_positions[0]=100, line_positions[-1]=200, line_spacing=25
    # Allowed hitbox range: [75, 225]
    # Hitbox top=75 (exactly at boundary), bottom=175
    sym = SymbolData(
        staff_index=0,
        x=50,
        y=75,
        width=5,
        height=100,
        matched_template_id=1,
        confidence=0.8,
    )
    ctx = _make_ctx(
        symbols=[sym],
        display_names={1: "Einfacher Taktstrich"},
    )
    stage = PostMatchingStage()
    result = stage.process(ctx)
    # sym.y=75 equals allowed_top → NOT filtered
    assert result.symbols[0].filtered is False


def test_multiple_staves():
    """Filter should work correctly across multiple staves."""
    staves = [
        StaffData(
            staff_index=0,
            y_top=50,
            y_bottom=150,
            line_positions=[50, 75, 100, 125, 150],
            line_spacing=25.0,
        ),
        StaffData(
            staff_index=1,
            y_top=250,
            y_bottom=350,
            line_positions=[250, 275, 300, 325, 350],
            line_spacing=25.0,
        ),
    ]
    # Barline on staff 0 — valid position
    b0 = SymbolData(
        staff_index=0,
        x=100,
        y=70,
        width=5,
        height=60,
        matched_template_id=1,
        confidence=0.8,
    )
    # Barline on staff 1 — way outside
    b1 = SymbolData(
        staff_index=1,
        x=100,
        y=10,
        width=5,
        height=40,
        matched_template_id=1,
        confidence=0.8,
    )
    ctx = _make_ctx(
        symbols=[b0, b1],
        staves=staves,
        display_names={1: "Einfacher Taktstrich"},
    )
    stage = PostMatchingStage()
    result = stage.process(ctx)
    assert result.symbols[0].filtered is False  # valid on staff 0
    assert result.symbols[1].filtered is True  # outside staff 1


# --- Rest position filter tests ---


def test_rest_position_filter_marks_outside_staff():
    """A rest with hitbox above the staff should be filtered."""
    # line_positions[0]=100, line_spacing=25 → allowed_top=75
    # sym.y=50 < 75 → filtered
    sym = SymbolData(
        staff_index=0,
        x=50,
        y=50,
        width=10,
        height=20,
        matched_template_id=2,
        confidence=0.7,
    )
    ctx = _make_ctx(
        symbols=[sym],
        categories={2: "rest"},
    )
    stage = PostMatchingStage()
    result = stage.process(ctx)
    assert result.symbols[0].filtered is True
    assert result.symbols[0].filter_reason == "rest_position_outside_staff"


def test_rest_position_filter_marks_below_staff():
    """A rest with hitbox below the staff should be filtered."""
    # line_positions[-1]=200, line_spacing=25 → allowed_bottom=225
    # sym.y + height = 210 + 20 = 230 > 225 → filtered
    sym = SymbolData(
        staff_index=0,
        x=50,
        y=210,
        width=10,
        height=20,
        matched_template_id=2,
        confidence=0.7,
    )
    ctx = _make_ctx(
        symbols=[sym],
        categories={2: "rest"},
    )
    stage = PostMatchingStage()
    result = stage.process(ctx)
    assert result.symbols[0].filtered is True
    assert result.symbols[0].filter_reason == "rest_position_outside_staff"


def test_rest_position_filter_keeps_inside_staff():
    """A rest within the staff region should not be filtered."""
    # sym.y=130, sym.y+height=160 → within [75, 225]
    sym = SymbolData(
        staff_index=0,
        x=50,
        y=130,
        width=10,
        height=30,
        matched_template_id=2,
        confidence=0.7,
    )
    ctx = _make_ctx(
        symbols=[sym],
        categories={2: "rest"},
    )
    stage = PostMatchingStage()
    result = stage.process(ctx)
    assert result.symbols[0].filtered is False


def test_rest_position_at_boundary():
    """A rest exactly at the allowed boundary should NOT be filtered."""
    # allowed_top=75, sym.y=75 → exactly at boundary
    sym = SymbolData(
        staff_index=0,
        x=50,
        y=75,
        width=10,
        height=30,
        matched_template_id=2,
        confidence=0.7,
    )
    ctx = _make_ctx(
        symbols=[sym],
        categories={2: "rest"},
    )
    stage = PostMatchingStage()
    result = stage.process(ctx)
    assert result.symbols[0].filtered is False


def test_rest_filter_ignores_non_rest_symbols():
    """Non-rest symbols should not be affected by the rest filter."""
    sym = SymbolData(
        staff_index=0,
        x=50,
        y=50,
        width=10,
        height=20,
        matched_template_id=3,
        confidence=0.7,
    )
    ctx = _make_ctx(
        symbols=[sym],
        categories={3: "note"},
    )
    stage = PostMatchingStage()
    result = stage.process(ctx)
    assert result.symbols[0].filtered is False
