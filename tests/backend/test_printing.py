"""PDF output: data sheets."""

import pymupdf


def _png() -> bytes:
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 40, 30), False)
    pix.set_rect(pix.irect, (200, 120, 40))
    return pix.tobytes("png")


PNG = _png()


async def _setup(client):
    tr = (
        await client.post(
            "/api/v1/instrument-types", json={"label": "Trompete", "label_short": "TR"}
        )
    ).json()["id"]
    eur = (
        await client.post(
            "/api/v1/currencies", json={"label": "Euro", "abbreviation": "€"}
        )
    ).json()["id"]
    item = (
        await client.post(
            "/api/v1/items",
            json={
                "category": "instrument",
                "label": "Trompete Größe B",
                "manufacturer": "Yamaha",
                "serial_nr": "S-4103",
                "acquisition_cost": 1234.5,
                "currency_id": eur,
                "notes": "Mundstück fehlt\nKoffer neu",
                "instrument_type_id": tr,
            },
        )
    ).json()
    m = (
        await client.post(
            "/api/v1/musicians", json={"first_name": "Anna", "last_name": "Maier"}
        )
    ).json()
    await client.post(
        "/api/v1/loans",
        json={
            "item_id": item["id"],
            "musician_id": m["id"],
            "start_date": "2026-09-01",
            "due_date": "2026-12-31",
        },
    )
    await client.post(
        f"/api/v1/items/{item['id']}/invoices",
        json={
            "title": "Reparatur",
            "amount": 80,
            "currency_id": eur,
            "date_issued": "2026-02-01",
        },
    )
    await client.post(
        f"/api/v1/items/{item['id']}/images",
        files={"file": ("a.png", PNG, "image/png")},
    )
    return tr, item


def _text(resp) -> str:
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == "application/pdf"
    doc = pymupdf.open("pdf", resp.content)
    return "\n".join(page.get_text() for page in doc)


async def test_datasheet_of_one_item_with_chosen_sections(client):
    _, item = await _setup(client)
    resp = await client.get(
        "/api/v1/print/datasheets",
        params={
            "category": "instrument",
            "item_id": item["id"],
            "sections": "loan,loan_history,invoices,notes,photo",
        },
    )
    text = _text(resp)
    assert "TR-0001" in text and "Trompete Größe B" in text
    assert "Ausgeliehen an Anna Maier seit 01.09.2026" in text
    assert "Seriennummer" in text and "S-4103" in text
    assert "1 234,50 €" in text
    assert "Rückgabe geplant" in text and "31.12.2026" in text
    assert "Leihhistorie" in text and "Reparatur" in text
    assert "Mundstück fehlt" in text
    assert "Seite 1 von 1" in text
    assert "Datenblatt%20TR-0001.pdf" in resp.headers["content-disposition"]
    doc = pymupdf.open("pdf", resp.content)
    page = doc[0]
    rects = [page.get_image_rects(img[0])[0] for img in page.get_images(full=True)]
    assert len(rects) == 3  # QR code, photo and the footer logo
    top = sorted((r for r in rects if r.y0 < 200), key=lambda r: r.x0)
    photo, qr = top
    footer = next(r for r in rects if r.y0 > page.rect.height - 100)
    assert footer.height < 20
    # QR code top right inside the 15 mm margin, photo top left as high as it.
    assert qr.x1 <= page.rect.width - 15 * 72 / 25.4 + 0.5
    assert abs(photo.y0 - qr.y0) < 0.5 and photo.x0 < qr.x0
    assert abs(photo.height - qr.height) < 1


async def test_sections_are_optional(client):
    _, item = await _setup(client)
    text = _text(
        await client.get(
            "/api/v1/print/datasheets",
            params={"category": "instrument", "item_id": item["id"]},
        )
    )
    assert "Stammdaten" in text
    assert "Leihhistorie" not in text and "Mundstück fehlt" not in text


async def test_datasheets_of_the_filtered_list(client):
    tr, _ = await _setup(client)
    for label in ("Zweite", "Dritte"):
        await client.post(
            "/api/v1/items",
            json={"category": "instrument", "label": label, "instrument_type_id": tr},
        )
    resp = await client.get(
        "/api/v1/print/datasheets", params={"category": "instrument", "search": "e"}
    )
    doc = pymupdf.open("pdf", resp.content)
    assert doc.page_count == 3
    assert [p.get_text().split("\n")[0] for p in doc] == [
        "TR-0001",
        "TR-0002",
        "TR-0003",
    ]
    assert "Datenblatt%20Instrumente.pdf" in resp.headers["content-disposition"]

    none = await client.get(
        "/api/v1/print/datasheets", params={"category": "instrument", "search": "xyz"}
    )
    assert none.status_code == 422


async def _two_instruments(client):
    tr = (
        await client.post(
            "/api/v1/instrument-types", json={"label": "Tuba", "label_short": "TU"}
        )
    ).json()["id"]
    return [
        (
            await client.post(
                "/api/v1/items",
                json={
                    "category": "instrument",
                    "label": label,
                    "instrument_type_id": tr,
                },
            )
        ).json()
        for label in ("Tuba A", "Tuba B")
    ]


async def test_labels_on_a_roll_one_page_each(client):
    await _two_instruments(client)
    resp = await client.get(
        "/api/v1/print/labels",
        params={"category": "instrument", "template": "roll-62x29"},
    )
    assert resp.status_code == 200, resp.text
    doc = pymupdf.open("pdf", resp.content)
    assert doc.page_count == 2
    page = doc[0]
    assert round(page.rect.width / 72 * 25.4) == 62
    assert round(page.rect.height / 72 * 25.4) == 29
    assert "TU-0001" in page.get_text() and "MV Hofkirchen" in page.get_text()
    assert len(page.get_images()) == 2  # QR code + logo
    without = await client.get(
        "/api/v1/print/labels",
        params={"category": "instrument", "template": "roll-62x29", "logo": "false"},
    )
    assert len(pymupdf.open("pdf", without.content)[0].get_images()) == 1


async def test_labels_on_a_sheet_start_at_a_position(client):
    items = await _two_instruments(client)
    resp = await client.get(
        "/api/v1/print/labels",
        params={"category": "instrument", "template": "a4-70x37", "start": 4},
    )
    doc = pymupdf.open("pdf", resp.content)
    assert doc.page_count == 1
    page = doc[0]
    # Position 4 is the first label of the second row (3 columns, 37 mm high).
    nr = page.search_for("TU-0001")[0]
    assert nr.y0 > 37 * 72 / 25.4 and nr.x0 < 70 * 72 / 25.4
    assert "Etiketten%20Instrumente.pdf" in resp.headers["content-disposition"]
    one = await client.get(
        "/api/v1/print/labels",
        params={"category": "instrument", "item_id": items[1]["id"]},
    )
    assert "Etiketten%20TU-0002.pdf" in one.headers["content-disposition"]


async def test_label_layout_checks(client):
    await _two_instruments(client)
    base = {"category": "instrument"}
    too_far = await client.get(
        "/api/v1/print/labels", params={**base, "template": "a4-70x37", "start": 25}
    )
    assert too_far.status_code == 422
    custom = await client.get(
        "/api/v1/print/labels",
        params={
            **base,
            "template": "custom",
            "width": 80,
            "height": 40,
            "cols": 3,
            "rows": 7,
        },
    )
    assert custom.status_code == 422
    assert "passen nicht auf A4" in custom.json()["detail"]
    ok = await client.get(
        "/api/v1/print/labels",
        params={
            **base,
            "template": "custom",
            "width": 50,
            "height": 30,
            "cols": 4,
            "rows": 9,
            "margin_left": 5,
            "margin_top": 10,
            "gap_x": 1,
        },
    )
    assert ok.status_code == 200
    info = (await client.get("/api/v1/print/label-presets")).json()
    assert info["public_url"] == "https://inventar.mvhofki.xyz"
    presets = info["presets"]
    assert {p["key"] for p in presets} >= {"roll-62x29", "a4-70x37"}
    assert next(p for p in presets if p["key"] == "a4-70x37")["per_page"] == 24


async def test_datasheet_footer_has_the_logo(client):
    items = await _two_instruments(client)
    resp = await client.get(
        "/api/v1/print/datasheets",
        params={"category": "instrument", "item_id": items[0]["id"]},
    )
    page = pymupdf.open("pdf", resp.content)[0]
    assert len(page.get_images()) == 2  # QR code + footer logo (no photo)


async def _inventory(client):
    eur = (
        await client.post(
            "/api/v1/currencies", json={"label": "Euro", "abbreviation": "€"}
        )
    ).json()["id"]
    types = {}
    for label, short in (("Tuba", "TU"), ("Horn", "HR")):
        types[label] = (
            await client.post(
                "/api/v1/instrument-types", json={"label": label, "label_short": short}
            )
        ).json()["id"]
    for label, type_label, cost in (
        ("Tuba A", "Tuba", 1000),
        ("Tuba B", "Tuba", 500.5),
        ("Horn A", "Horn", None),
    ):
        await client.post(
            "/api/v1/items",
            json={
                "category": "instrument",
                "label": label,
                "instrument_type_id": types[type_label],
                "manufacturer": "Melton",
                **({"acquisition_cost": cost, "currency_id": eur} if cost else {}),
            },
        )


async def test_inventory_list_grouped_with_columns_and_totals(client):
    await _inventory(client)
    resp = await client.get(
        "/api/v1/print/inventory-list",
        params={
            "category": "instrument",
            "group_by": "type",
            "columns": "label,manufacturer,acquisition_cost,status",
            "totals": "true",
        },
    )
    text = _text(resp)
    assert "Inventarliste Instrumente" in text and "im Bestand" in text
    assert "Horn (1)" in text and "Tuba (2)" in text
    assert text.index("Horn (1)") < text.index("Tuba (2)")
    assert "Hersteller" in text and "Melton" in text and "Verfügbar" in text
    assert "Seriennummer" not in text  # not chosen
    assert "3 Gegenstände · Anschaffungskosten: 1 500,50 €" in text
    assert "Inventarliste%20Instrumente.pdf" in resp.headers["content-disposition"]
    page = pymupdf.open("pdf", resp.content)[0]
    assert page.rect.width > page.rect.height  # landscape


async def test_inventory_list_says_which_filters_it_covers(client):
    await _inventory(client)
    text = _text(
        await client.get(
            "/api/v1/print/inventory-list",
            params={"category": "instrument", "search": "tuba", "bestand": "alle"},
        )
    )
    assert "Suche „tuba“ · Bestand und ausgeschiedene" in text
    assert "2 Gegenstände" in text and "Horn A" not in text
    columns = (
        await client.get(
            "/api/v1/print/inventory-list/columns", params={"category": "clothing"}
        )
    ).json()
    assert {"key": "size", "label": "Größe"} in columns
    assert {"key": "type", "label": "Typ"} in columns


async def test_inventory_list_repeats_the_head_row_on_every_page(client, db_session):
    tu = (
        await client.post(
            "/api/v1/instrument-types", json={"label": "Tuba", "label_short": "TU"}
        )
    ).json()["id"]
    for n in range(60):
        await client.post(
            "/api/v1/items",
            json={
                "category": "instrument",
                "label": f"Tuba {n}",
                "instrument_type_id": tu,
            },
        )
    resp = await client.get(
        "/api/v1/print/inventory-list",
        params={"category": "instrument", "columns": "label"},
    )
    doc = pymupdf.open("pdf", resp.content)
    assert doc.page_count >= 2
    assert all(page.get_text().count("Inv.-Nr.") == 1 for page in doc)
    assert "60 Gegenstände" in doc[-1].get_text()
