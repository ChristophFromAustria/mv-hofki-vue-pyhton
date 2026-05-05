"""Barline filter: removes false-positive single barline detections."""

from __future__ import annotations

from mv_hofki.services.scanner.stages.base import PipelineContext, SymbolData

# Display-name substrings that take priority over single barlines.
_BARLINE_PRIORITY_NAMES = [
    "Wiederholung",
    "Schlusstaktstrich",
    "Achtel",
    "Viertel",
    "Sechzehntel",
    "Halbe",
    "Doppelter Taktstrich",
]

_SINGLE_BARLINE_DISPLAY_NAME = "Einfacher Taktstrich"


class BarlineFilter:
    """Filter false-positive single barline detections."""

    name = "barline_filter"

    def apply(self, ctx: PipelineContext) -> None:
        display_names: dict[int, str] = ctx.metadata.get("template_display_names", {})
        staff_map = {s.staff_index: s for s in ctx.staves}

        # Step 1: Position filter
        for sym in ctx.symbols:
            if sym.filtered:
                continue
            dn = display_names.get(
                sym.matched_template_id if sym.matched_template_id is not None else -1,
                "",
            )
            if dn != _SINGLE_BARLINE_DISPLAY_NAME:
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
                sym.filter_reason = "barline_position_outside_staff"

        # Step 2: Overlap filter
        self._apply_overlap_filter(ctx.symbols, display_names)

    def _apply_overlap_filter(
        self,
        symbols: list[SymbolData],
        display_names: dict[int, str],
    ) -> None:
        for i, sym_a in enumerate(symbols):
            if sym_a.filtered:
                continue
            for j, sym_b in enumerate(symbols):
                if i == j or sym_b.filtered:
                    continue
                if not self._boxes_overlap(sym_a, sym_b):
                    continue

                dn_a = display_names.get(
                    sym_a.matched_template_id
                    if sym_a.matched_template_id is not None
                    else -1,
                    "",
                )
                dn_b = display_names.get(
                    sym_b.matched_template_id
                    if sym_b.matched_template_id is not None
                    else -1,
                    "",
                )

                a_is_single = dn_a == _SINGLE_BARLINE_DISPLAY_NAME
                b_is_single = dn_b == _SINGLE_BARLINE_DISPLAY_NAME

                # Case: single barline overlaps with a priority symbol
                if a_is_single and self._is_priority(dn_b):
                    sym_a.filtered = True
                    sym_a.filter_reason = f"barline_overlap_with_{dn_b}"
                    break
                if b_is_single and self._is_priority(dn_a):
                    sym_b.filtered = True
                    sym_b.filter_reason = f"barline_overlap_with_{dn_a}"
                    continue

                # Case: single barline overlaps with non-priority symbol
                if a_is_single or b_is_single:
                    if (sym_a.confidence or 0) <= (sym_b.confidence or 0):
                        sym_a.filtered = True
                        sym_a.filter_reason = "overlap_lower_confidence"
                        break
                    else:
                        sym_b.filtered = True
                        sym_b.filter_reason = "overlap_lower_confidence"

    @staticmethod
    def _is_priority(display_name: str) -> bool:
        return any(p in display_name for p in _BARLINE_PRIORITY_NAMES)

    @staticmethod
    def _boxes_overlap(a: SymbolData, b: SymbolData) -> bool:
        return (
            a.x < b.x + b.width
            and a.x + a.width > b.x
            and a.y < b.y + b.height
            and a.y + a.height > b.y
        )
