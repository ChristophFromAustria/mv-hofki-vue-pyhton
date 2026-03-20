"""Cloudflare Access email management service."""

from __future__ import annotations

import logging

import httpx
from fastapi import HTTPException

from mv_hofki.core.config import Settings

logger = logging.getLogger(__name__)

CF_API_BASE = "https://api.cloudflare.com/client/v4"


def _get_settings() -> Settings:
    """Load settings fresh (allows env overrides in tests)."""
    return Settings()


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


async def _fetch_policy(
    client: httpx.AsyncClient, zone_id: str, token: str
) -> tuple[str, str, dict]:
    """Find the first reusable allow policy and return (app_id, policy_id, policy)."""
    url = f"{CF_API_BASE}/zones/{zone_id}/access/apps"
    resp = await client.get(url, headers=_headers(token))
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail="Cloudflare API nicht erreichbar")

    data = resp.json()
    if not data.get("success") or not data.get("result"):
        raise HTTPException(status_code=502, detail="Keine Access-Anwendungen gefunden")

    for app in data["result"]:
        for policy in app.get("policies", []):
            if policy.get("decision") == "allow" and policy.get("reusable"):
                return app["id"], policy["id"], policy

    raise HTTPException(status_code=502, detail="Keine Allow-Policy gefunden")


def _extract_emails(policy: dict) -> list[str]:
    """Extract email addresses from policy include list."""
    emails = []
    for entry in policy.get("include", []):
        email_obj = entry.get("email", {})
        if email_obj and "email" in email_obj:
            emails.append(email_obj["email"])
    return sorted(emails)


async def get_emails() -> list[str]:
    """Get the list of allowed email addresses."""
    s = _get_settings()
    if not s.CLOUDFLARE_API_TOKEN or not s.CLOUDFLARE_ZONE_ID:
        raise HTTPException(status_code=500, detail="Cloudflare-Konfiguration fehlt")

    async with httpx.AsyncClient() as client:
        _, _, policy = await _fetch_policy(
            client, s.CLOUDFLARE_ZONE_ID, s.CLOUDFLARE_API_TOKEN
        )
    return _extract_emails(policy)


async def _update_policy_emails(
    client: httpx.AsyncClient,
    zone_id: str,
    token: str,
    app_id: str,
    policy_id: str,
    policy: dict,
    new_include: list[dict],
) -> list[str]:
    """PUT updated include list to Cloudflare and return the new email list."""
    url = f"{CF_API_BASE}/zones/{zone_id}/access/apps/{app_id}/policies/{policy_id}"
    payload = {
        "name": policy["name"],
        "decision": policy["decision"],
        "include": new_include,
        "exclude": policy.get("exclude", []),
        "require": policy.get("require", []),
    }
    resp = await client.put(url, headers=_headers(token), json=payload)
    if resp.status_code != 200:
        logger.error("Cloudflare PUT failed: %s", resp.status_code)
        raise HTTPException(
            status_code=502, detail="Cloudflare-Policy konnte nicht aktualisiert werden"
        )

    updated = resp.json()
    return _extract_emails(updated.get("result", {}))


async def add_email(email: str) -> list[str]:
    """Add an email to the access allow-list."""
    s = _get_settings()
    if not s.CLOUDFLARE_API_TOKEN or not s.CLOUDFLARE_ZONE_ID:
        raise HTTPException(status_code=500, detail="Cloudflare-Konfiguration fehlt")

    async with httpx.AsyncClient() as client:
        app_id, policy_id, policy = await _fetch_policy(
            client, s.CLOUDFLARE_ZONE_ID, s.CLOUDFLARE_API_TOKEN
        )

        existing = _extract_emails(policy)
        if email.lower() in [e.lower() for e in existing]:
            raise HTTPException(
                status_code=409, detail="E-Mail-Adresse bereits vorhanden"
            )

        new_include = policy.get("include", []) + [{"email": {"email": email}}]
        return await _update_policy_emails(
            client,
            s.CLOUDFLARE_ZONE_ID,
            s.CLOUDFLARE_API_TOKEN,
            app_id,
            policy_id,
            policy,
            new_include,
        )


async def remove_email(email: str) -> list[str]:
    """Remove an email from the access allow-list."""
    s = _get_settings()
    if not s.CLOUDFLARE_API_TOKEN or not s.CLOUDFLARE_ZONE_ID:
        raise HTTPException(status_code=500, detail="Cloudflare-Konfiguration fehlt")

    async with httpx.AsyncClient() as client:
        app_id, policy_id, policy = await _fetch_policy(
            client, s.CLOUDFLARE_ZONE_ID, s.CLOUDFLARE_API_TOKEN
        )

        existing = _extract_emails(policy)
        if email.lower() not in [e.lower() for e in existing]:
            raise HTTPException(status_code=404, detail="E-Mail-Adresse nicht gefunden")

        if len(existing) <= 1:
            raise HTTPException(
                status_code=400,
                detail="Letzte E-Mail-Adresse kann nicht entfernt werden",
            )

        new_include = [
            entry
            for entry in policy.get("include", [])
            if entry.get("email", {}).get("email", "").lower() != email.lower()
        ]
        return await _update_policy_emails(
            client,
            s.CLOUDFLARE_ZONE_ID,
            s.CLOUDFLARE_API_TOKEN,
            app_id,
            policy_id,
            policy,
            new_include,
        )
