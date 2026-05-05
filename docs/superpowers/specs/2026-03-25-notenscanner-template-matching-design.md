# Notenscanner Template Matching Redesign

**Date:** 2026-03-25
**Status:** Design approved
**Supersedes:** Parts of `2026-03-24-notenscanner-design.md` (segmentation + matching stages)

## Purpose

Replace the automated connected-component segmentation and Hu-moment matching with a **manual sample-based template matching** approach. The user captures symbol templates by drawing boxes on the sheet music during review, specifying what each symbol represents (MusicXML) and its height in staff-line units. The system then uses sliding-window template matching to find occurrences across the scan.

## Motivation

The automated approach produces too many false positives. Degraded sheet music has inconsistent quality that defeats generic pattern detection. By letting the user define exactly what a symbol looks like on their specific scans, the matching becomes more reliable and the library grows naturally through use.

## Changes Overview

1. **Monochrome filter** — replace adaptive thresholding with user-controlled global threshold
2. **Template capture** — draw-a-box workflow in the scan editor to capture symbol templates
3. **Sliding window matching** — replace segmentation + Hu-moment matching with `cv2.matchTemplate`
4. **Zoom support** — zoom in/out on the scan canvas for precise box drawing

## 1. Monochrome Filter

The `PreprocessStage` currently uses `cv2.adaptiveThreshold`. This is replaced by a user-controlled global threshold.

**Frontend:** A threshold slider (0–255, default 128) added to `ImageAdjustBar`. The Canvas preview applies the threshold client-side for instant visual feedback using Canvas pixel manipulation.

**Backend:** `PreprocessStage` reads `ctx.config["threshold"]`. If present, applies `cv2.threshold(gray, value, 255, THRESH_BINARY)`. If absent, falls back to adaptive thresholding for backwards compatibility. The threshold value is stored in `SheetMusicScan.adjustments_json` alongside brightness/contrast/rotation and sent to the backend when "Analyse starten" is clicked.

## 2. Template Capture

### Workflow

Integrated into the scan editor's review process:

1. User clicks "Vorlage erfassen" button in the toolbar — enters capture mode
2. Cursor changes to crosshair on the scan canvas
3. User draws a rectangle (click-drag) around a musical symbol
4. On mouse-up, a capture dialog opens showing the cropped region with fields:
   - **Name** — display name (e.g., "Viertelnote Hals aufwärts")
   - **Kategorie** — dropdown: note, rest, accidental, clef, time_sig, barline, dynamic, ornament, other
   - **MusicXML** — text/textarea for the MusicXML element representation
   - **Höhe in Notenlinien** — number input (e.g., 4 for a stemmed note, 1 for a notehead alone)
5. On save: creates a `SymbolTemplate` (or links to existing) + `SymbolVariant` with the cropped image and height metadata

### Cropping

The crop is taken from the **monochrome-filtered image** (same threshold the user sees) so the template matches what the sliding window will compare against. The crop coordinates are in natural image pixel space (zoom-independent).

### Data Model Changes

`SymbolVariant` gets one new field:

| Field | Type | Description |
|-------|------|-------------|
| height_in_lines | float, nullable | User-declared height in staff-line units, used for scaling during matching |

## 3. Sliding Window Matching

### New Stage: `TemplateMatchingStage`

Replaces the old `SegmentationStage` + `MatchingStage` in the pipeline. The old stages remain in the codebase but are disabled in the default pipeline config.

### Algorithm

For each detected staff:
1. Extract the staff region from the binarized image (y_top to y_bottom)
2. For each `SymbolVariant` that has `height_in_lines` set:
   - Compute target pixel height: `height_in_lines * staff.line_spacing`
   - Scale the variant image to that height, preserving aspect ratio
   - Binarize the scaled template with the same global threshold
   - Run `cv2.matchTemplate(region, scaled_template, cv2.TM_CCOEFF_NORMED)`
   - Collect all positions where match score > configurable confidence threshold (default 0.6, stored in pipeline config)
3. All matches across all templates are collected as `DetectedSymbol` entries with: position, dimensions, matched_symbol_id, confidence
4. No automatic deduplication — all matches above threshold are returned for user review and cleanup

### Pipeline Configuration

The default pipeline becomes:
1. `PreprocessStage` (with user threshold)
2. `StaveDetectionStage` (unchanged)
3. `TemplateMatchingStage` (new)

Staff removal and the old segmentation/matching stages are still available but disabled by default. The pipeline config in `pipeline_config_json` controls which stages run.

### Performance

`cv2.matchTemplate` uses FFT-based correlation internally. Staff regions are narrow (~200–300px height for high-res scans). Even with 50+ scaled templates, processing takes seconds per page.

## 4. Zoom Support

The `ScanCanvas` component gets zoom functionality:

- **Mouse wheel** zooms in/out in steps: 25%, 50%, 75%, 100%, 150%, 200%, 300%
- **Default: 100%** (natural image size)
- **Zoom indicator** displayed in the corner showing current level
- Image container scrolls when zoomed beyond viewport
- All SVG overlays (stave lines, symbol boxes, drawing rectangle) scale correctly via SVG `viewBox` — coordinates are always in image-pixel space
- Box drawing in capture mode works at any zoom level — mouse events are translated from screen coordinates to image coordinates

## 5. Backend API Changes

### New Endpoint

`POST /api/v1/scanner/library/templates/capture` — creates a template + variant from a captured region:

```json
Request:
{
  "scan_id": 1,
  "x": 100,
  "y": 200,
  "width": 30,
  "height": 80,
  "name": "Viertelnote Hals aufwärts",
  "category": "note",
  "musicxml_element": "<note>...</note>",
  "height_in_lines": 4.0
}

Response: SymbolTemplateRead (with nested variant)
```

The backend crops the region from the scan's binarized image (using the scan's stored threshold), saves it as a variant image file, and creates the template + variant records.

### Modified Endpoint

`POST /api/v1/scanner/scans/{scan_id}/process` — the pipeline now uses `TemplateMatchingStage` by default. Loads all variants with `height_in_lines` set for matching.

## 6. File Changes Summary

### Backend — Modify
- `services/scanner/stages/preprocess.py` — add global threshold mode
- `services/sheet_music_scan.py` — update `run_pipeline` to use new stage, pass threshold config
- `models/symbol_variant.py` — add `height_in_lines` column
- `services/symbol_library.py` — add `capture_template` function
- `api/routes/symbol_library.py` — add capture endpoint
- `api/routes/scan_processing.py` — update pipeline construction

### Backend — Create
- `services/scanner/stages/template_matching.py` — new sliding window matching stage

### Frontend — Modify
- `components/ImageAdjustBar.vue` — add threshold slider
- `components/ScanCanvas.vue` — add zoom support + box drawing mode
- `pages/ScanEditorPage.vue` — add capture mode toggle, capture dialog, zoom controls

### Database
- Alembic migration: add `height_in_lines` column to `symbol_variants`

## 7. Out of Scope

- Automatic deduplication/non-maximum suppression (user reviews all matches)
- LilyPond token in capture dialog (can be added later)
- Batch template import/export
- Template editing after capture (delete and re-capture instead)
