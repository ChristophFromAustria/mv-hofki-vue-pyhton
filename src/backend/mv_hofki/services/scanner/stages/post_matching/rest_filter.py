"""Rest filter: removes false-positive rest symbol detections."""

from __future__ import annotations

from mv_hofki.services.scanner.stages.base import PipelineContext

_REST_CATEGORY = "rest"


class RestFilter:
    """Filter false-positive rest detections."""

    name = "rest_filter"

    def apply(self, ctx: PipelineContext) -> None:
        template_categories: dict[int, str] = ctx.metadata.get(
            "template_categories", {}
        )
        staff_map = {s.staff_index: s for s in ctx.staves}

        # Position filter: hitbox must be within 1 line_spacing of staff lines
        for sym in ctx.symbols:
            if sym.filtered:
                continue
            tid = sym.matched_template_id if sym.matched_template_id is not None else -1
            cat = template_categories.get(tid, "")
            if cat != _REST_CATEGORY:
                continue

            staff = staff_map.get(sym.staff_index)
            if staff is None:
                continue

            top_line = staff.line_positions[0]
            bottom_line = staff.line_positions[-1]
            allowed_top = top_line - staff.line_spacing
            allowed_bottom = bottom_line + staff.line_spacing
            if sym.y < allowed_top or (sym.y + sym.height) > allowed_bottom:
                sym.filtered = True
                sym.filter_reason = "rest_position_outside_staff"
