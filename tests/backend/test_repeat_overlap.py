"""Tests for the repeat-sign overlap filter."""

import numpy as np

from mv_hofki.services.scanner.stages.base import PipelineContext, StaffData, SymbolData
from mv_hofki.services.scanner.stages.post_matching.repeat_overlap import (
    PriorityOverlapFilter,
    x_overlap_fraction,
)


def _sym(tid, x, w, staff=0):
    return SymbolData(
        staff_index=staff,
        x=x,
        y=0,
        width=w,
        height=40,
        matched_template_id=tid,
        confidence=0.7,
    )


def _ctx(symbols, config=None):
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
    ctx.metadata["template_categories"] = {
        1: "barline",
        2: "rest",
        3: "note",
        4: "barline",
        5: "other",
        6: "key_sig",
        7: "other",
    }
    ctx.metadata["template_display_names"] = {
        1: "Wiederholung Ende",
        2: "Viertelpause",
        3: "Viertel Stiel oben",
        4: "Einfacher Taktstrich",
        5: "Takt wiederholen",
        6: "Es-Dur",
        7: "Segno",
    }
    ctx.metadata["template_names"] = {
        5: "takt_wiederholen",
        6: "key_es_major",
        7: "segno",
    }
    return ctx


def test_x_overlap_fraction():
    rest = _sym(2, 100, 20)
    assert x_overlap_fraction(rest, _sym(1, 90, 40)) == 1.0
    assert x_overlap_fraction(rest, _sym(1, 112, 40)) == 0.4
    assert x_overlap_fraction(rest, _sym(1, 200, 40)) == 0.0


def test_rests_and_notes_inside_repeat_are_filtered():
    repeat = _sym(1, 100, 30)
    dot_as_rest = _sym(2, 105, 12)  # fully inside
    half_in_note = _sym(3, 120, 20)  # 10 of 20 px overlap → exactly 50 %, kept
    mostly_in_note = _sym(3, 118, 20)  # 12 of 20 px → 60 %, dropped
    far_rest = _sym(2, 300, 12)
    ctx = _ctx([repeat, dot_as_rest, half_in_note, mostly_in_note, far_rest])

    PriorityOverlapFilter().apply(ctx)

    assert not repeat.filtered
    assert dot_as_rest.filtered and dot_as_rest.filter_reason == "repeat_overlap"
    assert not half_in_note.filtered
    assert mostly_in_note.filtered
    assert not far_rest.filtered


def test_single_barlines_do_not_trigger_and_other_staff_is_ignored():
    single = _sym(4, 100, 6)
    rest = _sym(2, 98, 12)
    repeat_other_staff = _sym(1, 300, 30, staff=1)
    rest_here = _sym(2, 305, 12, staff=0)
    ctx = _ctx([single, rest, repeat_other_staff, rest_here])

    PriorityOverlapFilter().apply(ctx)

    assert not rest.filtered
    assert not rest_here.filtered


def test_threshold_is_configurable():
    repeat = _sym(1, 100, 30)
    note = _sym(3, 120, 20)  # 50 % overlap
    ctx = _ctx([repeat, note], config={"repeat_overlap_min_fraction": 0.3})
    PriorityOverlapFilter().apply(ctx)
    assert note.filtered


def test_phantom_repeat_next_to_real_one_does_not_filter():
    """A low-confidence repeat overlapping a confident one is ignored as a source."""
    phantom = _sym(1, 1279, 69)  # ":|." false hit
    phantom.confidence = 0.63
    real = _sym(1, 1322, 74)  # ".|:" real
    real.confidence = 0.74
    rest = _sym(2, 1262, 35)  # real rest, overlapped only by the phantom
    ctx = _ctx([phantom, real, rest])

    PriorityOverlapFilter().apply(ctx)

    assert not rest.filtered


def test_measure_repeat_and_key_signature_are_priority_sources():
    measure_repeat = _sym(5, 100, 60)
    slash_as_note = _sym(3, 120, 20)  # fully inside → dropped
    key_sig = _sym(6, 300, 45)
    flat_as_rest = _sym(2, 310, 12)  # fully inside → dropped
    segno = _sym(7, 500, 30)
    note_at_segno = _sym(3, 505, 20)  # "other" but not a priority sign → kept
    ctx = _ctx(
        [measure_repeat, slash_as_note, key_sig, flat_as_rest, segno, note_at_segno]
    )

    PriorityOverlapFilter().apply(ctx)

    assert slash_as_note.filtered
    assert slash_as_note.filter_reason == "measure_repeat_overlap"
    assert flat_as_rest.filtered and flat_as_rest.filter_reason == "key_sig_overlap"
    assert not note_at_segno.filtered
    assert not measure_repeat.filtered and not key_sig.filtered
