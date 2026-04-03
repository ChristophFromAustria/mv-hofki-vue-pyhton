"""Tests for VoltaDetectionStage."""

import numpy as np

from mv_hofki.services.scanner.stages.base import (
    MeasureData,
    PipelineContext,
    StaffData,
)
from mv_hofki.services.scanner.stages.volta_detection import VoltaDetectionStage


def _make_binary_image_with_volta(
    width,
    height,
    staff_y_top,
    line_spacing,
    volta_x_start,
    volta_x_end,
    thickness=3,
):
    """Create a white binary image with a horizontal volta line above the staff."""
    img = np.full((height, width), 255, dtype=np.uint8)
    volta_y = int(staff_y_top - line_spacing * 1.5)
    # Draw horizontal bracket line with realistic thickness
    for dy in range(thickness):
        img[volta_y + dy, volta_x_start:volta_x_end] = 0
    # Vertical hook at start
    img[volta_y : volta_y + int(line_spacing), volta_x_start] = 0
    return img


def test_single_volta_bracket_detected():
    """A horizontal line above the staff should be detected as a volta bracket."""
    staff = StaffData(
        staff_index=0,
        y_top=200,
        y_bottom=400,
        line_positions=[200, 250, 300, 350, 400],
        line_spacing=50.0,
    )
    measures = [
        MeasureData(
            staff_index=0,
            measure_number_in_staff=1,
            global_measure_number=1,
            x_start=50,
            x_end=200,
            end_barline="Einfacher Taktstrich",
        ),
        MeasureData(
            staff_index=0,
            measure_number_in_staff=2,
            global_measure_number=2,
            x_start=210,
            x_end=400,
            end_barline="Wiederholung Ende",
        ),
        MeasureData(
            staff_index=0,
            measure_number_in_staff=3,
            global_measure_number=3,
            x_start=410,
            x_end=600,
            end_barline=None,
        ),
    ]
    img = _make_binary_image_with_volta(
        width=700,
        height=500,
        staff_y_top=200,
        line_spacing=50.0,
        volta_x_start=210,
        volta_x_end=400,
    )
    ctx = PipelineContext(image=img, processed_image=img)
    ctx.staves = [staff]
    ctx.measures = measures
    result = VoltaDetectionStage().process(ctx)

    volta_measures = [m for m in result.measures if m.volta_number is not None]
    assert len(volta_measures) >= 1
    assert volta_measures[0].volta_number == 1


def test_no_volta_without_horizontal_line():
    """An image with no horizontal line above the staff should produce no voltas."""
    staff = StaffData(
        staff_index=0,
        y_top=200,
        y_bottom=400,
        line_positions=[200, 250, 300, 350, 400],
        line_spacing=50.0,
    )
    measures = [
        MeasureData(
            staff_index=0,
            measure_number_in_staff=1,
            global_measure_number=1,
            x_start=50,
            x_end=400,
            end_barline="Wiederholung Ende",
        ),
    ]
    img = np.full((500, 700), 255, dtype=np.uint8)
    ctx = PipelineContext(image=img, processed_image=img)
    ctx.staves = [staff]
    ctx.measures = measures
    result = VoltaDetectionStage().process(ctx)

    volta_measures = [m for m in result.measures if m.volta_number is not None]
    assert len(volta_measures) == 0


def test_two_brackets_get_different_numbers():
    """Two brackets near a repeat-end should be assigned volta 1 and volta 2."""
    staff = StaffData(
        staff_index=0,
        y_top=200,
        y_bottom=400,
        line_positions=[200, 250, 300, 350, 400],
        line_spacing=50.0,
    )
    measures = [
        MeasureData(
            staff_index=0,
            measure_number_in_staff=1,
            global_measure_number=1,
            x_start=50,
            x_end=200,
            end_barline="Einfacher Taktstrich",
        ),
        MeasureData(
            staff_index=0,
            measure_number_in_staff=2,
            global_measure_number=2,
            x_start=210,
            x_end=450,
            end_barline="Wiederholung Ende",
        ),
        MeasureData(
            staff_index=0,
            measure_number_in_staff=3,
            global_measure_number=3,
            x_start=470,
            x_end=720,
            end_barline=None,
        ),
    ]
    img = np.full((500, 800), 255, dtype=np.uint8)
    volta_y = int(200 - 50 * 1.5)
    # Volta 1: over measure 2 (3px thick, x=210-440)
    for dy in range(3):
        img[volta_y + dy, 210:440] = 0
    img[volta_y : volta_y + 50, 210] = 0
    # Gap of ~30px (barline area)
    # Volta 2: over measure 3 (3px thick, x=470-710)
    for dy in range(3):
        img[volta_y + dy, 470:710] = 0
    img[volta_y : volta_y + 50, 470] = 0

    ctx = PipelineContext(image=img, processed_image=img)
    ctx.staves = [staff]
    ctx.measures = measures
    result = VoltaDetectionStage().process(ctx)

    volta_measures = [m for m in result.measures if m.volta_number is not None]
    assert len(volta_measures) == 2
    volta_measures.sort(key=lambda m: m.x_start)
    assert volta_measures[0].volta_number == 1
    assert volta_measures[1].volta_number == 2
    assert volta_measures[0].volta_group_id == volta_measures[1].volta_group_id
