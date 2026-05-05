"""Musician API tests."""

import pytest


@pytest.fixture
async def musician(client):
    resp = await client.post(
        "/api/v1/musicians",
        json={"first_name": "Max", "last_name": "Mustermann", "is_extern": False},
    )
    assert resp.status_code == 201
    return resp.json()


async def test_create_musician(client):
    resp = await client.post(
        "/api/v1/musicians",
        json={
            "first_name": "Anna",
            "last_name": "Huber",
            "email": "anna@example.com",
            "city": "Hofkirchen",
            "is_extern": False,
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["first_name"] == "Anna"
    assert data["city"] == "Hofkirchen"


async def test_create_musician_empty_name_rejected(client):
    resp = await client.post(
        "/api/v1/musicians",
        json={"first_name": "", "last_name": "Test", "is_extern": False},
    )
    assert resp.status_code == 422


async def test_list_musicians_search(client, musician):
    resp = await client.get("/api/v1/musicians?search=Mustermann")
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


async def test_update_musician(client, musician):
    resp = await client.put(
        f"/api/v1/musicians/{musician['id']}", json={"phone": "+43 123 456"}
    )
    assert resp.status_code == 200
    assert resp.json()["phone"] == "+43 123 456"


async def test_delete_musician(client, musician):
    resp = await client.delete(f"/api/v1/musicians/{musician['id']}")
    assert resp.status_code == 204
