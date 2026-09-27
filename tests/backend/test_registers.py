"""Registers and the musicians' active flag / register membership."""


async def _register(client, label, **kw):
    resp = await client.post("/api/v1/registers", json={"label": label, **kw})
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _musician(client, first, last, **kw):
    resp = await client.post(
        "/api/v1/musicians", json={"first_name": first, "last_name": last, **kw}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_register_crud_and_order(client):
    await _register(client, "Tuba", sort_order=8)
    horn = await _register(client, "Horn", sort_order=6, expects_instrument=True)
    schlag = await _register(
        client, "Schlagwerk", sort_order=9, expects_instrument=False
    )

    resp = await client.get("/api/v1/registers")
    assert [r["label"] for r in resp.json()] == ["Horn", "Tuba", "Schlagwerk"]
    assert schlag["expects_instrument"] is False
    assert horn["expects_instrument"] is True

    resp = await client.put(
        f"/api/v1/registers/{horn['id']}", json={"label": "Waldhorn"}
    )
    assert resp.json()["label"] == "Waldhorn"


async def test_musician_is_active_by_default_and_gets_registers(client):
    tuba = await _register(client, "Tuba")
    horn = await _register(client, "Horn")

    m = await _musician(client, "Anna", "Hofer", register_ids=[tuba["id"], horn["id"]])

    assert m["is_active"] is True
    assert sorted(r["label"] for r in m["registers"]) == ["Horn", "Tuba"]


async def test_update_replaces_registers_and_active_flag(client):
    tuba = await _register(client, "Tuba")
    horn = await _register(client, "Horn")
    m = await _musician(client, "Anna", "Hofer", register_ids=[tuba["id"]])

    resp = await client.put(
        f"/api/v1/musicians/{m['id']}",
        json={"register_ids": [horn["id"]], "is_active": False, "notes": "pausiert"},
    )

    data = resp.json()
    assert [r["label"] for r in data["registers"]] == ["Horn"]
    assert data["is_active"] is False
    assert data["notes"] == "pausiert"


async def test_update_without_register_ids_keeps_registers(client):
    tuba = await _register(client, "Tuba")
    m = await _musician(client, "Anna", "Hofer", register_ids=[tuba["id"]])

    resp = await client.put(f"/api/v1/musicians/{m['id']}", json={"phone": "0664"})

    assert [r["label"] for r in resp.json()["registers"]] == ["Tuba"]


async def test_unknown_register_is_rejected(client):
    resp = await client.post(
        "/api/v1/musicians",
        json={"first_name": "Anna", "last_name": "Hofer", "register_ids": [999]},
    )
    assert resp.status_code == 400


async def test_musician_list_filters_active_and_register(client):
    tuba = await _register(client, "Tuba")
    await _musician(client, "Anna", "Aktiv", register_ids=[tuba["id"]])
    await _musician(client, "Bert", "Aktiv")
    await _musician(
        client, "Carl", "Inaktiv", is_active=False, register_ids=[tuba["id"]]
    )

    def names(resp):
        return sorted(m["first_name"] for m in resp.json()["items"])

    assert names(await client.get("/api/v1/musicians?is_active=true")) == [
        "Anna",
        "Bert",
    ]
    assert names(await client.get("/api/v1/musicians?is_active=false")) == ["Carl"]
    assert names(await client.get("/api/v1/musicians")) == ["Anna", "Bert", "Carl"]
    resp = await client.get(
        f"/api/v1/musicians?register_id__in={tuba['id']}&is_active=true"
    )
    assert names(resp) == ["Anna"]


async def test_register_in_use_cannot_be_deleted(client):
    tuba = await _register(client, "Tuba")
    await _musician(client, "Anna", "Hofer", register_ids=[tuba["id"]])

    resp = await client.delete(f"/api/v1/registers/{tuba['id']}")

    assert resp.status_code == 409
