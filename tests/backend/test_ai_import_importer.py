"""Import of a validated draft into the inventory."""

import io

import cv2
import numpy as np
import pytest

from mv_hofki.services import item_image as item_image_service
from mv_hofki.services.ai_import import archive as archive_mod
from mv_hofki.services.ai_import import session as session_service


@pytest.fixture(autouse=True)
def storage_roots(tmp_path, monkeypatch):
    monkeypatch.setattr(session_service, "IMPORTS_ROOT", tmp_path / "imports")
    monkeypatch.setattr(archive_mod, "ARCHIVE_ROOT", tmp_path / "archive")
    monkeypatch.setattr(session_service.settings, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(item_image_service, "UPLOAD_DIR", tmp_path / "images")
    return tmp_path


def _png(width=1000, height=600) -> bytes:
    img = np.full((height, width, 3), 235, np.uint8)
    cv2.rectangle(img, (100, 100), (400, 500), (50, 50, 90), -1)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    return buf.tobytes()


async def _seed(client):
    r = await client.post(
        "/api/v1/instrument-types", json={"label": "Trompete", "label_short": "TR"}
    )
    type_id = r.json()["id"]
    r = await client.post(
        "/api/v1/currencies", json={"label": "Euro", "abbreviation": "€"}
    )
    assert r.status_code == 201, r.text
    r = await client.post(
        "/api/v1/musicians", json={"first_name": "Anna", "last_name": "Hofer"}
    )
    musician_id = r.json()["id"]
    r = await client.post(
        "/api/v1/items",
        json={
            "category": "instrument",
            "label": "Alte Tuba",
            "instrument_type_id": type_id,
        },
    )
    assert r.status_code == 201, r.text
    existing_nr = r.json()["inventory_nr"]
    return type_id, musician_id, existing_nr


async def _session(client):
    r = await client.post("/api/v1/import/sessions", json={"title": "Import"})
    sid = r.json()["id"]
    r = await client.post(
        f"/api/v1/import/sessions/{sid}/files",
        files=[("files", ("a.png", io.BytesIO(_png()), "image/png"))],
    )
    page_id = r.json()["pages"][0]["id"]
    return sid, page_id


def _draft(page_id, rows=None, photos=None):
    return {
        "version": 1,
        "instruments": rows
        or [
            {
                "key": "r1",
                "page_id": page_id,
                "inventory_nr": "12",
                "instrument_type": "Trompete Bb",
                "manufacturer": "Yamaha",
                "model": "YTR-4335",
                "serial_nr": "S-1",
                "construction_year": 2009,
                "acquisition_date": "14.03.2010",
                "acquisition_cost": "1.200 €",
                "loan": {"musician_name": "Hofer Anna", "start_date": "1.9.2021"},
            },
            {
                "key": "r2",
                "page_id": page_id,
                "inventory_nr": None,
                "instrument_type": "Trompete",
                "loan": {
                    "musician_name": "Maier Karl",
                    "start_date": "1.1.2020",
                    "end_date": "1.1.2022",
                },
            },
            {
                "key": "r3",
                "page_id": page_id,
                "inventory_nr": "30",
                "instrument_type": "Trompete",
                "loan": {"musician_name": "Maier, Karl", "start_date": "2.2.2023"},
            },
            {
                "key": "r4",
                "page_id": page_id,
                "instrument_type": "Trompete",
                "skip": True,
            },
        ],
        "photos": photos
        if photos is not None
        else [
            {
                "key": "f1",
                "page_id": page_id,
                "row_key": "r1",
                "bbox_2d": [100, 100, 400, 500],
            },
            {
                "key": "f2",
                "page_id": page_id,
                "row_key": None,
                "bbox_2d": [0, 0, 50, 50],
            },
        ],
    }


async def test_import_creates_items_musicians_loans_and_images(client, storage_roots):
    type_id, musician_id, existing_nr = await _seed(client)
    assert existing_nr == 1
    sid, page_id = await _session(client)
    r = await client.put(
        f"/api/v1/import/sessions/{sid}/draft", json={"draft": _draft(page_id)}
    )
    assert r.json()["validation"]["summary"]["blocking"] is False, r.json()[
        "validation"
    ]

    r = await client.post(f"/api/v1/import/sessions/{sid}/import")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "imported"
    assert body["validation"] is None
    res = body["import_result"]
    assert res["counts"] == {"items": 3, "musicians": 1, "loans": 3, "images": 1}
    nrs = {i["row_key"]: i["inventory_nr"] for i in res["items"]}
    # r1 keeps 12, r3 keeps 30, r2 gets max+1 = 13 (12 already claimed in this run)
    assert nrs == {"r1": 12, "r2": 13, "r3": 30}
    assert res["items"][0]["display_nr"] == "I-012"
    assert res["musicians"][0]["name"] == "Karl Maier"  # created once for r2 and r3

    # database state via the regular API
    items = (await client.get("/api/v1/items?category=instrument&limit=100")).json()[
        "items"
    ]
    by_nr = {i["inventory_nr"]: i for i in items}
    assert set(by_nr) == {1, 12, 13, 30}
    t = by_nr[12]
    assert t["label"] == "Trompete Bb"
    assert t["manufacturer"] == "Yamaha"
    assert t["notes"] == "Modell: YTR-4335"
    assert t["acquisition_date"] == "2010-03-14"
    assert t["acquisition_cost"] == 1200.0
    assert t["currency"]["abbreviation"] == "€"
    assert t["serial_nr"] == "S-1"
    assert t["construction_year"] == 2009
    assert t["instrument_type"]["label"] == "Trompete"
    assert t["active_loan"]["musician_id"] == musician_id

    musicians = (await client.get("/api/v1/musicians?limit=100")).json()
    assert musicians["total"] == 2

    loans = (await client.get("/api/v1/loans?limit=100")).json()
    loans = loans["items"] if isinstance(loans, dict) else loans
    assert len(loans) == 3
    ended = [loan for loan in loans if loan["end_date"]]
    assert len(ended) == 1 and ended[0]["end_date"] == "2022-01-01"

    images = (await client.get(f"/api/v1/items/{t['id']}/images")).json()
    assert len(images) == 1 and images[0]["is_profile"] is True
    assert (storage_roots / "images" / str(t["id"]) / images[0]["filename"]).exists()

    # importing again is refused
    r = await client.post(f"/api/v1/import/sessions/{sid}/import")
    assert r.status_code == 409
    # and so is editing the draft
    r = await client.put(f"/api/v1/import/sessions/{sid}/draft", json={"draft": {}})
    assert r.status_code == 409


async def test_import_refuses_blocking_draft(client):
    await _seed(client)
    sid, page_id = await _session(client)
    rows = [
        {
            "key": "r1",
            "page_id": page_id,
            "inventory_nr": "1",
            "instrument_type": "Trompete",
        }
    ]
    await client.put(
        f"/api/v1/import/sessions/{sid}/draft",
        json={"draft": _draft(page_id, rows, [])},
    )
    r = await client.post(f"/api/v1/import/sessions/{sid}/import")
    assert r.status_code == 409
    assert "1 Fehler" in r.json()["detail"]
    assert (await client.get(f"/api/v1/import/sessions/{sid}")).json()[
        "status"
    ] == "uploaded"
    assert (await client.get("/api/v1/items?category=instrument")).json()["total"] == 1


async def test_import_without_draft(client):
    sid, _ = await _session(client)
    r = await client.post(f"/api/v1/import/sessions/{sid}/import")
    assert r.status_code == 400
