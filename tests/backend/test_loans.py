"""Loan API tests."""

import pytest


@pytest.fixture
async def setup_data(client):
    """Create currency, type, item, and musician for loan tests."""
    currency = (
        await client.post(
            "/api/v1/currencies", json={"label": "Euro", "abbreviation": "€"}
        )
    ).json()
    itype = (
        await client.post(
            "/api/v1/instrument-types", json={"label": "Trompete", "label_short": "TR"}
        )
    ).json()
    item = (
        await client.post(
            "/api/v1/items",
            json={
                "category": "instrument",
                "label": "Trompete",
                "owner": "Verein",
                "currency_id": currency["id"],
                "instrument_type_id": itype["id"],
            },
        )
    ).json()
    musician = (
        await client.post(
            "/api/v1/musicians",
            json={"first_name": "Max", "last_name": "Muster", "is_extern": False},
        )
    ).json()
    return {"item_id": item["id"], "musician_id": musician["id"]}


@pytest.fixture
async def loan(client, setup_data):
    resp = await client.post(
        "/api/v1/loans",
        json={**setup_data, "start_date": "2026-01-15"},
    )
    assert resp.status_code == 201
    return resp.json()


async def test_create_loan(client, setup_data):
    resp = await client.post(
        "/api/v1/loans",
        json={**setup_data, "start_date": "2026-03-01"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["end_date"] is None
    assert data["item"]["inventory_nr"] == 1


async def test_duplicate_active_loan_rejected(client, setup_data, loan):
    resp = await client.post(
        "/api/v1/loans",
        json={**setup_data, "start_date": "2026-03-01"},
    )
    assert resp.status_code == 409


async def test_return_item(client, loan):
    resp = await client.put(f"/api/v1/loans/{loan['id']}/return")
    assert resp.status_code == 200
    assert resp.json()["end_date"] is not None


async def test_list_active_loans(client, loan):
    resp = await client.get("/api/v1/loans?active=true")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


async def test_return_already_returned(client, loan):
    await client.put(f"/api/v1/loans/{loan['id']}/return")
    resp = await client.put(f"/api/v1/loans/{loan['id']}/return")
    assert resp.status_code == 409


async def test_return_with_custom_date(client, setup_data, loan):
    resp = await client.put(
        f"/api/v1/loans/{loan['id']}/return",
        json={"end_date": "2026-02-28"},
    )
    assert resp.status_code == 200
    assert resp.json()["end_date"] == "2026-02-28"


async def test_delete_musician_with_active_loan_rejected(client, setup_data, loan):
    """Cannot delete a musician who has an active loan."""
    resp = await client.delete(f"/api/v1/musicians/{setup_data['musician_id']}")
    assert resp.status_code == 409


async def test_create_loan_for_sheet_music_rejected(client, setup_data):
    """Sheet music items cannot be loaned → 400."""
    sheet_music = (
        await client.post(
            "/api/v1/items",
            json={
                "category": "sheet_music",
                "label": "Festmarsch",
                "owner": "Verein",
            },
        )
    ).json()
    resp = await client.post(
        "/api/v1/loans",
        json={
            "item_id": sheet_music["id"],
            "musician_id": setup_data["musician_id"],
            "start_date": "2026-03-01",
        },
    )
    assert resp.status_code == 400
