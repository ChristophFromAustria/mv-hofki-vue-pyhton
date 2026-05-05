"""InventoryItem API tests — all categories."""

import pytest

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def currency(client):
    resp = await client.post(
        "/api/v1/currencies", json={"label": "Euro", "abbreviation": "€"}
    )
    return resp.json()


@pytest.fixture
async def setup_refs(client, currency):
    """Create a currency and instrument type for FK references."""
    itype = (
        await client.post(
            "/api/v1/instrument-types", json={"label": "Querflöte", "label_short": "FL"}
        )
    ).json()
    return {"currency_id": currency["id"], "instrument_type_id": itype["id"]}


@pytest.fixture
async def instrument(client, setup_refs):
    resp = await client.post(
        "/api/v1/items",
        json={
            "category": "instrument",
            "label": "Flöte",
            "owner": "Musikverein",
            "manufacturer": "Yamaha",
            **setup_refs,
        },
    )
    assert resp.status_code == 201
    return resp.json()


# ---------------------------------------------------------------------------
# Instrument tests (existing)
# ---------------------------------------------------------------------------


async def test_create_instrument(client, setup_refs):
    resp = await client.post(
        "/api/v1/items",
        json={
            "category": "instrument",
            "label": "Querflöte",
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
    assert data["display_nr"] == "I-001"


async def test_list_instruments_paginated(client, instrument):
    resp = await client.get("/api/v1/items?category=instrument&limit=10&offset=0")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert len(data["items"]) >= 1


async def test_list_instruments_search(client, instrument):
    resp = await client.get("/api/v1/items?category=instrument&search=Yamaha")
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


async def test_get_item(client, instrument):
    resp = await client.get(f"/api/v1/items/{instrument['id']}")
    assert resp.status_code == 200
    assert resp.json()["owner"] == "Musikverein"


async def test_update_item(client, instrument):
    resp = await client.put(
        f"/api/v1/items/{instrument['id']}", json={"notes": "Frisch gewartet"}
    )
    assert resp.status_code == 200
    assert resp.json()["notes"] == "Frisch gewartet"


async def test_delete_item(client, instrument):
    resp = await client.delete(f"/api/v1/items/{instrument['id']}")
    assert resp.status_code == 204


async def test_inventory_nr_auto_increments(client, setup_refs):
    resp1 = await client.post(
        "/api/v1/items",
        json={
            "category": "instrument",
            "label": "Inst 1",
            "owner": "Verein",
            **setup_refs,
        },
    )
    resp2 = await client.post(
        "/api/v1/items",
        json={
            "category": "instrument",
            "label": "Inst 2",
            "owner": "Verein",
            **setup_refs,
        },
    )
    assert resp1.json()["inventory_nr"] == 1
    assert resp2.json()["inventory_nr"] == 2


# ---------------------------------------------------------------------------
# Clothing item tests
# ---------------------------------------------------------------------------


async def test_create_clothing_item(client, currency):
    ctype = (await client.post("/api/v1/clothing-types", json={"label": "Hut"})).json()
    resp = await client.post(
        "/api/v1/items",
        json={
            "category": "clothing",
            "label": "Vereinshut",
            "owner": "MV Hofkirchen",
            "clothing_type_id": ctype["id"],
            "size": "L",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["display_nr"] == "K-001"
    assert data["inventory_nr"] == 1
    assert data["clothing_type"]["label"] == "Hut"
    assert data["size"] == "L"


# ---------------------------------------------------------------------------
# Sheet music item tests
# ---------------------------------------------------------------------------


async def test_create_sheet_music_item(client):
    genre = (
        await client.post("/api/v1/sheet-music-genres", json={"label": "Marsch"})
    ).json()
    resp = await client.post(
        "/api/v1/items",
        json={
            "category": "sheet_music",
            "label": "Radetzkymarsch",
            "owner": "MV Hofkirchen",
            "composer": "Strauss",
            "arranger": "Müller",
            "genre_id": genre["id"],
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["display_nr"] == "N-001"
    assert data["inventory_nr"] == 1
    assert data["composer"] == "Strauss"
    assert data["arranger"] == "Müller"
    assert data["genre"]["label"] == "Marsch"


# ---------------------------------------------------------------------------
# General item tests
# ---------------------------------------------------------------------------


async def test_create_general_item(client):
    resp = await client.post(
        "/api/v1/items",
        json={
            "category": "general_item",
            "label": "XLR-Kabel 5m",
            "owner": "MV Hofkirchen",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["display_nr"] == "A-001"
    assert data["inventory_nr"] == 1
    assert data["label"] == "XLR-Kabel 5m"


async def test_create_general_item_with_storage_location(client):
    resp = await client.post(
        "/api/v1/items",
        json={
            "category": "general_item",
            "label": "Kabelbox",
            "owner": "MV Hofkirchen",
            "storage_location": "Schrank 3",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["storage_location"] == "Schrank 3"


async def test_create_sheet_music_with_storage_location(client):
    resp = await client.post(
        "/api/v1/items",
        json={
            "category": "sheet_music",
            "label": "Festmarsch",
            "owner": "MV Hofkirchen",
            "storage_location": "Regal 2",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["storage_location"] == "Regal 2"


# ---------------------------------------------------------------------------
# Cross-category tests
# ---------------------------------------------------------------------------


async def test_inventory_nr_independent_per_category(client, setup_refs):
    """Instrument and clothing each start their own sequence from 1."""
    ctype = (
        await client.post("/api/v1/clothing-types", json={"label": "Jacke"})
    ).json()

    inst = await client.post(
        "/api/v1/items",
        json={
            "category": "instrument",
            "label": "Trompete",
            "owner": "Verein",
            **setup_refs,
        },
    )
    cloth = await client.post(
        "/api/v1/items",
        json={
            "category": "clothing",
            "label": "Vereinsjacke",
            "owner": "Verein",
            "clothing_type_id": ctype["id"],
        },
    )
    assert inst.json()["inventory_nr"] == 1
    assert cloth.json()["inventory_nr"] == 1


async def test_list_by_category_filters_correctly(client, setup_refs):
    """GET /items?category=instrument returns only instruments."""
    ctype = (await client.post("/api/v1/clothing-types", json={"label": "Hemd"})).json()

    # Create one instrument and one clothing item
    await client.post(
        "/api/v1/items",
        json={
            "category": "instrument",
            "label": "Klarinette",
            "owner": "Verein",
            **setup_refs,
        },
    )
    await client.post(
        "/api/v1/items",
        json={
            "category": "clothing",
            "label": "Vereinshemd",
            "owner": "Verein",
            "clothing_type_id": ctype["id"],
        },
    )

    resp_inst = await client.get("/api/v1/items?category=instrument")
    assert resp_inst.status_code == 200
    inst_data = resp_inst.json()
    assert inst_data["total"] == 1
    assert inst_data["items"][0]["category"] == "instrument"

    resp_cloth = await client.get("/api/v1/items?category=clothing")
    assert resp_cloth.status_code == 200
    cloth_data = resp_cloth.json()
    assert cloth_data["total"] == 1
    assert cloth_data["items"][0]["category"] == "clothing"


async def test_cost_without_currency_rejected(client, setup_refs):
    """acquisition_cost without currency_id → 422."""
    resp = await client.post(
        "/api/v1/items",
        json={
            "category": "instrument",
            "label": "Tuba",
            "owner": "Verein",
            "instrument_type_id": setup_refs["instrument_type_id"],
            "acquisition_cost": 1500.0,
            # currency_id intentionally omitted
        },
    )
    assert resp.status_code == 422
