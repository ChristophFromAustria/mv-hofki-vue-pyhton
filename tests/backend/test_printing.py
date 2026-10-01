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
    rects = {
        img[2]: page.get_image_rects(img[0])[0] for img in page.get_images(full=True)
    }
    assert len(rects) == 2  # QR code + photo
    qr, photo = rects[max(rects)], rects[min(rects)]
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
