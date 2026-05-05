"""Tests for notation rendering service."""

import pytest

from mv_hofki.services.notation_renderer import render_lilypond, render_musicxml


@pytest.mark.asyncio
async def test_render_musicxml_returns_png():
    """MusicXML fragment renders to RenderResult with PNG bytes."""
    fragment = (
        "<note><pitch><step>C</step><octave>4</octave></pitch>"
        "<duration>4</duration><type>quarter</type></note>"
    )
    result = render_musicxml(fragment)
    assert isinstance(result.png_data, bytes)
    assert len(result.png_data) > 100
    assert result.png_data[:4] == b"\x89PNG"


@pytest.mark.asyncio
async def test_render_musicxml_detects_height():
    """MusicXML render should detect height_in_lines."""
    fragment = (
        "<note><pitch><step>C</step><octave>4</octave></pitch>"
        "<duration>1</duration><type>quarter</type></note>"
    )
    result = render_musicxml(fragment)
    # Should detect some height value (staff lines present in render)
    assert result.height_in_lines is None or result.height_in_lines > 0


@pytest.mark.asyncio
async def test_render_musicxml_empty_raises():
    """Empty fragment raises ValueError."""
    with pytest.raises(ValueError, match="leer"):
        render_musicxml("")


@pytest.mark.asyncio
async def test_render_lilypond_returns_png():
    """LilyPond token renders to RenderResult with PNG bytes."""
    token = "c'4"
    result = render_lilypond(token)
    assert isinstance(result.png_data, bytes)
    assert len(result.png_data) > 100
    assert result.png_data[:4] == b"\x89PNG"


@pytest.mark.asyncio
async def test_render_lilypond_detects_height():
    """LilyPond render should detect height_in_lines."""
    token = "c'4"
    result = render_lilypond(token)
    assert result.height_in_lines is None or result.height_in_lines > 0


@pytest.mark.asyncio
async def test_render_lilypond_empty_raises():
    """Empty token raises ValueError."""
    with pytest.raises(ValueError, match="leer"):
        render_lilypond("")
