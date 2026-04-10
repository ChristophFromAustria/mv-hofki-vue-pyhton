"""Tests for the volta bracket detection stage."""

import cv2
import numpy as np

from mv_hofki.services.scanner.stages.base import (
    MeasureData,
    PipelineContext,
    StaffData,
)


def test_find_runs_single_run():
    """A single black segment in a white row returns one run."""
    from mv_hofki.services.scanner.stages.volta_detection import _find_runs

    # Row: 10 white, 20 black, 10 white (40 px total)
    row = np.full(40, 255, dtype=np.uint8)
    row[10:30] = 0
    runs = _find_runs(row, min_length=10)
    assert len(runs) == 1
    assert runs[0] == (10, 29)  # (start_x, end_x) inclusive


def test_find_runs_filters_short():
    """Runs shorter than min_length are discarded."""
    from mv_hofki.services.scanner.stages.volta_detection import _find_runs

    row = np.full(40, 255, dtype=np.uint8)
    row[5:10] = 0  # 5 px run
    row[20:35] = 0  # 15 px run
    runs = _find_runs(row, min_length=10)
    assert len(runs) == 1
    assert runs[0] == (20, 34)


def test_find_runs_empty_row():
    """An all-white row returns no runs."""
    from mv_hofki.services.scanner.stages.volta_detection import _find_runs

    row = np.full(40, 255, dtype=np.uint8)
    runs = _find_runs(row, min_length=5)
    assert runs == []


def test_group_runs_simple_horizontal_line():
    """Runs on adjacent rows with strong X-overlap form one line group."""
    from mv_hofki.services.scanner.stages.volta_detection import (
        _group_runs_into_lines,
    )

    # 3 rows of runs at roughly the same X position
    runs_by_row = {
        10: [(50, 150)],
        11: [(51, 151)],
        12: [(50, 150)],
    }
    lines = _group_runs_into_lines(runs_by_row, min_height=2)
    assert len(lines) == 1
    line = lines[0]
    # Line bounding box: x_start, y_start, x_end, y_end
    assert line[0] <= 51  # x_start
    assert line[1] == 10  # y_start
    assert line[2] >= 150  # x_end
    assert line[3] == 12  # y_end


def test_group_runs_rejects_length_mismatch():
    """A short fragment does not merge with a much longer run on the next row."""
    from mv_hofki.services.scanner.stages.volta_detection import (
        _group_runs_into_lines,
    )

    # Row 10: short fragment (50px), Row 11-13: full line (300px)
    # The fragment is <50% of the full line length, so they should not merge.
    # The full line rows form their own group.
    runs_by_row = {
        10: [(100, 149)],  # 50px
        11: [(50, 349)],  # 300px
        12: [(50, 349)],
        13: [(50, 349)],
    }
    lines = _group_runs_into_lines(runs_by_row, min_height=2)
    assert len(lines) == 1
    # The group should be rows 11-13 (the full line), not 10-13
    assert lines[0][1] == 11  # y_start
    assert lines[0][3] == 13  # y_end


def test_group_runs_two_separate_lines():
    """Runs at different X positions on the same rows form separate groups."""
    from mv_hofki.services.scanner.stages.volta_detection import (
        _group_runs_into_lines,
    )

    runs_by_row = {
        10: [(50, 150), (300, 400)],
        11: [(50, 150), (300, 400)],
        12: [(50, 150), (300, 400)],
    }
    lines = _group_runs_into_lines(runs_by_row, min_height=2)
    assert len(lines) == 2


def test_scan_for_horizontal_lines_finds_bracket():
    """A drawn horizontal line in a binary image region is detected."""
    from mv_hofki.services.scanner.stages.volta_detection import (
        _scan_for_horizontal_lines,
    )

    img = np.full((100, 400), 255, dtype=np.uint8)
    # Draw a horizontal line at y=20, x=50..250 (2px thick)
    img[20:22, 50:250] = 0

    lines = _scan_for_horizontal_lines(
        binary=img,
        y_start=10,
        y_end=40,
        x_start=0,
        x_end=400,
        min_run_length=50,
        min_height=2,
    )
    assert len(lines) == 1
    x1, y1, x2, y2 = lines[0]
    assert x1 <= 50
    assert x2 >= 249
    assert y1 >= 20
    assert y2 <= 22


def test_scan_for_horizontal_lines_ignores_short():
    """Lines shorter than min_run_length are not returned."""
    from mv_hofki.services.scanner.stages.volta_detection import (
        _scan_for_horizontal_lines,
    )

    img = np.full((100, 400), 255, dtype=np.uint8)
    img[20:22, 50:80] = 0  # 30px, below threshold

    lines = _scan_for_horizontal_lines(
        binary=img,
        y_start=10,
        y_end=40,
        x_start=0,
        x_end=400,
        min_run_length=50,
        min_height=2,
    )
    assert len(lines) == 0


def _make_staff_image():
    """Create a binary image with staff lines."""
    img = np.full((400, 800), 255, dtype=np.uint8)
    # Staff lines at y=200..240 (5 lines, spacing=10)
    for y_pos in [200, 210, 220, 230, 240]:
        img[y_pos : y_pos + 2, 20:780] = 0
    staff = StaffData(
        staff_index=0,
        y_top=140,
        y_bottom=300,
        line_positions=[200, 210, 220, 230, 240],
        line_spacing=10.0,
        line_thickness=2,
        x_start=20,
        x_end=780,
    )
    return img, staff


def test_volta_detects_bracket_before_repeat():
    """Bracket above the measure before a repeat end is detected as volta 1."""
    from mv_hofki.services.scanner.stages.volta_detection import VoltaDetectionStage

    img, staff = _make_staff_image()

    # Volta bracket above measure 2 (x=300..500): horizontal at y=170, hook at x=300
    cv2.line(img, (300, 170), (500, 170), 0, 2)
    cv2.line(img, (300, 170), (300, 185), 0, 2)

    measures = [
        MeasureData(
            0, 1, 1, x_start=100, x_end=300, end_barline="Einfacher Taktstrich"
        ),
        MeasureData(0, 2, 2, x_start=300, x_end=500, end_barline="Wiederholung Ende"),
        MeasureData(
            0, 3, 3, x_start=500, x_end=700, end_barline="Einfacher Taktstrich"
        ),
    ]

    ctx = PipelineContext(
        image=img,
        processed_image=img.copy(),
        staves=[staff],
        measures=measures,
        metadata={"template_display_names": {60: "Wiederholungs Klammer"}},
    )

    stage = VoltaDetectionStage()
    result = stage.process(ctx)

    bracket_syms = [s for s in result.symbols if s.matched_template_id == 60]
    assert len(bracket_syms) >= 1

    # Measure 2 should be volta 1
    m2 = [m for m in result.measures if m.global_measure_number == 2][0]
    assert m2.volta_number == 1
    assert m2.volta_group_id is not None


def test_volta_detects_bracket_after_repeat():
    """A bracket above the measure after a repeat end is detected as volta 2."""
    from mv_hofki.services.scanner.stages.volta_detection import VoltaDetectionStage

    img, staff = _make_staff_image()

    # Volta 1 bracket above measure 2
    cv2.line(img, (300, 170), (500, 170), 0, 2)
    cv2.line(img, (300, 170), (300, 185), 0, 2)

    # Volta 2 bracket above measure 3
    cv2.line(img, (510, 170), (700, 170), 0, 2)
    cv2.line(img, (510, 170), (510, 185), 0, 2)

    measures = [
        MeasureData(
            0, 1, 1, x_start=100, x_end=300, end_barline="Einfacher Taktstrich"
        ),
        MeasureData(0, 2, 2, x_start=300, x_end=500, end_barline="Wiederholung Ende"),
        MeasureData(
            0, 3, 3, x_start=500, x_end=700, end_barline="Einfacher Taktstrich"
        ),
    ]

    ctx = PipelineContext(
        image=img,
        processed_image=img.copy(),
        staves=[staff],
        measures=measures,
        metadata={"template_display_names": {60: "Wiederholungs Klammer"}},
    )

    stage = VoltaDetectionStage()
    result = stage.process(ctx)

    bracket_syms = [s for s in result.symbols if s.matched_template_id == 60]
    assert len(bracket_syms) == 2

    m2 = [m for m in result.measures if m.global_measure_number == 2][0]
    m3 = [m for m in result.measures if m.global_measure_number == 3][0]
    assert m2.volta_number == 1
    assert m3.volta_number == 2
    assert m2.volta_group_id == m3.volta_group_id


def test_volta_no_detection_without_repeat():
    """No brackets are detected when there are no repeat barlines."""
    from mv_hofki.services.scanner.stages.volta_detection import VoltaDetectionStage

    img, staff = _make_staff_image()
    cv2.line(img, (300, 170), (500, 170), 0, 2)

    measures = [
        MeasureData(
            0, 1, 1, x_start=100, x_end=500, end_barline="Einfacher Taktstrich"
        ),
    ]

    ctx = PipelineContext(
        image=img,
        processed_image=img.copy(),
        staves=[staff],
        measures=measures,
        metadata={"template_display_names": {60: "Wiederholungs Klammer"}},
    )

    stage = VoltaDetectionStage()
    result = stage.process(ctx)

    bracket_syms = [s for s in result.symbols if s.matched_template_id == 60]
    assert len(bracket_syms) == 0


def test_volta_cross_staff():
    """When repeat is at end of staff, volta 2 is found above next staff."""
    from mv_hofki.services.scanner.stages.volta_detection import VoltaDetectionStage

    img = np.full((600, 800), 255, dtype=np.uint8)

    # Staff 0: lines at y=100..140
    for y_pos in [100, 110, 120, 130, 140]:
        img[y_pos : y_pos + 2, 20:780] = 0
    staff0 = StaffData(
        staff_index=0,
        y_top=50,
        y_bottom=200,
        line_positions=[100, 110, 120, 130, 140],
        line_spacing=10.0,
        line_thickness=2,
        x_start=20,
        x_end=780,
    )

    # Staff 1: lines at y=350..390
    for y_pos in [350, 360, 370, 380, 390]:
        img[y_pos : y_pos + 2, 20:780] = 0
    staff1 = StaffData(
        staff_index=1,
        y_top=300,
        y_bottom=450,
        line_positions=[350, 360, 370, 380, 390],
        line_spacing=10.0,
        line_thickness=2,
        x_start=20,
        x_end=780,
    )

    # Volta 1 bracket above staff 0, measure at end
    cv2.line(img, (600, 70), (770, 70), 0, 2)
    cv2.line(img, (600, 70), (600, 85), 0, 2)

    # Volta 2 bracket above staff 1, measure at start
    cv2.line(img, (30, 320), (200, 320), 0, 2)
    cv2.line(img, (30, 320), (30, 335), 0, 2)

    measures = [
        MeasureData(0, 1, 1, x_start=20, x_end=400, end_barline="Einfacher Taktstrich"),
        MeasureData(
            0, 2, 2, x_start=400, x_end=600, end_barline="Einfacher Taktstrich"
        ),
        MeasureData(0, 3, 3, x_start=600, x_end=780, end_barline="Wiederholung Ende"),
        MeasureData(1, 1, 4, x_start=20, x_end=200, end_barline="Einfacher Taktstrich"),
        MeasureData(
            1, 2, 5, x_start=200, x_end=500, end_barline="Einfacher Taktstrich"
        ),
    ]

    ctx = PipelineContext(
        image=img,
        processed_image=img.copy(),
        staves=[staff0, staff1],
        measures=measures,
        metadata={"template_display_names": {60: "Wiederholungs Klammer"}},
    )

    stage = VoltaDetectionStage()
    result = stage.process(ctx)

    m3 = [m for m in result.measures if m.global_measure_number == 3][0]
    m4 = [m for m in result.measures if m.global_measure_number == 4][0]

    assert m3.volta_number == 1
    assert m4.volta_number == 2
    assert m3.volta_group_id == m4.volta_group_id


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
