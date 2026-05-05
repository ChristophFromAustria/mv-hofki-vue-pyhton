"""Measure detection stage: builds measure boundaries from barline positions."""

from __future__ import annotations

from mv_hofki.services.scanner.stages.base import (
    MeasureData,
    PipelineContext,
    ProcessingStage,
)


class MeasureDetectionStage(ProcessingStage):
    """Detect measures by splitting staves at barline symbol positions."""

    name = "measure_detection"

    def process(self, ctx: PipelineContext) -> PipelineContext:
        template_categories: dict[int, str] = ctx.metadata.get(
            "template_categories", {}
        )
        template_display_names: dict[int, str] = ctx.metadata.get(
            "template_display_names", {}
        )
        staff_map = {s.staff_index: s for s in ctx.staves}

        barlines_by_staff: dict[int, list] = {}

        for sym in ctx.symbols:
            if sym.filtered:
                continue
            tid = sym.matched_template_id if sym.matched_template_id is not None else -1
            cat = template_categories.get(tid, "")
            if cat == "barline":
                if sym.staff_index not in barlines_by_staff:
                    barlines_by_staff[sym.staff_index] = []
                barlines_by_staff[sym.staff_index].append(sym)

        measures: list[MeasureData] = []
        global_num = 1

        for staff_index in sorted(staff_map.keys()):
            staff = staff_map[staff_index]

            # Skip staves without X-bounds
            if staff.x_start is None or staff.x_end is None:
                continue

            min_x = staff.x_start
            max_x = staff.x_end

            barlines = barlines_by_staff.get(staff_index, [])
            barlines.sort(key=lambda s: s.staff_x_start or s.x)

            # Deduplicate overlapping barlines — keep the one with higher confidence,
            # mark the other as filtered.
            deduped: list = []
            for bl in barlines:
                bl_start = bl.staff_x_start or bl.x
                if deduped:
                    prev = deduped[-1]
                    prev_end = prev.staff_x_end or (prev.x + prev.width)
                    if bl_start < prev_end:
                        if (bl.confidence or 0) > (prev.confidence or 0):
                            prev.filtered = True
                            prev.filter_reason = "barline_overlap_lower_confidence"
                            deduped[-1] = bl
                        else:
                            bl.filtered = True
                            bl.filter_reason = "barline_overlap_lower_confidence"
                        continue
                deduped.append(bl)
            barlines = deduped

            # Build boundaries: barline START is the boundary point
            boundary_list: list[tuple[int, int, str | None]] = []
            prev_end = min_x

            for bl in barlines:
                bl_start = bl.staff_x_start or bl.x
                if bl_start > prev_end:
                    tid = bl.matched_template_id or -1
                    bl_name = template_display_names.get(tid)
                    boundary_list.append((prev_end, bl_start, bl_name))
                prev_end = bl_start

            # Only add trailing segment if the last barline's hitbox
            # does not reach the staff end (x_end of hitbox < max_x).
            last_bl_end = 0
            if barlines:
                last = barlines[-1]
                last_bl_end = last.staff_x_end or (last.x + last.width)
            if prev_end < max_x and last_bl_end < max_x:
                boundary_list.append((prev_end, max_x, None))

            if not boundary_list:
                boundary_list = [(min_x, max_x, None)]

            local_num = 1
            min_width = staff.line_spacing
            for x_start, x_end, end_barline in boundary_list:
                if (x_end - x_start) < min_width:
                    continue
                measures.append(
                    MeasureData(
                        staff_index=staff_index,
                        measure_number_in_staff=local_num,
                        global_measure_number=global_num,
                        x_start=x_start,
                        x_end=x_end,
                        end_barline=end_barline,
                    )
                )
                local_num += 1
                global_num += 1

        ctx.measures = measures
        ctx.log(f"Taktstruktur erkannt: {len(measures)} Takte")
        return ctx

    def validate(self, ctx: PipelineContext) -> bool:
        return len(ctx.symbols) > 0
