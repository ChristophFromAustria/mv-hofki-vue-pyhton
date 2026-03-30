"""Tests for the post-matching stage."""

import numpy as np

from mv_hofki.services.scanner.stages.base import PipelineContext, StaffData, SymbolData
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


from mv_hofki.services.scanner.stages.post_matching import (  # noqa: E402
    PostMatchingStage,
)


def _make_ctx(symbols, staves=None, display_names=None):
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
    ctx = PipelineContext(
        image=np.full((400, 600), 255, dtype=np.uint8),
        staves=staves,
        symbols=symbols,
        metadata={"template_display_names": display_names or {}},
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
