"""Dynamic filter: removes false-positive dynamic symbol detections.

Dynamics (p, f, mf, ff, etc.) should always appear below the staff.
Detections whose top edge is more than 1 line-spacing above the
bottom staff line are filtered as false positives.
"""

from __future__ import annotations

from mv_hofki.services.scanner.stages.base import PipelineContext

_DYNAMIC_CATEGORY = "dynamic"


class DynamicFilter:
    """Filter dynamic symbols that are positioned too high (inside/above staff)."""

    name = "dynamic_filter"

    def apply(self, ctx: PipelineContext) -> None:
        template_categories: dict[int, str] = ctx.metadata.get(
            "template_categories", {}
        )
        staff_map = {s.staff_index: s for s in ctx.staves}

        for sym in ctx.symbols:
            if sym.filtered:
                continue
            tid = sym.matched_template_id if sym.matched_template_id is not None else -1
            cat = template_categories.get(tid, "")
            if cat != _DYNAMIC_CATEGORY:
                continue

            staff = staff_map.get(sym.staff_index)
            if staff is None:
                continue

            # staff_y_top = (bottom_line_y - sym.y) / line_spacing
            # Positive means above bottom line. > 1 means more than 1 line
            # above the bottom line — too high for a dynamic.
            if sym.staff_y_top is not None and sym.staff_y_top > 1:
                sym.filtered = True
                sym.filter_reason = "dynamic_position_above_staff"
