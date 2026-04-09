"""Volta bracket detection: find repeat brackets above staves via run-length scan."""

from __future__ import annotations

import math

import numpy as np

from mv_hofki.services.scanner.stages.base import (
    MeasureData,
    PipelineContext,
    ProcessingStage,
    SymbolData,
)
from mv_hofki.services.scanner.stages.utils import expand_to_connected

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

    # Check horizontality: right-edge drift vs height.
    # Using the right edge (x_end) rather than midpoint avoids false rejects
    # when a hook pixel slightly shifts the left boundary on one row.
    first_mid = group[0][2]
    last_mid = group[-1][2]
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


class VoltaDetectionStage(ProcessingStage):
    """Detect volta brackets above staves via run-length scanning,
    seeded from repeat barline positions."""

    name = "volta_detection"

    def process(self, ctx: PipelineContext) -> PipelineContext:
        binary = ctx.processed_image
        if binary is None:
            return ctx

        staves = sorted(ctx.staves, key=lambda s: s.staff_index)
        staff_by_index = {s.staff_index: s for s in staves}

        # Look up template ID for "Wiederholungs Klammer"
        display_names: dict[int, str] = ctx.metadata.get("template_display_names", {})
        bracket_id: int | None = None
        for tid, name in display_names.items():
            if name == "Wiederholungs Klammer":
                bracket_id = tid
                break

        # Build ordered list of all measures
        all_measures = sorted(ctx.measures, key=lambda m: (m.staff_index, m.x_start))

        # Find repeat-end measures and their neighbours
        repeat_pairs: list[tuple[MeasureData | None, MeasureData | None, int]] = []
        volta_group_id = 0

        for idx, m in enumerate(all_measures):
            if m.end_barline not in _REPEAT_BARLINES:
                continue
            volta_group_id += 1
            # Measure before (the repeat measure itself) -> volta 1 candidate
            before_m = m
            # Measure after -> volta 2 candidate (may be on next staff)
            after_m = all_measures[idx + 1] if idx + 1 < len(all_measures) else None
            repeat_pairs.append((before_m, after_m, volta_group_id))

        brackets: list[SymbolData] = []
        debug_lines: list[dict] = []

        for pair_before, pair_after, group_id in repeat_pairs:
            candidates: list[tuple[int, MeasureData | None]] = [
                (1, pair_before),
                (2, pair_after),
            ]
            for volta_num, measure in candidates:
                if measure is None:
                    continue

                staff = staff_by_index.get(measure.staff_index)
                if staff is None:
                    continue

                ls = staff.line_spacing
                top_line = min(staff.line_positions)
                min_thickness = staff.line_thickness or 2

                y_start = staff.y_top
                y_end = top_line - int(ls)
                if y_start >= y_end:
                    continue

                min_run_length = int(ls * 2)

                line_candidates = _scan_for_horizontal_lines(
                    binary,
                    y_start=y_start,
                    y_end=y_end,
                    x_start=measure.x_start,
                    x_end=measure.x_end,
                    min_run_length=min_run_length,
                    min_height=min_thickness,
                )

                for lx1, ly1, lx2, ly2 in line_candidates:
                    debug_lines.append(
                        {
                            "x1": lx1,
                            "y1": ly1,
                            "x2": lx2,
                            "y2": ly2,
                            "staff_index": staff.staff_index,
                        }
                    )

                    # Expand to full connected component
                    bx1, by1, bx2, by2 = expand_to_connected(
                        binary,
                        lx1,
                        ly1,
                        lx2,
                        ly2,
                        y_start,
                        y_end,
                    )

                    # Filter: must be wider than tall (factor 2)
                    box_w = bx2 - bx1
                    box_h = by2 - by1
                    if box_h > 0 and box_w < box_h * 2:
                        continue

                    bottom_line_y = max(staff.line_positions)

                    brackets.append(
                        SymbolData(
                            staff_index=staff.staff_index,
                            x=bx1,
                            y=by1,
                            width=box_w,
                            height=max(box_h, int(ls // 2)),
                            staff_y_top=round((bottom_line_y - by1) / ls, 2),
                            staff_y_bottom=round((bottom_line_y - by2) / ls, 2),
                            staff_x_start=bx1,
                            staff_x_end=bx2,
                            matched_template_id=bracket_id,
                            confidence=0.8,
                        )
                    )

                    # Assign volta number to all overlapping measures
                    for m in ctx.measures:
                        if m.staff_index != staff.staff_index:
                            continue
                        if m.x_start < bx2 and m.x_end > bx1:
                            m.volta_number = volta_num
                            m.volta_group_id = group_id

                    ctx.log(
                        f"  Volta-Klammer {volta_num} erkannt: "
                        f"System {staff.staff_index}, x={bx1}-{bx2}"
                    )
                    # Only use the first (longest) line candidate per measure
                    break

        # Add brackets to symbols list
        for b in brackets:
            b.sequence_order = len(ctx.symbols)
            ctx.symbols.append(b)

        ctx.metadata["volta_debug_lines"] = debug_lines
        ctx.log(
            f"Volta-Erkennung: {len(brackets)} Klammern, "
            f"{len(debug_lines)} Linienkandidaten"
        )
        return ctx

    def validate(self, ctx: PipelineContext) -> bool:
        return ctx.processed_image is not None and len(ctx.staves) > 0
