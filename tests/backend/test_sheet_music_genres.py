"""SheetMusicGenre API tests."""

import pytest


@pytest.fixture
async def genre(client):
    resp = await client.post("/api/v1/sheet-music-genres", json={"label": "Marsch"})
    assert resp.status_code == 201
    return resp.json()


async def test_create_genre(client):
    resp = await client.post("/api/v1/sheet-music-genres", json={"label": "Polka"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["label"] == "Polka"
    assert "id" in data


async def test_list_genres(client, genre):
    resp = await client.get("/api/v1/sheet-music-genres")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert any(g["label"] == "Marsch" for g in data)


async def test_get_genre(client, genre):
    resp = await client.get(f"/api/v1/sheet-music-genres/{genre['id']}")
    assert resp.status_code == 200
    assert resp.json()["label"] == "Marsch"


async def test_update_genre(client, genre):
    resp = await client.put(
        f"/api/v1/sheet-music-genres/{genre['id']}",
        json={"label": "Walzer"},
    )
    assert resp.status_code == 200
    assert resp.json()["label"] == "Walzer"


async def test_delete_genre(client, genre):
    resp = await client.delete(f"/api/v1/sheet-music-genres/{genre['id']}")
    assert resp.status_code == 204


async def test_delete_genre_in_use_rejected(client, genre):
    """Cannot delete a genre referenced by a sheet music item."""
    await client.post(
        "/api/v1/items",
        json={
            "category": "sheet_music",
            "label": "Festmarsch",
            "owner": "Verein",
            "genre_id": genre["id"],
        },
    )
    resp = await client.delete(f"/api/v1/sheet-music-genres/{genre['id']}")
    assert resp.status_code == 409
