"""InstrumentType API tests."""

import pytest


@pytest.fixture
async def instrument_type(client):
    resp = await client.post(
        "/api/v1/instrument-types", json={"label": "Querflöte", "label_short": "FL"}
    )
    assert resp.status_code == 201
    return resp.json()


async def test_create_instrument_type(client):
    resp = await client.post(
        "/api/v1/instrument-types", json={"label": "Klarinette", "label_short": "KL"}
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["label"] == "Klarinette"
    assert data["label_short"] == "KL"


async def test_list_instrument_types(client, instrument_type):
    resp = await client.get("/api/v1/instrument-types")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


async def test_update_instrument_type(client, instrument_type):
    resp = await client.put(
        f"/api/v1/instrument-types/{instrument_type['id']}",
        json={"label": "Piccolo"},
    )
    assert resp.status_code == 200
    assert resp.json()["label"] == "Piccolo"


async def test_delete_instrument_type(client, instrument_type):
    resp = await client.delete(f"/api/v1/instrument-types/{instrument_type['id']}")
    assert resp.status_code == 204


async def test_delete_instrument_type_in_use_rejected(client, instrument_type):
    """Cannot delete an instrument type that is referenced by an item."""
    await client.post(
        "/api/v1/items",
        json={
            "category": "instrument",
            "label": "Querflöte",
            "owner": "Verein",
            "instrument_type_id": instrument_type["id"],
        },
    )
    resp = await client.delete(f"/api/v1/instrument-types/{instrument_type['id']}")
    assert resp.status_code == 409
