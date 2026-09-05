"""Staff-start priority: clef → key signature → time signature.

Every staff line begins with a clef, optionally followed by a key
signature and a time signature. Nothing else can appear in that zone,
so any note, rest or other symbol detected there is a false positive
(typically a flat of the key signature matched as a note, or a clef
fragment matched as a rest). This module resolves that header zone and
is shared by the pipeline filter and the LilyPond score builder.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from mv_hofki.services.scanner.stages.base import PipelineContext

_HEADER_ORDER = ("clef", "key_sig", "time_sig")
# Categories that may legitimately sit inside/under the header zone.
_ZONE_EXEMPT = {"barline", "dynamic", "clef", "key_sig", "time_sig"}


@dataclass
class StaffStartItem:
    """Minimal symbol view used by the resolver."""

    key: int  # caller-defined identity (index or id)
    x_start: float
    x_end: float
    category: str
    confidence: float


@dataclass
class StaffStartResult:
    zone_end: float | None  # None → no clef found, zone undefined
    chosen: dict[str, int] = field(default_factory=dict)  # category → key
    drop: set[int] = field(default_factory=set)
    has_key_signature: bool = False


def resolve_staff_start(
    items: list[StaffStartItem],
    staff_x_start: float,
    line_spacing: float,
    *,
    max_gap_factor: float = 3.0,
    clef_search_factor: float = 6.0,
    key_conf_tolerance: float = 0.15,
) -> StaffStartResult:
    """Pick the header symbols of a staff and list what must be dropped.

    * the clef is the most confident clef starting within
      ``clef_search_factor`` line spacings of the staff start
    * a key signature / time signature must start within
      ``max_gap_factor`` line spacings after the previous header symbol
    * every non-exempt symbol whose centre lies before the zone end is
      dropped, as are competing header symbols that were not chosen and
      single accidentals when a key-signature template was chosen
    """
    result = StaffStartResult(zone_end=None)
    ls = max(line_spacing, 1.0)

    clefs = [
        it
        for it in items
        if it.category == "clef"
        and staff_x_start - ls <= it.x_start <= staff_x_start + clef_search_factor * ls
    ]
    if not clefs:
        return result
    clef = max(clefs, key=lambda it: it.confidence)
    result.chosen["clef"] = clef.key
    zone_end = clef.x_end

    for cat in ("key_sig", "time_sig"):
        candidates = [
            it
            for it in items
            if it.category == cat
            and it.x_end > clef.x_start
            and it.x_start <= zone_end + max_gap_factor * ls
        ]
        if candidates:
            best = max(candidates, key=lambda it: it.confidence)
            if cat == "key_sig":
                # A narrower key template (fewer accidentals) always matches
                # inside a wider group, so prefer the widest plausible one.
                plausible = [
                    it
                    for it in candidates
                    if it.confidence >= best.confidence - key_conf_tolerance
                ]
                best = max(
                    plausible, key=lambda it: (it.x_end - it.x_start, it.confidence)
                )
            result.chosen[cat] = best.key
            zone_end = max(zone_end, best.x_end)
            if cat == "key_sig":
                result.has_key_signature = True

    result.zone_end = zone_end
    chosen_keys = set(result.chosen.values())
    for it in items:
        if it.key in chosen_keys:
            continue
        centre = (it.x_start + it.x_end) / 2.0
        if it.category in _HEADER_ORDER:
            # Competing clef/key/time inside the zone → duplicate
            if it.x_start < zone_end:
                result.drop.add(it.key)
            continue
        if it.category in _ZONE_EXEMPT:
            continue
        if it.category == "accidental":
            # single accidentals are part of the key signature area
            if it.x_start < zone_end or (
                result.has_key_signature and it.x_start < zone_end + 0.5 * ls
            ):
                result.drop.add(it.key)
            continue
        if centre < zone_end:
            result.drop.add(it.key)
    return result


class StaffStartFilter:
    """Post-matching operation: enforce the clef/key/time zone per staff."""

    name = "staff_start_filter"

    def apply(self, ctx: PipelineContext) -> None:
        template_categories: dict[int, str] = ctx.metadata.get(
            "template_categories", {}
        )
        staff_map = {s.staff_index: s for s in ctx.staves}

        by_staff: dict[int, list[int]] = {}
        for idx, sym in enumerate(ctx.symbols):
            if sym.filtered:
                continue
            by_staff.setdefault(sym.staff_index, []).append(idx)

        for staff_index, indices in by_staff.items():
            staff = staff_map.get(staff_index)
            if staff is None:
                continue
            x_start = staff.x_start
            if x_start is None:
                x_start = min(ctx.symbols[i].x for i in indices)
            items = []
            for i in indices:
                sym = ctx.symbols[i]
                tid = (
                    sym.matched_template_id
                    if sym.matched_template_id is not None
                    else -1
                )
                items.append(
                    StaffStartItem(
                        key=i,
                        x_start=float(
                            sym.staff_x_start
                            if sym.staff_x_start is not None
                            else sym.x
                        ),
                        x_end=float(
                            sym.staff_x_end
                            if sym.staff_x_end is not None
                            else sym.x + sym.width
                        ),
                        category=template_categories.get(tid, ""),
                        confidence=sym.confidence or 0.0,
                    )
                )
            res = resolve_staff_start(items, float(x_start), staff.line_spacing)
            if res.zone_end is None:
                continue
            for i in res.drop:
                sym = ctx.symbols[i]
                tid = (
                    sym.matched_template_id
                    if sym.matched_template_id is not None
                    else -1
                )
                cat = template_categories.get(tid, "")
                sym.filtered = True
                sym.filter_reason = (
                    "staff_start_duplicate"
                    if cat in _HEADER_ORDER
                    else "staff_start_zone"
                )
            ctx.log(
                f"  Zeilenanfang System {staff_index}: "
                f"{len(res.chosen)} Kopfsymbole, {len(res.drop)} gefiltert"
            )
