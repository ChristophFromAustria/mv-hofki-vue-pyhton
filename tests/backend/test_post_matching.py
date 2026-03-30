"""Tests for the post-matching stage."""

import numpy as np

from mv_hofki.services.scanner.stages.base import PipelineContext, StaffData, SymbolData
from mv_hofki.services.scanner.stages.template_matching import TemplateMatchingStage


def test_symbol_data_has_filter_fields():
    """SymbolData should have filtered and filter_reason fields."""
    sym = SymbolData(staff_index=0, x=10, y=20, width=5, height=40)
    assert sym.filtered is False
    assert sym.filter_reason is None


def test_template_matching_exposes_display_names():
    """TemplateMatchingStage should store display names in ctx.metadata."""
    staff = StaffData(
        staff_index=0,
        y_top=10,
        y_bottom=170,
        line_positions=[10, 30, 50, 70, 90],
        line_spacing=20.0,
    )
    img = np.full((200, 400), 255, dtype=np.uint8)
    display_names = {42: "Einfacher Taktstrich"}

    stage = TemplateMatchingStage(
        variant_images=[],
        variant_template_ids=[],
        variant_heights=[],
        variant_line_spacings=[],
        template_display_names=display_names,
    )

    ctx = PipelineContext(image=img, staves=[staff], config={})
    result = stage.process(ctx)
    assert result.metadata["template_display_names"] == {42: "Einfacher Taktstrich"}
