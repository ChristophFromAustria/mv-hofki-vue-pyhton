# Access Management (Zugriffsverwaltung) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a settings page to manage the Cloudflare Access email allow-list from within the app.

**Architecture:** Backend proxies Cloudflare API calls via 3 endpoints (list/add/remove emails). Frontend adds a settings sub-page at `/einstellungen/zugriff`. The Cloudflare API token and zone ID are read from environment variables.

**Tech Stack:** FastAPI, httpx (async HTTP client), Pydantic, Vue 3 Composition API, Cloudflare Access API v4

**Spec:** `docs/superpowers/specs/2026-03-20-access-management-design.md`

---

## File Structure

| Action | File | Purpose |
|--------|------|---------|
| Modify | `pyproject.toml` | Add `httpx` to production dependencies |
| Modify | `src/backend/mv_hofki/core/config.py` | Add Cloudflare env vars to Settings |
| Modify | `.env.example` | Document new env vars |
| Create | `src/backend/mv_hofki/schemas/access.py` | Pydantic schemas for email list/add |
| Create | `src/backend/mv_hofki/services/access.py` | Cloudflare API client logic |
| Create | `src/backend/mv_hofki/api/routes/access.py` | FastAPI route handlers |
| Modify | `src/backend/mv_hofki/api/app.py` | Register access router |
| Create | `tests/backend/test_access.py` | Backend tests with mocked Cloudflare API |
| Create | `src/frontend/src/pages/AccessSettingsPage.vue` | Frontend page |
| Modify | `src/frontend/src/router.js` | Add route for settings page |

---

### Task 1: Add httpx production dependency and Cloudflare config

**Files:**
- Modify: `pyproject.toml:6-14`
- Modify: `src/backend/mv_hofki/core/config.py:20-31`
- Modify: `.env.example`

- [ ] **Step 1: Add httpx to production dependencies in pyproject.toml**

In `pyproject.toml`, add `httpx` to the `dependencies` list:

```toml
dependencies = [
    "fastapi>=0.115,<1",
    "uvicorn[standard]>=0.34,<1",
    "pydantic-settings>=2.0,<3",
    "sqlalchemy[asyncio]>=2.0,<3",
    "aiosqlite>=0.20,<1",
    "alembic>=1.13,<2",
    "python-multipart>=0.0.9,<1",
    "httpx>=0.27,<1",
]
```

- [ ] **Step 2: Install the updated dependencies**

Run: `cd /workspaces/mv_hofki && pip install -e ".[dev]"`

- [ ] **Step 3: Add Cloudflare env vars to Settings class**

In `src/backend/mv_hofki/core/config.py`, add two optional fields to the `Settings` class:

```python
class Settings(BaseSettings):
    APP_NAME: str = "mv_hofki"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"
    BASE_PATH: str = "/"

    PROJECT_ROOT: Path = _find_project_root()

    DATABASE_URL: str = "sqlite+aiosqlite:///data/mv_hofki.db"

    CLOUDFLARE_API_TOKEN: str | None = None
    CLOUDFLARE_ZONE_ID: str | None = None

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}
```

- [ ] **Step 4: Add env vars to .env.example**

Append to `.env.example`:

```
CLOUDFLARE_API_TOKEN=
CLOUDFLARE_ZONE_ID=
```

- [ ] **Step 5: Add actual values to .env**

Add to `.env` (do NOT commit this file):

```
CLOUDFLARE_API_TOKEN=<your-cloudflare-api-token>
CLOUDFLARE_ZONE_ID=<your-cloudflare-zone-id>
```

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src/backend/mv_hofki/core/config.py .env.example
git commit -m "feat: add httpx dependency and Cloudflare config settings"
```

---

### Task 2: Create Pydantic schemas for access endpoints

**Files:**
- Create: `src/backend/mv_hofki/schemas/access.py`

- [ ] **Step 1: Create the schema file**

Create `src/backend/mv_hofki/schemas/access.py`:

```python
"""Schemas for Cloudflare Access email management."""

from __future__ import annotations

import re

from pydantic import BaseModel, field_validator


class EmailList(BaseModel):
    emails: list[str]


class EmailAdd(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", v):
            msg = "Ungültige E-Mail-Adresse"
            raise ValueError(msg)
        return v
```

- [ ] **Step 2: Commit**

```bash
git add src/backend/mv_hofki/schemas/access.py
git commit -m "feat: add Pydantic schemas for access email management"
```

---

### Task 3: Create access service with Cloudflare API integration

**Files:**
- Create: `src/backend/mv_hofki/services/access.py`
- Create: `tests/backend/test_access.py`

- [ ] **Step 1: Write tests for the access service**

Create `tests/backend/test_access.py`:

```python
"""Tests for Cloudflare Access email management."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from mv_hofki.services import access as access_service


# --- Sample Cloudflare API responses ---

def _make_apps_response(emails: list[str]):
    """Build a fake Cloudflare GET /access/apps response."""
    include = [{"email": {"email": e}} for e in emails]
    return {
        "success": True,
        "result": [
            {
                "id": "app-1",
                "name": "mv-hofki",
                "policies": [
                    {
                        "id": "policy-1",
                        "decision": "allow",
                        "reusable": True,
                        "include": include,
                        "exclude": [],
                        "require": [],
                        "name": "Allow emails",
                    }
                ],
            }
        ],
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
        },
    }


def _mock_httpx_client(get_response=None, put_response=None):
    """Create a mock httpx.AsyncClient with preset responses."""
    mock_client = AsyncMock()
    if get_response is not None:
        mock_get_resp = AsyncMock()
        mock_get_resp.status_code = 200
        mock_get_resp.json.return_value = get_response
        mock_client.get.return_value = mock_get_resp
    if put_response is not None:
        mock_put_resp = AsyncMock()
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
    monkeypatch.setenv("CLOUDFLARE_ZONE_ID", "test-zone")


class TestGetEmails:
    async def test_returns_sorted_emails(self):
        mock = _mock_httpx_client(
            get_response=_make_apps_response(["b@example.com", "a@example.com"])
        )
        with patch("mv_hofki.services.access.httpx.AsyncClient", return_value=mock):
            result = await access_service.get_emails()
        assert result == ["a@example.com", "b@example.com"]

    async def test_raises_when_no_apps(self):
        mock = _mock_httpx_client(
            get_response={"success": True, "result": []}
        )
        with patch("mv_hofki.services.access.httpx.AsyncClient", return_value=mock):
            with pytest.raises(HTTPException) as exc_info:
                await access_service.get_emails()
            assert exc_info.value.status_code == 502


class TestAddEmail:
    async def test_adds_email(self):
        mock = _mock_httpx_client(
            get_response=_make_apps_response(["existing@example.com"]),
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
            get_response=_make_apps_response(["existing@example.com"])
        )
        with patch("mv_hofki.services.access.httpx.AsyncClient", return_value=mock):
            with pytest.raises(HTTPException) as exc_info:
                await access_service.add_email("existing@example.com")
            assert exc_info.value.status_code == 409


class TestRemoveEmail:
    async def test_removes_email(self):
        mock = _mock_httpx_client(
            get_response=_make_apps_response(
                ["keep@example.com", "remove@example.com"]
            ),
            put_response=_make_put_response(["keep@example.com"]),
        )
        with patch("mv_hofki.services.access.httpx.AsyncClient", return_value=mock):
            result = await access_service.remove_email("remove@example.com")
        assert result == ["keep@example.com"]

    async def test_rejects_nonexistent(self):
        mock = _mock_httpx_client(
            get_response=_make_apps_response(["existing@example.com"])
        )
        with patch("mv_hofki.services.access.httpx.AsyncClient", return_value=mock):
            with pytest.raises(HTTPException) as exc_info:
                await access_service.remove_email("notfound@example.com")
            assert exc_info.value.status_code == 404

    async def test_prevents_removing_last_email(self):
        mock = _mock_httpx_client(
            get_response=_make_apps_response(["last@example.com"])
        )
        with patch("mv_hofki.services.access.httpx.AsyncClient", return_value=mock):
            with pytest.raises(HTTPException) as exc_info:
                await access_service.remove_email("last@example.com")
            assert exc_info.value.status_code == 400
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /workspaces/mv_hofki && python -m pytest tests/backend/test_access.py -v`
Expected: FAIL (module `mv_hofki.services.access` does not exist)

- [ ] **Step 3: Create the access service**

Create `src/backend/mv_hofki/services/access.py`:

```python
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
        raise HTTPException(
            status_code=502, detail="Keine Access-Anwendungen gefunden"
        )

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
        raise HTTPException(
            status_code=500, detail="Cloudflare-Konfiguration fehlt"
        )

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
        raise HTTPException(
            status_code=500, detail="Cloudflare-Konfiguration fehlt"
        )

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
        raise HTTPException(
            status_code=500, detail="Cloudflare-Konfiguration fehlt"
        )

    async with httpx.AsyncClient() as client:
        app_id, policy_id, policy = await _fetch_policy(
            client, s.CLOUDFLARE_ZONE_ID, s.CLOUDFLARE_API_TOKEN
        )

        existing = _extract_emails(policy)
        if email.lower() not in [e.lower() for e in existing]:
            raise HTTPException(
                status_code=404, detail="E-Mail-Adresse nicht gefunden"
            )

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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /workspaces/mv_hofki && python -m pytest tests/backend/test_access.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/backend/mv_hofki/services/access.py tests/backend/test_access.py
git commit -m "feat: add Cloudflare Access email management service with tests"
```

---

### Task 4: Create API routes and register in app

**Files:**
- Create: `src/backend/mv_hofki/api/routes/access.py`
- Modify: `src/backend/mv_hofki/api/app.py:12-56`

- [ ] **Step 1: Create the route handler**

Create `src/backend/mv_hofki/api/routes/access.py`:

```python
"""Routes for Cloudflare Access email management."""

from __future__ import annotations

from fastapi import APIRouter

from mv_hofki.schemas.access import EmailAdd, EmailList
from mv_hofki.services import access as access_service

router = APIRouter(prefix="/api/v1/access", tags=["access"])


@router.get("/emails", response_model=EmailList)
async def list_emails():
    emails = await access_service.get_emails()
    return EmailList(emails=emails)


@router.post("/emails", response_model=EmailList, status_code=201)
async def add_email(data: EmailAdd):
    emails = await access_service.add_email(data.email)
    return EmailList(emails=emails)


@router.delete("/emails/{email:path}", response_model=EmailList)
async def remove_email(email: str):
    emails = await access_service.remove_email(email)
    return EmailList(emails=emails)
```

Note: `{email:path}` path converter handles the `@` character in email addresses.

- [ ] **Step 2: Register the router in app.py**

In `src/backend/mv_hofki/api/app.py`, add the import after the existing route imports:

```python
from mv_hofki.api.routes.access import router as access_router
```

And add `app.include_router(access_router)` after the existing `include_router` calls (after line 56, before the static file mounts).

- [ ] **Step 3: Restart the server and verify**

Run: `server-restart`
Then verify: `curl -s http://localhost:8000/api/v1/access/emails | python3 -m json.tool`
Expected: `{ "emails": ["choeftberger@gmail.com"] }` (if .env has the Cloudflare vars set)

- [ ] **Step 4: Commit**

```bash
git add src/backend/mv_hofki/api/routes/access.py src/backend/mv_hofki/api/app.py
git commit -m "feat: add access email management API routes"
```

---

### Task 5: Create frontend page and add route

**Files:**
- Create: `src/frontend/src/pages/AccessSettingsPage.vue`
- Modify: `src/frontend/src/router.js:61-79`

- [ ] **Step 1: Create the AccessSettingsPage component**

Create `src/frontend/src/pages/AccessSettingsPage.vue`:

```vue
<script setup>
import { ref, onMounted } from "vue";
import { get, post, del } from "../lib/api.js";
import ConfirmDialog from "../components/ConfirmDialog.vue";

const emails = ref([]);
const newEmail = ref("");
const loading = ref(true);
const saving = ref(false);
const error = ref("");
const deleteTarget = ref(null);

async function load() {
  loading.value = true;
  error.value = "";
  try {
    const data = await get("/access/emails");
    emails.value = data.emails;
  } catch (e) {
    error.value = "Fehler beim Laden: " + e.message;
  } finally {
    loading.value = false;
  }
}

onMounted(load);

async function addEmail() {
  if (!newEmail.value.trim()) return;
  saving.value = true;
  error.value = "";
  try {
    const data = await post("/access/emails", { email: newEmail.value.trim() });
    emails.value = data.emails;
    newEmail.value = "";
  } catch (e) {
    error.value = "Fehler: " + e.message;
  } finally {
    saving.value = false;
  }
}

async function removeEmail() {
  const email = deleteTarget.value;
  deleteTarget.value = null;
  if (!email) return;
  saving.value = true;
  error.value = "";
  try {
    const data = await del(`/access/emails/${encodeURIComponent(email)}`);
    emails.value = data.emails;
  } catch (e) {
    error.value = "Fehler: " + e.message;
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <div>
    <div class="page-header">
      <h1>Zugriffsverwaltung</h1>
    </div>

    <p style="margin-bottom: 1rem; color: var(--color-muted)">
      E-Mail-Adressen, die Zugriff auf die App haben.
    </p>

    <div v-if="error" class="alert alert-danger" style="margin-bottom: 1rem">
      {{ error }}
    </div>

    <form
      @submit.prevent="addEmail"
      style="display: flex; gap: 0.5rem; margin-bottom: 1.5rem; flex-wrap: wrap"
    >
      <input
        v-model="newEmail"
        type="email"
        placeholder="neue@email.at"
        :disabled="saving"
        style="flex: 1; min-width: 200px"
      />
      <button class="btn btn-primary" :disabled="saving || !newEmail.trim()" type="submit">
        Hinzufügen
      </button>
    </form>

    <p v-if="loading">Laden...</p>

    <div v-else-if="emails.length" style="overflow-x: auto; -webkit-overflow-scrolling: touch">
      <table>
        <thead>
          <tr>
            <th>E-Mail-Adresse</th>
            <th style="width: 80px"></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="email in emails" :key="email">
            <td>{{ email }}</td>
            <td>
              <button
                class="btn-sm btn-danger"
                :disabled="saving"
                @click="deleteTarget = email"
              >
                X
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <p v-else-if="!loading">Keine E-Mail-Adressen vorhanden.</p>

    <ConfirmDialog
      :open="!!deleteTarget"
      title="Zugriff entfernen"
      :message="`E-Mail-Adresse ${deleteTarget} wirklich entfernen?`"
      @confirm="removeEmail"
      @cancel="deleteTarget = null"
    />
  </div>
</template>
```

- [ ] **Step 2: Add the route to router.js**

In `src/frontend/src/router.js`, add a new route entry after the currencies route (after line 79):

```javascript
  {
    path: "/einstellungen/zugriff",
    name: "access-settings",
    component: () => import("./pages/AccessSettingsPage.vue"),
  },
```

- [ ] **Step 3: Verify in browser**

Wait for the frontend watcher to rebuild (check `frontend-logs`), then open `/einstellungen/zugriff` in the browser. Verify:
- Email list loads and shows `choeftberger@gmail.com`
- Can add a new email
- Can delete an email (with confirmation dialog)

- [ ] **Step 4: Commit**

```bash
git add src/frontend/src/pages/AccessSettingsPage.vue src/frontend/src/router.js
git commit -m "feat: add Zugriffsverwaltung settings page"
```

---

### Task 6: Add navigation link in NavBar

**Files:**
- Modify: `src/frontend/src/components/NavBar.vue:67-77`

- [ ] **Step 1: Add "Zugriffsverwaltung" link to settings dropdown**

In `src/frontend/src/components/NavBar.vue`, insert a new RouterLink before the Terminal link (between line 75 and 76). The dropdown-menu section should become:

```html
<div v-show="settingsOpen" class="dropdown-menu">
  <RouterLink to="/einstellungen/instrumententypen" @click="closeMenu">
    Instrumententypen
  </RouterLink>
  <RouterLink to="/einstellungen/kleidungstypen" @click="closeMenu">
    Kleidungstypen
  </RouterLink>
  <RouterLink to="/einstellungen/notengenres" @click="closeMenu">Notengenres</RouterLink>
  <RouterLink to="/einstellungen/waehrungen" @click="closeMenu">Währungen</RouterLink>
  <RouterLink to="/einstellungen/zugriff" @click="closeMenu">Zugriffsverwaltung</RouterLink>
  <a href="//localhost:7681" target="_blank" class="terminal-link">Terminal</a>
</div>
```

- [ ] **Step 2: Verify navigation works**

Check that the link appears in the settings dropdown and navigates to the correct page.

- [ ] **Step 3: Commit**

```bash
git add src/frontend/src/components/NavBar.vue
git commit -m "feat: add Zugriffsverwaltung link to settings navigation"
```

---

### Task 7: Run full test suite and lint

- [ ] **Step 1: Run backend tests**

Run: `cd /workspaces/mv_hofki && python -m pytest tests/backend/ -v`
Expected: All tests PASS

- [ ] **Step 2: Run linter**

Run: `cd /workspaces/mv_hofki && pre-commit run --all-files`
Expected: All checks pass. Fix any issues if they don't.

- [ ] **Step 3: Final commit if lint fixes needed**

```bash
git add -u
git commit -m "fix: lint and formatting fixes"
```
