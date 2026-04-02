"""DetectedSymbol Pydantic schemas."""

from __future__ import annotations

from pydantic import BaseModel

from mv_hofki.schemas.symbol_template import SymbolTemplateRead


class AlternativeMatch(BaseModel):
    template_id: int
    confidence: float
    display_name: str | None = None


class DetectedSymbolRead(BaseModel):
    id: int
    staff_id: int
    x: int
    y: int
    width: int
    height: int
    snippet_path: str | None
    staff_y_top: float | None
    staff_y_bottom: float | None
    staff_x_start: int | None
    staff_x_end: int | None
    sequence_order: int
    matched_symbol_id: int | None
    confidence: float | None
    user_verified: bool
    user_corrected_symbol_id: int | None
    matched_symbol: SymbolTemplateRead | None = None
    corrected_symbol: SymbolTemplateRead | None = None
    alternatives: list[AlternativeMatch] = []
    filtered: bool = False
    filter_reason: str | None = None

    model_config = {"from_attributes": True}


class SymbolCorrectionRequest(BaseModel):
    symbol_template_id: int
