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
        staff_map = {s.staff_index: s for s in ctx.staves}

        barlines_by_staff: dict[int, list] = {}
        all_symbols_by_staff: dict[int, list] = {}

        for sym in ctx.symbols:
            if sym.staff_index not in all_symbols_by_staff:
                all_symbols_by_staff[sym.staff_index] = []
            all_symbols_by_staff[sym.staff_index].append(sym)

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
            barlines = barlines_by_staff.get(staff_index, [])
            barlines.sort(key=lambda s: s.staff_x_start or s.x)

            staff_symbols = all_symbols_by_staff.get(staff_index, [])
            if not staff_symbols:
                continue

            min_x = min(s.staff_x_start or s.x for s in staff_symbols)
            max_x = max(s.staff_x_end or (s.x + s.width) for s in staff_symbols)

            boundaries: list[tuple[int, int]] = []
            prev_end = min_x

            for bl in barlines:
                bl_start = bl.staff_x_start or bl.x
                bl_end = bl.staff_x_end or (bl.x + bl.width)
                if bl_start > prev_end:
                    boundaries.append((prev_end, bl_start))
                prev_end = bl_end

            if prev_end < max_x:
                boundaries.append((prev_end, max_x))

            if not boundaries:
                boundaries = [(min_x, max_x)]

            local_num = 1
            for x_start, x_end in boundaries:
                measures.append(
                    MeasureData(
                        staff_index=staff_index,
                        measure_number_in_staff=local_num,
                        global_measure_number=global_num,
                        x_start=x_start,
                        x_end=x_end,
                    )
                )
                local_num += 1
                global_num += 1

        ctx.measures = measures
        ctx.log(f"Taktstruktur erkannt: {len(measures)} Takte")
        return ctx

    def validate(self, ctx: PipelineContext) -> bool:
        return len(ctx.symbols) > 0
