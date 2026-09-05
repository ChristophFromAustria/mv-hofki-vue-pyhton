# Frontend Quality Audit — MV Hofkirchen Inventar

**Date:** 2026-09-04 · **Scope:** `src/frontend/src` (45 files, ~11,300 lines) · **Method:** full read of every Vue/CSS/JS file plus grep-based systemic checks and computed contrast ratios. No fixes were applied.

**Design context:** No `.impeccable.md` exists and no design context was supplied. The audit uses what the code makes evident: an internal, German-language inventory, loan, invoice and sheet-music-scanning tool for the Musikverein Hofkirchen brass band. Run `/impeccable:teach-impeccable` before any design-direction work.

---

## 1. Anti-Patterns Verdict

**Verdict: FAIL on distinctiveness, PASS on the worst tells.**

Shown to a designer, this reads as "Tailwind slate admin template, probably scaffolded". It is competent and consistent, but nothing about it says brass band, sheet music, or Hofkirchen. Specific tells found:

| Tell | Evidence |
|---|---|
| Tailwind default palette, untinted | Every token in `style.css:11-56` is a Tailwind slate/sky/red/green hex (`#0f172a`, `#1e293b`, `#64748b`, `#e2e8f0`, `#7dd3fc`, `#dc2626`). Neutrals carry no brand hue. |
| Cyan-on-dark accent | Dark-mode primary is `#7dd3fc` (Tailwind sky-300) on `#0f172a` — the canonical AI dark palette. |
| Pure white ground | `--color-bg: #ffffff`. |
| Hero-metric dashboard | `DashboardPage.vue` renders up to 23 identical `StatCard`s (2rem number, small muted label), all centred, in `grid-4`/`grid-3`. |
| Thick coloured border on one side | `StatCard.vue:21` `border-left: 4px solid var(--color-primary)`; also `.field-modified` and active nav links. |
| Everything centred on the landing page | `DashboardPage.vue:31` `text-align: center` on the h1; every card centred. |
| Rounded rectangles + generic drop shadow | `.card`, `.instrument-card`, `.dialog`, `.project-card`, `.symbol-card` — same 8px radius and `0 4px 12px` shadow on every surface. |
| Modals as default container | 13 hand-rolled modal shells; the symbol-library editor opens a lightbox modal on top of an edit modal. |
| Gradient as decoration | `BatchAnalysisModal.vue:247` progress fill becomes `linear-gradient(primary → danger)` when any scan fails. |
| Redundant copy | `LoanListPage.vue:85-89` button "Neue Ausleihe" opens a card headed "Neue Ausleihe". Dashboard h1 shows the raw e-mail address. |

Not present (good): gradient text, glassmorphism/backdrop-filter, bounce or elastic easing, nested cards, monospace-as-vibe (mono is used only for code/log output), Inter/Roboto (DM Sans is loaded properly).

For an internal club tool a quiet utilitarian look is a legitimate choice. The distinctiveness gap is the lowest-priority problem in this report. The accessibility and robustness gaps below are not.

---

## 2. Executive Summary

Raw findings from three area passes plus systemic checks: ~170. Consolidated into distinct issues:

| Severity | Count |
|---|---|
| Critical | 5 |
| High | 17 |
| Medium | 21 |
| Low | 12 |

**Overall quality score: 4.5 / 10.** Solid token system, sensible information architecture, consistent German copy, and every table scrolls horizontally. But the app is unusable by keyboard, unreadable in dark mode wherever a primary button appears, ships a 5.5 MB invisible image on every page, and has three confirmed functional bugs.

**Top five issues**

1. **Zero keyboard support.** The entire frontend contains no `aria-*`, no `role`, no `tabindex`, and no `keydown` handler. Navigation to every detail page, the settings menu, every symbol on the scan canvas, every modal, and file upload are mouse-only.
2. **Dark mode primary buttons are unreadable.** `.btn-primary` and four sibling patterns set `color: white` on `--color-primary`, which is `#7dd3fc` in dark mode: **1.67:1** contrast. 42 usages in 22 files. Dark mode is the default for users whose OS prefers dark.
3. **5.5 MB logo on every page load.** `style.css:75-83` paints a 1945×1945 px PNG as a `body::before` watermark at `opacity: 0` in light mode. It is downloaded regardless and never seen by light-mode users.
4. **Every dialog is a bare `<div>`.** 13 modal shells with no `role="dialog"`, no focus move, no focus trap, no Escape, no focus return. Includes the delete-confirmation dialog.
5. **Confirmed functional bugs:** time-signature templates created in the UI never appear in their filter tab (`time_sig` vs `time_signature`); the invoice modal and loan form allow duplicate submissions on double-click; a failed analysis leaves the editor spinning with "Analyse läuft im Hintergrund".

**Recommended next steps:** build one `BaseModal` on native `<dialog>`, add a `--color-on-primary` token, delete the watermark or replace it with a small WebP, make the 20 clickable non-buttons real buttons or links, then fix the three functional bugs. That is roughly two days of work and clears every Critical.

---

## 3. Detailed Findings

Line numbers refer to each file as of commit `8ac384f`.

### 3.1 Critical

**C1 · Keyboard users cannot operate the application** · Accessibility · WCAG 2.1.1, 4.1.2
Clickable `div`/`span`/`tr`/`img`/`h2`/`h3`/`<g>` elements carry `@click` but no `tabindex`, `role`, or key handler. Verified sites:
- `components/NavBar.vue:67` settings submenu trigger is a `<span>` — the five settings pages are unreachable by keyboard
- `components/DataTable.vue:34, 68` rows and mobile cards (used by ItemList, MusicianList)
- `pages/ItemListPage.vue:176` instrument card · `pages/InvoiceListPage.vue:136` and `pages/ItemDetailPage.vue:396` invoice rows
- `components/ImageGallery.vue:50, 69, 101` placeholder, main image, thumbnails
- `pages/ScanProjectDetailPage.vue:217` scan thumbnail, `:253` drop zone with `display:none` file input
- `components/SymbolCard.vue:33` whole card · `pages/SymbolLibraryPage.vue:457` variant image
- `components/ScannerConfigModal.vue:193, 226` and `pages/ScannerConfigPage.vue:188, 223` headings used as accordion toggles
- `components/ScanCanvas.vue:607, 649` symbol and text-region bounding boxes
**Impact:** Keyboard, switch and screen-reader users cannot open any item, musician, invoice, scan, or symbol. **Fix:** Render navigation as `<RouterLink>`, actions as `<button>`; for SVG groups add `tabindex="0" role="button"` plus Enter/Space handlers and a `:focus-visible` stroke. Suggested command: `/harden`.

**C2 · All 13 dialogs lack dialog semantics, focus management and Escape** · Accessibility · WCAG 4.1.2, 2.4.3, 1.3.1
`ConfirmDialog.vue:12`, `ItemFormModal.vue:202`, `InvoiceModal.vue:148`, `ImageGallery.vue:113`, `LilypondModal.vue:53`, `BatchAnalysisModal.vue:125`, `AnalysisLogModal.vue:120`, `ScannerConfigModal.vue:175`, `SymbolLibraryPage.vue:373, 409, 506`, `ScanProjectListPage.vue:214`, `ScanEditorPage.vue:744, 795`. Each is `<div class="overlay|modal-backdrop" @click.self="close"><div class="dialog|modal">`. Eight files redefine their own `.modal-backdrop`/`.modal` instead of the global `.overlay`/`.dialog`.
**Impact:** Focus stays behind the overlay; Tab wanders through the hidden page; screen readers are not told a dialog opened; Escape does nothing. The delete-confirmation dialog is one of them. **Fix:** One `BaseModal.vue` built on native `<dialog>` + `showModal()` (gives role, focus trap, Escape, top layer for free). Suggested command: `/extract` then `/harden`.

**C3 · Primary buttons unreadable in dark mode** · Theming / Contrast · WCAG 1.4.3
`style.css:124` `.btn-primary { color: white }` and `:418` `.view-toggle button.active`, `ScanEditorPage.vue:1096` `.btn-active`, `ItemFormModal.vue:434` and `InvoiceModal.vue:358` `.currency-picker button.active`, `LilypondModal.vue:184` and `SymbolLibraryPage.vue:607` `.tab-btn.active`. Dark `--color-primary` is `#7dd3fc`. Computed contrast white on `#7dd3fc`: **1.67:1** (needs 4.5:1). 42 `btn-primary` usages in 22 files.
**Impact:** Every primary action, active toggle, and active tab is a pale-blue blob with invisible text for dark-mode users. **Fix:** Add `--color-on-primary` (`#ffffff` light, `#0f172a` dark) and use it in all seven places. Suggested command: `/normalize`.

**C4 · 5.5 MB invisible watermark on every page** · Performance
`style.css:75-83` `body::before { background: url("../public/mv-hofkirchen-logo.png") … 40vmin; opacity: 0 }`; `[data-theme="dark"] body::before { opacity: 0.04 }`. The PNG is 1945×1945 px, 5,557,380 bytes, and is bundled into `dist/assets/`.
**Impact:** Every first visit downloads 5.5 MB (roughly 50× the entire JS bundle) for an image that light-mode users never see and dark-mode users see at 4% opacity. On a phone over LTE that is 3–8 seconds of bandwidth. **Fix:** Drop the watermark, or ship a 400 px WebP (≈15 KB) and load it only under `[data-theme="dark"]`. Suggested command: `/optimize`.

**C5 · Canvas capture and crop are mouse-only** · Accessibility / Responsive · WCAG 2.1.1, 2.5.7
`components/ScanCanvas.vue:413-415` (`@mousedown/@mousemove/@mouseup`) and `pages/SymbolLibraryPage.vue:513-515`. No pointer/touch events, no numeric x/y/w/h fallback.
**Impact:** "Vorlage erfassen" and variant cropping do not work on tablets or touch laptops, which is where a scanning workflow is most likely used. **Fix:** Switch to pointer events with `touch-action: none`; add numeric inputs in the capture dialog. Suggested command: `/adapt`.

### 3.2 High

**H1 · Form labels not associated with inputs** · WCAG 1.3.1, 3.3.2, 4.1.2
42 `<label>` elements with no `for` (ItemFormModal ×21, InvoiceModal ×7, MusicianFormPage ×8, ItemDetailPage ×3, LoanListPage ×3); ~20 placeholder-only inputs (InvoiceListPage date/select filters, AccessSettingsPage e-mail, all settings inline edits, SearchBar); four `<input type="range">` in `ImageAdjustBar.vue:60-105` with the label as a sibling; `config/Field*.vue` wrap a `<button>` inside the `<label>`. In `ItemFormModal.vue:338-370` and `InvoiceModal.vue:237-269` the label's first labelable descendant is the currency pencil button, so the cost input has no name at all. `InvoiceListPage.vue:104-115` `type="date"` placeholders never render, leaving two unlabeled identical date fields.
**Fix:** A `FormField.vue` wiring `id/for/aria-describedby/aria-invalid`; `aria-label` on filter controls. Commands: `/extract`, `/harden`.

**H2 · ~40 icon- or glyph-only buttons without accessible names** · WCAG 4.1.2
Hamburger `NavBar.vue:39` (no name, no `aria-expanded`), theme toggle `:48` (`title` only, English), "X"/"OK" ×22 across the four settings pages and AccessSettingsPage/LoanListPage, gallery ‹ › × `ImageGallery.vue:70-121`, ↺ × `ScanProjectDetailPage.vue:236-246`, ◀▶ `ScanEditorPage.vue:677`, − + `ImageAdjustBar.vue:131`, ✕ closes in LilypondModal/ScannerConfigModal, reset ↺ in `config/Field*.vue`. "X" means both Abbrechen and Löschen in the same rows.
**Fix:** `aria-label` everywhere; replace X/OK with words. Command: `/clarify`.

**H3 · Confidence and status colours fail contrast and are colour-only** · WCAG 1.4.3, 1.4.1
`SymbolPanel.vue:213-223` and `TextRegionPanel.vue:13-19` text in `#22c55e` (2.3:1 on white) and `#f97316` (2.8:1). `ScanCanvas.vue:206-211` box strokes green/orange/red with no legend or dash pattern. `ScanProjectDetailPage.vue:473-491` badges white on `#f97316`/`#22c55e` at 0.65rem. `SymbolCard.vue:92-105` pastel chips at 3.1:1 and bright in dark mode. `SymbolPanel` and `TextRegionPanel` use different confidence thresholds and scales (0.85/0.4 on 0–1 vs 80/50 on 0–100).
**Fix:** `--color-success-*`/`--color-warning-*` tokens with dark variants, one `ConfidenceBadge.vue`, legend + dash patterns on the canvas. Commands: `/colorize`, `/normalize`.

**H4 · Duplicate submissions on double-click** · Robustness
`InvoiceModal.vue:102-116` sets `saving` then emits synchronously and resets in `finally`, so Speichern is re-enabled before the parent's POST finishes. `LoanListPage.vue:53-64` `createLoan()` has no saving guard and never disables the button.
**Impact:** Two invoices or two loans for the same item. **Fix:** Parent owns `saving` or handler returns a promise; disable while pending. Command: `/harden`.

**H5 · Failures are silent or leave a blank page** · Robustness
`ItemDetailPage.vue:207` and `MusicianDetailPage.vue:31` are `v-if="item"` with no loading/error branch — a 404 or network error is a permanently blank page. `DashboardPage.vue:21-25` swallows to `console.error` and renders nothing. 17 unguarded `await`s in the Notenscanner files (`ScanEditorPage` verify/correct/capture, `ScanProjectDetailPage` add/delete/reset, `ScanProjectListPage` fetch/create/delete, `SymbolLibraryPage` create/save/delete/crop) and ~20 more in inventory pages (`ItemDetailPage` reload/upload/return, `LoanListPage`, all settings `load()`). `ScanProjectListPage.vue:143-146` shows "Noch keine Scan-Projekte vorhanden" when the API is down.
**Fix:** `useApiError()` composable + inline error banner with retry; the `renderError` banner in `SymbolLibraryPage.vue:172-193` is the right model. Command: `/harden`.

**H6 · Raw `fetch()` bypasses the API base path** · Robustness
`ItemDetailPage.vue:61, 156, 171, 181` call `fetch("/api/v1/…")` directly instead of `api.js`, ignoring `VITE_BASE_PATH`, and never check `response.ok`.
**Impact:** Image and invoice-file uploads break under the documented sub-path deployment; failed uploads are silent. **Fix:** Add `upload(path, formData)` to `lib/api.js`.

**H7 · Time-signature templates vanish after creation** · Functional bug
`SymbolLibraryPage.vue:388` and `ScanEditorPage.vue:822` write `category = "time_sig"`; the filter tab at `SymbolLibraryPage.vue:15` is `time_signature`. `SymbolCard.vue:23-24` maps both labels, hiding the mismatch.
**Impact:** Every Taktart template created in the UI is missing from the "Taktarten" tab; users think creation failed. **Fix:** One key, matching the backend enum, in all four places.

**H8 · Image loading defeats caching and lazy loading** · Performance
`SymbolLibraryPage.vue:156-159` `const _cacheBust = Date.now()` appended to every variant URL — every page load refetches every thumbnail and lightbox image, contrary to the `updated_at` scheme used elsewhere. `ScanProjectDetailPage.vue:224` renders full-resolution scan originals into 120×90 boxes. Zero `loading="lazy"` in the codebase; four `<img>` without `alt` (`ItemListPage.vue:178`, `ImageGallery.vue:101`, `SymbolLibraryPage.vue:457`, `ScanProjectDetailPage.vue:224`).
**Fix:** `updated_at` cache key, backend thumbnail size, `loading="lazy" decoding="async" width height`. Command: `/optimize`.

**H9 · The most prominent CTA on the editor is a dead end** · UX
`ScanEditorPage.vue:733-739` the only `btn-primary` in the status bar, "Exportieren", calls `alert('MusicXML-Export noch nicht implementiert')`; same in `ScanProjectDetailPage.vue:162-164, 200`.
**Fix:** Remove, or render `disabled` with an explanation. Command: `/distill`.

**H10 · Navigation drawer: hidden at every width, still in tab order** · Accessibility / UX · WCAG 2.4.3, 2.4.7
`NavBar.vue:123-145` `.links` is `position: fixed; transform: translateX(-100%)` with no `min-width` media query, so on a 1200 px desktop nine sections sit behind a hamburger. The drawer stays in the DOM and tab order while off-screen (no `inert`/`aria-hidden`); no focus move on open, no Escape. Hamburger has no `aria-expanded`/`aria-controls`.
**Fix:** `:inert="!menuOpen"`, focus management, `aria-expanded`; show links inline at ≥1024 px or commit to the drawer with a visible close. Command: `/adapt`.

**H11 · `<button>` nested inside `<RouterLink>`** · WCAG 4.1.2, HTML conformance
`ScanProjectListPage.vue:163-208` renders the delete button inside the card link.
**Impact:** Screen readers read the whole card including "Löschen" as one link; Enter on the button can trigger both. **Fix:** Link only the title; delete button as a sibling.

**H12 · Hard-coded developer-only link in production nav** · Robustness / Security
`NavBar.vue:80` `<a href="//localhost:7681" target="_blank">Terminal</a>` with no `rel="noopener"`.
**Impact:** Dead link for every user except the developer's own machine. **Fix:** Gate behind a dev flag or `VITE_TERMINAL_URL`; add `rel="noopener noreferrer"`.

**H13 · CSS classes and tokens used but never defined** · Theming / Bug
`.btn-secondary` — 13 usages, 0 definitions (buttons fall back to default `.btn`). `.alert-danger` — `AccessSettingsPage.vue:70`, unstyled. `--color-danger-light` — `SymbolLibraryPage.vue:781` falls back to `#3a1c1c` (dark maroon) in light mode, 3.2:1 with red text. `.btn-active` — defined only inside `ScanEditorPage.vue` scoped styles, so `FilterDropdown.vue:108` has no visible open state.
**Fix:** Define in `style.css` or remove. Command: `/normalize`.

**H14 · Analysis failure leaves the editor in a false "running" state; SSE connections leak** · Robustness
`AnalysisLogModal.vue:62-78` sets `status = "error"` but only ever emits `done` or `close`; `ScanEditorPage.vue:279-285` resets `processing` only on `done` and sets "Analyse läuft im Hintergrund…" on close. Neither `AnalysisLogModal` nor `BatchAnalysisModal` closes its `EventSource` on unmount.
**Fix:** Emit `error`; `onBeforeUnmount(() => eventSource?.close())`.

**H15 · Threshold slider runs a synchronous full-image pixel loop per tick** · Performance
`ScanCanvas.vue:122-147` iterates every pixel (≈8.7 M iterations on a 300-dpi page) in a watcher; `ImageAdjustBar.vue:50` emits on every `input` tick with no debounce. `onMouseMove` (:288-316) writes reactive refs on every move, re-rendering hundreds of SVG nodes; `parseLinePositions()` JSON-parses in the template up to six times per staff per render (:435-455); `ScannerConfigModal.vue:191` calls `getGroupTree()` in the template.
**Fix:** Debounce/rAF, precomputed grayscale buffer, `computed` maps. Command: `/optimize`.

**H16 · Selected symbol indicator is invisible** · WCAG 1.4.11
`ScanCanvas.vue:631, 674` selection ring is `stroke="#fff" stroke-width="1"` over white paper.
**Fix:** Two-tone ring or translucent fill.

**H17 · 22 native `alert()` and one `confirm()`** · UX / Accessibility
All four settings pages ×2, `ItemFormModal:194`, `ItemDetailPage:121, 190, 195`, `MusicianDetailPage:24`, `MusicianFormPage:61`, `LoanListPage:62`, `SymbolLibraryPage:304`, `ScanProjectDetailPage:124, 163`, `ScanEditorPage:365, 374, 401, 736`.
**Impact:** Blocking OS dialogs, no dark mode, inconsistent with `ConfirmDialog` used everywhere else. **Fix:** Inline error banner / toast. Command: `/harden`.

### 3.3 Medium

**M1 · Search race conditions** — `ItemListPage.vue:108-115`, `MusicianListPage.vue:44-51`, `InvoiceListPage.vue:48-60`: debounced `load()` assigns results unconditionally; out-of-order responses win. `InvoiceListPage` date watchers fire per keystroke. Fix: AbortController or sequence number.

**M2 · No live regions** (WCAG 4.1.3) — `LoadingSpinner.vue` has no `role="status"`; `BatchAnalysisModal.vue:138` progress bar is a bare div (no `role="progressbar"`); `AnalysisLogModal` status, `ScanEditorPage.vue:716` statusMessage, `ScannerConfigPage.vue:146` success/error have no `aria-live`. Success auto-dismisses after 3 s.

**M3 · Motion** — `transition: all` in `style.css:495`, `NavBar.vue:154`, `StatCard.vue:22`, `SymbolLibraryPage.vue:595`; no `prefers-reduced-motion` anywhere; infinite spinners. Command: `/animate`.

**M4 · Touch targets** (WCAG 2.5.8) — `.btn-sm` 36 px; `.btn-xs` ≈19×18 px (below the 24 px minimum) in `ScanProjectDetailPage.vue:521`, `SymbolLibraryPage`; `config/Field*.vue` reset ≈14×18 px; `.currency-edit-btn` ≈14×22 px; view-toggle ≈30 px; filter rows ≈25 px; gallery close 32 px; editor panel toggle 20 px wide. Command: `/adapt`.

**M5 · Responsive coverage** — Three media queries in the whole app (`style.css` ×2, `App.vue` ×1). `ScanEditorPage.vue:876-916` uses `width: 100vw; margin-left: calc(-50vw + 50%)` (horizontal scrollbar whenever a vertical one exists) and hard-codes a 60 px header; toolbar has no wrap; no breakpoint for the side panel. Scoped `.page-header` in three scanner pages drops the global `flex-wrap`. `FilterDropdown.vue:192` fixed 240 px can overflow at 320 px. `grid-4` collapses straight from 4 to 1 column. Command: `/adapt`.

**M6 · Dashboard** — up to 23 identical centred stat cards; h1 is the raw e-mail address (`DashboardPage.vue:31-34`), wraps badly and destroys heading navigation; value precedes label in DOM (`StatCard.vue:10-13`). Commands: `/arrange`, `/critique`.

**M7 · Input focus ring effectively invisible** (WCAG 2.4.7) — `style.css:177-183` `outline: none` + 3 px ring at 8% alpha.

**M8 · Unformatted dates and money** — raw ISO dates in `ItemDetailPage`, `MusicianDetailPage`, `LoanListPage`, `InvoiceListPage`, `InvoiceModal`; raw `1234.5 €` in rows while the footer uses `toLocaleString("de-AT")`. `InvoiceModal.vue:22` uses UTC `toISOString()` for "today". Fix: `lib/format.js`.

**M9 · 128 colour literals outside `style.css`** — 40 in `ScanCanvas` (canvas chrome `#1a1a1a`, 15 overlay hues), 19 in `SymbolLibraryPage`, 14 hard-coded success greens (`#16a34a`/`#22c55e`) across 10 files, `#1a1a1a` viewer background copied three times. Missing tokens: on-primary, success, warning, info badge, canvas background, focus ring. Command: `/normalize`.

**M10 · Heading hierarchy** — `ScanEditorPage` has no h1 (first heading is h3); h1→h3 jumps in `ItemListPage`, `LoanListPage`, dialogs; `ConfirmDialog` hard-codes h3.

**M11 · Modal misuse** — `SymbolLibraryPage` edit modal (3 fields, render actions, variants grid, delete) opens a second full-screen lightbox modal on top; `ItemFormModal.vue:202` closes a 20-field form on accidental backdrop click without dirty check; `ScannerConfigModal.vue:88-93` commits overrides on backdrop click with no Abbrechen, and "Auf Global zurücksetzen" is unconfirmed. Command: `/distill`.

**M12 · N+1 and duplicated lookups** — `ScanEditorPage.vue:110-116, 184-194, 237-245` fetch scans for every part sequentially to find one scan, three copies, on every Vorschau/Analyse. `ItemDetailPage.vue:47-56` four sequential awaits per reload. `ScanEditorPage.vue:152-159` decodes the full scan a second time just for dimensions.

**M13 · Validation errors not associated** (WCAG 3.3.1) — `.form-error` spans in five forms lack `aria-describedby`/`aria-invalid`; required fields marked only by "*" with no `aria-required`.

**M14 · Data-model rough edges** — `ItemFormModal.vue:38, 252` construction year defaults to the current year with no empty option (unknown years saved as 2026); `MusicianFormPage.vue:100` postal code is `type="number"` (loses leading zeros); dropdowns hard-code `limit=200` (`ItemDetailPage.vue:81`, `LoanListPage.vue:33-36`); `InvoiceModal.vue:8` requires an `instrumentId` prop nobody passes (console warning per open); `ItemDetailPage.vue:238, 281` renders Hersteller twice; `LoanListPage.vue:94` item dropdown offers already-loaned items.

**M15 · Misleading labels** — "Abbrechen" in both SSE modals only closes the client stream while the server job continues; `ConfirmDialog.vue:18` always says "Löschen" even under the title "Zugriff entfernen" (`AccessSettingsPage.vue:117`). Command: `/clarify`.

**M16 · Scanner config page** — `ScannerConfigPage.vue:17-27, 153-260` opens as a grid of identical collapsed card headers with zero fields visible; no local dirty tracking, no unsaved-changes guard. Commands: `/arrange`, `/harden`.

**M17 · Version badge fails contrast** — `App.vue:33-41` muted colour at 50% opacity, 11 px: 1.96:1.

**M18 · Route transition delay** — `App.vue:13` `mode="out-in"` adds 150 ms before the next page mounts and starts fetching.

**M19 · UX copy inconsistencies** — "Review" (English) among German statuses, "Schliessen" vs "Schließen", "Rendere...", "Light Mode"/"Dark Mode", "Konfig. *", "Kleidung anlegen"; empty states differ in punctuation and none offers a CTA except `ScanProjectListPage`. Command: `/clarify`.

**M20 · LilyPond preview** — `LilypondModal.vue:29-32` shows only `pngPaths[0]` with no pager; the dashed crop rectangle (`:81-98`) has no caption.

**M21 · Canvas legibility** — `ScanCanvas.vue:466-643` SVG labels use fixed image-unit font sizes (2.5–7 px at fit zoom); Ctrl+wheel is hijacked for canvas zoom with no documentation or key alternative (`:65-70`).

### 3.4 Low

- **L1 · Duplication** — four settings pages are ~95% identical (`InstrumentType`, `ClothingType`, `SheetMusicGenre`, `CurrencyListPage`); modal shell ×8 files; currency picker + CSS byte-identical in `ItemFormModal`/`InvoiceModal`; pagination ×3; `config/Field*.vue` CSS ×3; timestamp formatting ×4 in `AnalysisLogModal`; loan-return controls ×2; loan status badge ×3. Command: `/extract`.
- **L2 · ~70 inline `style=""` attributes** for spacing/alignment (`ItemDetailPage` alone ≈25), bypassing tokens and responsive rules.
- **L3 · Dead code** — `categories.js` `hasStorageLocation`, `apiCategory`, `formatDisplayNr` unused; `ScanEditorPage.vue:544` empty `onUnmounted`; `await new Promise(r => setTimeout(r, 50))` to wait for child mount (`ScanEditorPage.vue:206`, `ScanProjectListPage.vue:88`) instead of `nextTick`.
- **L4 · `target="_blank"` without `rel="noopener"`** — `NavBar.vue:80`, `LilypondModal.vue:123`, `InvoiceModal.vue:196`.
- **L5 · Hard-coded `border-radius: 8px` / `rgba(0,0,0,…)` shadows** instead of `--radius`/`--color-shadow` — `DataTable.vue:105`, `ImageGallery.vue:132-244`, `FilterDropdown.vue:194`, `SymbolCard.vue:62`, `ScanProjectDetailPage.vue:447`.
- **L6 · Logo `alt="MVH"` duplicates adjacent text** (`NavBar.vue:44`); no `width/height`.
- **L7 · Unicode glyph icons** (☀ ☾ ▾ ↺ ◀ ▶ ✕) render inconsistently across OS fonts; use inline SVG with `aria-hidden`.
- **L8 · Empty `<th>` for action columns** in six tables; use a visually-hidden "Aktionen". No `.sr-only` utility exists.
- **L9 · Unguarded `localStorage`** in `ItemListPage.vue:22-26, 123` and `NavBar.vue:17-26` (throws in locked-down browsers).
- **L10 · Missing `autocomplete`/`type="tel"`** on musician form fields (WCAG 1.3.5).
- **L11 · `router.back()` for Abbrechen** (`MusicianFormPage.vue:123`) can leave the app.
- **L12 · Spinner track** `--color-border` on white is 1.23:1 (acceptable, indicator arc passes).

---

## 4. Patterns & Systemic Issues

1. **No accessibility layer exists at all.** 0 `aria-*`, 0 `role`, 0 `tabindex`, 0 `keydown` across 45 files. This is not scattered omissions; it is an absent concern. One `useDismissable()` composable, one `BaseModal`, one `FormField`, and a rule "clickable → `<button>` or `<a>`" fix most of it.
2. **Dark mode was designed at token level but never tested at component level.** White-on-primary (7 sites), pastel chips, hard-coded success greens, `#3a1c1c` fallback, `rgba(255,255,255,0.8)` gallery buttons.
3. **Errors go to `console.error` or `alert()`.** ~37 unguarded awaits, 23 native dialogs, 3 blank-page-on-failure views. The inline banner pattern already exists in `SymbolLibraryPage` and `AccessSettingsPage`.
4. **Each modal author started from scratch.** 8 files × own backdrop CSS, 13 dialogs, 0 with semantics.
5. **Missing tokens force literals.** Success, warning, on-primary, canvas background, focus ring — 128 literals outside `style.css`.
6. **Responsive is global-only.** Three media queries total; component CSS assumes desktop.
7. **Copy-paste over extraction.** Four near-identical pages, duplicated pickers, pagination, SSE handling.

---

## 5. Positive Findings

- Complete token set with a full dark-theme override and `color-scheme` (`style.css:11-56`); nearly all component CSS uses tokens.
- Global `:focus-visible` outlines for buttons and links; hamburger and theme toggle are 44 px; theme respects `prefers-color-scheme` and persists.
- Drawer and spinner animate `transform`/`opacity` only; no gradient text, glassmorphism, or bounce easing anywhere.
- Every data table is wrapped in `overflow-x: auto`; `DataTable` has loading, empty state, listener cleanup and a mobile card fallback.
- Status badges always pair colour with text ("Ausgeliehen", "Verfügbar") — never colour-only.
- Deletes go through `ConfirmDialog` in 8 of 9 places; Cancel is placed first.
- Forms submit via `<form @submit.prevent>` so Enter works; `type="button"` on non-submit buttons; `saving` state disables submit in `ItemFormModal`/`ItemDetailPage`.
- Search is debounced in all three list pages; `Promise.all` used in dashboard, item detail, loans, scan detail.
- `SymbolLibraryPage` inline `renderError` banner and `AccessSettingsPage` error state are the model for the rest of the app.
- Cache-busting via `updated_at` (recent commits) rather than timestamps — except the one `Date.now()` in `SymbolLibraryPage`.
- Scan canvas uses an SVG `viewBox` in image coordinates so zoom is one style change; original `ImageData` cached once; `AnalysisLogModal` emits `done` so the canvas keeps its zoom.
- Domain-aware defaults: currency €, owner "MV Hofkirchen", project category "Marschbuch", `localeCompare(…, "de")`, correct German typography (–, —, ·) and pluralisation.
- DM Sans loaded with `preconnect` + `display=swap` and a real fallback stack; `lang="de"` set.

---

## 6. Recommendations by Priority

**Immediate (clears all Criticals, ~2 days)**
1. `BaseModal.vue` on native `<dialog>`; migrate 13 dialogs (C2).
2. `--color-on-primary` token; fix 7 white-on-primary sites (C3).
3. Remove or shrink the watermark PNG (C4).
4. Convert 20 clickable non-buttons to `<button>`/`<RouterLink>`; `tabindex`+key handlers on canvas `<g>` (C1).
5. Pointer events + numeric fallback for capture/crop (C5).

**Short-term (this sprint)**
6. Fix `time_sig`/`time_signature`, duplicate-submit guards, AnalysisLogModal `error` emit, SSE unmount cleanup (H4, H7, H14).
7. `FormField.vue` + `aria-label` sweep for labels and icon buttons (H1, H2).
8. `useApiError()` + banner; replace 23 native dialogs; loading/error states on detail pages (H5, H17).
9. `upload()` in `api.js` (H6); `updated_at` cache key, lazy thumbnails (H8).
10. Define or remove `.btn-secondary`, `.alert-danger`, `--color-danger-light`, `.btn-active` (H13); remove dead "Exportieren" (H9); gate Terminal link (H12).
11. Success/warning tokens + `ConfidenceBadge`; canvas legend and two-tone selection (H3, H16).

**Medium-term (next sprint)**
12. Debounce threshold pipeline, computed canvas helpers, resolve N+1 (H15, M12).
13. `prefers-reduced-motion`, drop `transition: all`, live regions (M2, M3).
14. Responsive pass on ScanEditorPage, scanner headers, touch targets ≥24 px (M4, M5).
15. `lib/format.js` for dates/money; focus-ring visibility; error association (M7, M8, M13).
16. Dashboard restructure; ScannerConfigPage layout + dirty tracking (M6, M16).

**Long-term**
17. Extract `LookupListPage`, `MoneyInput`, `Pagination`, `LoanReturnControls` (L1).
18. Replace inline styles with utilities; remove dead code (L2, L3).
19. Run `/impeccable:teach-impeccable`, then decide whether the app should carry any brand identity beyond the logo (tinted neutrals, a display face, a non-Tailwind primary).

---

## 7. Suggested Commands

| Command | Addresses |
|---|---|
| `/harden` | C1, C2, H4, H5, H14, H17, M1, M13, M14, M16 — keyboard, dialogs, error handling, robustness (~12 issues) |
| `/normalize` | C3, H13, M9, L5 — tokens, undefined classes, colour literals (~4 issues, 140+ sites) |
| `/optimize` | C4, H8, H15, M12, M18 — watermark, images, canvas performance, N+1 (~5 issues) |
| `/extract` | C2, H1, L1 — BaseModal, FormField, LookupListPage, MoneyInput, Pagination |
| `/adapt` | C5, H10, M4, M5 — touch/pointer, navigation, breakpoints, target sizes |
| `/clarify` | H2, M15, M19 — button names, misleading labels, copy consistency |
| `/colorize` | H3 — success/warning palette, confidence encoding with legend |
| `/animate` | M3 — reduced motion, specific transition properties |
| `/distill` | H9, M11 — dead CTA, modal-in-modal, backdrop-close hazards |
| `/arrange` | M6, M16 — dashboard hierarchy, config page layout |
| `/critique` | Section 1 — after `/impeccable:teach-impeccable` establishes direction |
