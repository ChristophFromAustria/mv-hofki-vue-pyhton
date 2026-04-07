"""Tests for the volta bracket detection stage."""

import cv2
import numpy as np

from mv_hofki.services.scanner.stages.base import (
    MeasureData,
    PipelineContext,
    StaffData,
)


def _make_image_with_bracket():
    """Create a binary image with staff lines and a volta bracket above."""
    img = np.full((400, 800), 255, dtype=np.uint8)

    # Staff lines at y=200..240
    for y in [200, 210, 220, 230, 240]:
        img[y : y + 2, 20:780] = 0

    # Volta bracket above staff: horizontal line at y=170 from x=400 to x=600
    cv2.line(img, (400, 170), (600, 170), 0, 2)
    # Vertical hook at left end
    cv2.line(img, (400, 170), (400, 185), 0, 2)

    staff = StaffData(
        staff_index=0,
        y_top=140,
        y_bottom=300,
        line_positions=[200, 210, 220, 230, 240],
        line_spacing=10.0,
    )
    return img, staff


def test_volta_detects_bracket_above_repeat_barline():
    from mv_hofki.services.scanner.stages.volta_detection import VoltaDetectionStage

    img, staff = _make_image_with_bracket()
    measures = [
        MeasureData(
            staff_index=0,
            measure_number_in_staff=1,
            global_measure_number=1,
            x_start=200,
            x_end=400,
            end_barline="Wiederholung Ende",
        ),
        MeasureData(
            staff_index=0,
            measure_number_in_staff=2,
            global_measure_number=2,
            x_start=400,
            x_end=600,
            end_barline="Einfacher Taktstrich",
        ),
    ]

    ctx = PipelineContext(
        image=img,
        processed_image=img.copy(),
        staves=[staff],
        measures=measures,
        metadata={
            "template_display_names": {60: "Wiederholungs Klammer"},
        },
    )

    stage = VoltaDetectionStage()
    result = stage.process(ctx)

    bracket_syms = [s for s in result.symbols if s.matched_template_id == 60]
    assert len(bracket_syms) >= 1
    bracket = bracket_syms[0]
    assert bracket.staff_index == 0
    assert bracket.staff_x_start is not None
    assert bracket.staff_x_start <= 410
    assert bracket.staff_x_end is not None
    assert bracket.staff_x_end >= 590


def test_volta_assigns_volta_numbers_to_measures():
    from mv_hofki.services.scanner.stages.volta_detection import VoltaDetectionStage

    img, staff = _make_image_with_bracket()

    # Add a second bracket at x=610-780 (gap at x=600-610 separates them)
    cv2.line(img, (610, 170), (780, 170), 0, 2)
    cv2.line(img, (610, 170), (610, 185), 0, 2)

    measures = [
        MeasureData(
            staff_index=0,
            measure_number_in_staff=1,
            global_measure_number=1,
            x_start=200,
            x_end=400,
            end_barline="Wiederholung Ende",
        ),
        MeasureData(
            staff_index=0,
            measure_number_in_staff=2,
            global_measure_number=2,
            x_start=400,
            x_end=600,
            end_barline=None,
        ),
        MeasureData(
            staff_index=0,
            measure_number_in_staff=3,
            global_measure_number=3,
            x_start=600,
            x_end=780,
            end_barline=None,
        ),
    ]

    ctx = PipelineContext(
        image=img,
        processed_image=img.copy(),
        staves=[staff],
        measures=measures,
        metadata={
            "template_display_names": {60: "Wiederholungs Klammer"},
        },
    )

    stage = VoltaDetectionStage()
    result = stage.process(ctx)

    volta_measures = [m for m in result.measures if m.volta_number is not None]
    assert len(volta_measures) >= 2

    nums = sorted(set(m.volta_number for m in volta_measures))
    assert 1 in nums
    assert 2 in nums


def test_volta_no_detection_without_repeat_barlines():
    from mv_hofki.services.scanner.stages.volta_detection import VoltaDetectionStage

    img, staff = _make_image_with_bracket()
    measures = [
        MeasureData(
            staff_index=0,
            measure_number_in_staff=1,
            global_measure_number=1,
            x_start=200,
            x_end=600,
            end_barline="Einfacher Taktstrich",
        ),
    ]

    ctx = PipelineContext(
        image=img,
        processed_image=img.copy(),
        staves=[staff],
        measures=measures,
        metadata={
            "template_display_names": {60: "Wiederholungs Klammer"},
        },
    )

    stage = VoltaDetectionStage()
    result = stage.process(ctx)

    bracket_syms = [s for s in result.symbols if s.matched_template_id == 60]
    assert len(bracket_syms) == 0


def test_volta_validate():
    from mv_hofki.services.scanner.stages.volta_detection import VoltaDetectionStage

    stage = VoltaDetectionStage()

    ctx = PipelineContext(image=None, processed_image=None)
    assert stage.validate(ctx) is False

    img = np.zeros((100, 100), dtype=np.uint8)
    ctx = PipelineContext(image=img, processed_image=img)
    assert stage.validate(ctx) is False

    staff = StaffData(
        staff_index=0,
        y_top=0,
        y_bottom=100,
        line_positions=[20, 30, 40, 50, 60],
        line_spacing=10.0,
    )
    ctx = PipelineContext(image=img, processed_image=img, staves=[staff])
    assert stage.validate(ctx) is True
