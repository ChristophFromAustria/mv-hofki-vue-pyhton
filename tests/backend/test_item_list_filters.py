"""GET /items filters, sorting, paging and facets."""

import pytest

URL = "/api/v1/items"


@pytest.fixture
async def refs(client):
    tuba = (
        await client.post(
            "/api/v1/instrument-types", json={"label": "Tuba", "label_short": "TU"}
        )
    ).json()
    horn = (
        await client.post(
            "/api/v1/instrument-types", json={"label": "Horn", "label_short": "HR"}
        )
    ).json()
    hat = (await client.post("/api/v1/clothing-types", json={"label": "Hut"})).json()
    jacket = (
        await client.post("/api/v1/clothing-types", json={"label": "Jacke"})
    ).json()
    return {
        "tuba": tuba["id"],
        "horn": horn["id"],
        "hat": hat["id"],
        "jacket": jacket["id"],
    }


async def _item(client, **data):
    resp = await client.post(URL, json=data)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _labels(client, query):
    resp = await client.get(f"{URL}?{query}")
    assert resp.status_code == 200, resp.text
    return [i["label"] for i in resp.json()["items"]]


async def _musician(client):
    resp = await client.post(
        "/api/v1/musicians", json={"first_name": "Anna", "last_name": "Maier"}
    )
    return resp.json()["id"]


async def test_instrument_filters(client, refs):
    t1 = await _item(
        client,
        category="instrument",
        label="Tuba 1",
        instrument_type_id=refs["tuba"],
        construction_year=1990,
        owner="MV Hofkirchen",
    )
    await _item(
        client,
        category="instrument",
        label="Horn 1",
        instrument_type_id=refs["horn"],
        construction_year=2010,
        owner="Privat",
    )
    await _item(
        client,
        category="instrument",
        label="Tuba 2",
        instrument_type_id=refs["tuba"],
        construction_year=2005,
        owner="MV Hofkirchen",
    )
    await client.post(
        "/api/v1/loans",
        json={
            "item_id": t1["id"],
            "musician_id": await _musician(client),
            "start_date": "2026-01-01",
        },
    )
    base = "category=instrument"
    assert await _labels(client, f"{base}&instrument_type_id__in={refs['tuba']}") == [
        "Tuba 1",
        "Tuba 2",
    ]
    assert await _labels(client, f"{base}&status=verliehen") == ["Tuba 1"]
    assert await _labels(client, f"{base}&status=verfuegbar") == ["Horn 1", "Tuba 2"]
    assert await _labels(client, f"{base}&owner=Privat") == ["Horn 1"]
    assert await _labels(
        client, f"{base}&construction_year__gte=2000&construction_year__lte=2006"
    ) == ["Tuba 2"]


async def test_search_and_sort_by_borrower(client, refs):
    base = "category=instrument"
    names = [("Anna", "Maier"), ("Bernd", "Huber"), ("Clara", "Zach")]
    for i, (first, last) in enumerate(names):
        item = await _item(
            client,
            category="instrument",
            label=f"Tuba {i + 1}",
            instrument_type_id=refs["tuba"],
        )
        musician = (
            await client.post(
                "/api/v1/musicians", json={"first_name": first, "last_name": last}
            )
        ).json()
        await client.post(
            "/api/v1/loans",
            json={
                "item_id": item["id"],
                "musician_id": musician["id"],
                "start_date": "2026-01-01",
            },
        )
    await _item(
        client,
        category="instrument",
        label="Tuba frei",
        instrument_type_id=refs["tuba"],
    )

    assert await _labels(client, f"{base}&search=huber") == ["Tuba 2"]
    assert await _labels(client, f"{base}&search=anna maier") == ["Tuba 1"]
    assert await _labels(client, f"{base}&order_by=borrower") == [
        "Tuba 2",
        "Tuba 1",
        "Tuba 3",
        "Tuba frei",
    ]
    assert await _labels(client, f"{base}&order_by=-borrower") == [
        "Tuba 3",
        "Tuba 1",
        "Tuba 2",
        "Tuba frei",
    ]


async def test_returned_loan_is_not_the_borrower(client, refs):
    item = await _item(
        client, category="clothing", label="Hut 1", clothing_type_id=refs["hat"]
    )
    loan = (
        await client.post(
            "/api/v1/loans",
            json={
                "item_id": item["id"],
                "musician_id": await _musician(client),
                "start_date": "2026-01-01",
            },
        )
    ).json()
    resp = await client.put(f"/api/v1/loans/{loan['id']}/return", json={})
    assert resp.status_code == 200, resp.text
    assert await _labels(client, "category=clothing&search=maier") == []


async def test_instrument_sorting(client, refs):
    await _item(
        client,
        category="instrument",
        label="Tuba",
        instrument_type_id=refs["tuba"],
        manufacturer="Yamaha",
        construction_year=1990,
    )
    await _item(
        client,
        category="instrument",
        label="Horn",
        instrument_type_id=refs["horn"],
        manufacturer="Alexander",
        construction_year=None,
    )
    base = "category=instrument"
    assert await _labels(client, f"{base}") == ["Horn", "Tuba"]  # number: HR before TU
    assert await _labels(client, f"{base}&order_by=-type") == ["Tuba", "Horn"]
    assert await _labels(client, f"{base}&order_by=manufacturer") == ["Horn", "Tuba"]
    # NULL construction year last in both directions
    assert await _labels(client, f"{base}&order_by=construction_year") == [
        "Tuba",
        "Horn",
    ]
    assert await _labels(client, f"{base}&order_by=-construction_year") == [
        "Tuba",
        "Horn",
    ]


async def test_clothing_filters_and_type_sort(client, refs):
    await _item(
        client,
        category="clothing",
        label="Jacke L",
        clothing_type_id=refs["jacket"],
        size="L",
        gender="Herren",
    )
    await _item(
        client,
        category="clothing",
        label="Hut M",
        clothing_type_id=refs["hat"],
        size="M",
        gender="Damen",
    )
    base = "category=clothing"
    assert await _labels(client, f"{base}&clothing_type_id__in={refs['hat']}") == [
        "Hut M"
    ]
    assert await _labels(client, f"{base}&size=L") == ["Jacke L"]
    assert await _labels(client, f"{base}&gender=Damen") == ["Hut M"]
    assert await _labels(client, f"{base}&order_by=type") == ["Hut M", "Jacke L"]


async def test_sheet_music_filters(client):
    genre = (
        await client.post("/api/v1/sheet-music-genres", json={"label": "Marsch"})
    ).json()
    await _item(
        client,
        category="sheet_music",
        label="Radetzky",
        composer="Strauss",
        genre_id=genre["id"],
        difficulty="C",
        storage_location="Archiv Kasten 3",
    )
    await _item(
        client, category="sheet_music", label="Bolero", composer="Ravel", difficulty="D"
    )
    base = "category=sheet_music"
    assert await _labels(client, f"{base}&genre_id__in={genre['id']}") == ["Radetzky"]
    assert await _labels(client, f"{base}&difficulty=D") == ["Bolero"]
    assert await _labels(client, f"{base}&storage_location__ilike=kasten") == [
        "Radetzky"
    ]
    assert await _labels(client, f"{base}&order_by=composer") == ["Bolero", "Radetzky"]


async def test_general_item_category_filters(client):
    deko = (
        await client.post("/api/v1/general-item-categories", json={"label": "Deko"})
    ).json()
    gastro = (
        await client.post("/api/v1/general-item-categories", json={"label": "Gastro"})
    ).json()
    await _item(
        client, category="general_item", label="Girlande", category_ids=[deko["id"]]
    )
    await _item(
        client, category="general_item", label="Gläser", category_ids=[gastro["id"]]
    )
    await _item(client, category="general_item", label="Leiter")
    base = "category=general_item"
    assert await _labels(client, f"{base}&category_id__in={deko['id']}") == ["Girlande"]
    assert await _labels(client, f"{base}&without_category=true") == ["Leiter"]
    assert await _labels(
        client, f"{base}&category_id__in={deko['id']}&without_category=true"
    ) == ["Girlande", "Leiter"]
    assert await _labels(client, f"{base}&order_by=-label") == [
        "Leiter",
        "Gläser",
        "Girlande",
    ]


async def test_search_keeps_display_number_match(client, refs):
    await _item(
        client, category="instrument", label="Tuba", instrument_type_id=refs["tuba"]
    )
    await _item(
        client, category="instrument", label="Tuba", instrument_type_id=refs["tuba"]
    )
    assert await _labels(client, "category=instrument&search=tu 2") == ["Tuba"]
    resp = await client.get(f"{URL}?category=instrument&search=tu-002")
    assert [i["display_nr"] for i in resp.json()["items"]] == ["TU-0002"]


async def test_filter_not_for_category_is_422(client):
    resp = await client.get(f"{URL}?category=instrument&size=L")
    assert resp.status_code == 422
    assert resp.json()["detail"] == "Filter „size“ gibt es für Instrumente nicht"
    resp = await client.get(f"{URL}?category=general_item&order_by=type")
    assert resp.status_code == 422
    assert resp.json()["detail"] == "Sortierung „type“ gibt es für Allgemein nicht"


async def test_paging_is_stable(client):
    for i in range(7):
        await _item(
            client, category="general_item", label="Stuhl", owner="MV Hofkirchen"
        )
    ids = []
    for offset in (0, 3, 6):
        page = (
            await client.get(
                f"{URL}?category=general_item&order_by=label&limit=3&offset={offset}"
            )
        ).json()
        assert page["total"] == 7
        ids += [i["id"] for i in page["items"]]
    assert len(ids) == 7 and len(set(ids)) == 7


async def test_details_are_included_in_list(client, refs):
    await _item(
        client,
        category="instrument",
        label="Tuba",
        instrument_type_id=refs["tuba"],
        serial_nr="S-1",
    )
    item = (await client.get(f"{URL}?category=instrument")).json()["items"][0]
    assert item["serial_nr"] == "S-1"
    assert item["instrument_type"]["label"] == "Tuba"


async def test_facets(client, refs):
    await _item(
        client,
        category="instrument",
        label="A",
        instrument_type_id=refs["tuba"],
        owner="Privat",
    )
    await _item(
        client,
        category="instrument",
        label="B",
        instrument_type_id=refs["tuba"],
        owner="MV Hofkirchen",
    )
    await _item(
        client,
        category="clothing",
        label="J",
        clothing_type_id=refs["jacket"],
        size="L",
        gender="",
    )
    resp = await client.get(f"{URL}/facets?category=instrument")
    assert resp.status_code == 200
    assert resp.json() == {"owners": ["MV Hofkirchen", "Privat"]}
    assert (await client.get(f"{URL}/facets?category=clothing")).json() == {
        "sizes": ["L"],
        "genders": [],
    }
    assert (await client.get(f"{URL}/facets?category=general_item")).json() == {}
    assert (await client.get(f"{URL}/facets?category=unsinn")).status_code == 400


async def _groups(client, query):
    resp = await client.get(f"{URL}?{query}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    return body, [(g["label"], g["count"]) for g in body["groups"]]


async def test_instruments_group_by_type_status_owner(client, refs):
    t1 = await _item(
        client,
        category="instrument",
        label="Tuba 1",
        instrument_type_id=refs["tuba"],
        owner="MV Hofkirchen",
    )
    await _item(
        client,
        category="instrument",
        label="Horn 1",
        instrument_type_id=refs["horn"],
        owner="Privat",
    )
    await _item(
        client,
        category="instrument",
        label="Tuba 2",
        instrument_type_id=refs["tuba"],
        owner="MV Hofkirchen",
    )
    await client.post(
        "/api/v1/loans",
        json={
            "item_id": t1["id"],
            "musician_id": await _musician(client),
            "start_date": "2026-01-01",
        },
    )
    body, groups = await _groups(client, "category=instrument&group_by=type")
    assert groups == [("Horn", 1), ("Tuba", 2)]
    assert [i["label"] for i in body["items"]] == ["Horn 1", "Tuba 1", "Tuba 2"]
    assert body["items"][0]["group_key"] == str(refs["horn"])
    _, groups = await _groups(client, "category=instrument&group_by=status")
    assert groups == [("Ausgeliehen", 1), ("Verfügbar", 2)]
    _, groups = await _groups(client, "category=instrument&group_by=owner")
    assert groups == [("MV Hofkirchen", 2), ("Privat", 1)]


async def test_clothing_group_by_size_with_empty_group(client, refs):
    await _item(
        client, category="clothing", label="Hut", clothing_type_id=refs["hat"], size="M"
    )
    await _item(
        client, category="clothing", label="Jacke", clothing_type_id=refs["jacket"]
    )
    _, groups = await _groups(client, "category=clothing&group_by=size")
    assert groups == [("M", 1), ("Ohne Größe", 1)]
    _, groups = await _groups(client, "category=clothing&group_by=type")
    assert groups == [("Hut", 1), ("Jacke", 1)]


async def test_sheet_music_group_by_genre(client):
    genre = (
        await client.post("/api/v1/sheet-music-genres", json={"label": "Marsch"})
    ).json()
    await _item(client, category="sheet_music", label="Radetzky", genre_id=genre["id"])
    await _item(client, category="sheet_music", label="Bolero")
    _, groups = await _groups(client, "category=sheet_music&group_by=genre")
    assert groups == [("Marsch", 1), ("Ohne Gattung", 1)]


async def test_general_items_group_by_category_repeats_and_room(client):
    deko = (
        await client.post("/api/v1/general-item-categories", json={"label": "Deko"})
    ).json()
    fest = (
        await client.post("/api/v1/general-item-categories", json={"label": "Fest"})
    ).json()
    await _item(
        client,
        category="general_item",
        label="Girlande",
        category_ids=[deko["id"], fest["id"]],
        storage_location="Sesselarchiv / Kasten 1",
    )
    await _item(
        client, category="general_item", label="Leiter", storage_location="Bauhof"
    )
    await _item(client, category="general_item", label="Kiste")
    body, groups = await _groups(client, "category=general_item&group_by=category")
    assert groups == [("Deko", 1), ("Fest", 1), ("Ohne Kategorie", 2)]
    assert [(i["label"], i["group_label"]) for i in body["items"]] == [
        ("Girlande", "Deko"),
        ("Girlande", "Fest"),
        ("Leiter", "Ohne Kategorie"),
        ("Kiste", "Ohne Kategorie"),
    ]
    assert body["total"] == 4 and body["item_total"] == 3
    _, groups = await _groups(client, "category=general_item&group_by=room")
    assert groups == [("Bauhof", 1), ("Sesselarchiv", 1), ("Ohne Lagerort", 1)]


async def test_group_not_for_category_is_422(client):
    resp = await client.get(f"{URL}?category=general_item&group_by=type")
    assert resp.status_code == 422
    assert resp.json()["detail"] == "Gruppierung „type“ gibt es für Allgemein nicht"
    assert (
        await client.get(f"{URL}?category=instrument&group_by=unsinn")
    ).status_code == 422
