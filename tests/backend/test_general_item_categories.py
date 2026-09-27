"""GeneralItemCategory API tests."""

import pytest

URL = "/api/v1/general-item-categories"


@pytest.fixture
async def deko(client):
    resp = await client.post(URL, json={"label": "Deko"})
    assert resp.status_code == 201
    return resp.json()


async def test_create_category_trims_label(client):
    resp = await client.post(URL, json={"label": "  Gastro  "})
    assert resp.status_code == 201
    data = resp.json()
    assert data["label"] == "Gastro"
    assert data["item_count"] == 0


async def test_empty_label_rejected(client):
    resp = await client.post(URL, json={"label": "   "})
    assert resp.status_code == 422


async def test_label_too_long_rejected(client):
    resp = await client.post(URL, json={"label": "x" * 51})
    assert resp.status_code == 422


async def test_duplicate_ignores_case_including_umlauts(client):
    assert (await client.post(URL, json={"label": "Küche"})).status_code == 201
    resp = await client.post(URL, json={"label": "KÜCHE"})
    assert resp.status_code == 409
    assert resp.json()["detail"] == "Kategorie existiert bereits"


async def test_list_sorted_by_label(client):
    for label in ("technik", "Deko", "Gastro"):
        await client.post(URL, json={"label": label})
    resp = await client.get(URL)
    assert resp.status_code == 200
    assert [c["label"] for c in resp.json()] == ["Deko", "Gastro", "technik"]


async def test_get_category(client, deko):
    resp = await client.get(f"{URL}/{deko['id']}")
    assert resp.status_code == 200
    assert resp.json() == {"id": deko["id"], "label": "Deko", "item_count": 0}


async def test_get_unknown_category_404(client):
    resp = await client.get(f"{URL}/999")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Kategorie nicht gefunden"


async def test_rename_category(client, deko):
    resp = await client.put(f"{URL}/{deko['id']}", json={"label": "Dekoration"})
    assert resp.status_code == 200
    assert resp.json()["label"] == "Dekoration"


async def test_rename_to_own_label_other_case_allowed(client, deko):
    resp = await client.put(f"{URL}/{deko['id']}", json={"label": "DEKO"})
    assert resp.status_code == 200
    assert resp.json()["label"] == "DEKO"


async def test_rename_to_existing_label_rejected(client, deko):
    await client.post(URL, json={"label": "Gastro"})
    resp = await client.put(f"{URL}/{deko['id']}", json={"label": "gastro"})
    assert resp.status_code == 409


async def test_delete_category(client, deko):
    resp = await client.delete(f"{URL}/{deko['id']}")
    assert resp.status_code == 204
    assert (await client.get(f"{URL}/{deko['id']}")).status_code == 404


async def test_delete_unknown_category_404(client):
    assert (await client.delete(f"{URL}/999")).status_code == 404
