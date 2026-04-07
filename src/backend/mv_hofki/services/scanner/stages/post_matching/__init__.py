"""Post-matching stage: filters and cleans up template matching results."""

from __future__ import annotations

import logging
from typing import Protocol

from mv_hofki.services.scanner.stages.base import PipelineContext, ProcessingStage
from mv_hofki.services.scanner.stages.post_matching.barline_filter import BarlineFilter
from mv_hofki.services.scanner.stages.post_matching.dynamic_filter import DynamicFilter

logger = logging.getLogger(__name__)


class PostMatchingOperation(Protocol):
    """Protocol for post-matching sub-operations."""

    name: str

    def apply(self, ctx: PipelineContext) -> None: ...


class PostMatchingStage(ProcessingStage):
    """Runs post-matching sub-operations on detected symbols."""

    name = "post_matching"

    def __init__(self) -> None:
        self._operations: list[PostMatchingOperation] = [
            BarlineFilter(),
            DynamicFilter(),
        ]

    def process(self, ctx: PipelineContext) -> PipelineContext:
        for op in self._operations:
            ctx.log(f"  Post-Matching: {op.name}...")
            op.apply(ctx)
            filtered_count = sum(1 for s in ctx.symbols if s.filtered)
            ctx.log(
                f"  Post-Matching: {op.name} abgeschlossen ({filtered_count} gefiltert)"
            )
        return ctx

    def validate(self, ctx: PipelineContext) -> bool:
        return len(ctx.symbols) > 0
