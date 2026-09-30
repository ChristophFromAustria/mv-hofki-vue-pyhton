"""Event log: changes are recorded while saving, with who, old → new."""

URL = "/api/v1/events"
ME = {"Cf-Access-Authenticated-User-Email": "zeugwart@mv-hofkirchen.at"}


async def _events(client, **params):
    resp = await client.get(URL, params={"limit": 100, **params})
    assert resp.status_code == 200, resp.text
    return resp.json()["items"]


async def _setup(client):
    tr = (
        await client.post(
            "/api/v1/instrument-types",
            json={"label": "Trompete", "label_short": "TR"},
            headers=ME,
        )
    ).json()["id"]
    fh = (
        await client.post(
            "/api/v1/instrument-types",
            json={"label": "Flügelhorn", "label_short": "FH"},
        )
    ).json()["id"]
    item = (
        await client.post(
            "/api/v1/items",
            json={
                "category": "instrument",
                "label": "Trompete",
                "manufacturer": "Yamaha",
                "instrument_type_id": tr,
            },
            headers=ME,
        )
    ).json()
    return tr, fh, item


async def test_create_and_field_changes_with_old_and_new(client):
    tr, fh, item = await _setup(client)
    resp = await client.put(
        f"/api/v1/items/{item['id']}",
        json={"manufacturer": "Bach", "serial_nr": "123", "instrument_type_id": fh},
        headers=ME,
    )
    assert resp.status_code == 200

    events = await _events(client, item_id=item["id"])
    assert [e["action"] for e in events] == ["updated", "created"]
    created = events[1]
    assert created["actor"] == "zeugwart@mv-hofkirchen.at"
    assert created["source"] == "web"
    assert created["entity_label"] == "TR-0001 Trompete"
    changes = {
        c["field"]: (c["label"], c["old"], c["new"]) for c in events[0]["changes"]
    }
    assert changes["manufacturer"] == ("Hersteller", "Yamaha", "Bach")
    assert changes["serial_nr"] == ("Seriennummer", None, "123")
    # Foreign keys as text; the new number comes with the new type.
    assert changes["instrument_type_id"] == ("Typ", "Trompete", "Flügelhorn")
    assert changes["number_prefix"] == ("Nummernkreis", "TR", "FH")
    assert events[0]["at"].endswith("Z")


async def test_saving_without_changes_is_not_logged(client):
    _, _, item = await _setup(client)
    await client.put(f"/api/v1/items/{item['id']}", json={"manufacturer": "Yamaha"})
    assert [e["action"] for e in await _events(client, item_id=item["id"])] == [
        "created"
    ]


async def test_loan_return_and_invoice_appear_in_item_and_musician_history(client):
    _, _, item = await _setup(client)
    m = (
        await client.post(
            "/api/v1/musicians", json={"first_name": "Anna", "last_name": "Maier"}
        )
    ).json()
    loan = (
        await client.post(
            "/api/v1/loans",
            json={
                "item_id": item["id"],
                "musician_id": m["id"],
                "start_date": "2026-09-01",
            },
            headers=ME,
        )
    ).json()
    await client.put(
        f"/api/v1/loans/{loan['id']}/return", json={"end_date": "2026-09-20"}
    )
    eur = (
        await client.post(
            "/api/v1/currencies", json={"label": "Euro", "abbreviation": "€"}
        )
    ).json()
    await client.post(
        f"/api/v1/items/{item['id']}/invoices",
        json={
            "title": "Reparatur",
            "amount": 50,
            "currency_id": eur["id"],
            "date_issued": "2026-09-21",
        },
    )

    item_events = await _events(client, item_id=item["id"])
    assert [e["action"] for e in item_events] == [
        "created",  # the invoice
        "returned",
        "loaned",
        "created",  # the item
    ]
    assert item_events[0]["entity_type"] == "invoice"
    loaned = item_events[2]
    assert loaned["entity_label"] == "TR-0001 Trompete an Anna Maier"
    assert loaned["actor"] == "zeugwart@mv-hofkirchen.at"  # Todo 2: who lent it
    returned = item_events[1]
    assert returned["changes"] == [
        {
            "field": "end_date",
            "label": "Zurückgegeben am",
            "old": None,
            "new": "20.09.2026",
        }
    ]
    musician_events = await _events(client, musician_id=m["id"])
    assert [e["action"] for e in musician_events] == ["returned", "loaned", "created"]


async def test_musician_registers_and_general_item_categories(client):
    reg = (await client.post("/api/v1/registers", json={"label": "Blech"})).json()
    m = (
        await client.post(
            "/api/v1/musicians", json={"first_name": "Anna", "last_name": "Maier"}
        )
    ).json()
    await client.put(f"/api/v1/musicians/{m['id']}", json={"register_ids": [reg["id"]]})
    changes = (await _events(client, musician_id=m["id"]))[0]["changes"]
    assert changes == [
        {"field": "registers", "label": "Register", "old": None, "new": "Blech"}
    ]

    cat = (
        await client.post("/api/v1/general-item-categories", json={"label": "Deko"})
    ).json()
    item = (
        await client.post(
            "/api/v1/items", json={"category": "general_item", "label": "Kerze"}
        )
    ).json()
    await client.put(f"/api/v1/items/{item['id']}", json={"category_ids": [cat["id"]]})
    latest = (await _events(client, item_id=item["id"]))[0]
    assert latest["changes"] == [
        {"field": "categories", "label": "Kategorien", "old": None, "new": "Deko"}
    ]


async def test_delete_and_filters(client):
    tr, _, item = await _setup(client)
    await client.delete(f"/api/v1/items/{item['id']}", headers=ME)
    deleted = (await _events(client, item_id=item["id"]))[0]
    assert deleted["action"] == "deleted"
    assert deleted["entity_label"] == "TR-0001 Trompete"

    assert {e["entity_type"] for e in await _events(client, area="master_data")} == {
        "instrument_type"
    }
    mine = await _events(client, actor="zeugwart@mv-hofkirchen.at")
    assert {e["action"] for e in mine} == {"created", "deleted"}
    unknown = await _events(client, actor="unknown")
    assert all(e["actor"] is None for e in unknown) and unknown
    actors = (await client.get(f"{URL}/actors")).json()
    assert set(actors) == {None, "zeugwart@mv-hofkirchen.at"}
    assert await _events(client, date_from="2999-01-01") == []
    assert await _events(client, search="trompete")
