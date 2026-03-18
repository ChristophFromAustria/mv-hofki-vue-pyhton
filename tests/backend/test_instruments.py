"""Instrument API tests."""

import pytest


@pytest.fixture
async def setup_refs(client):
    """Create a currency and instrument type for FK references."""
    currency = (
        await client.post(
            "/api/v1/currencies", json={"label": "Euro", "abbreviation": "€"}
        )
    ).json()
    itype = (
        await client.post(
            "/api/v1/instrument-types", json={"label": "Querflöte", "label_short": "FL"}
        )
    ).json()
    return {"currency_id": currency["id"], "instrument_type_id": itype["id"]}


@pytest.fixture
async def instrument(client, setup_refs):
    resp = await client.post(
        "/api/v1/instruments",
        json={
            "owner": "Musikverein",
            "manufacturer": "Yamaha",
            **setup_refs,
        },
    )
    assert resp.status_code == 201
    return resp.json()


async def test_create_instrument(client, setup_refs):
    resp = await client.post(
        "/api/v1/instruments",
        json={
            "owner": "Musikverein",
            "serial_nr": "YM-12345",
            **setup_refs,
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["inventory_nr"] == 1
    assert data["serial_nr"] == "YM-12345"
    assert data["instrument_type"]["label"] == "Querflöte"


async def test_list_instruments_paginated(client, instrument):
    resp = await client.get("/api/v1/instruments?limit=10&offset=0")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert len(data["items"]) >= 1


async def test_list_instruments_search(client, instrument):
    resp = await client.get("/api/v1/instruments?search=Yamaha")
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


async def test_list_instruments_search_by_type(client, setup_refs, instrument):
    resp = await client.get("/api/v1/instruments?search=Querfl")
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


async def test_list_instruments_filter_by_type(client, setup_refs, instrument):
    resp = await client.get(
        f"/api/v1/instruments?type_id={setup_refs['instrument_type_id']}"
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 1
    resp2 = await client.get("/api/v1/instruments?type_id=999")
    assert resp2.json()["total"] == 0


async def test_get_instrument(client, instrument):
    resp = await client.get(f"/api/v1/instruments/{instrument['id']}")
    assert resp.status_code == 200
    assert resp.json()["owner"] == "Musikverein"


async def test_update_instrument(client, instrument):
    resp = await client.put(
        f"/api/v1/instruments/{instrument['id']}", json={"notes": "Frisch gewartet"}
    )
    assert resp.status_code == 200
    assert resp.json()["notes"] == "Frisch gewartet"


async def test_delete_instrument(client, instrument):
    resp = await client.delete(f"/api/v1/instruments/{instrument['id']}")
    assert resp.status_code == 204


async def test_inventory_nr_auto_increments(client, setup_refs):
    resp1 = await client.post(
        "/api/v1/instruments",
        json={"owner": "Verein", **setup_refs},
    )
    resp2 = await client.post(
        "/api/v1/instruments",
        json={"owner": "Verein", **setup_refs},
    )
    assert resp1.json()["inventory_nr"] == 1
    assert resp2.json()["inventory_nr"] == 2
