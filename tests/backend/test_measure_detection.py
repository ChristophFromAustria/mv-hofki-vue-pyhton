"""Tests for MeasureDetectionStage."""

import numpy as np

from mv_hofki.services.scanner.stages.base import (
    PipelineContext,
    StaffData,
    SymbolData,
)
from mv_hofki.services.scanner.stages.measure_detection import MeasureDetectionStage


def _make_staff(staff_index=0, x_start=0, x_end=800):
    return StaffData(
        staff_index=staff_index,
        y_top=50,
        y_bottom=100,
        line_positions=[50, 60, 70, 80, 90],
        line_spacing=10.0,
        x_start=x_start,
        x_end=x_end,
    )


def _ctx_with_symbols(staves, symbols, template_categories=None):
    ctx = PipelineContext(image=np.zeros((100, 800), dtype=np.uint8))
    ctx.staves = staves
    ctx.symbols = symbols
    ctx.metadata["template_categories"] = template_categories or {}
    return ctx


def test_barline_start_is_measure_boundary():
    """Measure boundary should be at barline start (x), not barline end (x+width)."""
    staff = _make_staff(x_start=0, x_end=700)
    symbols = [
        SymbolData(
            staff_index=0,
            x=100,
            y=50,
            width=10,
            height=50,
            staff_x_start=100,
            staff_x_end=110,
            matched_template_id=10,
        ),
    ]
    categories = {10: "barline"}
    ctx = _ctx_with_symbols([staff], symbols, categories)
    result = MeasureDetectionStage().process(ctx)

    assert len(result.measures) == 2
    # First measure: staff x_start to barline start
    assert result.measures[0].x_start == 0
    assert result.measures[0].x_end == 100
    # Second measure: barline start to staff x_end
    assert result.measures[1].x_start == 100
    assert result.measures[1].x_end == 700


def test_staff_x_bounds_used_instead_of_symbol_minmax():
    """Measures should use staff.x_start/x_end, not symbol min/max."""
    staff = _make_staff(x_start=5, x_end=795)
    symbols = [
        # Note at x=50 — should NOT define measure start
        SymbolData(
            staff_index=0,
            x=50,
            y=60,
            width=20,
            height=30,
            staff_x_start=50,
            staff_x_end=70,
            matched_template_id=1,
        ),
        # Note at x=600 — should NOT define measure end
        SymbolData(
            staff_index=0,
            x=600,
            y=60,
            width=20,
            height=30,
            staff_x_start=600,
            staff_x_end=620,
            matched_template_id=1,
        ),
    ]
    categories = {1: "note"}
    ctx = _ctx_with_symbols([staff], symbols, categories)
    result = MeasureDetectionStage().process(ctx)

    assert len(result.measures) == 1
    assert result.measures[0].x_start == 5
    assert result.measures[0].x_end == 795


def test_single_staff_three_barlines_four_measures():
    staff = _make_staff(x_start=10, x_end=620)
    symbols = [
        SymbolData(
            staff_index=0,
            x=10,
            y=60,
            width=20,
            height=30,
            staff_x_start=10,
            staff_x_end=30,
            matched_template_id=1,
        ),
        SymbolData(
            staff_index=0,
            x=100,
            y=50,
            width=5,
            height=50,
            staff_x_start=100,
            staff_x_end=105,
            matched_template_id=10,
        ),
        SymbolData(
            staff_index=0,
            x=300,
            y=50,
            width=5,
            height=50,
            staff_x_start=300,
            staff_x_end=305,
            matched_template_id=10,
        ),
        SymbolData(
            staff_index=0,
            x=500,
            y=50,
            width=5,
            height=50,
            staff_x_start=500,
            staff_x_end=505,
            matched_template_id=10,
        ),
        SymbolData(
            staff_index=0,
            x=600,
            y=60,
            width=20,
            height=30,
            staff_x_start=600,
            staff_x_end=620,
            matched_template_id=1,
        ),
    ]
    categories = {1: "note", 10: "barline"}
    ctx = _ctx_with_symbols([staff], symbols, categories)
    result = MeasureDetectionStage().process(ctx)

    assert len(result.measures) == 4
    assert result.measures[0].measure_number_in_staff == 1
    assert result.measures[0].x_start == 10
    assert result.measures[0].x_end == 100
    assert result.measures[1].measure_number_in_staff == 2
    assert result.measures[1].x_start == 100
    assert result.measures[1].x_end == 300
    assert result.measures[2].x_start == 300
    assert result.measures[2].x_end == 500
    assert result.measures[3].measure_number_in_staff == 4
    assert result.measures[3].x_start == 500
    assert result.measures[3].x_end == 620


def test_two_staffs_global_numbering():
    staff0 = _make_staff(staff_index=0, x_start=10, x_end=370)
    staff1 = StaffData(
        staff_index=1,
        y_top=150,
        y_bottom=200,
        line_positions=[150, 160, 170, 180, 190],
        line_spacing=10.0,
        x_start=10,
        x_end=370,
    )
    symbols = [
        SymbolData(
            staff_index=0,
            x=10,
            y=60,
            width=20,
            height=30,
            staff_x_start=10,
            staff_x_end=30,
            matched_template_id=1,
        ),
        SymbolData(
            staff_index=0,
            x=200,
            y=50,
            width=5,
            height=50,
            staff_x_start=200,
            staff_x_end=205,
            matched_template_id=10,
        ),
        SymbolData(
            staff_index=0,
            x=350,
            y=60,
            width=20,
            height=30,
            staff_x_start=350,
            staff_x_end=370,
            matched_template_id=1,
        ),
        SymbolData(
            staff_index=1,
            x=10,
            y=160,
            width=20,
            height=30,
            staff_x_start=10,
            staff_x_end=30,
            matched_template_id=1,
        ),
        SymbolData(
            staff_index=1,
            x=200,
            y=150,
            width=5,
            height=50,
            staff_x_start=200,
            staff_x_end=205,
            matched_template_id=10,
        ),
        SymbolData(
            staff_index=1,
            x=350,
            y=160,
            width=20,
            height=30,
            staff_x_start=350,
            staff_x_end=370,
            matched_template_id=1,
        ),
    ]
    categories = {1: "note", 10: "barline"}
    ctx = _ctx_with_symbols([staff0, staff1], symbols, categories)
    result = MeasureDetectionStage().process(ctx)

    assert len(result.measures) == 4
    assert result.measures[0].global_measure_number == 1
    assert result.measures[1].global_measure_number == 2
    assert result.measures[2].global_measure_number == 3
    assert result.measures[3].global_measure_number == 4


def test_no_barlines_single_measure():
    staff = _make_staff(x_start=10, x_end=220)
    symbols = [
        SymbolData(
            staff_index=0,
            x=10,
            y=60,
            width=20,
            height=30,
            staff_x_start=10,
            staff_x_end=30,
            matched_template_id=1,
        ),
        SymbolData(
            staff_index=0,
            x=200,
            y=60,
            width=20,
            height=30,
            staff_x_start=200,
            staff_x_end=220,
            matched_template_id=1,
        ),
    ]
    categories = {1: "note"}
    ctx = _ctx_with_symbols([staff], symbols, categories)
    result = MeasureDetectionStage().process(ctx)

    assert len(result.measures) == 1
    assert result.measures[0].x_start == 10
    assert result.measures[0].x_end == 220


def test_filtered_barlines_ignored():
    staff = _make_staff(x_start=10, x_end=420)
    symbols = [
        SymbolData(
            staff_index=0,
            x=10,
            y=60,
            width=20,
            height=30,
            staff_x_start=10,
            staff_x_end=30,
            matched_template_id=1,
        ),
        SymbolData(
            staff_index=0,
            x=200,
            y=50,
            width=5,
            height=50,
            staff_x_start=200,
            staff_x_end=205,
            matched_template_id=10,
            filtered=True,
            filter_reason="barline_position_outside_staff",
        ),
        SymbolData(
            staff_index=0,
            x=400,
            y=60,
            width=20,
            height=30,
            staff_x_start=400,
            staff_x_end=420,
            matched_template_id=1,
        ),
    ]
    categories = {1: "note", 10: "barline"}
    ctx = _ctx_with_symbols([staff], symbols, categories)
    result = MeasureDetectionStage().process(ctx)

    assert len(result.measures) == 1


def test_staff_without_x_bounds_skipped():
    """A staff without x_start/x_end should be skipped gracefully."""
    staff = StaffData(
        staff_index=0,
        y_top=50,
        y_bottom=100,
        line_positions=[50, 60, 70, 80, 90],
        line_spacing=10.0,
    )
    symbols = [
        SymbolData(
            staff_index=0,
            x=10,
            y=60,
            width=20,
            height=30,
            staff_x_start=10,
            staff_x_end=30,
            matched_template_id=1,
        ),
    ]
    categories = {1: "note"}
    ctx = _ctx_with_symbols([staff], symbols, categories)
    result = MeasureDetectionStage().process(ctx)

    assert len(result.measures) == 0
