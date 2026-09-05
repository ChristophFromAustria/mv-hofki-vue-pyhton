"""Tests for the staff-start (clef → key → time) priority zone."""

import numpy as np

from mv_hofki.services.scanner.stages.base import PipelineContext, StaffData, SymbolData
from mv_hofki.services.scanner.stages.post_matching.staff_start import (
    StaffStartFilter,
    StaffStartItem,
    resolve_staff_start,
)


def _item(key, x, w, cat, conf=0.7):
    return StaffStartItem(
        key=key, x_start=x, x_end=x + w, category=cat, confidence=conf
    )


def test_resolver_picks_clef_key_time_and_drops_intruders():
    items = [
        _item(0, 10, 40, "clef", 0.6),
        _item(1, 55, 30, "key_sig", 0.7),
        _item(2, 60, 20, "note", 0.9),  # flat matched as a note
        _item(3, 90, 25, "time_sig", 0.65),
        _item(4, 95, 15, "rest", 0.8),  # time sig fragment matched as rest
        _item(5, 130, 20, "note", 0.8),  # first real note
        _item(6, 60, 10, "accidental", 0.7),  # single flat inside key group
        _item(7, 40, 20, "dynamic", 0.7),  # "f" under the staff start — keep
    ]
    res = resolve_staff_start(items, staff_x_start=10, line_spacing=10)
    assert res.zone_end == 115
    assert res.chosen == {"clef": 0, "key_sig": 1, "time_sig": 3}
    assert res.drop == {2, 4, 6}
    assert res.has_key_signature


def test_resolver_without_clef_is_undefined():
    res = resolve_staff_start([_item(0, 50, 20, "note")], 10, 10)
    assert res.zone_end is None
    assert not res.drop


def test_resolver_keeps_most_confident_clef_and_drops_duplicate():
    items = [_item(0, 10, 40, "clef", 0.6), _item(1, 20, 40, "clef", 0.9)]
    res = resolve_staff_start(items, 10, 10)
    assert res.chosen["clef"] == 1
    assert res.drop == {0}


def test_key_signature_must_follow_clef_closely():
    items = [_item(0, 10, 40, "clef"), _item(1, 200, 30, "key_sig")]
    res = resolve_staff_start(items, 10, 10)
    assert "key_sig" not in res.chosen
    assert res.zone_end == 50


def test_filter_marks_symbols_in_pipeline_context():
    staff = StaffData(
        staff_index=0,
        y_top=0,
        y_bottom=40,
        line_positions=[0, 10, 20, 30, 40],
        line_spacing=10,
        x_start=10,
        x_end=1000,
    )
    cats = {1: "clef", 2: "key_sig", 3: "note", 4: "note"}

    def sym(tid, x, w):
        return SymbolData(
            staff_index=0,
            x=x,
            y=0,
            width=w,
            height=40,
            staff_x_start=x,
            staff_x_end=x + w,
            matched_template_id=tid,
            confidence=0.7,
        )

    ctx = PipelineContext(image=np.zeros((50, 1000), dtype=np.uint8))
    ctx.staves = [staff]
    ctx.symbols = [sym(1, 10, 40), sym(2, 55, 30), sym(3, 62, 15), sym(4, 200, 15)]
    ctx.metadata["template_categories"] = cats

    StaffStartFilter().apply(ctx)

    assert [s.filtered for s in ctx.symbols] == [False, False, True, False]
    assert ctx.symbols[2].filter_reason == "staff_start_zone"


def test_widest_key_signature_wins_over_narrower_subset():
    items = [
        _item(0, 10, 40, "clef", 0.6),
        _item(1, 55, 20, "key_sig", 0.68),  # 1 flat, matched inside the group
        _item(2, 55, 34, "key_sig", 0.62),  # 2 flats, the real signature
    ]
    res = resolve_staff_start(items, 10, 10)
    assert res.chosen["key_sig"] == 2
    assert res.drop == {1}
