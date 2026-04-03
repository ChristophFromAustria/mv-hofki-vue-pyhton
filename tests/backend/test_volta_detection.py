"""Tests for VoltaDetectionStage — Hough line scan above staff lines."""

import numpy as np

from mv_hofki.services.scanner.stages.base import PipelineContext, StaffData
from mv_hofki.services.scanner.stages.volta_detection import VoltaDetectionStage


def test_finds_line_above_top_staff_line():
    """A horizontal line between y_top and the top staff line should be found."""
    img = np.full((500, 800), 255, dtype=np.uint8)
    # Staff: y_top=100, lines at 200,230,260,290,320
    # Draw a volta bracket at y=150 (between y_top=100 and top_line=200)
    for dy in range(3):
        img[150 + dy, 100:600] = 0

    staff = StaffData(
        staff_index=0,
        y_top=100,
        y_bottom=350,
        line_positions=[200, 230, 260, 290, 320],
        line_spacing=30.0,
    )

    ctx = PipelineContext(image=img, processed_image=img)
    ctx.staves = [staff]
    result = VoltaDetectionStage().process(ctx)

    debug_lines = result.metadata.get("volta_debug_lines", [])
    assert len(debug_lines) > 0


def test_no_lines_on_blank_image():
    """A blank image should produce no debug lines."""
    img = np.full((500, 800), 255, dtype=np.uint8)

    staff = StaffData(
        staff_index=0,
        y_top=100,
        y_bottom=350,
        line_positions=[200, 230, 260, 290, 320],
        line_spacing=30.0,
    )

    ctx = PipelineContext(image=img, processed_image=img)
    ctx.staves = [staff]
    result = VoltaDetectionStage().process(ctx)

    debug_lines = result.metadata.get("volta_debug_lines", [])
    assert len(debug_lines) == 0
