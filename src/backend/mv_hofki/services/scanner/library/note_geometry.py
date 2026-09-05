"""Geometry shared by the scanner filters and the LilyPond generator.

Kept free of other project imports so both sides can use it without
import cycles.
"""

from __future__ import annotations

import re

# Offset (in line spacings) from the stem-free box edge to the head centre.
HEAD_OFFSET = 0.5
# Staff step (half line-spacings above the bottom line) of the middle line.
MIDDLE_LINE_STEP = 4


def stem_direction(name: str, display: str) -> str | None:
    """Return "up", "down" or None (no stem, e.g. whole note).

    The display name is authoritative — internal template names have been
    observed to contradict it (e.g. ``halbe_note_steil_unten`` labelled
    "Halbe Note Stiel oben").
    """
    for text in (display.lower(), name.lower()):
        if re.search(r"unten|down", text):
            return "down"
        if re.search(r"oben|\bup\b", text):
            return "up"
    if re.search(r"ganze|whole", f"{name} {display}".lower()):
        return None
    return "up"


def head_center_lines(
    sym_top: float,
    sym_bot: float,
    stem: str | None,
    offset_lines: float = 0.0,
) -> float:
    """Note-head centre in line spacings above the bottom staff line.

    ``sym_top``/``sym_bot`` are the box edges in the same unit. The head
    sits half a line spacing inside the stem-free end; ``offset_lines`` is
    the manual per-variant correction (positive = further down).
    """
    if stem == "up":
        center = sym_bot + HEAD_OFFSET
    elif stem == "down":
        center = sym_top - HEAD_OFFSET
    else:
        center = (sym_top + sym_bot) / 2.0
    return center - offset_lines


def expected_stem_for_step(step: float) -> str | None:
    """Engraving rule: heads below the middle line get stems up, above down.

    Returns None on the middle line, where both directions are common.
    """
    if step < MIDDLE_LINE_STEP:
        return "up"
    if step > MIDDLE_LINE_STEP:
        return "down"
    return None
