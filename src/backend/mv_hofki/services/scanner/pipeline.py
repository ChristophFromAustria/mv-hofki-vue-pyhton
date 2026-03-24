"""Pipeline runner — executes processing stages in order."""

from __future__ import annotations

import logging

from mv_hofki.services.scanner.stages.base import PipelineContext, ProcessingStage

logger = logging.getLogger(__name__)


class Pipeline:
    """Runs a sequence of processing stages, respecting disabled stages."""

    def __init__(self, stages: list[ProcessingStage]) -> None:
        self.stages = stages

    def run(self, ctx: PipelineContext) -> PipelineContext:
        disabled = set(ctx.config.get("disabled_stages", []))

        for stage in self.stages:
            if stage.name in disabled:
                logger.info("Skipping disabled stage: %s", stage.name)
                continue

            if not stage.validate(ctx):
                logger.warning("Stage %s validation failed, skipping", stage.name)
                continue

            logger.info("Running stage: %s", stage.name)
            ctx = stage.process(ctx)
            ctx.completed_stages.append(stage.name)
            logger.info("Stage %s completed", stage.name)

        return ctx
