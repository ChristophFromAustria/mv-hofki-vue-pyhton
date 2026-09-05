"""Tests for the stem-direction duplicate filter."""

import numpy as np

from mv_hofki.services.scanner.stages.base import PipelineContext, StaffData, SymbolData
from mv_hofki.services.scanner.stages.post_matching.stem_direction_filter import (
    StemDirectionFilter,
)

UP, DOWN, WHOLE = 3, 55, 1


def _note(tid, x, sy_top, sy_bot, conf=0.7, w=40, variant=None):
    return SymbolData(
        staff_index=0,
        x=x,
        y=0,
        width=w,
        height=40,
        staff_y_top=sy_top,
        staff_y_bottom=sy_bot,
        matched_template_id=tid,
        matched_variant_id=variant,
        confidence=conf,
    )


def _ctx(symbols, offsets=None, config=None):
    ctx = PipelineContext(
        image=np.zeros((50, 500), dtype=np.uint8), config=config or {}
    )
    ctx.staves = [
        StaffData(
            staff_index=0,
            y_top=0,
            y_bottom=40,
            line_positions=[0, 10, 20, 30, 40],
            line_spacing=10,
        )
    ]
    ctx.symbols = symbols
    ctx.metadata["template_categories"] = {UP: "note", DOWN: "note", WHOLE: "note"}
    ctx.metadata["template_names"] = {
        UP: "quarter_note",
        DOWN: "viertelnote_steil_unten",
        WHOLE: "whole_note",
    }
    ctx.metadata["template_display_names"] = {
        UP: "Viertel Stiel oben",
        DOWN: "Viertel Steil unten",
        WHOLE: "Ganze Note",
    }
    ctx.metadata["variant_anchor_offsets"] = offsets or {}
    return ctx


def test_low_head_keeps_stem_up():
    # Head on the 2nd line (step 2): up-box bottom at 0.5 lines, down-box top at 1.5
    up = _note(UP, 100, 4.0, 0.5)
    down = _note(DOWN, 104, 1.5, -2.0, conf=0.9)  # even more confident — irrelevant
    ctx = _ctx([up, down])
    StemDirectionFilter().apply(ctx)
    assert not up.filtered
    assert down.filtered and down.filter_reason == "stem_direction_up"


def test_high_head_keeps_stem_down():
    # Head on the 4th line (step 6): up-box bottom 2.5, down-box top 3.5
    up = _note(UP, 100, 6.0, 2.5)
    down = _note(DOWN, 102, 3.5, 0.0)
    ctx = _ctx([up, down])
    StemDirectionFilter().apply(ctx)
    assert up.filtered and up.filter_reason == "stem_direction_down"
    assert not down.filtered


def test_middle_line_uses_confidence():
    # Head on the middle line (step 4): up-box bottom 1.5, down-box top 2.5
    up = _note(UP, 100, 5.0, 1.5, conf=0.6)
    down = _note(DOWN, 100, 2.5, -1.0, conf=0.8)
    ctx = _ctx([up, down])
    StemDirectionFilter().apply(ctx)
    assert up.filtered and up.filter_reason == "stem_direction_confidence"
    assert not down.filtered


def test_different_heads_are_a_chord_and_kept():
    up = _note(UP, 100, 4.0, 0.5)  # head step 2
    down = _note(DOWN, 102, 4.5, 1.0)  # head step 8
    ctx = _ctx([up, down])
    StemDirectionFilter().apply(ctx)
    assert not up.filtered and not down.filtered


def test_no_overlap_or_same_stem_untouched():
    a = _note(UP, 100, 4.0, 0.5)
    b = _note(DOWN, 160, 1.5, -2.0)  # far away
    c = _note(UP, 105, 4.0, 0.5)  # same stem direction, overlapping
    ctx = _ctx([a, b, c])
    StemDirectionFilter().apply(ctx)
    assert not any(s.filtered for s in (a, b, c))


def test_anchor_offset_is_respected():
    # Without offset the boxes disagree by 1.5 lines (3 steps) → chord.
    # The down variant's anchor is corrected 1.5 lines further down → same head.
    up = _note(UP, 100, 4.0, 0.5)  # head step 2
    down = _note(DOWN, 104, 3.0, -0.5, variant=77)  # head step 5 before correction
    ctx = _ctx([up, down], offsets={77: 1.5})
    StemDirectionFilter().apply(ctx)
    assert down.filtered and not up.filtered
