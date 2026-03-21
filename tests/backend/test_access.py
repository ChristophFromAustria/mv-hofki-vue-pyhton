"""Tests for Cloudflare Access email management."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from mv_hofki.services import access as access_service

# --- Sample Cloudflare API responses ---


def _make_policy_response(emails: list[str]):
    """Build a fake Cloudflare GET /access/policies/{id} response."""
    include = [{"email": {"email": e}} for e in emails]
    return {
        "success": True,
        "result": {
            "id": "policy-1",
            "decision": "allow",
            "reusable": True,
            "include": include,
            "exclude": [],
            "require": [],
            "name": "Allow emails",
            "session_duration": "24h",
        },
    }


def _make_put_response(emails: list[str]):
    """Build a fake Cloudflare PUT policy response."""
    include = [{"email": {"email": e}} for e in emails]
    return {
        "success": True,
        "result": {
            "id": "policy-1",
            "decision": "allow",
            "include": include,
            "exclude": [],
            "require": [],
            "name": "Allow emails",
            "session_duration": "24h",
        },
    }


def _mock_httpx_client(get_response=None, put_response=None):
    """Create a mock httpx.AsyncClient with preset responses."""
    mock_client = AsyncMock()
    if get_response is not None:
        mock_get_resp = MagicMock()
        mock_get_resp.status_code = 200
        mock_get_resp.json.return_value = get_response
        mock_client.get.return_value = mock_get_resp
    if put_response is not None:
        mock_put_resp = MagicMock()
        mock_put_resp.status_code = 200
        mock_put_resp.json.return_value = put_response
        mock_client.put.return_value = mock_put_resp
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


# --- Tests ---


@pytest.fixture(autouse=True)
def _cf_settings(monkeypatch):
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "test-token")
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "test-account")
    monkeypatch.setenv("CLOUDFLARE_POLICY_ID", "test-policy")


class TestGetEmails:
    async def test_returns_sorted_emails(self):
        mock = _mock_httpx_client(
            get_response=_make_policy_response(["b@example.com", "a@example.com"])
        )
        with patch("mv_hofki.services.access.httpx.AsyncClient", return_value=mock):
            result = await access_service.get_emails()
        assert result == ["a@example.com", "b@example.com"]

    async def test_raises_when_policy_not_found(self):
        mock = _mock_httpx_client(get_response={"success": True, "result": None})
        with patch("mv_hofki.services.access.httpx.AsyncClient", return_value=mock):
            with pytest.raises(HTTPException) as exc_info:
                await access_service.get_emails()
            assert exc_info.value.status_code == 502


class TestAddEmail:
    async def test_adds_email(self):
        mock = _mock_httpx_client(
            get_response=_make_policy_response(["existing@example.com"]),
            put_response=_make_put_response(
                ["existing@example.com", "new@example.com"]
            ),
        )
        with patch("mv_hofki.services.access.httpx.AsyncClient", return_value=mock):
            result = await access_service.add_email("new@example.com")
        assert "new@example.com" in result
        mock.put.assert_called_once()

    async def test_rejects_duplicate(self):
        mock = _mock_httpx_client(
            get_response=_make_policy_response(["existing@example.com"])
        )
        with patch("mv_hofki.services.access.httpx.AsyncClient", return_value=mock):
            with pytest.raises(HTTPException) as exc_info:
                await access_service.add_email("existing@example.com")
            assert exc_info.value.status_code == 409


class TestRemoveEmail:
    async def test_removes_email(self):
        mock = _mock_httpx_client(
            get_response=_make_policy_response(
                ["keep@example.com", "remove@example.com"]
            ),
            put_response=_make_put_response(["keep@example.com"]),
        )
        with patch("mv_hofki.services.access.httpx.AsyncClient", return_value=mock):
            result = await access_service.remove_email("remove@example.com")
        assert result == ["keep@example.com"]

    async def test_rejects_nonexistent(self):
        mock = _mock_httpx_client(
            get_response=_make_policy_response(["existing@example.com"])
        )
        with patch("mv_hofki.services.access.httpx.AsyncClient", return_value=mock):
            with pytest.raises(HTTPException) as exc_info:
                await access_service.remove_email("notfound@example.com")
            assert exc_info.value.status_code == 404

    async def test_prevents_removing_last_email(self):
        mock = _mock_httpx_client(
            get_response=_make_policy_response(["last@example.com"])
        )
        with patch("mv_hofki.services.access.httpx.AsyncClient", return_value=mock):
            with pytest.raises(HTTPException) as exc_info:
                await access_service.remove_email("last@example.com")
            assert exc_info.value.status_code == 400
