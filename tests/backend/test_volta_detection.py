"""Tests for VoltaDetectionStage — Hough line scan between staves."""

import numpy as np

from mv_hofki.services.scanner.stages.base import PipelineContext, StaffData
from mv_hofki.services.scanner.stages.volta_detection import VoltaDetectionStage


def test_finds_horizontal_line_between_staves():
    """A horizontal line between two staves should appear in debug output."""
    img = np.full((500, 800), 255, dtype=np.uint8)
    # Draw a horizontal line between staff 0 (bottom=180) and staff 1 (top=300)
    for dy in range(3):
        img[240 + dy, 100:600] = 0

    staff0 = StaffData(
        staff_index=0,
        y_top=50,
        y_bottom=180,
        line_positions=[50, 80, 110, 140, 170],
        line_spacing=30.0,
    )
    staff1 = StaffData(
        staff_index=1,
        y_top=300,
        y_bottom=430,
        line_positions=[300, 330, 360, 390, 420],
        line_spacing=30.0,
    )

    ctx = PipelineContext(image=img, processed_image=img)
    ctx.staves = [staff0, staff1]
    result = VoltaDetectionStage().process(ctx)

    debug_lines = result.metadata.get("volta_debug_lines", [])
    assert len(debug_lines) > 0


def test_no_lines_on_blank_image():
    """A blank image should produce no debug lines."""
    img = np.full((500, 800), 255, dtype=np.uint8)

    staff0 = StaffData(
        staff_index=0,
        y_top=50,
        y_bottom=180,
        line_positions=[50, 80, 110, 140, 170],
        line_spacing=30.0,
    )
    staff1 = StaffData(
        staff_index=1,
        y_top=300,
        y_bottom=430,
        line_positions=[300, 330, 360, 390, 420],
        line_spacing=30.0,
    )

    ctx = PipelineContext(image=img, processed_image=img)
    ctx.staves = [staff0, staff1]
    result = VoltaDetectionStage().process(ctx)

    debug_lines = result.metadata.get("volta_debug_lines", [])
    assert len(debug_lines) == 0
