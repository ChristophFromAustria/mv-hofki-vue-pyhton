# Image Cache-Busting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate stale cached images after analysis/preview by using the existing `updated_at` timestamp as a data-driven cache-bust parameter.

**Architecture:** The API already returns `updated_at` in `SheetMusicScanRead`. The frontend appends `?v={updated_at}` to mutable image URLs (processed images, LilyPond PNGs). Original images remain without cache-bust since they never change. Manual `?t=Date.now()` cache-busting is removed.

**Tech Stack:** Vue 3 (Composition API), FastAPI, existing `updated_at` DB column

---

### File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `src/frontend/src/components/ScanCanvas.vue` | Modify (lines 4-43) | Add `cacheVersion` prop, update `resolveImageUrl` and `activeImageUrl` |
| `src/frontend/src/pages/ScanEditorPage.vue` | Modify (lines 214-308, 649-672, 783-789) | Pass `cacheVersion`, remove manual cache-busting, add cache-bust to LilyPond |
| `src/frontend/src/components/LilypondModal.vue` | Modify (lines 4-28) | Add `cacheVersion` prop, apply to `assetUrl` |

---

### Task 1: Add `cacheVersion` prop to ScanCanvas and use it for processed images

**Files:**
- Modify: `src/frontend/src/components/ScanCanvas.vue:4-43`

- [ ] **Step 1: Add `cacheVersion` prop**

In `ScanCanvas.vue`, add the new prop after line 25 (`viewMode`):

```js
  cacheVersion: { type: String, default: null },
```

- [ ] **Step 2: Update `resolveImageUrl` to accept optional cache-bust parameter**

Replace the existing `resolveImageUrl` function (lines 32-36):

```js
function resolveImageUrl(path, cacheBust = null) {
  if (!path) return null;
  const relative = path.replace(/^data\/scans\//, "");
  const url = `${BASE}/scans/${relative}`;
  return cacheBust ? `${url}?v=${cacheBust}` : url;
}
```

- [ ] **Step 3: Update `activeImageUrl` to pass `cacheVersion` only for processed images**

Replace the existing `activeImageUrl` computed (lines 38-43):

```js
const activeImageUrl = computed(() => {
  if (props.viewMode === "binary" && props.processedImagePath) {
    return resolveImageUrl(props.processedImagePath, props.cacheVersion);
  }
  return resolveImageUrl(props.imagePath);
});
```

- [ ] **Step 4: Verify the dev server shows no errors**

Run: `frontend-logs`

Expected: No compilation errors. The app should work as before (no `cacheVersion` is passed yet, so it defaults to `null` and no query param is appended).

- [ ] **Step 5: Commit**

```bash
git add src/frontend/src/components/ScanCanvas.vue
git commit -m "feat: add cacheVersion prop to ScanCanvas for data-driven cache-busting"
```

---

### Task 2: Pass `updated_at` from ScanEditorPage to ScanCanvas and remove manual cache-busting

**Files:**
- Modify: `src/frontend/src/pages/ScanEditorPage.vue:214-308, 649-672`

- [ ] **Step 1: Add `cacheVersion` computed property**

Add after the `avgLineThickness` computed (after line 72):

```js
const cacheVersion = computed(() => scan.value?.updated_at ?? null);
```

- [ ] **Step 2: Pass `cacheVersion` to ScanCanvas in the template**

In the `<ScanCanvas>` usage (line 649-672), add the prop after `:view-mode="viewMode"`:

```html
            :cache-version="cacheVersion"
```

- [ ] **Step 3: Remove manual cache-busting in `onAnalysisDone`**

In `onAnalysisDone()` (lines 238-244), replace:

```js
      const foundScan = scansData.find((s) => String(s.id) === String(props.scanId));
      if (foundScan) {
        // Cache-bust the processed image so the browser loads the fresh version
        if (foundScan.processed_image_path) {
          foundScan.processed_image_path += "?t=" + Date.now();
        }
        scan.value = foundScan;
        break;
      }
```

with:

```js
      const foundScan = scansData.find((s) => String(s.id) === String(props.scanId));
      if (foundScan) {
        scan.value = foundScan;
        break;
      }
```

- [ ] **Step 4: Remove manual cache-busting in `startPreview`**

In `startPreview()` (lines 299-302), replace:

```js
    if (result.processed_image_path && scan.value) {
      // Append cache-buster so the browser fetches the freshly generated image
      scan.value.processed_image_path = result.processed_image_path + "?t=" + Date.now();
    }
```

with:

```js
    if (result.processed_image_path && scan.value) {
      scan.value.processed_image_path = result.processed_image_path;
      scan.value.updated_at = new Date().toISOString();
    }
```

The preview endpoint doesn't return `updated_at`, so we set it to the current time. This updates the `cacheVersion` computed, which triggers a fresh image load.

- [ ] **Step 5: Verify the dev server shows no errors**

Run: `frontend-logs`

Expected: No compilation errors.

- [ ] **Step 6: Commit**

```bash
git add src/frontend/src/pages/ScanEditorPage.vue
git commit -m "feat: use updated_at for cache-busting, remove manual ?t= timestamps"
```

---

### Task 3: Add cache-busting to LilypondModal

**Files:**
- Modify: `src/frontend/src/components/LilypondModal.vue:4-28`
- Modify: `src/frontend/src/pages/ScanEditorPage.vue:783-789`

- [ ] **Step 1: Add `cacheVersion` prop to LilypondModal**

In `LilypondModal.vue`, add the prop after `pngPaths` (line 8):

```js
  cacheVersion: { type: String, default: null },
```

- [ ] **Step 2: Update `assetUrl` to accept cache-bust parameter**

Replace the existing `assetUrl` function (lines 19-23):

```js
function assetUrl(path, cacheBust = null) {
  if (!path) return null;
  const relative = path.replace(/^data\/scans\//, "");
  const url = `${BASE}/scans/${relative}`;
  return cacheBust ? `${url}?v=${cacheBust}` : url;
}
```

- [ ] **Step 3: Update `previewUrl` to use cache-busting**

Replace the existing `previewUrl` computed (lines 25-28):

```js
const previewUrl = computed(() => {
  if (!props.pngPaths.length) return null;
  return assetUrl(props.pngPaths[0], props.cacheVersion);
});
```

- [ ] **Step 4: Pass `cacheVersion` from ScanEditorPage to LilypondModal**

In `ScanEditorPage.vue`, update the `<LilypondModal>` usage (lines 783-789). Add the prop after `:png-paths`:

```html
      :cache-version="cacheVersion"
```

- [ ] **Step 5: Verify the dev server shows no errors**

Run: `frontend-logs`

Expected: No compilation errors.

- [ ] **Step 6: Commit**

```bash
git add src/frontend/src/components/LilypondModal.vue src/frontend/src/pages/ScanEditorPage.vue
git commit -m "feat: add cache-busting to LilyPond preview images"
```

---

### Task 4: Manual verification

- [ ] **Step 1: Test mass analysis cache-busting**

1. Open the app in the browser
2. Navigate to a scan that has already been analyzed (has a processed image)
3. Note the current processed image
4. Go back to the Scan-Projekte page
5. Run Massenanalyse for that project
6. Navigate back to the scan editor
7. Verify the processed image is the freshly generated version (not cached)

- [ ] **Step 2: Test in-editor analysis**

1. Open a scan in the editor
2. Run analysis (Analyse starten)
3. After completion, verify the processed image updates without manual refresh

- [ ] **Step 3: Test preview**

1. Open a scan in the editor
2. Adjust preprocessing settings (brightness, contrast, threshold)
3. Click preview
4. Verify the binary view shows the fresh preview image

- [ ] **Step 4: Test LilyPond generation**

1. Open a scan that has been analyzed
2. Click LilyPond generation
3. Verify the PNG preview loads correctly
4. Generate again and verify the preview updates

- [ ] **Step 5: Run pre-commit checks**

```bash
pre-commit run --all-files
```

Expected: All checks pass.

- [ ] **Step 6: Final commit (if pre-commit required fixes)**

```bash
git add -u
git commit -m "style: apply pre-commit formatting fixes"
```
