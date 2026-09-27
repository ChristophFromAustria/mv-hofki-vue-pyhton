"""POST /items/bulk-categories."""

import pytest

URL = "/api/v1/items/bulk-categories"
CATS = "/api/v1/general-item-categories"


@pytest.fixture
async def data(client):
    deko = (await client.post(CATS, json={"label": "Deko"})).json()["id"]
    fest = (await client.post(CATS, json={"label": "Fest"})).json()["id"]

    async def item(label, **extra):
        r = await client.post(
            "/api/v1/items", json={"category": "general_item", "label": label, **extra}
        )
        return r.json()["id"]

    a = await item("Girlande", category_ids=[deko])
    b = await item("Leiter")
    return {"deko": deko, "fest": fest, "a": a, "b": b}


async def _cats(client, item_id):
    return [
        c["label"]
        for c in (await client.get(f"/api/v1/items/{item_id}")).json()["categories"]
    ]


async def test_add_and_remove(client, data):
    r = await client.post(
        URL, json={"item_ids": [data["a"], data["b"]], "add_ids": [data["fest"]]}
    )
    assert r.status_code == 200 and r.json() == {"updated": 2}
    assert await _cats(client, data["a"]) == ["Deko", "Fest"]
    assert await _cats(client, data["b"]) == ["Fest"]
    r = await client.post(
        URL, json={"item_ids": [data["a"], data["b"]], "remove_ids": [data["deko"]]}
    )
    assert r.json() == {"updated": 2}
    assert await _cats(client, data["a"]) == ["Fest"]
    assert await _cats(client, data["b"]) == ["Fest"]


async def test_adding_twice_is_idempotent(client, data):
    body = {"item_ids": [data["a"]], "add_ids": [data["deko"]]}
    assert (await client.post(URL, json=body)).status_code == 200
    assert await _cats(client, data["a"]) == ["Deko"]


@pytest.mark.parametrize(
    "payload, detail",
    [
        ({"add_ids": [], "remove_ids": []}, "Keine Kategorien angegeben"),
        (
            {"add_ids": ["deko"], "remove_ids": ["deko"]},
            "Kategorie kann nicht gleichzeitig hinzugefügt und entfernt werden",
        ),
        ({"add_ids": [999]}, "Unbekannte Kategorie: 999"),
    ],
)
async def test_validation_errors(client, data, payload, detail):
    payload = {
        k: [data[x] if isinstance(x, str) else x for x in v] for k, v in payload.items()
    }
    r = await client.post(URL, json={"item_ids": [data["a"]], **payload})
    assert r.status_code == 422
    assert r.json()["detail"] == detail
    assert await _cats(client, data["a"]) == ["Deko"]


async def test_non_general_items_rejected(client, data):
    tu = (
        await client.post(
            "/api/v1/instrument-types", json={"label": "Tuba", "label_short": "TU"}
        )
    ).json()
    inst = (
        await client.post(
            "/api/v1/items",
            json={
                "category": "instrument",
                "label": "Tuba",
                "instrument_type_id": tu["id"],
            },
        )
    ).json()["id"]
    r = await client.post(
        URL, json={"item_ids": [data["a"], inst, 999], "add_ids": [data["fest"]]}
    )
    assert r.status_code == 422
    assert r.json()["detail"] == f"Nur allgemeine Gegenstände: {inst}, 999"
    assert await _cats(client, data["a"]) == ["Deko"]


async def test_item_ids_required(client, data):
    r = await client.post(URL, json={"item_ids": [], "add_ids": [data["fest"]]})
    assert r.status_code == 422
