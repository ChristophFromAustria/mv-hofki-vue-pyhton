# Template Manager & Capture Dialog Improvements

**Date:** 2026-03-25
**Status:** Approved

## Summary

Enhance the existing SymbolLibraryPage into a full template manager with editing/deletion capabilities, and change the capture dialog to use a grouped dropdown instead of free-text name input so captured symbols become variants of existing templates.

## Changes

### 1. Template Manager Page (SymbolLibraryPage)

**Current state:** Display-only grid of templates with category filter tabs. Not linked from any UI.

**Changes:**

- Add "Vorlagen verwalten" button on `ScanProjectListPage` linking to `/notenscanner/bibliothek`
- Each `SymbolCard` gains an edit button opening an edit/detail view
- Edit view contains:
  - Editable fields: `display_name`, `musicxml_element`, `lilypond_token`
  - Save and cancel buttons
  - Delete template button with confirmation dialog
  - Variants section: grid of variant images, each with a delete button (with confirmation)
- Variant images served via existing `/scans/` static path (already configured)

### 2. Capture Dialog (ScanEditorPage)

**Current state:** Free-text `name` input, category dropdown, musicxml textarea, height_in_lines number input.

**Changes:**

- Replace `name` text input with a grouped `<select>` dropdown:
  - First option: "-- Neue Vorlage erstellen --"
  - Then `<optgroup>` per category (Note, Pause, Vorzeichen, etc.) listing existing templates by `display_name`
- When an existing template is selected:
  - Category auto-fills and becomes read-only
  - MusicXML auto-fills from template (still editable — only applies to the capture request, doesn't change the template)
  - On submit: captured image becomes a new variant of the selected template
- When "Neue Vorlage erstellen" is selected:
  - Show a text input for the new template name
  - Category and other fields remain editable
  - On submit: creates new template + first variant (current behavior)

### 3. Backend API Changes

**New endpoints:**

| Method | Path | Purpose |
|--------|------|---------|
| `PUT` | `/api/v1/scanner/library/templates/{template_id}` | Update display_name, musicxml_element, lilypond_token |
| `DELETE` | `/api/v1/scanner/library/templates/{template_id}` | Delete template, all variants, and variant image files |
| `DELETE` | `/api/v1/scanner/library/templates/{template_id}/variants/{variant_id}` | Delete single variant and its image file |

**Modified endpoint:**

- `POST /api/v1/scanner/library/templates/capture` — accept optional `template_id` field. When present, skip template creation and add variant to the existing template. When absent, require `name` and create a new template (current behavior).

**Schema changes:**

- `TemplateCaptureRequest`: add optional `template_id: int | None = None`, make `name` optional (required only when `template_id` is None)
- New `SymbolTemplateUpdate` schema: `display_name`, `musicxml_element`, `lilypond_token` (all optional)

### 4. File Structure

No new pages or components needed beyond what exists:

- **Enhanced:** `SymbolLibraryPage.vue` — add edit/delete functionality
- **Enhanced:** `SymbolCard.vue` — add edit button and expanded detail view
- **Enhanced:** `ScanEditorPage.vue` — modify capture dialog
- **Enhanced:** `symbol_library.py` (routes) — add PUT/DELETE endpoints
- **Enhanced:** `symbol_template.py` (schemas) — add update schema, modify capture schema

### 5. Deletion Behavior

- Deleting a template also deletes all its variants and their image files from disk
- Deleting a variant deletes the image file from disk
- Seed templates (`is_seed=True`) can be deleted — they were just initial data, not sacred
- Confirmation dialogs required for all deletions
