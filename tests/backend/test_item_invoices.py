"""ItemInvoice API tests — /api/v1/items/{item_id}/invoices."""

import io

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def currency(client):
    resp = await client.post(
        "/api/v1/currencies", json={"label": "Euro", "abbreviation": "€"}
    )
    return resp.json()


@pytest.fixture
async def instrument_item(client, currency):
    itype = (
        await client.post(
            "/api/v1/instrument-types", json={"label": "Trompete", "label_short": "TR"}
        )
    ).json()
    resp = await client.post(
        "/api/v1/items",
        json={
            "category": "instrument",
            "label": "Trompete",
            "owner": "Verein",
            "instrument_type_id": itype["id"],
        },
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture
async def sheet_music_item(client):
    resp = await client.post(
        "/api/v1/items",
        json={
            "category": "sheet_music",
            "label": "Marsch",
            "owner": "Verein",
        },
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture
async def invoice(client, instrument_item, currency):
    resp = await client.post(
        f"/api/v1/items/{instrument_item['id']}/invoices",
        json={
            "title": "Reparatur",
            "amount": 120.50,
            "currency_id": currency["id"],
            "date_issued": "2026-01-10",
        },
    )
    assert resp.status_code == 201
    return resp.json()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_create_invoice_on_instrument(client, instrument_item, currency):
    resp = await client.post(
        f"/api/v1/items/{instrument_item['id']}/invoices",
        json={
            "title": "Ankauf",
            "amount": 450.00,
            "currency_id": currency["id"],
            "date_issued": "2026-02-01",
            "invoice_issuer": "Musikhaus Wien",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["invoice_nr"] == 1
    assert data["item_id"] == instrument_item["id"]
    assert data["title"] == "Ankauf"
    assert data["amount"] == 450.00
    assert data["currency"]["abbreviation"] == "€"


async def test_create_invoice_on_sheet_music_rejected(
    client, sheet_music_item, currency
):
    """Sheet music is not invoiceable → 400."""
    resp = await client.post(
        f"/api/v1/items/{sheet_music_item['id']}/invoices",
        json={
            "title": "Ankauf",
            "amount": 20.00,
            "currency_id": currency["id"],
            "date_issued": "2026-02-01",
        },
    )
    assert resp.status_code == 400


async def test_list_invoices(client, invoice, instrument_item):
    resp = await client.get(f"/api/v1/items/{instrument_item['id']}/invoices")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["id"] == invoice["id"]


async def test_get_invoice(client, invoice, instrument_item):
    resp = await client.get(
        f"/api/v1/items/{instrument_item['id']}/invoices/{invoice['id']}"
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "Reparatur"


async def test_update_invoice(client, invoice, instrument_item):
    resp = await client.put(
        f"/api/v1/items/{instrument_item['id']}/invoices/{invoice['id']}",
        json={"title": "Reparatur aktualisiert", "amount": 135.00},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Reparatur aktualisiert"
    assert data["amount"] == 135.00


async def test_delete_invoice(client, invoice, instrument_item):
    resp = await client.delete(
        f"/api/v1/items/{instrument_item['id']}/invoices/{invoice['id']}"
    )
    assert resp.status_code == 204

    # Confirm it is gone
    resp = await client.get(f"/api/v1/items/{instrument_item['id']}/invoices")
    assert resp.json() == []


async def test_invoice_nr_auto_increments(client, instrument_item, currency):
    """Each new invoice on the same item gets an incremented invoice_nr."""
    r1 = await client.post(
        f"/api/v1/items/{instrument_item['id']}/invoices",
        json={
            "title": "Erste Rechnung",
            "amount": 50.00,
            "currency_id": currency["id"],
            "date_issued": "2026-01-01",
        },
    )
    r2 = await client.post(
        f"/api/v1/items/{instrument_item['id']}/invoices",
        json={
            "title": "Zweite Rechnung",
            "amount": 80.00,
            "currency_id": currency["id"],
            "date_issued": "2026-01-02",
        },
    )
    assert r1.json()["invoice_nr"] == 1
    assert r2.json()["invoice_nr"] == 2


async def test_upload_file_to_invoice(client, invoice, instrument_item):
    pdf_bytes = b"%PDF-1.4 fake pdf content"
    resp = await client.post(
        f"/api/v1/items/{instrument_item['id']}/invoices/{invoice['id']}/file",
        files={"file": ("rechnung.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["filename"] is not None
    assert data["file_url"].startswith("/uploads/invoices/")


async def test_replace_file_on_invoice(client, invoice, instrument_item):
    pdf_bytes = b"%PDF-1.4 original"
    await client.post(
        f"/api/v1/items/{instrument_item['id']}/invoices/{invoice['id']}/file",
        files={"file": ("original.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    new_pdf = b"%PDF-1.4 replacement"
    resp = await client.post(
        f"/api/v1/items/{instrument_item['id']}/invoices/{invoice['id']}/file",
        files={"file": ("replacement.pdf", io.BytesIO(new_pdf), "application/pdf")},
    )
    assert resp.status_code == 200
    assert resp.json()["filename"] is not None


async def test_delete_file_from_invoice(client, invoice, instrument_item):
    pdf_bytes = b"%PDF-1.4 fake"
    await client.post(
        f"/api/v1/items/{instrument_item['id']}/invoices/{invoice['id']}/file",
        files={"file": ("rechnung.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    resp = await client.delete(
        f"/api/v1/items/{instrument_item['id']}/invoices/{invoice['id']}/file"
    )
    assert resp.status_code == 200
    assert resp.json()["filename"] is None
    assert resp.json()["file_url"] is None


async def test_upload_invalid_file_type_rejected(client, invoice, instrument_item):
    resp = await client.post(
        f"/api/v1/items/{instrument_item['id']}/invoices/{invoice['id']}/file",
        files={
            "file": ("script.js", io.BytesIO(b"alert('x')"), "application/javascript")
        },
    )
    assert resp.status_code == 400
