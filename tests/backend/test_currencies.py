"""Currency API tests."""

import pytest


@pytest.fixture
async def currency(client):
    resp = await client.post(
        "/api/v1/currencies", json={"label": "Euro", "abbreviation": "€"}
    )
    assert resp.status_code == 201
    return resp.json()


async def test_create_currency(client):
    resp = await client.post(
        "/api/v1/currencies", json={"label": "Euro", "abbreviation": "€"}
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["label"] == "Euro"
    assert data["abbreviation"] == "€"
    assert "id" in data


async def test_list_currencies(client, currency):
    resp = await client.get("/api/v1/currencies")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


async def test_get_currency(client, currency):
    resp = await client.get(f"/api/v1/currencies/{currency['id']}")
    assert resp.status_code == 200
    assert resp.json()["label"] == "Euro"


async def test_update_currency(client, currency):
    resp = await client.put(
        f"/api/v1/currencies/{currency['id']}", json={"label": "US Dollar"}
    )
    assert resp.status_code == 200
    assert resp.json()["label"] == "US Dollar"


async def test_delete_currency(client, currency):
    resp = await client.delete(f"/api/v1/currencies/{currency['id']}")
    assert resp.status_code == 204


async def test_get_currency_not_found(client):
    resp = await client.get("/api/v1/currencies/999")
    assert resp.status_code == 404


async def test_delete_currency_in_use_rejected(client, currency):
    """Cannot delete a currency that is referenced by an instrument."""
    itype = (
        await client.post(
            "/api/v1/instrument-types",
            json={"label": "Trompete", "label_short": "TR"},
        )
    ).json()
    await client.post(
        "/api/v1/instruments",
        json={
            "inventory_nr": 1,
            "owner": "Verein",
            "currency_id": currency["id"],
            "instrument_type_id": itype["id"],
        },
    )
    resp = await client.delete(f"/api/v1/currencies/{currency['id']}")
    assert resp.status_code == 409
