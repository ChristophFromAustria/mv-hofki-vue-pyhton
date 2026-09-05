"""Priority symbols: notes and rests inside them are false hits.

Some templates are wide, structured signs whose inner parts look like
notes or rests to the matcher: the dots of a repeat barline (":|." /
".|:"), the slash-and-dots of a measure-repeat sign, and the flats or
sharps of a key-signature group. Whenever a note or rest hitbox overlaps
such a priority symbol by more than a configurable share of its own
width, the priority symbol wins and the note/rest is marked as filtered.
"""

from __future__ import annotations

import re

from mv_hofki.services.scanner.stages.base import PipelineContext, SymbolData

_REPEAT_BARLINE_RE = re.compile(r"wiederhol|repeat", re.IGNORECASE)
_MEASURE_REPEAT_RE = re.compile(r"takt.*wiederhol|percent|simile", re.IGNORECASE)
_VICTIM_CATEGORIES = {"note", "rest"}
DEFAULT_MIN_OVERLAP = 0.5


def x_overlap_fraction(victim: SymbolData, source: SymbolData) -> float:
    """Share of the victim's width covered by the source's x-range."""
    if victim.width <= 0:
        return 0.0
    left = max(victim.x, source.x)
    right = min(victim.x + victim.width, source.x + source.width)
    return max(0, right - left) / victim.width


def priority_kind(category: str, name: str, display: str) -> str | None:
    """Classify a template as priority source: repeat / measure_repeat / key_sig."""
    text = f"{name} {display}"
    if category == "barline" and _REPEAT_BARLINE_RE.search(text):
        return "repeat"
    if category == "other" and _MEASURE_REPEAT_RE.search(text):
        return "measure_repeat"
    if category == "key_sig":
        return "key_sig"
    return None


def _dedupe_overlapping(sources: list[SymbolData]) -> list[SymbolData]:
    """Keep only the most confident of mutually overlapping priority signs."""
    kept: list[SymbolData] = []
    for src in sorted(sources, key=lambda r: -(r.confidence or 0.0)):
        clashes = any(src.x < k.x + k.width and src.x + src.width > k.x for k in kept)
        if not clashes:
            kept.append(src)
    return kept


class PriorityOverlapFilter:
    """Filter notes/rests overlapping repeats, measure repeats or key signatures."""

    name = "priority_overlap_filter"

    def apply(self, ctx: PipelineContext) -> None:
        categories: dict[int, str] = ctx.metadata.get("template_categories", {})
        display_names: dict[int, str] = ctx.metadata.get("template_display_names", {})
        template_names: dict[int, str] = ctx.metadata.get("template_names", {})
        min_overlap = float(
            ctx.config.get("repeat_overlap_min_fraction", DEFAULT_MIN_OVERLAP)
        )

        def tid(sym: SymbolData) -> int:
            return (
                sym.matched_template_id if sym.matched_template_id is not None else -1
            )

        kinds: dict[int, str] = {}
        sources_by_staff: dict[int, list[SymbolData]] = {}
        for sym in ctx.symbols:
            if sym.filtered:
                continue
            t = tid(sym)
            kind = priority_kind(
                categories.get(t, ""),
                template_names.get(t, ""),
                display_names.get(t, ""),
            )
            if kind:
                kinds[id(sym)] = kind
                sources_by_staff.setdefault(sym.staff_index, []).append(sym)
        if not sources_by_staff:
            return

        # Two priority signs cannot overlap; when they do, one is a false hit
        # (e.g. ":|." matched next to a real ".|:"). Only the more confident
        # one may filter its neighbours — otherwise a phantom would take a
        # real rest with it. Measure detection removes the loser later.
        for staff_index, srcs in sources_by_staff.items():
            sources_by_staff[staff_index] = _dedupe_overlapping(srcs)

        dropped: dict[str, int] = {}
        for sym in ctx.symbols:
            if sym.filtered or categories.get(tid(sym)) not in _VICTIM_CATEGORIES:
                continue
            for src in sources_by_staff.get(sym.staff_index, []):
                if x_overlap_fraction(sym, src) > min_overlap:
                    kind = kinds[id(src)]
                    sym.filtered = True
                    sym.filter_reason = f"{kind}_overlap"
                    dropped[kind] = dropped.get(kind, 0) + 1
                    break
        summary = ", ".join(f"{k}: {v}" for k, v in sorted(dropped.items())) or "0"
        ctx.log(
            f"  Prioritäts-Symbole: überlappende Noten/Pausen gefiltert ({summary})"
        )


# Backwards-compatible name
RepeatOverlapFilter = PriorityOverlapFilter
