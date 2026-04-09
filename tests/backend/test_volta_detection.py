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
