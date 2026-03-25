"""Tests for notation rendering service."""

import pytest

from mv_hofki.services.notation_renderer import render_lilypond, render_musicxml


@pytest.mark.asyncio
async def test_render_musicxml_returns_png():
    """MusicXML fragment renders to PNG bytes."""
    fragment = (
        "<note><pitch><step>C</step><octave>4</octave></pitch>"
        "<duration>4</duration><type>quarter</type></note>"
    )
    result = render_musicxml(fragment)
    assert isinstance(result, bytes)
    assert len(result) > 100
    assert result[:4] == b"\x89PNG"


@pytest.mark.asyncio
async def test_render_musicxml_empty_raises():
    """Empty fragment raises ValueError."""
    with pytest.raises(ValueError, match="leer"):
        render_musicxml("")


@pytest.mark.asyncio
async def test_render_lilypond_returns_png():
    """LilyPond token renders to PNG bytes."""
    token = "c'4"
    result = render_lilypond(token)
    assert isinstance(result, bytes)
    assert len(result) > 100
    assert result[:4] == b"\x89PNG"


@pytest.mark.asyncio
async def test_render_lilypond_empty_raises():
    """Empty token raises ValueError."""
    with pytest.raises(ValueError, match="leer"):
        render_lilypond("")
