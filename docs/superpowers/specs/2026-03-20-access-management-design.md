# Access Management (Zugriffsverwaltung)

## Summary

Add a settings sub-page that allows managing the Cloudflare Access email allow-list directly from the app. Users can view, add, and remove email addresses that are permitted to access the application via Cloudflare Access.

## Context

The app is protected by Cloudflare Access with a reusable "allow" policy. This policy contains an `include` list of permitted email addresses. Currently, managing this list requires logging into the Cloudflare dashboard. This feature brings that management into the app itself.

**Cloudflare API details:**
- Zone: `mvhofki.xyz` (zone ID from env var)
- Two Access apps share one reusable policy (mv-hofki at `inventar.mvhofki.xyz`, mv-hofki-terminal at `t1.mvhofki.xyz`)
- Policy type: `allow` with `include` containing `{ email: { email: "..." } }` entries
- API base: `https://api.cloudflare.com/client/v4/zones/{zone_id}/access/apps`

## Backend

### Configuration

Two new environment variables in `.env`:

- `CLOUDFLARE_API_TOKEN` — API token with `#access:read` and `#access:edit` permissions
- `CLOUDFLARE_ZONE_ID` — the Cloudflare zone ID for `mvhofki.xyz`

These are added as `Optional[str] = None` fields in the `Settings` class in `core/config.py` (so the app still starts without them) and documented in `.env.example`.

### Service Layer

**File:** `src/backend/mv_hofki/services/access.py`

Uses `httpx.AsyncClient` to call the Cloudflare API.

**Policy discovery:** The zone-level endpoint `GET /zones/{zone_id}/access/apps` returns apps with their policies inline. The service finds the first app that has a reusable `allow` policy and uses that policy's ID. Since both apps share the same reusable policy, it doesn't matter which app is found first. The policy is updated via `PUT /zones/{zone_id}/access/apps/{app_id}/policies/{policy_id}`.

Functions:
- `get_emails() -> list[str]` — fetches the Access apps, finds the reusable allow policy, extracts emails from the `include` list. Returns emails sorted alphabetically.
- `add_email(email: str) -> list[str]` — reads current policy, appends email to `include`, PUTs updated policy, returns updated email list. Raises error if email already exists.
- `remove_email(email: str) -> list[str]` — reads current policy, removes email from `include`, PUTs updated policy, returns updated email list. Raises error if email not found. Prevents removing the last email (safety guard).

**Concurrency:** This is a single-admin, low-traffic feature. The read-modify-write race condition is acknowledged and accepted — no locking needed.

### Schemas

**File:** `src/backend/mv_hofki/schemas/access.py`

- `EmailList(BaseModel)` — `emails: list[str]`
- `EmailAdd(BaseModel)` — `email: str` with simple regex validation (no `email-validator` dependency needed)

### Routes

**File:** `src/backend/mv_hofki/api/routes/access.py`

Router prefix: `/api/v1/access`

| Method | Path | Body | Response | Description |
|--------|------|------|----------|-------------|
| GET | `/emails` | — | `EmailList` | List allowed emails |
| POST | `/emails` | `EmailAdd` | `EmailList` | Add an email |
| DELETE | `/emails/{email}` | — | `EmailList` | Remove an email (frontend must `encodeURIComponent(email)`) |

All endpoints return the full updated email list for simplicity (frontend can just replace its state).

Registered in `app.py` via `app.include_router(access_router)`.

### Error Handling

- Missing/invalid `CLOUDFLARE_API_TOKEN` or `CLOUDFLARE_ZONE_ID` → 500 with descriptive message
- Cloudflare API errors → 502 Bad Gateway with sanitized error message (no internal IDs or token info leaked to client)
- Email already exists → 409 Conflict
- Email not found → 404 Not Found
- Attempt to remove last email → 400 Bad Request

## Frontend

### Page

**File:** `src/frontend/src/pages/AccessSettingsPage.vue`

**Route:** `/einstellungen/zugriff` — added to the settings section in `router.js`

**Layout:**
- Page header: "Zugriffsverwaltung"
- Description text: "E-Mail-Adressen, die Zugriff auf die App haben."
- Add form: email input + "Hinzufügen" button
- Email list: each row shows the email and a delete button (trash icon)
- ConfirmDialog before deleting

**Behavior:**
- `onMounted`: calls `GET /api/v1/access/emails`, populates list
- Add: client-side email format validation, calls `POST /api/v1/access/emails`, updates list from response, clears input
- Delete: shows ConfirmDialog ("E-Mail-Adresse XYZ wirklich entfernen?"), on confirm calls `DELETE /api/v1/access/emails/{email}`, updates list from response
- Loading state while fetching
- Disable add/delete buttons during in-flight mutations to prevent double-submissions
- Error display for API failures

**Styling:** Follows existing page patterns and CSS variables. No new component library.

### Navigation

Add a link/entry for "Zugriffsverwaltung" in the settings navigation so it's discoverable from the Einstellungen area.

## Testing

### Backend Tests

**File:** `tests/backend/test_access.py`

- Test GET returns email list
- Test POST adds an email and returns updated list
- Test POST with duplicate email returns 409
- Test DELETE removes an email and returns updated list
- Test DELETE with nonexistent email returns 404
- Test DELETE last email returns 400

Mock the Cloudflare API calls using `httpx` mock/respx to avoid real API calls in tests.

## Out of Scope

- Managing multiple separate policies
- Managing Access apps (only the shared policy's email list)
- User authentication within the app (handled by Cloudflare Access itself)
- Managing other policy types (require, exclude)
