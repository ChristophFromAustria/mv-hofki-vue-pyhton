"""Tests for template variant upload endpoints (unified upload flow)."""

import io
import struct
import zlib

import pytest


def _fake_png():
    """Minimal valid 10x10 black PNG (non-white so auto-crop keeps content)."""
    header = b"\x89PNG\r\n\x1a\n"
    width, height = 10, 10
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    ihdr_crc = zlib.crc32(b"IHDR" + ihdr_data) & 0xFFFFFFFF
    ihdr = struct.pack(">I", 13) + b"IHDR" + ihdr_data + struct.pack(">I", ihdr_crc)
    raw_rows = b""
    for _ in range(height):
        raw_rows += b"\x00" + b"\x00\x00\x00" * width
    raw = zlib.compress(raw_rows)
    idat_crc = zlib.crc32(b"IDAT" + raw) & 0xFFFFFFFF
    idat = struct.pack(">I", len(raw)) + b"IDAT" + raw + struct.pack(">I", idat_crc)
    iend_crc = zlib.crc32(b"IEND") & 0xFFFFFFFF
    iend = struct.pack(">I", 0) + b"IEND" + struct.pack(">I", iend_crc)
    return header + ihdr + idat + iend


@pytest.mark.asyncio
async def test_upload_new_template(client):
    """Upload image + create new template in one call."""
    resp = await client.post(
        "/api/v1/scanner/library/templates/upload-new",
        files={"file": ("test.png", io.BytesIO(_fake_png()), "image/png")},
        data={
            "source_line_spacing": "20.0",
            "name": "Viertelnote",
            "category": "note",
            "source": "user_capture",
            "height_in_lines": "4.0",
            "musicxml_element": "<note/>",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Viertelnote"
    assert data["category"] == "note"
    assert data["variant_count"] == 1


@pytest.mark.asyncio
async def test_upload_variant_to_existing_template(client):
    """Upload image as variant to an existing template."""
    resp = await client.post(
        "/api/v1/scanner/library/templates",
        json={"category": "note", "name": "existing_tpl", "display_name": "Existing"},
    )
    tid = resp.json()["id"]

    resp = await client.post(
        f"/api/v1/scanner/library/templates/{tid}/variants/upload",
        files={"file": ("test.png", io.BytesIO(_fake_png()), "image/png")},
        data={
            "source_line_spacing": "20.0",
            "source": "user_capture",
            "height_in_lines": "4.0",
        },
    )
    assert resp.status_code == 201
    assert resp.json()["id"] == tid
    assert resp.json()["variant_count"] == 1


@pytest.mark.asyncio
async def test_upload_new_template_missing_name(client):
    """Upload-new without name should fail validation."""
    resp = await client.post(
        "/api/v1/scanner/library/templates/upload-new",
        files={"file": ("test.png", io.BytesIO(_fake_png()), "image/png")},
        data={
            "source_line_spacing": "20.0",
            "category": "note",
        },
    )
    assert resp.status_code == 422
