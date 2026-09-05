"""Stem-direction priority: one note head, one stem.

A filled note head matches both the stem-up and the stem-down template of
the same note value: the up-box extends above the head, the down-box
below it, and both put the head at the same staff position. When two
notes of opposite stem direction overlap in x and resolve to the same
head position, only one is real. The engraving rule decides: heads below
the middle line carry the stem up, heads above it carry the stem down.
On the middle line the more confident match wins. Different head
positions are left alone — that is a chord.
"""

from __future__ import annotations

from mv_hofki.services.scanner.library.note_geometry import (
    expected_stem_for_step,
    head_center_lines,
    stem_direction,
)
from mv_hofki.services.scanner.stages.base import PipelineContext, SymbolData

DEFAULT_MIN_OVERLAP = 0.5
SAME_HEAD_TOLERANCE_STEPS = 1.0


def _x_overlap_fraction(a: SymbolData, b: SymbolData) -> float:
    """Overlap of the x-ranges relative to the narrower box."""
    narrow = min(a.width, b.width)
    if narrow <= 0:
        return 0.0
    left = max(a.x, b.x)
    right = min(a.x + a.width, b.x + b.width)
    return max(0, right - left) / narrow


class StemDirectionFilter:
    """Drop the wrong-stem duplicate of a note detected with both stems."""

    name = "stem_direction_filter"

    def apply(self, ctx: PipelineContext) -> None:
        categories: dict[int, str] = ctx.metadata.get("template_categories", {})
        display_names: dict[int, str] = ctx.metadata.get("template_display_names", {})
        template_names: dict[int, str] = ctx.metadata.get("template_names", {})
        anchor_offsets: dict[int, float] = ctx.metadata.get(
            "variant_anchor_offsets", {}
        )
        min_overlap = float(
            ctx.config.get("stem_overlap_min_fraction", DEFAULT_MIN_OVERLAP)
        )

        def tid(sym: SymbolData) -> int:
            return (
                sym.matched_template_id if sym.matched_template_id is not None else -1
            )

        def stem_of(sym: SymbolData) -> str | None:
            t = tid(sym)
            return stem_direction(template_names.get(t, ""), display_names.get(t, ""))

        def head_step(sym: SymbolData, stem: str | None) -> float | None:
            if sym.staff_y_top is None or sym.staff_y_bottom is None:
                return None
            offset = 0.0
            if sym.matched_variant_id is not None:
                offset = anchor_offsets.get(sym.matched_variant_id, 0.0)
            return (
                head_center_lines(sym.staff_y_top, sym.staff_y_bottom, stem, offset) * 2
            )

        notes_by_staff: dict[int, list[SymbolData]] = {}
        for sym in ctx.symbols:
            if sym.filtered or categories.get(tid(sym)) != "note":
                continue
            notes_by_staff.setdefault(sym.staff_index, []).append(sym)

        dropped = 0
        for notes in notes_by_staff.values():
            notes.sort(key=lambda s: s.x)
            for i, a in enumerate(notes):
                if a.filtered:
                    continue
                stem_a = stem_of(a)
                if stem_a is None:
                    continue
                for b in notes[i + 1 :]:
                    if b.x >= a.x + a.width:
                        break  # sorted by x — nothing further can overlap
                    if b.filtered:
                        continue
                    stem_b = stem_of(b)
                    if stem_b is None or stem_b == stem_a:
                        continue
                    if _x_overlap_fraction(a, b) <= min_overlap:
                        continue
                    step_a = head_step(a, stem_a)
                    step_b = head_step(b, stem_b)
                    if step_a is None or step_b is None:
                        continue
                    if abs(step_a - step_b) > SAME_HEAD_TOLERANCE_STEPS:
                        continue  # two different heads → chord, keep both

                    step = round((step_a + step_b) / 2.0)
                    expected = expected_stem_for_step(step)
                    if expected is None:
                        loser = a if (a.confidence or 0) < (b.confidence or 0) else b
                    else:
                        loser = b if stem_a == expected else a
                    loser.filtered = True
                    loser.filter_reason = f"stem_direction_{expected or 'confidence'}"
                    dropped += 1
                    if loser is a:
                        break
        ctx.log(f"  Stielrichtung: {dropped} doppelte Notenerkennungen gefiltert")
