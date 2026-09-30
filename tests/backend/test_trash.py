"""Papierkorb: delete moves to the trash, restore, purge, 90-day cleanup."""

from datetime import timedelta

from mv_hofki.db.soft_delete import utcnow
from mv_hofki.services import item_image
from mv_hofki.services.trash import purge_expired

TRASH = "/api/v1/trash"
ME = {"Cf-Access-Authenticated-User-Email": "zeugwart@mv-hofkirchen.at"}
PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06"
    b"\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\x0f\x00\x00\x01\x01"
    b"\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


async def _tuba(client, label="Tuba"):
    tu = (
        await client.post(
            "/api/v1/instrument-types", json={"label": "Tuba", "label_short": "TU"}
        )
    ).json()["id"]
    item = (
        await client.post(
            "/api/v1/items",
            json={"category": "instrument", "label": label, "instrument_type_id": tu},
        )
    ).json()
    return tu, item


async def _labels(client, url):
    return [i["label"] for i in (await client.get(url)).json()["items"]]


async def test_trashed_item_disappears_everywhere_and_comes_back(client):
    tu, item = await _tuba(client)
    base = "/api/v1/items?category=instrument"
    assert (
        await client.delete(f"/api/v1/items/{item['id']}", headers=ME)
    ).status_code == 204

    assert await _labels(client, base) == []
    assert (await client.get(f"/api/v1/items/{item['id']}")).status_code == 404
    assert (await client.get("/api/v1/search", params={"q": "tuba"})).json()[
        "items"
    ] == []
    assert (await client.get("/api/v1/dashboard")).json()["total_items"] == 0
    # The number stays taken while the item is in the trash.
    new = (
        await client.post(
            "/api/v1/items",
            json={"category": "instrument", "label": "Neu", "instrument_type_id": tu},
        )
    ).json()
    assert new["display_nr"] == "TU-0002"

    [entry] = [e for e in (await client.get(TRASH)).json() if e["kind"] == "item"]
    assert entry["label"] == "TU-0001 Tuba"
    assert entry["kind_label"] == "Gegenstand"
    assert entry["deleted_by"] == "zeugwart@mv-hofkirchen.at"
    assert entry["purge_at"] > entry["deleted_at"]

    assert (await client.post(f"{TRASH}/item/{item['id']}/restore")).status_code == 204
    assert sorted(await _labels(client, base)) == ["Neu", "Tuba"]
    assert (await client.get(TRASH)).json() == []

    events = (await client.get(f"/api/v1/events?item_id={item['id']}")).json()["items"]
    assert [e["action"] for e in events] == ["restored", "trashed", "created"]


async def test_purge_deletes_rows_and_files_and_retires_the_number(client):
    tu, item = await _tuba(client)
    resp = await client.post(
        f"/api/v1/items/{item['id']}/images",
        files={"file": ("a.png", PNG, "image/png")},
    )
    assert resp.status_code == 201, resp.text
    folder = item_image.UPLOAD_DIR / str(item["id"])
    assert any(folder.iterdir())

    await client.delete(f"/api/v1/items/{item['id']}")
    assert folder.exists()  # files stay while it is in the trash
    assert (await client.delete(f"{TRASH}/item/{item['id']}")).status_code == 204
    assert not folder.exists()
    assert (await client.get(TRASH)).json() == []
    assert (await client.post(f"{TRASH}/item/{item['id']}/restore")).status_code == 404
    new = (
        await client.post(
            "/api/v1/items",
            json={"category": "instrument", "label": "Neu", "instrument_type_id": tu},
        )
    ).json()
    assert new["display_nr"] == "TU-0002"
    events = (await client.get(f"/api/v1/events?item_id={item['id']}")).json()["items"]
    assert events[0]["action"] == "purged"


async def test_single_image_and_invoice_go_to_the_trash(client):
    _, item = await _tuba(client)
    image = (
        await client.post(
            f"/api/v1/items/{item['id']}/images",
            files={"file": ("a.png", PNG, "image/png")},
        )
    ).json()
    eur = (
        await client.post(
            "/api/v1/currencies", json={"label": "Euro", "abbreviation": "€"}
        )
    ).json()
    invoice = (
        await client.post(
            f"/api/v1/items/{item['id']}/invoices",
            json={
                "title": "Kauf",
                "amount": 10,
                "currency_id": eur["id"],
                "date_issued": "2026-01-01",
            },
        )
    ).json()
    await client.delete(f"/api/v1/items/{item['id']}/images/{image['id']}")
    await client.delete(f"/api/v1/items/{item['id']}/invoices/{invoice['id']}")
    assert (await client.get(f"/api/v1/items/{item['id']}/images")).json() == []
    assert (await client.get(f"/api/v1/items/{item['id']}/invoices")).json() == []
    trash = {e["kind"]: e for e in (await client.get(TRASH)).json()}
    assert trash["image"]["context"] == "TU-0001 Tuba"
    assert trash["invoice"]["label"] == "Rechnung „Kauf“"
    await client.post(f"{TRASH}/invoice/{invoice['id']}/restore")
    assert len((await client.get(f"/api/v1/items/{item['id']}/invoices")).json()) == 1


async def test_trashed_musician_stays_in_loan_history_marked(client):
    _, item = await _tuba(client)
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
    assert (await client.delete(f"/api/v1/musicians/{m['id']}")).status_code == 409
    await client.put(f"/api/v1/loans/{loan['id']}/return", json={})
    assert (await client.delete(f"/api/v1/musicians/{m['id']}")).status_code == 204

    assert (await client.get("/api/v1/musicians?is_active=true")).json()["items"] == []
    history = (await client.get(f"/api/v1/loans?item_id={item['id']}")).json()["items"]
    assert history[0]["musician"]["last_name"] == "Maier"
    assert history[0]["musician"]["deleted_at"] is not None
    # Can't lend to a musician in the trash.
    resp = await client.post(
        "/api/v1/loans",
        json={
            "item_id": item["id"],
            "musician_id": m["id"],
            "start_date": "2026-02-01",
        },
    )
    assert resp.status_code == 404

    # Purging the musician also removes their loans.
    await client.delete(f"{TRASH}/musician/{m['id']}")
    assert (await client.get(f"/api/v1/loans?item_id={item['id']}")).json()[
        "total"
    ] == 0


async def test_master_data_names_in_the_trash_and_in_use(client):
    hut = (await client.post("/api/v1/clothing-types", json={"label": "Hut"})).json()
    await client.delete(f"/api/v1/clothing-types/{hut['id']}")
    assert (await client.get("/api/v1/clothing-types")).json() == []
    again = await client.post("/api/v1/clothing-types", json={"label": "hut"})
    assert again.status_code == 409
    assert "liegt im Papierkorb" in again.json()["detail"]
    dup = await client.post("/api/v1/clothing-types", json={"label": "Jacke"})
    assert dup.status_code == 201
    assert (
        await client.post("/api/v1/clothing-types", json={"label": "Jacke"})
    ).status_code == 409

    # A type used by an item in the trash can't be deleted either.
    tu, item = await _tuba(client)
    await client.delete(f"/api/v1/items/{item['id']}")
    assert (await client.delete(f"/api/v1/instrument-types/{tu}")).status_code == 409


async def test_purge_expired_after_90_days(client, db_session):
    _, old = await _tuba(client, "Alt")
    await client.delete(f"/api/v1/items/{old['id']}")
    assert await purge_expired(db_session, now=utcnow() + timedelta(days=89)) == 0
    assert await purge_expired(db_session, now=utcnow() + timedelta(days=91)) == 1
    assert (await client.get(TRASH)).json() == []
