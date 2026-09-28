"""Musician API tests."""

import pytest


@pytest.fixture
async def musician(client):
    resp = await client.post(
        "/api/v1/musicians",
        json={"first_name": "Max", "last_name": "Mustermann", "is_extern": False},
    )
    assert resp.status_code == 201
    return resp.json()


async def test_create_musician(client):
    resp = await client.post(
        "/api/v1/musicians",
        json={
            "first_name": "Anna",
            "last_name": "Huber",
            "email": "anna@example.com",
            "city": "Hofkirchen",
            "is_extern": False,
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["first_name"] == "Anna"
    assert data["city"] == "Hofkirchen"


async def test_create_musician_empty_name_rejected(client):
    resp = await client.post(
        "/api/v1/musicians",
        json={"first_name": "", "last_name": "Test", "is_extern": False},
    )
    assert resp.status_code == 422


async def test_list_musicians_search(client, musician):
    resp = await client.get("/api/v1/musicians?search=Mustermann")
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


async def test_update_musician(client, musician):
    resp = await client.put(
        f"/api/v1/musicians/{musician['id']}", json={"phone": "+43 123 456"}
    )
    assert resp.status_code == 200
    assert resp.json()["phone"] == "+43 123 456"


async def test_delete_musician(client, musician):
    resp = await client.delete(f"/api/v1/musicians/{musician['id']}")
    assert resp.status_code == 204


# ---------------------------------------------------------------------------
# List filters, sorting and paging
# ---------------------------------------------------------------------------


async def _musician(client, first, last, **extra):
    resp = await client.post(
        "/api/v1/musicians", json={"first_name": first, "last_name": last, **extra}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_filters_active_extern_and_registers(client):
    flute = (await client.post("/api/v1/registers", json={"label": "Querflöte"})).json()
    tuba = (await client.post("/api/v1/registers", json={"label": "Tuba"})).json()
    a = await _musician(client, "Anna", "Maier", register_ids=[flute["id"]])
    b = await _musician(
        client, "Berta", "Huber", is_extern=True, register_ids=[tuba["id"]]
    )
    await _musician(client, "Carl", "Aigner", is_active=False)

    async def names(query):
        resp = await client.get(f"/api/v1/musicians?{query}")
        assert resp.status_code == 200, resp.text
        return [m["first_name"] for m in resp.json()["items"]]

    assert await names("is_active=true") == ["Berta", "Anna"]
    assert await names("") == ["Carl", "Berta", "Anna"]
    assert await names("is_extern=true") == ["Berta"]
    assert await names(f"register_id__in={flute['id']},{tuba['id']}") == [
        "Berta",
        "Anna",
    ]
    assert await names(f"register_id__in={flute['id']}&is_active=true") == ["Anna"]
    assert a["id"] and b["id"]


async def test_sort_keys_and_unknown_key(client):
    await _musician(client, "Anna", "Maier")
    await _musician(client, "Zoe", "Maier")
    await _musician(client, "Carl", "Aigner")
    resp = await client.get("/api/v1/musicians?order_by=-first_name")
    assert [m["first_name"] for m in resp.json()["items"]] == ["Zoe", "Carl", "Anna"]
    resp = await client.get("/api/v1/musicians?order_by=city")
    assert resp.status_code == 422


async def test_default_sort_breaks_ties_on_the_other_name(client):
    await _musician(client, "Zoe", "Maier")
    await _musician(client, "Anna", "Maier")

    async def names(query):
        resp = await client.get(f"/api/v1/musicians?{query}")
        assert resp.status_code == 200, resp.text
        return [m["first_name"] for m in resp.json()["items"]]

    assert await names("order_by=last_name") == ["Anna", "Zoe"]
    assert await names("order_by=-last_name") == ["Zoe", "Anna"]


async def test_paging_with_equal_sort_values_has_no_gaps(client):
    for i in range(60):
        await _musician(client, f"Vorname{i:02d}", "Maier")
    first = (await client.get("/api/v1/musicians?limit=50&offset=0")).json()
    second = (await client.get("/api/v1/musicians?limit=50&offset=50")).json()
    ids = [m["id"] for m in first["items"] + second["items"]]
    assert first["total"] == 60
    assert len(ids) == 60
    assert len(set(ids)) == 60


# ---------------------------------------------------------------------------
# Grouping
# ---------------------------------------------------------------------------


async def test_group_by_register_repeats_members_and_counts(client):
    wood = (
        await client.post("/api/v1/registers", json={"label": "Holz", "sort_order": 1})
    ).json()
    brass = (
        await client.post("/api/v1/registers", json={"label": "Blech", "sort_order": 2})
    ).json()
    await _musician(client, "Anna", "Maier", register_ids=[wood["id"], brass["id"]])
    await _musician(client, "Berta", "Huber", register_ids=[brass["id"]])
    await _musician(client, "Carl", "Aigner")
    body = (await client.get("/api/v1/musicians?group_by=register")).json()
    assert [(m["first_name"], m["group_label"]) for m in body["items"]] == [
        ("Anna", "Holz"),
        ("Berta", "Blech"),
        ("Anna", "Blech"),
        ("Carl", "Ohne Register"),
    ]
    assert body["total"] == 4 and body["item_total"] == 3
    assert body["groups"] == [
        {"key": str(wood["id"]), "label": "Holz", "count": 1},
        {"key": str(brass["id"]), "label": "Blech", "count": 2},
        {"key": "", "label": "Ohne Register", "count": 1},
    ]


async def test_group_by_status_and_invalid_group(client):
    await _musician(client, "Anna", "Maier")
    await _musician(client, "Berta", "Huber", is_active=False)
    body = (await client.get("/api/v1/musicians?group_by=status")).json()
    assert [g["label"] for g in body["groups"]] == ["Aktiv", "Inaktiv"]
    assert (await client.get("/api/v1/musicians?group_by=city")).status_code == 422


async def test_without_grouping_no_group_fields(client):
    await _musician(client, "Anna", "Maier")
    body = (await client.get("/api/v1/musicians")).json()
    assert body["groups"] is None
    assert body["item_total"] == body["total"] == 1
    assert body["items"][0]["group_key"] is None


# ---------------------------------------------------------------------------
# Notes length limit
# ---------------------------------------------------------------------------


async def test_notes_max_length_on_create(client):
    ok = await client.post(
        "/api/v1/musicians",
        json={"first_name": "Anna", "last_name": "Huber", "notes": "x" * 10_000},
    )
    assert ok.status_code == 201, ok.text
    assert len(ok.json()["notes"]) == 10_000

    too_long = await client.post(
        "/api/v1/musicians",
        json={"first_name": "Anna", "last_name": "Huber", "notes": "x" * 10_001},
    )
    assert too_long.status_code == 422


async def test_notes_max_length_on_update(client, musician):
    ok = await client.put(
        f"/api/v1/musicians/{musician['id']}", json={"notes": "x" * 10_000}
    )
    assert ok.status_code == 200, ok.text
    assert len(ok.json()["notes"]) == 10_000

    too_long = await client.put(
        f"/api/v1/musicians/{musician['id']}", json={"notes": "x" * 10_001}
    )
    assert too_long.status_code == 422
