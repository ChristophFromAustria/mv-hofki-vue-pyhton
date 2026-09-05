"""Repeat-sign priority: notes and rests inside a repeat barline are false hits.

The dots of a repeat sign (":|." / ".|:") are regularly matched as quarter
or eighth rests, sometimes as note heads. Whenever a note or rest hitbox
overlaps a repeat barline by more than a configurable share of its own
width, the repeat sign wins and the note/rest is marked as filtered.
"""

from __future__ import annotations

import re

from mv_hofki.services.scanner.stages.base import PipelineContext, SymbolData

_REPEAT_RE = re.compile(r"wiederhol|repeat", re.IGNORECASE)
_VICTIM_CATEGORIES = {"note", "rest"}
DEFAULT_MIN_OVERLAP = 0.5


def x_overlap_fraction(victim: SymbolData, repeat: SymbolData) -> float:
    """Share of the victim's width covered by the repeat sign's x-range."""
    if victim.width <= 0:
        return 0.0
    left = max(victim.x, repeat.x)
    right = min(victim.x + victim.width, repeat.x + repeat.width)
    return max(0, right - left) / victim.width


def _dedupe_overlapping(repeats: list[SymbolData]) -> list[SymbolData]:
    """Keep only the most confident of mutually overlapping repeat signs."""
    kept: list[SymbolData] = []
    for rep in sorted(repeats, key=lambda r: -(r.confidence or 0.0)):
        clashes = any(rep.x < k.x + k.width and rep.x + rep.width > k.x for k in kept)
        if not clashes:
            kept.append(rep)
    return kept


class RepeatOverlapFilter:
    """Filter notes/rests that overlap a repeat barline in x."""

    name = "repeat_overlap_filter"

    def apply(self, ctx: PipelineContext) -> None:
        categories: dict[int, str] = ctx.metadata.get("template_categories", {})
        display_names: dict[int, str] = ctx.metadata.get("template_display_names", {})
        min_overlap = float(
            ctx.config.get("repeat_overlap_min_fraction", DEFAULT_MIN_OVERLAP)
        )

        def tid(sym: SymbolData) -> int:
            return (
                sym.matched_template_id if sym.matched_template_id is not None else -1
            )

        repeats_by_staff: dict[int, list[SymbolData]] = {}
        for sym in ctx.symbols:
            if sym.filtered or categories.get(tid(sym)) != "barline":
                continue
            if _REPEAT_RE.search(display_names.get(tid(sym), "")):
                repeats_by_staff.setdefault(sym.staff_index, []).append(sym)
        if not repeats_by_staff:
            return

        # Two repeat signs cannot overlap; when they do, one is a false hit
        # (e.g. ":|." matched next to a real ".|:"). Only the more confident
        # one may filter its neighbours — otherwise a phantom repeat would
        # take a real rest with it. Measure detection removes the loser later.
        for staff_index, reps in repeats_by_staff.items():
            repeats_by_staff[staff_index] = _dedupe_overlapping(reps)

        dropped = 0
        for sym in ctx.symbols:
            if sym.filtered or categories.get(tid(sym)) not in _VICTIM_CATEGORIES:
                continue
            for rep in repeats_by_staff.get(sym.staff_index, []):
                if x_overlap_fraction(sym, rep) > min_overlap:
                    sym.filtered = True
                    sym.filter_reason = "repeat_overlap"
                    dropped += 1
                    break
        ctx.log(
            f"  Wiederholungszeichen: {dropped} überlappende Noten/Pausen gefiltert"
        )
