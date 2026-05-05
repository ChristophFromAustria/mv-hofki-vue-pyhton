"""Tests for symbol library endpoints."""

import pytest

from mv_hofki.services.scanner.library.seed import SYMBOL_TEMPLATES


@pytest.mark.asyncio
async def test_list_symbol_templates_empty(client):
    resp = await client.get("/api/v1/scanner/library/templates")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_create_symbol_template(client):
    resp = await client.post(
        "/api/v1/scanner/library/templates",
        json={
            "category": "note",
            "name": "test_note",
            "display_name": "Testnote",
        },
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == "test_note"


@pytest.mark.asyncio
async def test_list_symbol_templates_by_category(client):
    await client.post(
        "/api/v1/scanner/library/templates",
        json={"category": "note", "name": "n1", "display_name": "Note 1"},
    )
    await client.post(
        "/api/v1/scanner/library/templates",
        json={"category": "rest", "name": "r1", "display_name": "Pause 1"},
    )
    resp = await client.get("/api/v1/scanner/library/templates?category=note")
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["category"] == "note"


@pytest.mark.asyncio
async def test_get_symbol_template(client):
    create_resp = await client.post(
        "/api/v1/scanner/library/templates",
        json={
            "category": "clef",
            "name": "treble_clef",
            "display_name": "Violinschlüssel",
        },
    )
    template_id = create_resp.json()["id"]
    resp = await client.get(f"/api/v1/scanner/library/templates/{template_id}")
    assert resp.status_code == 200
    assert resp.json()["display_name"] == "Violinschlüssel"


@pytest.mark.asyncio
async def test_update_template(client):
    resp = await client.post(
        "/api/v1/scanner/library/templates",
        json={"category": "note", "name": "test_update", "display_name": "Test Update"},
    )
    assert resp.status_code == 201
    tid = resp.json()["id"]
    resp = await client.put(
        f"/api/v1/scanner/library/templates/{tid}",
        json={
            "display_name": "Updated Name",
            "musicxml_element": "<note/>",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["display_name"] == "Updated Name"
    assert resp.json()["musicxml_element"] == "<note/>"


@pytest.mark.asyncio
async def test_delete_template(client):
    resp = await client.post(
        "/api/v1/scanner/library/templates",
        json={"category": "note", "name": "test_delete", "display_name": "Test Delete"},
    )
    tid = resp.json()["id"]
    resp = await client.delete(f"/api/v1/scanner/library/templates/{tid}")
    assert resp.status_code == 200
    resp = await client.get(f"/api/v1/scanner/library/templates/{tid}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_variant(client):
    resp = await client.post(
        "/api/v1/scanner/library/templates",
        json={
            "category": "note",
            "name": "test_del_var",
            "display_name": "Test Del Var",
        },
    )
    tid = resp.json()["id"]
    resp = await client.delete(
        f"/api/v1/scanner/library/templates/{tid}/variants/99999"
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_render_musicxml_creates_variant(client):
    """Render MusicXML should create a variant."""
    resp = await client.post(
        "/api/v1/scanner/library/templates",
        json={
            "category": "note",
            "name": "test_render_xml",
            "display_name": "Test Render XML",
            "musicxml_element": (
                "<note><pitch><step>C</step><octave>4</octave></pitch>"
                "<duration>4</duration><type>quarter</type></note>"
            ),
        },
    )
    assert resp.status_code == 201
    tid = resp.json()["id"]

    resp = await client.post(f"/api/v1/scanner/library/templates/{tid}/render-musicxml")
    assert resp.status_code == 200
    assert resp.json()["variant_count"] >= 1

    resp = await client.get(f"/api/v1/scanner/library/templates/{tid}/variants")
    variants = resp.json()
    assert any(v["source"] == "rendered_musicxml" for v in variants)


@pytest.mark.asyncio
async def test_render_musicxml_no_element_returns_400(client):
    """Render MusicXML without element should return 400."""
    resp = await client.post(
        "/api/v1/scanner/library/templates",
        json={
            "category": "note",
            "name": "test_render_empty",
            "display_name": "Test Render Empty",
        },
    )
    tid = resp.json()["id"]

    resp = await client.post(f"/api/v1/scanner/library/templates/{tid}/render-musicxml")
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_render_lilypond_no_token_returns_400(client):
    """Render LilyPond without token should return 400."""
    resp = await client.post(
        "/api/v1/scanner/library/templates",
        json={
            "category": "note",
            "name": "test_render_ly_empty",
            "display_name": "Test Render LY Empty",
        },
    )
    tid = resp.json()["id"]

    resp = await client.post(f"/api/v1/scanner/library/templates/{tid}/render-lilypond")
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_seed_data_structure():
    """Verify seed data has required fields."""
    assert len(SYMBOL_TEMPLATES) > 30
    for t in SYMBOL_TEMPLATES:
        assert "category" in t
        assert "name" in t
        assert "display_name" in t
