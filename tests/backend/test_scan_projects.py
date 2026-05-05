"""Tests for scan project CRUD endpoints."""

import pytest


@pytest.mark.asyncio
async def test_create_scan_project(client):
    resp = await client.post(
        "/api/v1/scanner/projects",
        json={"name": "Böhmischer Traum", "composer": "J. Brunner"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Böhmischer Traum"
    assert data["composer"] == "J. Brunner"
    assert data["id"] is not None


@pytest.mark.asyncio
async def test_create_scan_project_empty_name_rejected(client):
    resp = await client.post("/api/v1/scanner/projects", json={"name": "  "})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_scan_projects(client):
    await client.post(
        "/api/v1/scanner/projects",
        json={"name": "Projekt A"},
    )
    await client.post(
        "/api/v1/scanner/projects",
        json={"name": "Projekt B"},
    )
    resp = await client.get("/api/v1/scanner/projects")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


@pytest.mark.asyncio
async def test_get_scan_project(client):
    create_resp = await client.post(
        "/api/v1/scanner/projects",
        json={"name": "Test Projekt"},
    )
    project_id = create_resp.json()["id"]
    resp = await client.get(f"/api/v1/scanner/projects/{project_id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Test Projekt"


@pytest.mark.asyncio
async def test_get_scan_project_not_found(client):
    resp = await client.get("/api/v1/scanner/projects/999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_scan_project(client):
    create_resp = await client.post(
        "/api/v1/scanner/projects",
        json={"name": "Original"},
    )
    project_id = create_resp.json()["id"]
    resp = await client.put(
        f"/api/v1/scanner/projects/{project_id}",
        json={"name": "Geändert"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Geändert"


@pytest.mark.asyncio
async def test_delete_scan_project(client):
    create_resp = await client.post(
        "/api/v1/scanner/projects",
        json={"name": "Zum Löschen"},
    )
    project_id = create_resp.json()["id"]
    resp = await client.delete(f"/api/v1/scanner/projects/{project_id}")
    assert resp.status_code == 204
    resp = await client.get(f"/api/v1/scanner/projects/{project_id}")
    assert resp.status_code == 404
