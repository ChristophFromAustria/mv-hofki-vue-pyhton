"""Dynamic masking stage: erase dynamic symbols from the binary image.

Runs after post-matching and before hairpin detection. Overwrites the
hitbox area of all unfiltered dynamic symbols with white pixels so
they don't produce false positives in Hough-based line detection.
"""

from __future__ import annotations

from mv_hofki.services.scanner.stages.base import PipelineContext, ProcessingStage

_DYNAMIC_CATEGORY = "dynamic"


class DynamicMaskingStage(ProcessingStage):
    """Mask dynamic symbols in the binary image."""

    name = "dynamic_masking"

    def process(self, ctx: PipelineContext) -> PipelineContext:
        binary = ctx.processed_image
        if binary is None:
            return ctx

        template_categories: dict[int, str] = ctx.metadata.get(
            "template_categories", {}
        )

        masked = 0
        for sym in ctx.symbols:
            if sym.filtered:
                continue
            tid = sym.matched_template_id if sym.matched_template_id is not None else -1
            cat = template_categories.get(tid, "")
            if cat != _DYNAMIC_CATEGORY:
                continue

            binary[sym.y : sym.y + sym.height, sym.x : sym.x + sym.width] = 255
            masked += 1

        ctx.log(f"Dynamic-Maskierung: {masked} Symbole maskiert")
        return ctx

    def validate(self, ctx: PipelineContext) -> bool:
        return ctx.processed_image is not None and len(ctx.symbols) > 0
