"""Tests for MeasureDetectionStage."""

import numpy as np

from mv_hofki.services.scanner.stages.base import (
    PipelineContext,
    StaffData,
    SymbolData,
)
from mv_hofki.services.scanner.stages.measure_detection import MeasureDetectionStage


def _ctx_with_symbols(staves, symbols, template_categories=None):
    ctx = PipelineContext(image=np.zeros((100, 800), dtype=np.uint8))
    ctx.staves = staves
    ctx.symbols = symbols
    ctx.metadata["template_categories"] = template_categories or {}
    return ctx


def test_single_staff_three_barlines_four_measures():
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
    assert result.measures[1].x_start == 105
    assert result.measures[1].x_end == 300
    assert result.measures[3].measure_number_in_staff == 4
    assert result.measures[3].x_end == 620


def test_two_staffs_global_numbering():
    staff0 = StaffData(
        staff_index=0,
        y_top=50,
        y_bottom=100,
        line_positions=[50, 60, 70, 80, 90],
        line_spacing=10.0,
    )
    staff1 = StaffData(
        staff_index=1,
        y_top=150,
        y_bottom=200,
        line_positions=[150, 160, 170, 180, 190],
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
