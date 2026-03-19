"""ItemImage API tests."""

import io

import pytest


@pytest.fixture
async def item(client):
    currency = (
        await client.post(
            "/api/v1/currencies", json={"label": "Euro", "abbreviation": "€"}
        )
    ).json()
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
            "currency_id": currency["id"],
            "instrument_type_id": itype["id"],
        },
    )
    return resp.json()


def _fake_image():
    """Create a minimal valid PNG."""
    import struct
    import zlib

    def chunk(chunk_type, data):
        c = chunk_type + data
        return (
            struct.pack(">I", len(data))
            + c
            + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
        )

    header = b"\x89PNG\r\n\x1a\n"
    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
    raw = zlib.compress(b"\x00\x00\x00\x00")
    idat = chunk(b"IDAT", raw)
    iend = chunk(b"IEND", b"")
    return header + ihdr + idat + iend


async def test_upload_image(client, item):
    png = _fake_image()
    resp = await client.post(
        f"/api/v1/items/{item['id']}/images",
        files={"file": ("test.png", io.BytesIO(png), "image/png")},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["item_id"] == item["id"]
    assert data["is_profile"] is True  # First image is profile
    assert data["url"].startswith("/uploads/")


async def test_upload_second_image_not_profile(client, item):
    png = _fake_image()
    await client.post(
        f"/api/v1/items/{item['id']}/images",
        files={"file": ("first.png", io.BytesIO(png), "image/png")},
    )
    resp = await client.post(
        f"/api/v1/items/{item['id']}/images",
        files={"file": ("second.png", io.BytesIO(png), "image/png")},
    )
    assert resp.json()["is_profile"] is False


async def test_list_images(client, item):
    png = _fake_image()
    await client.post(
        f"/api/v1/items/{item['id']}/images",
        files={"file": ("test.png", io.BytesIO(png), "image/png")},
    )
    resp = await client.get(f"/api/v1/items/{item['id']}/images")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


async def test_set_profile(client, item):
    png = _fake_image()
    img1 = (
        await client.post(
            f"/api/v1/items/{item['id']}/images",
            files={"file": ("a.png", io.BytesIO(png), "image/png")},
        )
    ).json()
    img2 = (
        await client.post(
            f"/api/v1/items/{item['id']}/images",
            files={"file": ("b.png", io.BytesIO(png), "image/png")},
        )
    ).json()

    resp = await client.put(f"/api/v1/items/{item['id']}/images/{img2['id']}/profile")
    assert resp.status_code == 200
    assert resp.json()["is_profile"] is True

    # Verify first is no longer profile
    images = (await client.get(f"/api/v1/items/{item['id']}/images")).json()
    first = next(i for i in images if i["id"] == img1["id"])
    assert first["is_profile"] is False


async def test_delete_image(client, item):
    png = _fake_image()
    img = (
        await client.post(
            f"/api/v1/items/{item['id']}/images",
            files={"file": ("test.png", io.BytesIO(png), "image/png")},
        )
    ).json()
    resp = await client.delete(f"/api/v1/items/{item['id']}/images/{img['id']}")
    assert resp.status_code == 204


async def test_reject_non_image(client, item):
    resp = await client.post(
        f"/api/v1/items/{item['id']}/images",
        files={"file": ("test.txt", io.BytesIO(b"hello"), "text/plain")},
    )
    assert resp.status_code == 400
