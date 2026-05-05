# Scan Analysis Reset Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the reset endpoint to delete all analysis data and add a reset button per scan thumbnail in the project detail page.

**Architecture:** Extend existing `PUT /scans/{scan_id}/reset-status` to accept any status except "processing", delete all analysis data (staves, symbols, measures, text regions), then set status to "uploaded". Add a small reset button in the scan thumbnail footer on `ScanProjectDetailPage.vue`.

**Tech Stack:** Python/FastAPI, SQLAlchemy, Vue 3

---

### Task 1: Extend the reset endpoint

**Files:**
- Modify: `src/backend/mv_hofki/api/routes/scan_processing.py:332-349`

- [ ] **Step 1: Write the failing test**

Create `tests/backend/test_scan_reset.py`:

```python
"""Tests for scan analysis reset endpoint."""

import pytest
from httpx import ASGITransport, AsyncClient

from mv_hofki.api.app import app
from mv_hofki.db.session import async_session


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


@pytest.fixture
async def scan_in_review(client):
    """Create a project/part/scan and run a minimal pipeline to get 'review' status."""
    # Create project
    resp = await client.post(
        "/api/v1/scanner/projects", json={"title": "Test", "composer": "X"}
    )
    project = resp.json()
    project_id = project["id"]

    # Get default part
    resp = await client.get(f"/api/v1/scanner/projects/{project_id}/parts")
    parts = resp.json()
    part_id = parts[0]["id"]

    # We need a scan — insert directly via DB to avoid file upload
    async with async_session() as session:
        from mv_hofki.models.sheet_music_scan import SheetMusicScan

        scan = SheetMusicScan(
            part_id=part_id,
            page_number=1,
            image_path="data/scans/test/test.png",
            status="review",
        )
        session.add(scan)
        await session.flush()
        scan_id = scan.id

        # Add a detected staff
        from mv_hofki.models.detected_staff import DetectedStaff

        staff = DetectedStaff(
            scan_id=scan_id,
            staff_index=0,
            y_top=10,
            y_bottom=100,
            line_positions_json="[10,30,50,70,90]",
            line_spacing=20.0,
        )
        session.add(staff)
        await session.flush()
        staff_id = staff.id

        # Add a detected symbol
        from mv_hofki.models.detected_symbol import DetectedSymbol

        symbol = DetectedSymbol(
            staff_id=staff_id,
            x=50,
            y=30,
            width=10,
            height=20,
            sequence_order=0,
        )
        session.add(symbol)

        # Add a detected measure
        from mv_hofki.models.detected_measure import DetectedMeasure

        measure = DetectedMeasure(
            scan_id=scan_id,
            staff_id=staff_id,
            staff_index=0,
            measure_number_in_staff=1,
            global_measure_number=1,
            x_start=0,
            x_end=100,
        )
        session.add(measure)

        # Add a detected text region
        from mv_hofki.models.detected_text_region import DetectedTextRegion

        text_region = DetectedTextRegion(
            scan_id=scan_id,
            staff_index=0,
            x=10,
            y=10,
            width=50,
            height=20,
        )
        session.add(text_region)
        await session.commit()

    return {"scan_id": scan_id, "project_id": project_id, "part_id": part_id}


@pytest.mark.asyncio
async def test_reset_deletes_analysis_data(client, scan_in_review):
    scan_id = scan_in_review["scan_id"]

    resp = await client.put(f"/api/v1/scanner/scans/{scan_id}/reset-status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["new_status"] == "uploaded"

    # Verify analysis data is gone
    resp = await client.get(f"/api/v1/scanner/scans/{scan_id}/staves")
    assert resp.status_code == 200
    assert resp.json() == []

    resp = await client.get(f"/api/v1/scanner/scans/{scan_id}/symbols")
    assert resp.status_code == 200
    assert resp.json() == []

    resp = await client.get(f"/api/v1/scanner/scans/{scan_id}/measures")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_reset_from_review_status(client, scan_in_review):
    """Reset should work from 'review' status (not just error/processing)."""
    scan_id = scan_in_review["scan_id"]
    resp = await client.put(f"/api/v1/scanner/scans/{scan_id}/reset-status")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_reset_rejects_processing_status(client, scan_in_review):
    """Reset should reject scans currently being processed."""
    scan_id = scan_in_review["scan_id"]

    # Set status to processing
    async with async_session() as session:
        from mv_hofki.models.sheet_music_scan import SheetMusicScan

        scan = await session.get(SheetMusicScan, scan_id)
        scan.status = "processing"
        await session.commit()

    resp = await client.put(f"/api/v1/scanner/scans/{scan_id}/reset-status")
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_reset_uploaded_is_noop(client, scan_in_review):
    """Resetting an already-uploaded scan should succeed (idempotent)."""
    scan_id = scan_in_review["scan_id"]

    # First reset
    resp = await client.put(f"/api/v1/scanner/scans/{scan_id}/reset-status")
    assert resp.status_code == 200

    # Second reset (now status is 'uploaded')
    resp = await client.put(f"/api/v1/scanner/scans/{scan_id}/reset-status")
    assert resp.status_code == 200
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/backend/test_scan_reset.py -v`
Expected: FAIL — `test_reset_from_review_status` fails with 400 (current guard rejects "review")

- [ ] **Step 3: Rewrite the reset endpoint**

Replace the `reset_scan_status` function in `src/backend/mv_hofki/api/routes/scan_processing.py` (lines 332-349):

```python
@router.put("/scans/{scan_id}/reset-status")
async def reset_scan_status(scan_id: int, db: AsyncSession = Depends(get_db)):
    """Reset a scan: delete all analysis data and set status to 'uploaded'."""
    from sqlalchemy import delete as sa_delete, select as sa_select

    from mv_hofki.models.detected_measure import DetectedMeasure
    from mv_hofki.models.detected_staff import DetectedStaff
    from mv_hofki.models.detected_symbol import DetectedSymbol
    from mv_hofki.models.detected_text_region import DetectedTextRegion
    from mv_hofki.models.sheet_music_scan import SheetMusicScan

    scan = await db.get(SheetMusicScan, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan nicht gefunden")

    if scan.status == "processing":
        raise HTTPException(
            status_code=400,
            detail="Scan wird gerade verarbeitet und kann nicht zurückgesetzt werden",
        )

    # Delete all analysis data
    staff_ids_q = sa_select(DetectedStaff.id).where(DetectedStaff.scan_id == scan_id)
    await db.execute(
        sa_delete(DetectedSymbol).where(DetectedSymbol.staff_id.in_(staff_ids_q))
    )
    await db.execute(
        sa_delete(DetectedMeasure).where(DetectedMeasure.scan_id == scan_id)
    )
    await db.execute(
        sa_delete(DetectedTextRegion).where(DetectedTextRegion.scan_id == scan_id)
    )
    await db.execute(
        sa_delete(DetectedStaff).where(DetectedStaff.scan_id == scan_id)
    )

    scan.status = "uploaded"
    await db.commit()
    return {"status": "ok", "new_status": "uploaded"}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/backend/test_scan_reset.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/backend/mv_hofki/api/routes/scan_processing.py tests/backend/test_scan_reset.py
git commit -m "feat: extend reset endpoint to delete analysis data, allow from any status"
```

---

### Task 2: Add reset button to ScanProjectDetailPage

**Files:**
- Modify: `src/frontend/src/pages/ScanProjectDetailPage.vue`

- [ ] **Step 1: Add the resetScan function**

In `src/frontend/src/pages/ScanProjectDetailPage.vue`, add the `put` import and the `resetScan` function. Change line 4:

```javascript
import { get, post, del } from "../lib/api.js";
```

to:

```javascript
import { get, post, put, del } from "../lib/api.js";
```

Then add the `resetScan` function after the `deleteScan` function (after line 108):

```javascript
async function resetScan(scan) {
  await put(`/scanner/scans/${scan.id}/reset-status`);
  await fetchData();
}
```

- [ ] **Step 2: Add the reset button to the template**

In the `thumb-footer` div (lines 228-233), add a reset button before the delete button. Replace:

```html
              <div class="thumb-footer">
                <span class="page-label">Seite {{ scan.page_number }}</span>
                <button class="btn btn-xs btn-danger" @click.stop="confirmDeleteScan(scan, part)">
                  ×
                </button>
              </div>
```

with:

```html
              <div class="thumb-footer">
                <span class="page-label">Seite {{ scan.page_number }}</span>
                <div class="thumb-actions">
                  <button
                    v-if="scan.status !== 'uploaded'"
                    class="btn btn-xs btn-muted"
                    title="Analyse zurücksetzen"
                    @click.stop="resetScan(scan)"
                  >
                    ↺
                  </button>
                  <button class="btn btn-xs btn-danger" @click.stop="confirmDeleteScan(scan, part)">
                    ×
                  </button>
                </div>
              </div>
```

- [ ] **Step 3: Add CSS for thumb-actions and btn-muted**

Add the following CSS rules inside the `<style scoped>` block, after the `.page-label` rule (after line 488):

```css
.thumb-actions {
  display: flex;
  gap: 0.2rem;
}

.btn-muted {
  color: var(--color-muted);
  background: transparent;
  border: 1px solid var(--color-border);
}

.btn-muted:hover {
  color: var(--color-text);
  border-color: var(--color-text);
}
```

- [ ] **Step 4: Verify in browser**

Open the ScanProjectDetailPage in the browser. Verify:
- Scans with status "uploaded" do NOT show the ↺ button
- Scans with status "review", "completed", or "error" DO show the ↺ button
- Clicking ↺ resets the scan and the status badge changes to "Hochgeladen"

- [ ] **Step 5: Run pre-commit**

Run: `pre-commit run --all-files`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add src/frontend/src/pages/ScanProjectDetailPage.vue
git commit -m "feat: add analysis reset button to scan thumbnails"
```
