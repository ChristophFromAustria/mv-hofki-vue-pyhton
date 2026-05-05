# Music Notation Rendering for Symbol Templates

**Date:** 2026-03-25
**Status:** Approved

## Summary

Add backend rendering of MusicXML and LilyPond notation to generate digital symbol variant images. Two new endpoints render notation code from a template's fields into PNG images and save them as variants.

## Backend

### Dependencies

- `verovio` (PyPI) — MusicXML → SVG rendering via C++ engine
- `lilypond` (PyPI) — LilyPond CLI binary, bundled for pip
- `cairosvg` (PyPI) — SVG → PNG conversion for Verovio output

### New endpoints

**`POST /api/v1/scanner/library/templates/{template_id}/render-musicxml`**

1. Loads template, reads `musicxml_element` field (must be non-empty, else 400)
2. Wraps the fragment in a minimal valid MusicXML `<score-partwise>` document
3. Calls `verovio.toolkit.renderToSVG()` to produce SVG
4. Converts SVG → PNG via `cairosvg.svg2png()`
5. Saves PNG to `data/symbol_library/{template_id}/{uuid}.png`
6. Creates `SymbolVariant` record with `source="rendered_musicxml"`
7. Returns updated `SymbolTemplateRead`

**`POST /api/v1/scanner/library/templates/{template_id}/render-lilypond`**

1. Loads template, reads `lilypond_token` field (must be non-empty, else 400)
2. Wraps token in a minimal LilyPond file: `\version "2.24.0" { <token> }`
3. Writes to a temp `.ly` file
4. Shells out to `lilypond --png -dresolution=300 -o <tmpdir> <file>.ly`
5. Reads the output PNG
6. Saves PNG to `data/symbol_library/{template_id}/{uuid}.png`
7. Creates `SymbolVariant` record with `source="rendered_lilypond"`
8. Returns updated `SymbolTemplateRead`

### Rendering service

New file `src/backend/mv_hofki/services/notation_renderer.py` with two functions:

- `render_musicxml(fragment: str) -> bytes` — returns PNG bytes
- `render_lilypond(token: str) -> bytes` — returns PNG bytes

The route handler in `symbol_library.py` calls these, saves the file, creates the variant — same pattern as `capture_template`.

## Frontend

### Edit modal changes (SymbolLibraryPage.vue)

Add two buttons in the edit modal, below the MusicXML and LilyPond fields respectively:

- "MusicXML rendern" — calls `POST .../render-musicxml`, disabled when `musicxml_element` is empty, shows loading state
- "LilyPond rendern" — calls `POST .../render-lilypond`, disabled when `lilypond_token` is empty, shows loading state

After successful render, refresh the variants list to show the new image.

## File structure

- **New:** `src/backend/mv_hofki/services/notation_renderer.py` — rendering logic
- **Modify:** `src/backend/mv_hofki/api/routes/symbol_library.py` — add two routes
- **Modify:** `src/frontend/src/pages/SymbolLibraryPage.vue` — add render buttons
- **Modify:** `requirements.txt` or `pyproject.toml` — add verovio, lilypond, cairosvg
