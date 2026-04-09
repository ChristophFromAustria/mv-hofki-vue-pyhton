"""Volta bracket detection: find repeat brackets above staves via run-length scan."""

from __future__ import annotations

import numpy as np

# Barline names that indicate a repeat boundary
_REPEAT_BARLINES = {
    "Wiederholung Ende",
    "Wiederholung Beidseitig",
}

_BLACK_THRESHOLD = 128


def _find_runs(row: np.ndarray, min_length: int) -> list[tuple[int, int]]:
    """Find contiguous black pixel runs in a single row.

    Parameters
    ----------
    row : 1-D uint8 array (one row of a grayscale image)
    min_length : minimum run length in pixels

    Returns list of (start_x, end_x) inclusive.
    """
    black = row < _BLACK_THRESHOLD
    runs: list[tuple[int, int]] = []
    n = len(black)
    i = 0
    while i < n:
        if black[i]:
            start = i
            while i < n and black[i]:
                i += 1
            end = i - 1
            if (end - start + 1) >= min_length:
                runs.append((start, end))
        else:
            i += 1
    return runs
