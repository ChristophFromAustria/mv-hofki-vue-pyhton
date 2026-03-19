"""ClothingType API tests."""

import pytest


@pytest.fixture
async def clothing_type(client):
    resp = await client.post("/api/v1/clothing-types", json={"label": "Hut"})
    assert resp.status_code == 201
    return resp.json()


async def test_create_clothing_type(client):
    resp = await client.post("/api/v1/clothing-types", json={"label": "Jacke"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["label"] == "Jacke"
    assert "id" in data


async def test_list_clothing_types(client, clothing_type):
    resp = await client.get("/api/v1/clothing-types")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert any(ct["label"] == "Hut" for ct in data)


async def test_get_clothing_type(client, clothing_type):
    resp = await client.get(f"/api/v1/clothing-types/{clothing_type['id']}")
    assert resp.status_code == 200
    assert resp.json()["label"] == "Hut"


async def test_update_clothing_type(client, clothing_type):
    resp = await client.put(
        f"/api/v1/clothing-types/{clothing_type['id']}",
        json={"label": "Kappe"},
    )
    assert resp.status_code == 200
    assert resp.json()["label"] == "Kappe"


async def test_delete_clothing_type(client, clothing_type):
    resp = await client.delete(f"/api/v1/clothing-types/{clothing_type['id']}")
    assert resp.status_code == 204


async def test_delete_clothing_type_in_use_rejected(client, clothing_type):
    """Cannot delete a clothing type referenced by an item."""
    await client.post(
        "/api/v1/items",
        json={
            "category": "clothing",
            "label": "Vereinshut",
            "owner": "Verein",
            "clothing_type_id": clothing_type["id"],
        },
    )
    resp = await client.delete(f"/api/v1/clothing-types/{clothing_type['id']}")
    assert resp.status_code == 409
