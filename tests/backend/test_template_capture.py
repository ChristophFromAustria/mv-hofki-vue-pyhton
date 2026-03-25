"""Tests for template capture endpoint."""

import io
import struct
import zlib

import pytest


def _fake_png():
    """Minimal valid 10x10 white PNG."""
    header = b"\x89PNG\r\n\x1a\n"
    width, height = 10, 10
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    ihdr_crc = zlib.crc32(b"IHDR" + ihdr_data) & 0xFFFFFFFF
    ihdr = struct.pack(">I", 13) + b"IHDR" + ihdr_data + struct.pack(">I", ihdr_crc)
    raw_rows = b""
    for _ in range(height):
        raw_rows += b"\x00" + b"\xff\xff\xff" * width
    raw = zlib.compress(raw_rows)
    idat_crc = zlib.crc32(b"IDAT" + raw) & 0xFFFFFFFF
    idat = struct.pack(">I", len(raw)) + b"IDAT" + raw + struct.pack(">I", idat_crc)
    iend_crc = zlib.crc32(b"IEND") & 0xFFFFFFFF
    iend = struct.pack(">I", 0) + b"IEND" + struct.pack(">I", iend_crc)
    return header + ihdr + idat + iend


@pytest.fixture
async def scan_id(client):
    """Create a project/part/scan to capture from."""
    resp = await client.post("/api/v1/scanner/projects", json={"name": "Test"})
    project_id = resp.json()["id"]
    resp = await client.post(
        f"/api/v1/scanner/projects/{project_id}/parts",
        json={"part_name": "Flügelhorn"},
    )
    part_id = resp.json()["id"]
    resp = await client.post(
        f"/api/v1/scanner/projects/{project_id}/parts/{part_id}/scans",
        files={"file": ("test.png", io.BytesIO(_fake_png()), "image/png")},
    )
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_capture_template(client, scan_id):
    resp = await client.post(
        "/api/v1/scanner/library/templates/capture",
        json={
            "scan_id": scan_id,
            "x": 0,
            "y": 0,
            "width": 5,
            "height": 8,
            "name": "Viertelnote",
            "category": "note",
            "musicxml_element": "<note/>",
            "height_in_lines": 4.0,
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Viertelnote"
    assert data["category"] == "note"


@pytest.mark.asyncio
async def test_capture_template_missing_name(client, scan_id):
    resp = await client.post(
        "/api/v1/scanner/library/templates/capture",
        json={
            "scan_id": scan_id,
            "x": 0,
            "y": 0,
            "width": 5,
            "height": 8,
            "name": "",
            "category": "note",
            "height_in_lines": 4.0,
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_capture_to_existing_template(client, scan_id):
    """Capture should add variant to existing template when template_id is given."""
    resp = await client.post(
        "/api/v1/scanner/library/templates",
        json={"category": "note", "name": "existing_tpl", "display_name": "Existing"},
    )
    tid = resp.json()["id"]

    resp = await client.post(
        "/api/v1/scanner/library/templates/capture",
        json={
            "scan_id": scan_id,
            "x": 0,
            "y": 0,
            "width": 5,
            "height": 5,
            "template_id": tid,
            "category": "note",
            "height_in_lines": 4.0,
        },
    )
    assert resp.status_code == 201
    assert resp.json()["id"] == tid
