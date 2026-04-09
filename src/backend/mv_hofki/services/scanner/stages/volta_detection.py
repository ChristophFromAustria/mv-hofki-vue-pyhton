"""Volta bracket detection: find repeat brackets above staves via run-length scan."""

from __future__ import annotations

import math

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


# Maximum angle deviation from horizontal (degrees)
_MAX_ANGLE_DEG = 2.0


def _group_runs_into_lines(
    runs_by_row: dict[int, list[tuple[int, int]]],
    min_height: int,
) -> list[tuple[int, int, int, int]]:
    """Group runs on adjacent rows into horizontal line candidates.

    Parameters
    ----------
    runs_by_row : mapping of absolute Y -> list of (start_x, end_x) runs
    min_height : minimum number of rows a group must span

    Returns list of (x_start, y_start, x_end, y_end) bounding boxes
    for line candidates that pass the horizontality check.
    """
    if not runs_by_row:
        return []

    sorted_rows = sorted(runs_by_row.keys())

    # Each active group tracks: list of (y, start_x, end_x) per row
    active_groups: list[list[tuple[int, int, int]]] = []
    result: list[tuple[int, int, int, int]] = []

    for y in sorted_rows:
        row_runs = runs_by_row[y]
        next_active: list[list[tuple[int, int, int]]] = []
        used_runs: set[int] = set()

        for group in active_groups:
            last_y, last_sx, last_ex = group[-1]
            if y - last_y > 1:
                # Gap — finalize this group
                _finalize_group(group, min_height, result)
                continue

            # Find a matching run in this row (>=80% X overlap)
            best_idx = _best_overlap_run(last_sx, last_ex, row_runs, used_runs)
            if best_idx is not None:
                sx, ex = row_runs[best_idx]
                group.append((y, sx, ex))
                used_runs.add(best_idx)
                next_active.append(group)
            else:
                _finalize_group(group, min_height, result)

        # Start new groups from unmatched runs
        for idx, (sx, ex) in enumerate(row_runs):
            if idx not in used_runs:
                next_active.append([(y, sx, ex)])

        active_groups = next_active

    # Finalize remaining groups
    for group in active_groups:
        _finalize_group(group, min_height, result)

    return result


def _best_overlap_run(
    last_sx: int,
    last_ex: int,
    row_runs: list[tuple[int, int]],
    used: set[int],
) -> int | None:
    """Find the run in row_runs with >=80% X overlap to (last_sx, last_ex)."""
    last_len = last_ex - last_sx + 1
    best_idx = None
    best_overlap = 0
    for idx, (sx, ex) in enumerate(row_runs):
        if idx in used:
            continue
        overlap = max(0, min(last_ex, ex) - max(last_sx, sx) + 1)
        run_len = ex - sx + 1
        min_len = min(last_len, run_len)
        if min_len > 0 and overlap >= min_len * 0.8 and overlap > best_overlap:
            best_overlap = overlap
            best_idx = idx
    return best_idx


def _finalize_group(
    group: list[tuple[int, int, int]],
    min_height: int,
    result: list[tuple[int, int, int, int]],
) -> None:
    """Check a completed group for height and horizontality, append to result."""
    if len(group) < min_height:
        return

    y_start = group[0][0]
    y_end = group[-1][0]
    height = y_end - y_start + 1

    if height < min_height:
        return

    # Check horizontality: midpoint drift vs height
    first_mid = (group[0][1] + group[0][2]) / 2
    last_mid = (group[-1][1] + group[-1][2]) / 2
    drift = abs(last_mid - first_mid)
    max_drift = math.tan(math.radians(_MAX_ANGLE_DEG)) * height
    if drift > max_drift:
        return

    x_start = min(sx for _, sx, _ in group)
    x_end = max(ex for _, _, ex in group)
    result.append((x_start, y_start, x_end, y_end))


def _scan_for_horizontal_lines(
    binary: np.ndarray,
    y_start: int,
    y_end: int,
    x_start: int,
    x_end: int,
    min_run_length: int,
    min_height: int,
) -> list[tuple[int, int, int, int]]:
    """Scan a region for horizontal line candidates via run-length analysis.

    Parameters
    ----------
    binary : grayscale image (0=black, 255=white)
    y_start, y_end : Y range to scan (absolute pixel coords, exclusive end)
    x_start, x_end : X range to scan (absolute pixel coords, exclusive end)
    min_run_length : minimum horizontal run length in pixels
    min_height : minimum number of rows a line must span

    Returns list of (x_start, y_start, x_end, y_end) bounding boxes.
    """
    h, w = binary.shape[:2]
    y_start = max(0, y_start)
    y_end = min(h, y_end)
    x_start = max(0, x_start)
    x_end = min(w, x_end)

    if y_start >= y_end or x_start >= x_end:
        return []

    runs_by_row: dict[int, list[tuple[int, int]]] = {}
    for y in range(y_start, y_end):
        row_slice = binary[y, x_start:x_end]
        runs = _find_runs(row_slice, min_run_length)
        if runs:
            # Shift X coordinates back to absolute
            runs_by_row[y] = [(sx + x_start, ex + x_start) for sx, ex in runs]

    return _group_runs_into_lines(runs_by_row, min_height)
