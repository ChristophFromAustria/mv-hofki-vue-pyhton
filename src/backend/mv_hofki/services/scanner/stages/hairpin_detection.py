"""Hairpin detection: find crescendo/decrescendo wedges below staves via Hough."""

from __future__ import annotations

import cv2
import numpy as np

from mv_hofki.services.scanner.stages.base import (
    PipelineContext,
    ProcessingStage,
    SymbolData,
)


class HairpinDetectionStage(ProcessingStage):
    """Detect crescendo/decrescendo hairpins below staff lines using Hough."""

    name = "hairpin_detection"

    def process(self, ctx: PipelineContext) -> PipelineContext:
        binary = ctx.processed_image
        if binary is None:
            return ctx

        staves = sorted(ctx.staves, key=lambda s: s.staff_index)
        hairpins: list[SymbolData] = []
        debug_lines: list[dict] = []

        # Look up template IDs for crescendo/decrescendo from metadata
        display_names: dict[int, str] = ctx.metadata.get("template_display_names", {})
        cresc_id = None
        decresc_id = None
        for tid, name in display_names.items():
            if name == "Crescendo":
                cresc_id = tid
            elif name == "Decrescendo":
                decresc_id = tid

        for staff in staves:
            bottom_line = max(staff.line_positions)
            region_top = bottom_line
            region_bottom = staff.y_bottom

            if region_top >= region_bottom:
                continue

            region = binary[region_top:region_bottom, :]
            inverted = cv2.bitwise_not(region)

            edges = cv2.Canny(inverted, 50, 150, apertureSize=3)
            lines = cv2.HoughLinesP(
                edges,
                rho=1,
                theta=np.pi / 180,
                threshold=20,
                minLineLength=20,
                maxLineGap=10,
            )

            if lines is None:
                continue

            # Collect angled lines (hairpins are 5-30 degrees from horizontal)
            angled: list[tuple[int, int, int, int, float]] = []
            for line in lines:
                x1, y1, x2, y2 = line[0]
                abs_y1 = region_top + y1
                abs_y2 = region_top + y2
                angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))
                abs_angle = abs(angle)

                # Store all lines for debug
                debug_lines.append(
                    {
                        "x1": int(x1),
                        "y1": int(abs_y1),
                        "x2": int(x2),
                        "y2": int(abs_y2),
                        "staff_index": staff.staff_index,
                    }
                )

                # Hairpin lines are angled 3-25 degrees from horizontal
                if 3 <= abs_angle <= 25:
                    angled.append((int(x1), int(abs_y1), int(x2), int(abs_y2), angle))

            # Pair angled lines into V-shapes (crescendo/decrescendo)
            found = _find_hairpin_pairs(angled, staff.line_spacing)
            for hp_type, x_min, y_min, x_max, y_max in found:
                template_id = cresc_id if hp_type == "crescendo" else decresc_id
                bottom_line_y = max(staff.line_positions)
                ls = staff.line_spacing
                hairpins.append(
                    SymbolData(
                        staff_index=staff.staff_index,
                        x=x_min,
                        y=y_min,
                        width=x_max - x_min,
                        height=max(y_max - y_min, int(ls // 2)),
                        staff_y_top=round((bottom_line_y - y_min) / ls, 2),
                        staff_y_bottom=round((bottom_line_y - y_max) / ls, 2),
                        staff_x_start=x_min,
                        staff_x_end=x_max,
                        matched_template_id=template_id,
                        confidence=0.5,
                    )
                )
                ctx.log(
                    f"  Hairpin ({hp_type}) erkannt: "
                    f"System {staff.staff_index}, x={x_min}-{x_max}"
                )

        # Add hairpins to symbols list
        for hp in hairpins:
            hp.sequence_order = len(ctx.symbols)
            ctx.symbols.append(hp)

        ctx.metadata["hairpin_debug_lines"] = debug_lines
        ctx.log(
            f"Hairpin-Erkennung: {len(hairpins)} Crescendo/Decrescendo, "
            f"{len(debug_lines)} Hough-Linien"
        )
        return ctx

    def validate(self, ctx: PipelineContext) -> bool:
        return ctx.processed_image is not None and len(ctx.staves) > 0


def _find_hairpin_pairs(
    angled_lines: list[tuple[int, int, int, int, float]],
    line_spacing: float,
) -> list[tuple[str, int, int, int, int]]:
    """Find V-shaped pairs of angled lines (crescendo/decrescendo).

    A hairpin is two lines that:
    - Have opposite angles (one going up, one going down)
    - Share a common vertex (the point of the V)
    - The vertex ends are close together (within 1 line_spacing)

    Returns list of (type, x_min, y_min, x_max, y_max) where type is
    'crescendo' or 'decrescendo'.
    """
    if len(angled_lines) < 2:
        return []

    max_vertex_gap = line_spacing * 1.5
    results: list[tuple[str, int, int, int, int]] = []
    used: set[int] = set()

    for i, (x1a, y1a, x2a, y2a, angle_a) in enumerate(angled_lines):
        if i in used:
            continue
        for j, (x1b, y1b, x2b, y2b, angle_b) in enumerate(angled_lines):
            if j <= i or j in used:
                continue
            # Opposite angles (one positive, one negative)
            if angle_a * angle_b >= 0:
                continue

            # Find the vertex: the ends that are closest together
            # Check all 4 endpoint combinations
            pairs = [
                ((x1a, y1a), (x1b, y1b), (x2a, y2a), (x2b, y2b)),
                ((x1a, y1a), (x2b, y2b), (x2a, y2a), (x1b, y1b)),
                ((x2a, y2a), (x1b, y1b), (x1a, y1a), (x2b, y2b)),
                ((x2a, y2a), (x2b, y2b), (x1a, y1a), (x1b, y1b)),
            ]

            for (vxa, vya), (vxb, vyb), (ea, _eya), (eb, _eyb) in pairs:
                dist = np.hypot(vxa - vxb, vya - vyb)
                if dist > max_vertex_gap:
                    continue

                # Vertex is the close end, open end is the far end
                vertex_x = (vxa + vxb) // 2
                open_a_x = ea
                open_b_x = eb

                # Determine type: vertex on left = crescendo, right = decrescendo
                avg_open_x = (open_a_x + open_b_x) / 2
                if vertex_x < avg_open_x:
                    hp_type = "crescendo"
                else:
                    hp_type = "decrescendo"

                all_x = [x1a, x2a, x1b, x2b]
                all_y = [y1a, y2a, y1b, y2b]
                results.append(
                    (
                        hp_type,
                        min(all_x),
                        min(all_y),
                        max(all_x),
                        max(all_y),
                    )
                )
                used.add(i)
                used.add(j)
                break

            if i in used:
                break

    return results
