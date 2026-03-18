"""Dashboard API tests."""


async def test_dashboard_empty(client):
    resp = await client.get("/api/v1/dashboard")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_instruments"] == 0
    assert data["total_musicians"] == 0
    assert data["active_loans"] == 0
    assert data["instruments_by_type"] == []


async def test_dashboard_with_data(client):
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
    await client.post(
        "/api/v1/instruments",
        json={
            "owner": "Verein",
            "currency_id": currency["id"],
            "instrument_type_id": itype["id"],
        },
    )
    await client.post(
        "/api/v1/musicians",
        json={"first_name": "Max", "last_name": "Muster", "is_extern": False},
    )

    resp = await client.get("/api/v1/dashboard")
    data = resp.json()
    assert data["total_instruments"] == 1
    assert data["total_musicians"] == 1
    assert data["instruments_by_type"][0]["label"] == "Trompete"
    assert data["instruments_by_type"][0]["count"] == 1
