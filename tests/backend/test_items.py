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
    assert data["display_nr"] == "FL-001"


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
# Instrument numbering per short code
# ---------------------------------------------------------------------------


async def _itype(client, label, short):
    resp = await client.post(
        "/api/v1/instrument-types", json={"label": label, "label_short": short}
    )
    return resp.json()["id"]


async def _instrument(client, type_id, label="Inst"):
    resp = await client.post(
        "/api/v1/items",
        json={
            "category": "instrument",
            "label": label,
            "owner": "Verein",
            "instrument_type_id": type_id,
        },
    )
    assert resp.status_code == 201
    return resp.json()


async def test_instrument_numbers_run_per_short_code(client):
    """Each instrument-type short code has its own sequence (TU-001, TR-001)."""
    tuba = await _itype(client, "Tuba", "TU")
    trompete = await _itype(client, "Trompete", "TR")

    t1 = await _instrument(client, tuba)
    r1 = await _instrument(client, trompete)
    t2 = await _instrument(client, tuba)

    assert (t1["display_nr"], r1["display_nr"], t2["display_nr"]) == (
        "TU-001",
        "TR-001",
        "TU-002",
    )


async def test_types_sharing_a_short_code_share_the_sequence(client):
    b = await _itype(client, "Klarinette in B", "KL")
    es = await _itype(client, "Klarinette in Es", "KL")

    first = await _instrument(client, b)
    second = await _instrument(client, es)

    assert first["display_nr"] == "KL-001"
    assert second["display_nr"] == "KL-002"


async def test_changing_type_to_other_code_renumbers(client):
    tuba = await _itype(client, "Tuba", "TU")
    trompete = await _itype(client, "Trompete", "TR")
    await _instrument(client, trompete)
    item = await _instrument(client, tuba)

    resp = await client.put(
        f"/api/v1/items/{item['id']}", json={"instrument_type_id": trompete}
    )

    assert resp.status_code == 200
    assert resp.json()["display_nr"] == "TR-002"


async def test_changing_type_within_code_keeps_number(client):
    b = await _itype(client, "Klarinette in B", "KL")
    es = await _itype(client, "Klarinette in Es", "KL")
    item = await _instrument(client, b)

    resp = await client.put(
        f"/api/v1/items/{item['id']}", json={"instrument_type_id": es}
    )

    assert resp.json()["display_nr"] == "KL-001"


async def test_editing_short_code_keeps_existing_numbers(client):
    tuba = await _itype(client, "Tuba", "TU")
    item = await _instrument(client, tuba)

    await client.put(f"/api/v1/instrument-types/{tuba}", json={"label_short": "TB"})

    resp = await client.get(f"/api/v1/items/{item['id']}")
    assert resp.json()["display_nr"] == "TU-001"


async def test_search_matches_display_number(client):
    tuba = await _itype(client, "Tuba", "TU")
    trompete = await _itype(client, "Trompete", "TR")
    await _instrument(client, tuba, "Melton")
    await _instrument(client, tuba, "Cerveny")
    await _instrument(client, trompete, "Lechner")

    for term in ("TU-002", "tu 2", "TU2"):
        resp = await client.get(
            "/api/v1/items", params={"category": "instrument", "search": term}
        )
        labels = [i["label"] for i in resp.json()["items"]]
        assert labels == ["Cerveny"], term


async def test_instrument_list_sorted_by_code_then_number(client):
    tuba = await _itype(client, "Tuba", "TU")
    trompete = await _itype(client, "Trompete", "TR")
    await _instrument(client, tuba)
    await _instrument(client, trompete)
    await _instrument(client, tuba)

    resp = await client.get("/api/v1/items?category=instrument")
    assert [i["display_nr"] for i in resp.json()["items"]] == [
        "TR-001",
        "TU-001",
        "TU-002",
    ]


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


# ---------------------------------------------------------------------------
# Quantity
# ---------------------------------------------------------------------------


async def test_quantity_defaults_to_one_and_can_be_set(client):
    one = await client.post(
        "/api/v1/items", json={"category": "general_item", "label": "Stehleiter"}
    )
    three = await client.post(
        "/api/v1/items",
        json={"category": "general_item", "label": "Kühlschrank", "quantity": 3},
    )
    assert one.json()["quantity"] == 1
    assert three.json()["quantity"] == 3

    resp = await client.put(f"/api/v1/items/{three.json()['id']}", json={"quantity": 2})
    assert resp.json()["quantity"] == 2


async def test_quantity_must_be_positive(client):
    resp = await client.post(
        "/api/v1/items",
        json={"category": "general_item", "label": "Tisch", "quantity": 0},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Categories of general items
# ---------------------------------------------------------------------------

CATS = "/api/v1/general-item-categories"


async def _cat(client, label):
    resp = await client.post(CATS, json={"label": label})
    assert resp.status_code == 201
    return resp.json()["id"]


async def _general(client, **extra):
    resp = await client.post(
        "/api/v1/items",
        json={"category": "general_item", "label": "Stehtisch", **extra},
    )
    return resp


async def test_general_item_without_categories_has_empty_list(client):
    resp = await _general(client)
    assert resp.status_code == 201
    assert resp.json()["categories"] == []


async def test_create_general_item_with_categories_sorted_and_deduped(client):
    gastro = await _cat(client, "Gastro")
    deko = await _cat(client, "deko")
    resp = await _general(client, category_ids=[gastro, deko, gastro])
    assert resp.status_code == 201
    assert resp.json()["categories"] == [
        {"id": deko, "label": "deko"},
        {"id": gastro, "label": "Gastro"},
    ]


async def test_unknown_category_rejected_and_no_item_created(client):
    resp = await _general(client, category_ids=[999])
    assert resp.status_code == 422
    assert "Unbekannte Kategorie" in resp.json()["detail"]
    listing = await client.get("/api/v1/items?category=general_item")
    assert listing.json()["total"] == 0


async def test_update_replaces_keeps_or_clears_categories(client):
    gastro = await _cat(client, "Gastro")
    deko = await _cat(client, "Deko")
    item = (await _general(client, category_ids=[gastro])).json()
    url = f"/api/v1/items/{item['id']}"

    resp = await client.put(url, json={"category_ids": [deko]})
    assert [c["label"] for c in resp.json()["categories"]] == ["Deko"]

    resp = await client.put(url, json={"notes": "wackelt"})
    assert [c["label"] for c in resp.json()["categories"]] == ["Deko"]

    resp = await client.put(url, json={"category_ids": []})
    assert resp.json()["categories"] == []


async def test_update_with_unknown_category_rejected_and_unchanged(client):
    gastro = await _cat(client, "Gastro")
    item = (await _general(client, category_ids=[gastro])).json()
    resp = await client.put(
        f"/api/v1/items/{item['id']}", json={"category_ids": [gastro, 999]}
    )
    assert resp.status_code == 422
    detail = (await client.get(f"/api/v1/items/{item['id']}")).json()
    assert [c["label"] for c in detail["categories"]] == ["Gastro"]


async def test_category_ids_rejected_for_other_item_kinds(client, setup_refs):
    gastro = await _cat(client, "Gastro")
    resp = await client.post(
        "/api/v1/items",
        json={
            "category": "instrument",
            "label": "Flöte",
            **setup_refs,
            "category_ids": [gastro],
        },
    )
    assert resp.status_code == 422
    assert resp.json()["detail"] == "Kategorien gibt es nur für allgemeine Gegenstände"


async def test_list_contains_categories(client):
    gastro = await _cat(client, "Gastro")
    await _general(client, category_ids=[gastro])
    await _general(client)
    items = (await client.get("/api/v1/items?category=general_item")).json()["items"]
    assert [i["categories"] for i in items] == [
        [{"id": gastro, "label": "Gastro"}],
        [],
    ]


async def test_item_count_and_delete_item_removes_links(client):
    gastro = await _cat(client, "Gastro")
    item = (await _general(client, category_ids=[gastro])).json()
    assert (await client.get(f"{CATS}/{gastro}")).json()["item_count"] == 1
    assert (await client.delete(f"/api/v1/items/{item['id']}")).status_code == 204
    assert (await client.get(f"{CATS}/{gastro}")).json()["item_count"] == 0


async def test_delete_category_removes_it_from_items(client):
    gastro = await _cat(client, "Gastro")
    item = (await _general(client, category_ids=[gastro])).json()
    assert (await client.delete(f"{CATS}/{gastro}")).status_code == 204
    detail = (await client.get(f"/api/v1/items/{item['id']}")).json()
    assert detail["categories"] == []


async def test_wipe_inventory_removes_category_links(client, db_session):
    from sqlalchemy import func, select

    from mv_hofki.models.general_item_category import general_item_category_links
    from mv_hofki.services.inventar_import import wipe_inventory

    gastro = await _cat(client, "Gastro")
    await _general(client, category_ids=[gastro])
    await wipe_inventory(db_session)
    await db_session.commit()
    count = await db_session.scalar(
        select(func.count()).select_from(general_item_category_links)
    )
    assert count == 0
