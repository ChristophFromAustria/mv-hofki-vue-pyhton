"""GET /api/v1/search — the global search field."""

URL = "/api/v1/search"


async def _setup(client):
    tr = (
        await client.post(
            "/api/v1/instrument-types", json={"label": "Trompete", "label_short": "TR"}
        )
    ).json()["id"]
    hat = (await client.post("/api/v1/clothing-types", json={"label": "Hut"})).json()
    eur = (
        await client.post(
            "/api/v1/currencies", json={"label": "Euro", "abbreviation": "€"}
        )
    ).json()

    async def item(**data):
        resp = await client.post("/api/v1/items", json=data)
        assert resp.status_code == 201, resp.text
        return resp.json()

    t1 = await item(
        category="instrument", label="Trompete Yamaha", instrument_type_id=tr
    )
    t2 = await item(
        category="instrument",
        label="Trompete",
        instrument_type_id=tr,
        notes="Spieler früher Markus Müller",
    )
    await item(category="clothing", label="Hut Müller", clothing_type_id=hat["id"])
    await item(category="general_item", label="Notenständer")
    markus = (
        await client.post(
            "/api/v1/musicians",
            json={"first_name": "Markus", "last_name": "Müller", "is_active": False},
        )
    ).json()
    await client.post(
        "/api/v1/musicians", json={"first_name": "Anna", "last_name": "Mueller"}
    )
    await client.post(
        "/api/v1/loans",
        json={
            "item_id": t1["id"],
            "musician_id": markus["id"],
            "start_date": "2026-01-01",
        },
    )
    resp = await client.post(
        f"/api/v1/items/{t2['id']}/invoices",
        json={
            "title": "Reparatur Müller",
            "amount": 120,
            "currency_id": eur["id"],
            "date_issued": "2026-02-01",
            "invoice_issuer": "Musikhaus Müller",
        },
    )
    assert resp.status_code == 201, resp.text
    return {"t1": t1, "t2": t2}


async def test_search_groups_in_fixed_order_with_totals(client):
    data = await _setup(client)
    body = (await client.get(URL, params={"q": "müller"})).json()

    assert [g["category"] for g in body["items"]] == ["instrument", "clothing"]
    instruments = body["items"][0]
    assert instruments["label"] == "Instrumente"
    # t1 via its borrower, t2 via its notes.
    assert {h["id"] for h in instruments["hits"]} == {
        data["t1"]["id"],
        data["t2"]["id"],
    }
    borrowed = next(h for h in instruments["hits"] if h["id"] == data["t1"]["id"])
    assert borrowed["active_loan"]["musician_name"] == "Markus Müller"

    musicians = body["musicians"]
    assert musicians["total"] == 2
    # Active musicians first; the inactive one is still found.
    assert [(m["last_name"], m["is_active"]) for m in musicians["hits"]] == [
        ("Mueller", True),
        ("Müller", False),
    ]
    invoices = body["invoices"]
    assert invoices["total"] == 1
    assert invoices["hits"][0]["item_display_nr"] == data["t2"]["display_nr"]
    assert invoices["hits"][0]["currency"] == "€"
    assert body["exact"] is None


async def test_limit_caps_hits_but_not_totals_and_label_hits_come_first(client):
    await _setup(client)
    body = (await client.get(URL, params={"q": "trompete", "limit": 1})).json()
    instruments = body["items"][0]
    assert instruments["total"] == 2
    assert len(instruments["hits"]) == 1
    body = (await client.get(URL, params={"q": "markus"})).json()
    # "Trompete" has Markus only in the notes, "Trompete Yamaha" via the loan:
    # neither has the word in the label, so inventory number order decides.
    assert [h["display_nr"] for h in body["items"][0]["hits"]] == ["TR-0001", "TR-0002"]


async def test_exact_inventory_number(client):
    data = await _setup(client)
    body = (await client.get(URL, params={"q": "tr 2"})).json()
    assert body["exact"]["id"] == data["t2"]["id"]
    assert [h["id"] for h in body["items"][0]["hits"]] == [data["t2"]["id"]]
    # One letter + digit is enough for a number, one letter alone finds nothing.
    assert (await client.get(URL, params={"q": "A 1"})).json()["exact"]["label"] == (
        "Notenständer"
    )
    empty = (await client.get(URL, params={"q": "t"})).json()
    assert empty["items"] == [] and empty["musicians"]["total"] == 0
    assert (await client.get(URL, params={"q": "   "})).json()["items"] == []
