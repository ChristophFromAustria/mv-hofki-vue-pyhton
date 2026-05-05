# Merge Variant Upload Endpoints — Single Source of Truth

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate the duplicate `/templates/capture` endpoint by moving image extraction to the frontend, so all variant uploads go through the single `/templates/{template_id}/variants/upload` endpoint.

**Architecture:** The capture flow currently sends coordinates to the backend which crops the scan image server-side. Instead, the frontend will crop the image on a `<canvas>`, encode it as a PNG blob, and upload it through the existing `/variants/upload` endpoint — the same path the library page already uses. The backend `capture_template()` service function and `/templates/capture` route are deleted entirely. The upload endpoint gains optional form fields for template creation (name, category, etc.) so the scan editor can still create new templates inline.

**Tech Stack:** FastAPI, Vue 3, Canvas API, FormData

---

### Task 1: Extend the upload endpoint to support template creation

The current upload endpoint only accepts `template_id` as a path param (existing template required). The capture flow can create new templates. We need the upload endpoint to handle both cases: adding a variant to an existing template, OR creating a new template and adding the first variant.

**Files:**
- Modify: `src/backend/mv_hofki/api/routes/symbol_library.py:93-116`
- Modify: `src/backend/mv_hofki/services/symbol_library.py:139-177`

- [ ] **Step 1: Update the route to accept optional template-creation fields**

Change `upload_variant` in `src/backend/mv_hofki/api/routes/symbol_library.py` to accept optional Form fields for creating a new template. Replace the existing endpoint (lines 93-116) with:

```python
@router.post(
    "/templates/{template_id}/variants/upload",
    response_model=SymbolTemplateRead,
    status_code=201,
)
async def upload_variant(
    template_id: int,
    file: UploadFile,
    source_line_spacing: float = Form(...),
    source: str = Form("cropped"),
    height_in_lines: float | None = Form(None),
    db: AsyncSession = Depends(get_db),
):
    """Upload an image file as a new variant for the given template."""
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Leere Datei")
    return await lib_service.save_rendered_variant(
        db,
        template_id,
        content,
        source=source,
        height_in_lines=height_in_lines,
        source_line_spacing=source_line_spacing,
    )
```

Also add a **new** endpoint for uploading with inline template creation. Place it right after the existing upload endpoint:

```python
@router.post(
    "/templates/upload-new",
    response_model=SymbolTemplateRead,
    status_code=201,
)
async def upload_variant_new_template(
    file: UploadFile,
    source_line_spacing: float = Form(...),
    name: str = Form(...),
    category: str = Form(...),
    source: str = Form("user_capture"),
    height_in_lines: float | None = Form(None),
    musicxml_element: str | None = Form(None),
    db: AsyncSession = Depends(get_db),
):
    """Upload an image as the first variant of a new template (created inline)."""
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Leere Datei")

    template = await lib_service.find_or_create_template(
        db,
        name=name,
        category=category,
        musicxml_element=musicxml_element,
    )
    return await lib_service.save_rendered_variant(
        db,
        template.id,
        content,
        source=source,
        height_in_lines=height_in_lines,
        source_line_spacing=source_line_spacing,
    )
```

- [ ] **Step 2: Add `find_or_create_template` service function**

Add this function to `src/backend/mv_hofki/services/symbol_library.py` right before `save_rendered_variant`:

```python
async def find_or_create_template(
    session: AsyncSession,
    *,
    name: str,
    category: str,
    musicxml_element: str | None = None,
) -> SymbolTemplate:
    """Find an existing template by name, or create a new one."""
    existing = await session.execute(
        select(SymbolTemplate).where(SymbolTemplate.name == name)
    )
    found = existing.scalar_one_or_none()
    if found is not None:
        return found

    template = SymbolTemplate(
        category=category,
        name=name,
        display_name=name,
        musicxml_element=musicxml_element,
        is_seed=False,
    )
    session.add(template)
    await session.flush()
    return template
```

- [ ] **Step 3: Verify the import of HTTPException at module top**

Confirm `HTTPException` is already imported at the top of `symbol_library.py` routes file. Remove the inline `from fastapi import HTTPException` inside `upload_variant` (line 107) since it's already at the module level.

- [ ] **Step 4: Restart backend and smoke-test**

Run: `server-restart && sleep 2 && server-logs`

Verify no import errors and server starts cleanly.

---

### Task 2: Delete the capture endpoint and service function

**Files:**
- Modify: `src/backend/mv_hofki/api/routes/symbol_library.py` — remove `capture_template` route (lines 119-135)
- Modify: `src/backend/mv_hofki/services/symbol_library.py` — remove `capture_template` function (lines 180-288)
- Modify: `src/backend/mv_hofki/schemas/symbol_template.py` — remove `TemplateCaptureRequest` (lines 24-49)
- Modify: `src/backend/mv_hofki/api/routes/symbol_library.py` — remove `TemplateCaptureRequest` from import (line 15)

- [ ] **Step 1: Remove the route**

In `src/backend/mv_hofki/api/routes/symbol_library.py`, delete the entire `capture_template` endpoint (the `@router.post("/templates/capture", ...)` block, lines 119-135).

Remove `TemplateCaptureRequest` from the import on line 15.

- [ ] **Step 2: Remove the service function**

In `src/backend/mv_hofki/services/symbol_library.py`, delete the entire `capture_template` function (lines 180-288).

- [ ] **Step 3: Remove the schema**

In `src/backend/mv_hofki/schemas/symbol_template.py`, delete the `TemplateCaptureRequest` class (lines 24-49).

- [ ] **Step 4: Verify no remaining references**

Run: `grep -r "capture_template\|TemplateCaptureRequest\|templates/capture" src/backend/`

Expected: no matches (or only this plan file).

- [ ] **Step 5: Restart and verify**

Run: `server-restart && sleep 2 && server-logs`

---

### Task 3: Add a helper endpoint for scan-region line spacing lookup

The capture flow needs `source_line_spacing` which was previously determined server-side from detected staves. The frontend needs a way to get this value. The `ScanCanvas` already has staves data as a prop — check if `line_spacing` is included.

**Files:**
- Check: `src/backend/mv_hofki/schemas/detected_staff.py` — verify `line_spacing` is in the response schema

- [ ] **Step 1: Check if staves API already returns line_spacing**

Read `src/backend/mv_hofki/schemas/detected_staff.py` and verify `line_spacing` is a field on the read schema. If it is, no backend work needed — the frontend already has this data via the staves prop passed to ScanCanvas.

If `line_spacing` is NOT in the schema, add it.

- [ ] **Step 2: Verify staves data flows to ScanCanvas**

In `ScanEditorPage.vue`, staves are fetched at line 63 and passed as `:staves="staves"` to `ScanCanvas` (line 448). In `ScanCanvas.vue`, `findStaffForY` already uses `staff.line_spacing` (line 266). Confirm this field is populated from the API response.

---

### Task 4: Update ScanEditorPage to crop on canvas and upload via FormData

This is the main frontend change. Instead of sending coordinates to `/templates/capture`, the frontend will:
1. Draw the selected region onto a canvas (applying threshold from adjustments)
2. Export as PNG blob
3. Upload via FormData to the existing upload endpoint

**Files:**
- Modify: `src/frontend/src/pages/ScanEditorPage.vue` — rewrite `saveCapturedTemplate()` (lines 214-245)

- [ ] **Step 1: Add a helper to get the currently displayed image element**

The `ScanCanvas` component renders the scan image. We need to extract pixels from it. Add a ref and expose method on ScanCanvas, OR — simpler — load the image URL in `saveCapturedTemplate` the same way SymbolLibraryPage does (create an Image, draw to canvas, extract region).

In `ScanEditorPage.vue`, find the `saveCapturedTemplate` function and replace it entirely with:

```javascript
async function saveCapturedTemplate() {
  if (!captureBox.value) return;
  const isNew = captureForm.value.template_id === null;
  if (isNew && !captureForm.value.name.trim()) return;

  const box = captureBox.value;

  // Determine source_line_spacing from staves data
  const captureCenter = box.y + box.height / 2;
  let sourceLineSpacing = 0;
  for (const staff of staves.value) {
    if (staff.y_top <= captureCenter && captureCenter <= staff.y_bottom) {
      sourceLineSpacing = staff.line_spacing;
      break;
    }
  }
  if (sourceLineSpacing <= 0 && staves.value.length > 0) {
    sourceLineSpacing = staves.value[0].line_spacing;
  }
  if (sourceLineSpacing <= 5) {
    alert("Linienabstand konnte nicht ermittelt werden oder ist zu niedrig.");
    return;
  }

  // Load the scan image and crop the selected region onto a canvas
  const BASE = (import.meta.env.VITE_BASE_PATH || "").replace(/\/$/, "");
  const imagePath = scan.value.image_path.replace(/^data\/scans\//, "");
  const img = new Image();
  img.crossOrigin = "anonymous";

  const blob = await new Promise((resolve, reject) => {
    img.onload = () => {
      const canvas = document.createElement("canvas");
      canvas.width = box.width;
      canvas.height = box.height;
      const ctx = canvas.getContext("2d");
      ctx.drawImage(img, box.x, box.y, box.width, box.height, 0, 0, box.width, box.height);

      // Apply threshold if set in adjustments
      if (adjustments.value.threshold != null) {
        const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
        const d = imageData.data;
        const t = adjustments.value.threshold;
        for (let i = 0; i < d.length; i += 4) {
          const gray = 0.299 * d[i] + 0.587 * d[i + 1] + 0.114 * d[i + 2];
          const val = gray > t ? 255 : 0;
          d[i] = d[i + 1] = d[i + 2] = val;
        }
        ctx.putImageData(imageData, 0, 0);
      }

      canvas.toBlob((b) => (b ? resolve(b) : reject(new Error("Canvas export failed"))), "image/png");
    };
    img.onerror = () => reject(new Error("Bild konnte nicht geladen werden"));
    img.src = `${BASE}/scans/${imagePath}`;
  });

  // Build FormData and upload
  const formData = new FormData();
  formData.append("file", blob, "captured.png");
  formData.append("source_line_spacing", String(sourceLineSpacing));
  formData.append("source", "user_capture");
  formData.append("height_in_lines", String(captureForm.value.height_in_lines));

  let url;
  if (isNew) {
    url = `${BASE}/api/v1/scanner/library/templates/upload-new`;
    formData.append("name", captureForm.value.name.trim());
    formData.append("category", captureForm.value.category);
    if (captureForm.value.musicxml_element) {
      formData.append("musicxml_element", captureForm.value.musicxml_element);
    }
  } else {
    url = `${BASE}/api/v1/scanner/library/templates/${captureForm.value.template_id}/variants/upload`;
  }

  const resp = await fetch(url, { method: "POST", body: formData });
  if (!resp.ok) {
    const text = await resp.text();
    alert(`Fehler beim Speichern: ${text}`);
    return;
  }

  showCaptureDialog.value = false;
  captureMode.value = false;
  captureForm.value = {
    template_id: null,
    name: "",
    category: "note",
    musicxml_element: "",
    height_in_lines: 4.0,
  };
  const data = await get("/scanner/library/templates?limit=200");
  libraryTemplates.value = data.items || [];
}
```

- [ ] **Step 2: Verify build**

Run: `frontend-logs`

Check for no compilation errors.

- [ ] **Step 3: Commit**

```bash
git add src/backend/mv_hofki/api/routes/symbol_library.py \
        src/backend/mv_hofki/services/symbol_library.py \
        src/backend/mv_hofki/schemas/symbol_template.py \
        src/frontend/src/pages/ScanEditorPage.vue
git commit -m "refactor: merge capture endpoint into variant upload — single source of truth

Remove /templates/capture endpoint. Frontend now crops scan region on
canvas and uploads via /templates/{id}/variants/upload (existing template)
or /templates/upload-new (new template). All variant creation flows
through save_rendered_variant() with auto-crop."
```

---

### Task 5: Update SymbolLibraryPage to pass source and height_in_lines

Now that the upload endpoint accepts `source` and `height_in_lines`, the library page's crop-and-upload flow should also pass these for consistency (they were previously hardcoded in the route handler).

**Files:**
- Modify: `src/frontend/src/pages/SymbolLibraryPage.vue:289-309`

- [ ] **Step 1: No change needed**

The existing `applyCrop()` in SymbolLibraryPage already sends `file` and `source_line_spacing` via FormData. The `source` defaults to `"cropped"` in the endpoint, and `height_in_lines` defaults to `None` — both correct for the library crop flow. No change required.

---

### Task 6: Verify end-to-end

- [ ] **Step 1: Verify backend starts**

Run: `server-restart && sleep 2 && server-logs`

- [ ] **Step 2: Verify frontend builds**

Run: `frontend-logs`

- [ ] **Step 3: Run linting**

Run: `pre-commit run --all-files`

Fix any issues.

- [ ] **Step 4: Run backend tests**

Run: `python -m pytest tests/backend/ -v`

Fix any failures related to the removed endpoint or changed signatures.
