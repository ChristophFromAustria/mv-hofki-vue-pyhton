"""DetectedSymbol Pydantic schemas."""

from __future__ import annotations

from pydantic import BaseModel

from mv_hofki.schemas.symbol_template import SymbolTemplateRead


class DetectedSymbolRead(BaseModel):
    id: int
    staff_id: int
    x: int
    y: int
    width: int
    height: int
    snippet_path: str | None
    position_on_staff: int | None
    sequence_order: int
    matched_symbol_id: int | None
    confidence: float | None
    user_verified: bool
    user_corrected_symbol_id: int | None
    matched_symbol: SymbolTemplateRead | None = None
    corrected_symbol: SymbolTemplateRead | None = None

    model_config = {"from_attributes": True}


class SymbolCorrectionRequest(BaseModel):
    symbol_template_id: int
