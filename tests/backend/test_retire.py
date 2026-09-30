"""Retired items: out of stock, kept with history and number."""

BASE = "/api/v1/items?category=instrument"


async def _setup(client):
    tu = (
        await client.post(
            "/api/v1/instrument-types", json={"label": "Tuba", "label_short": "TU"}
        )
    ).json()["id"]
    items = []
    for label in ("Alte Tuba", "Neue Tuba"):
        items.append(
            (
                await client.post(
                    "/api/v1/items",
                    json={
                        "category": "instrument",
                        "label": label,
                        "instrument_type_id": tu,
                    },
                )
            ).json()
        )
    return tu, items


async def _labels(client, url):
    return sorted(i["label"] for i in (await client.get(url)).json()["items"])


async def test_retire_and_reinstate(client):
    _, (old, new) = await _setup(client)
    resp = await client.post(
        f"/api/v1/items/{old['id']}/retire",
        json={
            "reason": "sold",
            "retired_at": "2026-09-01",
            "notes": "  an MV Nachbar ",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert (body["retired_at"], body["retired_reason"], body["retired_notes"]) == (
        "2026-09-01",
        "sold",
        "an MV Nachbar",
    )

    assert await _labels(client, BASE) == ["Neue Tuba"]
    assert await _labels(client, f"{BASE}&bestand=ausgeschieden") == ["Alte Tuba"]
    assert await _labels(client, f"{BASE}&bestand=alle") == ["Alte Tuba", "Neue Tuba"]
    # Still reachable, found by the global search (marked), not in stock figures.
    assert (await client.get(f"/api/v1/items/{old['id']}")).status_code == 200
    hits = (await client.get("/api/v1/search", params={"q": "alte tuba"})).json()
    assert hits["items"][0]["hits"][0]["retired_reason"] == "sold"
    stats = (await client.get("/api/v1/dashboard")).json()
    assert stats["total_items"] == 1
    assert [t["count"] for t in stats["instruments_by_type"]] == [1]

    events = (await client.get(f"/api/v1/events?item_id={old['id']}")).json()["items"]
    assert events[0]["action"] == "retired"
    changes = {c["field"]: c["new"] for c in events[0]["changes"]}
    assert changes == {
        "retired_at": "01.09.2026",
        "retired_reason": "Verkauft",
        "retired_notes": "an MV Nachbar",
    }

    again = await client.post(f"/api/v1/items/{old['id']}/reinstate")
    assert again.status_code == 200
    assert again.json()["retired_at"] is None
    assert await _labels(client, BASE) == ["Alte Tuba", "Neue Tuba"]
    events = (await client.get(f"/api/v1/events?item_id={old['id']}")).json()["items"]
    assert events[0]["action"] == "reinstated"


async def test_retire_rules(client):
    _, (item, _) = await _setup(client)
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
                "start_date": "2026-01-01",
            },
        )
    ).json()
    url = f"/api/v1/items/{item['id']}/retire"
    assert (await client.post(url, json={"reason": "lost"})).status_code == 409
    await client.put(f"/api/v1/loans/{loan['id']}/return", json={})
    assert (await client.post(url, json={"reason": "gestohlen"})).status_code == 422
    resp = await client.post(url, json={"reason": "lost"})
    assert resp.status_code == 200
    assert resp.json()["retired_at"]  # defaults to today
    assert (await client.post(url, json={"reason": "lost"})).status_code == 409

    # Not loanable any more, and not offered as available.
    resp = await client.post(
        "/api/v1/loans",
        json={
            "item_id": item["id"],
            "musician_id": m["id"],
            "start_date": "2026-09-01",
        },
    )
    assert resp.status_code == 409
    avail = await _labels(client, f"{BASE}&status=verfuegbar")
    assert "Alte Tuba" not in avail
    # The loan history stays.
    assert (await client.get(f"/api/v1/loans?item_id={item['id']}")).json()[
        "total"
    ] == 1
    assert (
        await client.post(f"/api/v1/items/{item['id']}/reinstate")
    ).status_code == 200
    assert (
        await client.post(f"/api/v1/items/{item['id']}/reinstate")
    ).status_code == 409
