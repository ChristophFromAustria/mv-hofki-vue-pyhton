"""Processing stage base class and pipeline context."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass
class StaffData:
    """Data for a single detected staff."""

    staff_index: int
    y_top: int
    y_bottom: int
    line_positions: list[int]
    line_spacing: float
    line_thickness: int | None = None
    clef: str | None = None
    key_signature: str | None = None
    time_signature: str | None = None


@dataclass
class SymbolData:
    """Data for a single detected symbol."""

    staff_index: int
    x: int
    y: int
    width: int
    height: int
    snippet: np.ndarray | None = None
    staff_y_top: float | None = None
    staff_y_bottom: float | None = None
    staff_x_start: int | None = None
    staff_x_end: int | None = None
    sequence_order: int = 0
    matched_template_id: int | None = None
    confidence: float | None = None
    alternatives: list[tuple[int, float]] = field(default_factory=list)
    filtered: bool = False
    filter_reason: str | None = None


@dataclass
class MeasureData:
    """Data for a single detected measure (Takt)."""

    staff_index: int
    measure_number_in_staff: int
    global_measure_number: int
    x_start: int
    x_end: int
    end_barline: str | None = None


@dataclass
class PipelineContext:
    """Shared context passed between pipeline stages."""

    image: np.ndarray | None
    original_image: np.ndarray | None = None
    processed_image: np.ndarray | None = None
    corrected_image: np.ndarray | None = None
    staves: list[StaffData] = field(default_factory=list)
    symbols: list[SymbolData] = field(default_factory=list)
    measures: list[MeasureData] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    config: dict[str, Any] = field(default_factory=dict)
    completed_stages: list[str] = field(default_factory=list)
    log_callback: Callable[[str], None] | None = None

    def log(self, message: str) -> None:
        """Emit a log message via the callback if one is set."""
        if self.log_callback is not None:
            self.log_callback(message)


class ProcessingStage(ABC):
    """Abstract base for all processing pipeline stages."""

    name: str

    @abstractmethod
    def process(self, ctx: PipelineContext) -> PipelineContext:
        """Run this stage's processing on the context."""

    @abstractmethod
    def validate(self, ctx: PipelineContext) -> bool:
        """Check if prerequisites for this stage are met."""
