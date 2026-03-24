"""Tests for sheet music scan endpoints."""

import io

import pytest


@pytest.fixture
async def part_id(client):
    resp = await client.post("/api/v1/scanner/projects", json={"name": "Test"})
    project_id = resp.json()["id"]
    resp = await client.post(
        f"/api/v1/scanner/projects/{project_id}/parts",
        json={"part_name": "1. Flügelhorn"},
    )
    return project_id, resp.json()["id"]


def _fake_png():
    """Minimal valid PNG (1x1 white pixel)."""
    import struct
    import zlib

    header = b"\x89PNG\r\n\x1a\n"
    ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    ihdr_crc = zlib.crc32(b"IHDR" + ihdr_data) & 0xFFFFFFFF
    ihdr = struct.pack(">I", 13) + b"IHDR" + ihdr_data + struct.pack(">I", ihdr_crc)
    raw = zlib.compress(b"\x00\xff\xff\xff")
    idat_crc = zlib.crc32(b"IDAT" + raw) & 0xFFFFFFFF
    idat = struct.pack(">I", len(raw)) + b"IDAT" + raw + struct.pack(">I", idat_crc)
    iend_crc = zlib.crc32(b"IEND") & 0xFFFFFFFF
    iend = struct.pack(">I", 0) + b"IEND" + struct.pack(">I", iend_crc)
    return header + ihdr + idat + iend


@pytest.mark.asyncio
async def test_upload_scan(client, part_id):
    project_id, p_id = part_id
    png_data = _fake_png()
    resp = await client.post(
        f"/api/v1/scanner/projects/{project_id}/parts/{p_id}/scans",
        files={"file": ("test.png", io.BytesIO(png_data), "image/png")},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["original_filename"] == "test.png"
    assert data["status"] == "uploaded"


@pytest.mark.asyncio
async def test_upload_scan_invalid_type(client, part_id):
    project_id, p_id = part_id
    resp = await client.post(
        f"/api/v1/scanner/projects/{project_id}/parts/{p_id}/scans",
        files={"file": ("test.txt", io.BytesIO(b"not an image"), "text/plain")},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_list_scans(client, part_id):
    project_id, p_id = part_id
    png_data = _fake_png()
    await client.post(
        f"/api/v1/scanner/projects/{project_id}/parts/{p_id}/scans",
        files={"file": ("page1.png", io.BytesIO(png_data), "image/png")},
    )
    resp = await client.get(f"/api/v1/scanner/projects/{project_id}/parts/{p_id}/scans")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_delete_scan(client, part_id):
    project_id, p_id = part_id
    png_data = _fake_png()
    create_resp = await client.post(
        f"/api/v1/scanner/projects/{project_id}/parts/{p_id}/scans",
        files={"file": ("page1.png", io.BytesIO(png_data), "image/png")},
    )
    scan_id = create_resp.json()["id"]
    resp = await client.delete(
        f"/api/v1/scanner/projects/{project_id}/parts/{p_id}/scans/{scan_id}"
    )
    assert resp.status_code == 204
