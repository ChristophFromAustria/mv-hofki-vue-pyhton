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
    assert len(resp.json()["items"]) == 1


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


async def test_loan_shows_item_display_number(client, loan):
    assert loan["item"]["display_nr"] == "TR-0001"


async def test_loan_filters_sort_and_search(client):
    tu = (
        await client.post(
            "/api/v1/instrument-types", json={"label": "Tuba", "label_short": "TU"}
        )
    ).json()
    hr = (
        await client.post(
            "/api/v1/instrument-types", json={"label": "Horn", "label_short": "HR"}
        )
    ).json()
    hat_type = (
        await client.post("/api/v1/clothing-types", json={"label": "Hut"})
    ).json()

    async def item(**data):
        resp = await client.post("/api/v1/items", json=data)
        assert resp.status_code == 201, resp.text
        return resp.json()["id"]

    async def musician(first, last):
        resp = await client.post(
            "/api/v1/musicians", json={"first_name": first, "last_name": last}
        )
        return resp.json()["id"]

    async def lend(item_id, musician_id, start):
        resp = await client.post(
            "/api/v1/loans",
            json={"item_id": item_id, "musician_id": musician_id, "start_date": start},
        )
        assert resp.status_code == 201, resp.text
        return resp.json()["id"]

    tuba = await item(category="instrument", label="Tuba", instrument_type_id=tu["id"])
    hat = await item(category="clothing", label="Hut", clothing_type_id=hat_type["id"])
    horn = await item(category="instrument", label="Horn", instrument_type_id=hr["id"])
    anna_id = await musician("Anna", "Maier")
    berta_id = await musician("Berta", "Huber")
    await lend(tuba, anna_id, "2026-01-01")
    hat_loan = await lend(hat, anna_id, "2026-02-01")
    await client.put(
        f"/api/v1/loans/{hat_loan}/return", json={"end_date": "2026-03-01"}
    )
    await lend(horn, berta_id, "2026-03-01")

    def labels(r):
        assert r.status_code == 200, r.text
        return [loan["item"]["label"] for loan in r.json()["items"]]

    assert labels(await client.get("/api/v1/loans")) == ["Horn", "Hut", "Tuba"]
    assert labels(await client.get("/api/v1/loans?active=true")) == ["Horn", "Tuba"]
    assert labels(await client.get("/api/v1/loans?active=false")) == ["Hut"]
    assert labels(await client.get("/api/v1/loans?item_category=clothing")) == ["Hut"]
    assert labels(await client.get(f"/api/v1/loans?musician_id={anna_id}")) == [
        "Hut",
        "Tuba",
    ]
    assert labels(await client.get("/api/v1/loans?search=huber")) == ["Horn"]
    assert labels(await client.get("/api/v1/loans?search=tu-001")) == ["Tuba"]
    assert labels(await client.get("/api/v1/loans?order_by=start_date")) == [
        "Tuba",
        "Hut",
        "Horn",
    ]
    # NULL end dates last
    assert labels(await client.get("/api/v1/loans?order_by=-end_date")) == [
        "Hut",
        "Tuba",
        "Horn",
    ]
    body = (await client.get("/api/v1/loans?limit=2")).json()
    assert body["total"] == 3 and len(body["items"]) == 2


# ---------------------------------------------------------------------------
# Grouping
# ---------------------------------------------------------------------------


async def _setup_three_loans(client):
    tu = (
        await client.post(
            "/api/v1/instrument-types", json={"label": "Tuba", "label_short": "TU"}
        )
    ).json()
    hat_type = (
        await client.post("/api/v1/clothing-types", json={"label": "Hut"})
    ).json()

    async def item(**data):
        return (await client.post("/api/v1/items", json=data)).json()["id"]

    async def musician(first, last):
        return (
            await client.post(
                "/api/v1/musicians", json={"first_name": first, "last_name": last}
            )
        ).json()["id"]

    tuba = await item(category="instrument", label="Tuba", instrument_type_id=tu["id"])
    tuba2 = await item(category="instrument", label="Tuba", instrument_type_id=tu["id"])
    hat = await item(category="clothing", label="Hut", clothing_type_id=hat_type["id"])
    anna = await musician("Anna", "Maier")
    berta = await musician("Berta", "Huber")
    for item_id, m, start in (
        (tuba, anna, "2026-01-01"),
        (hat, anna, "2026-02-01"),
        (tuba2, berta, "2026-03-01"),
    ):
        r = await client.post(
            "/api/v1/loans",
            json={"item_id": item_id, "musician_id": m, "start_date": start},
        )
        assert r.status_code == 201
    return anna, berta


async def test_loans_group_by_musician_category_status(client):
    anna, berta = await _setup_three_loans(client)
    body = (await client.get("/api/v1/loans?group_by=musician")).json()
    assert [g["label"] for g in body["groups"]] == ["Huber Berta", "Maier Anna"]
    assert [g["count"] for g in body["groups"]] == [1, 2]
    body = (await client.get("/api/v1/loans?group_by=item_category")).json()
    assert [(g["key"], g["label"]) for g in body["groups"]] == [
        ("instrument", "Instrumente"),
        ("clothing", "Kleidung"),
    ]
    body = (await client.get("/api/v1/loans?group_by=status")).json()
    assert body["groups"] == [{"key": "offen", "label": "Offen", "count": 3}]
    assert all(row["group_key"] == "offen" for row in body["items"])


async def test_loan_notes_create_edit_clear_and_search(client, setup_data):
    resp = await client.post(
        "/api/v1/loans",
        json={**setup_data, "start_date": "2026-03-01", "notes": "  mit Koffer  "},
    )
    assert resp.status_code == 201
    loan = resp.json()
    assert loan["notes"] == "mit Koffer"

    item = (await client.get(f"/api/v1/items/{setup_data['item_id']}")).json()
    assert item["active_loan"]["notes"] == "mit Koffer"

    found = (await client.get("/api/v1/loans?search=koffer&active=true")).json()
    assert [row["id"] for row in found["items"]] == [loan["id"]]

    edited = await client.put(
        f"/api/v1/loans/{loan['id']}", json={"notes": "Mundstück fehlt"}
    )
    assert edited.json()["notes"] == "Mundstück fehlt"
    assert edited.json()["start_date"] == "2026-03-01"

    cleared = await client.put(f"/api/v1/loans/{loan['id']}", json={"notes": "   "})
    assert cleared.json()["notes"] is None


async def test_loan_notes_length_is_limited(client, setup_data):
    resp = await client.post(
        "/api/v1/loans",
        json={**setup_data, "start_date": "2026-03-01", "notes": "x" * 1001},
    )
    assert resp.status_code == 422
