# Notenscanner — Sheet Music Digitization Feature

**Date:** 2026-03-24
**Status:** Design approved

## Purpose

Digitize degraded sheet music from the Musikverein's archive by scanning printed (typeset) parts, detecting musical symbols, matching them against a growing reference library, and exporting to MusicXML (with optional LilyPond conversion). The system assists the user rather than attempting full automation — uncertain detections are flagged for human review and correction.

## Context

The Musikverein owns many pieces of sheet music that exist only as photocopies of photocopies. Each reproduction degrades the quality further. This feature preserves them by converting the visual notation into a structured digital format that can be re-rendered cleanly. Initial focus is on single-page Austrian march music (single-voice brass band parts in treble or bass clef), but the data model supports multi-page parts for future use.

## Architecture: Hybrid (Backend Processing + Frontend Interaction)

All image processing, symbol detection, and matching runs on the **Python backend** (OpenCV, NumPy). The **Vue 3 frontend** handles upload, image preview/adjustment, interactive review/correction, and export download.

**Rationale:** Python's image processing ecosystem (OpenCV, scikit-image) is vastly superior to browser-based alternatives. The frontend provides the interactive correction workflow. Basic adjustments (brightness, contrast) happen client-side for instant feedback before backend processing.

## Processing Pipeline

The backend uses a modular pipeline of processing stages. Each stage implements a common interface (`ProcessingStage` ABC) with `name`, `process(input) → output`, and `validate(input) → bool`. Stages live in `src/backend/mv_hofki/services/scanner/stages/`.

### Stages

1. **PreprocessStage** (always on) — Adaptive thresholding (handles uneven contrast from degraded copies), deskew via Hough line transform, noise removal via morphological operations (opening/closing).

2. **StaveDetectionStage** (always on) — Horizontal projection to find staff lines (5 evenly-spaced peaks = 1 staff). Outputs line positions (y-coordinates), staff regions (bounding boxes), and line spacing (fundamental sizing unit).

3. **StaffRemovalStage** (optional) — Removes staff lines to isolate symbols, preserving vertical components (stems, barlines) at intersection points. May corrupt already degraded data, so it is toggleable per scan. Segmentation works on either original or staff-removed image.

4. **SegmentationStage** (always on) — Connected component analysis within each staff region. Groups nearby components that form single symbols (head + stem + flag). Extracts bounding boxes ordered left-to-right. Determines vertical position relative to staff lines.

5. **MatchingStage** (always on) — Normalizes each snippet to standard size (relative to staff line spacing). Computes feature vectors using Hu moments (shape-based, rotation/scale invariant), aspect ratio and fill density (pre-filter), and normalized cross-correlation against library variants. Ranks matches by weighted similarity. Confidence thresholds: ≥85% auto-accept (green), 40–84% needs review (orange), <40% no match (red).

### Pipeline Properties

- Per-scan configuration stored in `pipeline_config_json` — user can toggle stages and adjust parameters.
- Stages are swappable — multiple implementations can be registered per stage type.
- Intermediate results are saved — re-run from any point without starting over.
- Original scan is always preserved (non-destructive).

## Data Model

### ScanProject
Groups all parts of one musical piece.

| Field | Type | Description |
|-------|------|-------------|
| id | PK | |
| name | string | Piece name, e.g. "Böhmischer Traum" |
| composer | string, nullable | |
| notes | text, nullable | |
| created_at | datetime | |
| updated_at | datetime | |

### ScanPart
One instrument part within a project.

| Field | Type | Description |
|-------|------|-------------|
| id | PK | |
| project_id | FK → ScanProject | |
| part_name | string | e.g. "1. Flügelhorn" |
| part_order | integer | Display/export ordering |
| clef_hint | string, nullable | treble \| bass — user override for detection |
| created_at | datetime | |

### SheetMusicScan
One scanned page of an instrument part.

| Field | Type | Description |
|-------|------|-------------|
| id | PK | |
| part_id | FK → ScanPart | |
| page_number | integer | |
| original_filename | string | |
| image_path | string | Stored original |
| processed_image_path | string, nullable | After preprocessing |
| status | enum | uploaded \| processing \| review \| completed |
| adjustments_json | JSON | {brightness, contrast, rotation} |
| pipeline_config_json | JSON | Enabled/disabled stages + parameters |
| created_at | datetime | |
| updated_at | datetime | |

### DetectedStaff
One staff found on a scanned page.

| Field | Type | Description |
|-------|------|-------------|
| id | PK | |
| scan_id | FK → SheetMusicScan | |
| staff_index | integer | Order on page (0, 1, 2…) |
| y_top | integer | Top of bounding region |
| y_bottom | integer | Bottom of bounding region |
| line_positions_json | JSON | Array of 5 y-coordinates |
| line_spacing | float | Pixels between lines |
| clef | string, nullable | Detected or user-set |
| key_signature | string, nullable | |
| time_signature | string, nullable | |

### DetectedSymbol
One detected symbol region on a staff.

| Field | Type | Description |
|-------|------|-------------|
| id | PK | |
| staff_id | FK → DetectedStaff | |
| x, y, width, height | integer | Bounding box |
| snippet_path | string | Extracted image region |
| position_on_staff | integer | Line/space index |
| sequence_order | integer | Left-to-right position |
| matched_symbol_id | FK → SymbolTemplate, nullable | Best match |
| confidence | float | 0.0–1.0 |
| user_verified | boolean | |
| user_corrected_symbol_id | FK → SymbolTemplate, nullable | If user chose differently |

### SymbolTemplate
One logical musical symbol in the library.

| Field | Type | Description |
|-------|------|-------------|
| id | PK | |
| category | enum | note \| rest \| accidental \| clef \| time_sig \| barline \| dynamic \| ornament \| other |
| name | string | e.g. "quarter_note" |
| display_name | string | e.g. "Viertelnote" |
| musicxml_element | text | XML snippet for export |
| lilypond_token | string | e.g. "c4", "r2" |
| is_seed | boolean | true for pre-seeded |
| created_at | datetime | |

### SymbolVariant
One visual appearance of a symbol template.

| Field | Type | Description |
|-------|------|-------------|
| id | PK | |
| template_id | FK → SymbolTemplate | |
| image_path | string | Reference image |
| source | enum | seed \| user_correction \| auto_clustered |
| feature_vector_json | JSON | Pre-computed for matching |
| usage_count | integer | Times this variant matched |
| created_at | datetime | |

### Relationships

- ScanProject 1 → N ScanPart
- ScanPart 1 → N SheetMusicScan
- SheetMusicScan 1 → N DetectedStaff
- DetectedStaff 1 → N DetectedSymbol
- SymbolTemplate 1 → N SymbolVariant
- DetectedSymbol N → 1 SymbolTemplate (match + correction)

## Frontend

### Navigation

New top-level menu entry **"Notenscanner"** in the NavBar. All routes under `/notenscanner/`.

### Pages

**`/notenscanner` — Projektliste**
List of scan projects with name, composer, and aggregated status (how many parts, how many completed). Button to create new project.

**`/notenscanner/:id` — Projekt-Detail**
Shows the project's parts grouped with their page scans as thumbnails. Each scan shows its status (uploaded, processing, review, completed). Upload button per part. Export button (MusicXML per part, or all parts as ZIP).

**`/notenscanner/:id/scan/:scanId` — Scan-Editor (Main Workspace)**
The core page with three areas:
1. **Toolbar** — brightness/contrast sliders, rotation, toggle staff removal, "Analyse starten" button, export button.
2. **Image canvas (left, ~75%)** — the scan with detection overlays. Detected staves shown as dashed outlines. Symbol bounding boxes color-coded: green (≥85% confidence, auto-accepted or confirmed), orange (40–84%, needs review), red (<40%, no match). Clicking a symbol selects it.
3. **Symbol panel (right, ~25%)** — shows the selected symbol's extracted snippet, matched template with confidence, ranked alternatives, and buttons to confirm, pick an alternative, or manually assign from the full library.
4. **Status bar** — progress per staff and overall page.

**`/notenscanner/bibliothek` — Symbol-Bibliothek**
Browse all symbol templates, filterable by category. Each template shows its display name, Unicode preview (where possible), and variant count. Clicking a template shows its variants with source labels (seed, user correction, auto-clustered).

### Color Coding

- Green border: high confidence or user-confirmed
- Orange border + tint: low confidence, needs review
- Red border + tint: no match, must be manually assigned

### UI Language

All labels and text in German, consistent with the existing application.

## Symbol Library

### Structure

Two-level: Template (logical meaning) → Variants (visual appearances). This handles the reality that the same musical symbol can look very different across degraded copies (e.g., 4+ visual representations of a quarter rest).

### Pre-seeded Content

~50–70 templates covering:
- **Notes:** whole, half, quarter, eighth, sixteenth (+ dotted variants)
- **Rests:** whole, half, quarter, eighth, sixteenth
- **Accidentals:** sharp, flat, natural, double sharp, double flat
- **Clefs:** treble, bass
- **Time signatures:** common patterns (4/4, 3/4, 2/4, 6/8, C, cut C)
- **Barlines:** single, double, final, repeat start/end
- **Dynamics:** pp, p, mp, mf, f, ff, crescendo, decrescendo
- **Articulations:** staccato, accent, tenuto, fermata
- **Other:** ties, slurs, repeat signs

Each seed template starts with 1 clean reference variant image.

### Feedback Loop

When a user corrects a match (selects a different template than what the system proposed), the detected snippet is automatically added as a new variant of the correct template. Its feature vector is computed and stored for future matching. Over time, the library accumulates real-world degraded variants, improving recognition accuracy.

## Export

### MusicXML

Walk confirmed symbols per staff left-to-right. Determine concrete pitch by mapping `position_on_staff` (line/space index) through the detected clef and key signature (e.g., space 1 in treble clef = F4, line 2 in bass clef = B2). Map each SymbolTemplate to its `musicxml_element`, injecting the computed pitch. Assemble into valid MusicXML per part.

### LilyPond (Optional)

Either convert from MusicXML via `musicxml2ly` (external tool) or generate directly from `lilypond_token` fields. LilyPond produces high-quality rendered PDF output.

### Export Scope

- Per part (one file per instrument)
- Per project (ZIP with all parts)

## Backend File Structure

```
src/backend/mv_hofki/
├── services/scanner/
│   ├── __init__.py
│   ├── pipeline.py          — Pipeline runner, stage orchestration
│   ├── stages/
│   │   ├── __init__.py
│   │   ├── base.py          — ProcessingStage ABC
│   │   ├── preprocess.py    — Binarization, deskew, denoise
│   │   ├── stave_detection.py
│   │   ├── staff_removal.py
│   │   ├── segmentation.py
│   │   └── matching.py
│   ├── export/
│   │   ├── __init__.py
│   │   ├── musicxml.py
│   │   └── lilypond.py
│   └── library/
│       ├── __init__.py
│       └── seed.py          — Pre-seed symbol templates + variants
├── api/routes/
│   ├── scan_projects.py
│   ├── scan_parts.py
│   ├── scans.py
│   ├── scan_processing.py   — Trigger/monitor pipeline
│   └── symbol_library.py
├── models/
│   ├── scan_project.py
│   ├── scan_part.py
│   ├── sheet_music_scan.py
│   ├── detected_staff.py
│   ├── detected_symbol.py
│   ├── symbol_template.py
│   └── symbol_variant.py
└── schemas/
    ├── scan_project.py
    ├── scan_part.py
    ├── sheet_music_scan.py
    ├── detected_staff.py
    ├── detected_symbol.py
    ├── symbol_template.py
    └── symbol_variant.py
```

## Frontend File Structure

```
src/frontend/src/
├── pages/
│   ├── ScanProjectListPage.vue
│   ├── ScanProjectDetailPage.vue
│   ├── ScanEditorPage.vue
│   └── SymbolLibraryPage.vue
├── components/
│   ├── ScanCanvas.vue         — Image display with detection overlays
│   ├── SymbolPanel.vue        — Selected symbol detail + correction UI
│   ├── ImageAdjustBar.vue     — Brightness/contrast/rotation controls
│   └── SymbolCard.vue         — Symbol template card for library view
```

## Python Dependencies

- `opencv-python-headless` — image processing (no GUI needed on server)
- `numpy` — array operations (comes with OpenCV)
- `scikit-image` — optional, additional image analysis utilities

No ML frameworks required. This is classical computer vision + template matching.

## File Storage

Uploaded scans and processing artifacts are stored under `data/scans/`:
- Original uploads: `data/scans/{project_id}/{part_id}/{scan_id}/original.{ext}`
- Preprocessed images: `data/scans/{project_id}/{part_id}/{scan_id}/processed.png`
- Extracted symbol snippets: `data/scans/{project_id}/{part_id}/{scan_id}/snippets/{symbol_id}.png`
- Symbol library variant images: `data/symbol_library/{template_id}/{variant_id}.png`

Accepted upload formats: TIFF, PNG, JPEG. Maximum file size: 50 MB (high-DPI scans can be large).

## Processing Progress

Backend processing uses polling. The frontend polls `GET /api/v1/scanner/scans/{id}/status` while status is `processing`. The response includes the current stage name and a progress percentage. This keeps things simple — SSE/WebSocket can be added later if needed.

## Testing Strategy

- **Backend unit tests:** Each pipeline stage tested independently with fixture images (clean + degraded samples)
- **Backend integration tests:** Full pipeline run on sample scans, verify staff/symbol counts
- **Frontend component tests:** Vitest for page components
- **E2E tests:** Upload → process → review → export workflow via Playwright

## Out of Scope (for now)

- Multi-voice / polyphonic parts
- Conductor scores / full scores
- Handwritten manuscripts
- Real-time camera capture (phone scanning)
- ML-based recognition (may be added later as an alternative MatchingStage)
- Transposition between parts
