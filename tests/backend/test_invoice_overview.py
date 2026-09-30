"""Invoice overview API tests — GET /api/v1/invoices."""

from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def setup_invoices(client):
    """Create items with invoices for testing."""
    # Create currencies
    eur = (
        await client.post(
            "/api/v1/currencies", json={"label": "Euro", "abbreviation": "€"}
        )
    ).json()
    ats = (
        await client.post(
            "/api/v1/currencies", json={"label": "Schilling", "abbreviation": "ATS"}
        )
    ).json()

    # Create instrument type
    itype = (
        await client.post(
            "/api/v1/instrument-types",
            json={"label": "Querflöte", "label_short": "FL"},
        )
    ).json()

    # Create instrument item
    inst = (
        await client.post(
            "/api/v1/items",
            json={
                "category": "instrument",
                "label": "Querflöte",
                "owner": "MV",
                "instrument_type_id": itype["id"],
            },
        )
    ).json()

    # Create general item
    gen = (
        await client.post(
            "/api/v1/items",
            json={"category": "general_item", "label": "Mischpult", "owner": "MV"},
        )
    ).json()

    # Create invoices
    inv1 = (
        await client.post(
            f"/api/v1/items/{inst['id']}/invoices",
            json={
                "title": "Reparatur",
                "amount": 150.0,
                "currency_id": eur["id"],
                "date_issued": "2026-01-15",
            },
        )
    ).json()
    inv2 = (
        await client.post(
            f"/api/v1/items/{gen['id']}/invoices",
            json={
                "title": "Kauf",
                "amount": 500.0,
                "currency_id": ats["id"],
                "date_issued": "2026-02-20",
            },
        )
    ).json()

    return {
        "eur": eur,
        "ats": ats,
        "inst": inst,
        "gen": gen,
        "inv1": inv1,
        "inv2": inv2,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_list_invoices_empty(client):
    resp = await client.get("/api/v1/invoices")
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["totals_by_currency"] == []


async def test_list_invoices_with_data(client, setup_invoices):
    resp = await client.get("/api/v1/invoices")
    assert resp.status_code == 200
    data = resp.json()

    assert data["total"] == 2
    assert len(data["items"]) == 2

    # Most-recent date first (2026-02-20 before 2026-01-15)
    first = data["items"][0]
    assert first["title"] == "Kauf"
    assert first["item_category"] == "general_item"
    assert first["item_display_nr"] == "A-0001"
    assert first["item_label"] == "Mischpult"
    assert first["amount"] == 500.0
    assert first["currency"]["abbreviation"] == "ATS"
    assert first["filename"] is None
    assert first["file_url"] is None

    second = data["items"][1]
    assert second["title"] == "Reparatur"
    assert second["item_category"] == "instrument"
    assert second["item_display_nr"] == "FL-0001"
    assert second["item_label"] == "Querflöte"
    assert second["amount"] == 150.0
    assert second["currency"]["abbreviation"] == "€"


async def test_list_invoices_filter_by_category(client, setup_invoices):
    resp = await client.get("/api/v1/invoices", params={"item_category": "instrument"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["item_category"] == "instrument"
    assert data["items"][0]["title"] == "Reparatur"


async def test_list_invoices_filter_by_date_range(client, setup_invoices):
    # Only the invoice from January
    resp = await client.get(
        "/api/v1/invoices",
        params={"date_issued__gte": "2026-01-01", "date_issued__lte": "2026-01-31"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["date_issued"] == "2026-01-15"

    # Only the invoice from February
    resp = await client.get(
        "/api/v1/invoices",
        params={"date_issued__gte": "2026-02-01", "date_issued__lte": "2026-02-28"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["date_issued"] == "2026-02-20"


async def test_list_invoices_search(client, setup_invoices):
    resp = await client.get("/api/v1/invoices", params={"search": "Repar"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "Reparatur"

    # Search returns nothing for an unknown term
    resp = await client.get("/api/v1/invoices", params={"search": "XYZ_NOMATCH"})
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


async def test_list_invoices_totals_by_currency(client, setup_invoices):
    resp = await client.get("/api/v1/invoices")
    assert resp.status_code == 200
    data = resp.json()

    totals = {t["abbreviation"]: t["total"] for t in data["totals_by_currency"]}
    assert totals["€"] == pytest.approx(150.0)
    assert totals["ATS"] == pytest.approx(500.0)

    # Filter to one category — only that currency should appear
    resp = await client.get("/api/v1/invoices", params={"item_category": "instrument"})
    data = resp.json()
    totals = {t["abbreviation"]: t["total"] for t in data["totals_by_currency"]}
    assert list(totals.keys()) == ["€"]
    assert totals["€"] == pytest.approx(150.0)


async def _invoice(client, item_id, title, amount, currency_id, date_issued, issuer):
    resp = await client.post(
        f"/api/v1/items/{item_id}/invoices",
        json={
            "title": title,
            "amount": amount,
            "currency_id": currency_id,
            "date_issued": date_issued,
            "invoice_issuer": issuer,
        },
    )
    assert resp.status_code == 201, resp.text


def _titles(resp):
    assert resp.status_code == 200, resp.text
    return [i["title"] for i in resp.json()["items"]]


@pytest.fixture
async def three_invoices(client):
    eur = (
        await client.post(
            "/api/v1/currencies", json={"label": "Euro", "abbreviation": "EUR"}
        )
    ).json()
    chf = (
        await client.post(
            "/api/v1/currencies", json={"label": "Franken", "abbreviation": "CHF"}
        )
    ).json()
    item = (
        await client.post(
            "/api/v1/items",
            json={"category": "general_item", "label": "Zelt", "owner": "MV"},
        )
    ).json()
    await _invoice(client, item["id"], "A", 100.0, eur["id"], "2026-01-10", "Musikhaus")
    await _invoice(client, item["id"], "B", 50.0, eur["id"], "2026-02-01", "Alpha")
    await _invoice(client, item["id"], "C", 70.0, chf["id"], "2026-01-20", "Zeta")
    return {"eur": eur["id"], "chf": chf["id"], "item": item["id"]}


async def test_sort_by_amount_and_issuer_and_currency_filter(client, three_invoices):
    assert _titles(await client.get("/api/v1/invoices")) == ["B", "C", "A"]
    assert _titles(await client.get("/api/v1/invoices?order_by=amount")) == [
        "B",
        "C",
        "A",
    ]
    assert _titles(await client.get("/api/v1/invoices?order_by=-invoice_issuer")) == [
        "C",
        "A",
        "B",
    ]
    resp = await client.get(f"/api/v1/invoices?currency_id={three_invoices['chf']}")
    assert _titles(resp) == ["C"]
    assert resp.json()["totals_by_currency"] == [{"abbreviation": "CHF", "total": 70.0}]
    assert resp.json()["items"][0]["invoice_issuer"] == "Zeta"


async def test_totals_cover_all_filtered_rows_not_just_the_page(client, three_invoices):
    body = (await client.get("/api/v1/invoices?limit=1")).json()
    assert len(body["items"]) == 1
    assert body["total"] == 3
    assert body["limit"] == 1 and body["offset"] == 0
    assert body["totals_by_currency"] == [
        {"abbreviation": "CHF", "total": 70.0},
        {"abbreviation": "EUR", "total": 150.0},
    ]


async def test_unknown_invoice_sort_key_is_422(client):
    assert (await client.get("/api/v1/invoices?order_by=title")).status_code == 422
