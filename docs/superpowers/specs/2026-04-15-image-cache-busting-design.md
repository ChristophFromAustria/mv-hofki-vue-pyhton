# Image Cache-Busting Design

## Problem

Generated images (`processed.png`, LilyPond PNGs) are served as static files via
FastAPI `StaticFiles` without cache headers. When the analysis pipeline overwrites
`processed.png` on disk, the browser may serve the cached old version.

Cache-busting via `?t=Date.now()` exists only inside `ScanEditorPage` after
in-editor analysis/preview. When mass analysis runs from `ScanProjectListPage` →
`BatchAnalysisModal`, no cache-busting happens. The user navigates to the editor
afterwards and sees stale images.

## Approach

Use the existing `updated_at` database column (auto-updated via `onupdate=func.now()`)
as a data-driven cache-bust parameter. The API already returns `updated_at` in
`SheetMusicScanRead`. The frontend appends `?v={updated_at}` to mutable image URLs.

No database migration needed.

## Changes

### ScanCanvas.vue

- New prop: `cacheVersion` (String, optional, default `null`)
- `resolveImageUrl(path, cacheBust)` gets optional second parameter:
  - Returns `${BASE}/scans/${relative}?v=${cacheBust}` when cacheBust is provided
  - Returns `${BASE}/scans/${relative}` otherwise
- `activeImageUrl` computed: passes `cacheVersion` only for `processedImagePath`,
  not for `imagePath` (originals are immutable)

### ScanEditorPage.vue

- Passes `scan.updated_at` as `cacheVersion` prop to `ScanCanvas`
- Removes manual `?t=Date.now()` cache-busting (line ~240 after analysis, line ~299
  after preview) — replaced by data-driven mechanism
- After analysis completion (SSE done) and after preview response: refreshes scan
  data from API (`fetchScanData()`) to get the current `updated_at`. This is
  consistent with the existing pattern of reloading symbols/staves after analysis.

### LilypondModal.vue

- `assetUrl()` receives a cache-bust parameter
- The timestamp is passed as a prop from `ScanEditorPage`
- Applied to all LilyPond PNG paths returned by `/generate-lilypond`

### No changes needed

- **ScanProjectListPage.vue / BatchAnalysisModal.vue** — the problem is solved at
  navigation time: when the user opens the editor, `fetchScanData()` fetches fresh
  data with current `updated_at`
- **SymbolLibraryPage.vue** — existing static `_cacheBust = Date.now()` is sufficient
  (low risk, optional future cleanup)
- **Backend** — no changes needed, `updated_at` with `onupdate=func.now()` already
  works correctly

## Edge Cases

### After in-editor analysis/preview

The pipeline overwrites `processed.png` but the editor still holds the old
`updated_at`. Solution: call `fetchScanData()` after SSE completion / preview
response to get the fresh timestamp. This is already the natural pattern since
symbols, staves, and measures are reloaded too.

### Race condition during batch analysis

If the user navigates to the editor while batch analysis is running for that scan,
`fetchScanData()` returns the current state. If analysis finishes afterwards and the
user refreshes, they get the new `updated_at`. No special handling needed.

### LilyPond PNGs

These paths are not stored in the DB but returned directly by the
`/generate-lilypond` endpoint. Cache-bust is applied in the frontend at response
time: append `?v=Date.now()` when receiving the paths. This mirrors the current
approach but makes it explicit.
