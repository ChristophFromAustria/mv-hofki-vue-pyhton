"""Tests for crop mark generation."""

from mv_hofki.services.lilypond_generator import add_crop_marks_to_pdf


def test_crop_marks_content_stream():
    """add_crop_marks_to_pdf returns a valid PDF content stream.

    Checks that PDF drawing operators m, l, S, and w are present.
    """
    content = add_crop_marks_to_pdf(
        page_width_mm=210.0,
        page_height_mm=148.0,
        crop_width_mm=165.0,
        crop_height_mm=123.0,
    )
    decoded = content.decode("latin-1")
    assert " m " in decoded or " m\n" in decoded
    assert " l " in decoded or " l\n" in decoded
    assert "S" in decoded
    assert "w" in decoded


def test_crop_marks_centered():
    """Crop marks should be centered on the page."""
    content = add_crop_marks_to_pdf(
        page_width_mm=210.0,
        page_height_mm=148.0,
        crop_width_mm=165.0,
        crop_height_mm=123.0,
    )
    decoded = content.decode("latin-1")
    # Left offset = (210-165)/2 = 22.5mm = ~63.78pt
    assert "63" in decoded
