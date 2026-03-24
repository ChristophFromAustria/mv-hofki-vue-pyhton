"""Tests for scan part CRUD endpoints."""

import pytest


@pytest.fixture
async def project_id(client):
    resp = await client.post("/api/v1/scanner/projects", json={"name": "Test Projekt"})
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_create_scan_part(client, project_id):
    resp = await client.post(
        f"/api/v1/scanner/projects/{project_id}/parts",
        json={"part_name": "1. Flügelhorn", "part_order": 1, "clef_hint": "treble"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["part_name"] == "1. Flügelhorn"
    assert data["clef_hint"] == "treble"


@pytest.mark.asyncio
async def test_create_scan_part_invalid_clef(client, project_id):
    resp = await client.post(
        f"/api/v1/scanner/projects/{project_id}/parts",
        json={"part_name": "Test", "clef_hint": "alto"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_scan_parts(client, project_id):
    await client.post(
        f"/api/v1/scanner/projects/{project_id}/parts",
        json={"part_name": "1. Flügelhorn", "part_order": 1},
    )
    await client.post(
        f"/api/v1/scanner/projects/{project_id}/parts",
        json={"part_name": "Posaune", "part_order": 2},
    )
    resp = await client.get(f"/api/v1/scanner/projects/{project_id}/parts")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["part_name"] == "1. Flügelhorn"


@pytest.mark.asyncio
async def test_delete_scan_part(client, project_id):
    create_resp = await client.post(
        f"/api/v1/scanner/projects/{project_id}/parts",
        json={"part_name": "Zum Löschen"},
    )
    part_id = create_resp.json()["id"]
    resp = await client.delete(f"/api/v1/scanner/projects/{project_id}/parts/{part_id}")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_project_cascades_parts(client, project_id):
    await client.post(
        f"/api/v1/scanner/projects/{project_id}/parts",
        json={"part_name": "Stimme"},
    )
    await client.delete(f"/api/v1/scanner/projects/{project_id}")
    resp = await client.get(f"/api/v1/scanner/projects/{project_id}/parts")
    assert resp.status_code == 404
