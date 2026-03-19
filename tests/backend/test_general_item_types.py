"""GeneralItemType API tests."""

import pytest


@pytest.fixture
async def general_item_type(client):
    resp = await client.post("/api/v1/general-item-types", json={"label": "Kabel"})
    assert resp.status_code == 201
    return resp.json()


async def test_create_general_item_type(client):
    resp = await client.post("/api/v1/general-item-types", json={"label": "Stativ"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["label"] == "Stativ"
    assert "id" in data


async def test_list_general_item_types(client, general_item_type):
    resp = await client.get("/api/v1/general-item-types")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert any(t["label"] == "Kabel" for t in data)


async def test_get_general_item_type(client, general_item_type):
    resp = await client.get(f"/api/v1/general-item-types/{general_item_type['id']}")
    assert resp.status_code == 200
    assert resp.json()["label"] == "Kabel"


async def test_update_general_item_type(client, general_item_type):
    resp = await client.put(
        f"/api/v1/general-item-types/{general_item_type['id']}",
        json={"label": "Mikrofon"},
    )
    assert resp.status_code == 200
    assert resp.json()["label"] == "Mikrofon"


async def test_delete_general_item_type(client, general_item_type):
    resp = await client.delete(f"/api/v1/general-item-types/{general_item_type['id']}")
    assert resp.status_code == 204


async def test_delete_general_item_type_in_use_rejected(client, general_item_type):
    """Cannot delete a general item type referenced by an item."""
    await client.post(
        "/api/v1/items",
        json={
            "category": "general_item",
            "label": "XLR-Kabel 5m",
            "owner": "Verein",
            "general_item_type_id": general_item_type["id"],
        },
    )
    resp = await client.delete(f"/api/v1/general-item-types/{general_item_type['id']}")
    assert resp.status_code == 409
