"""Tests for the volta bracket detection stage."""

import numpy as np


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


def test_group_runs_rejects_non_horizontal():
    """Runs that drift too much in X are rejected (>2 degree drift)."""
    from mv_hofki.services.scanner.stages.volta_detection import (
        _group_runs_into_lines,
    )

    # 20 rows where the midpoint drifts 20px — that's atan(20/20)=45 degrees
    runs_by_row = {}
    for i in range(20):
        start = 50 + i
        runs_by_row[i] = [(start, start + 100)]
    lines = _group_runs_into_lines(runs_by_row, min_height=2)
    assert len(lines) == 0


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
