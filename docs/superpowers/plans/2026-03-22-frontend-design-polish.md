# Frontend Design Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve the MV Hofkirchen Inventar frontend's usability and visual quality for daily internal use — better readability, clearer feedback, smoother navigation — without adding complexity or slowing workflows.

**Architecture:** CSS-first approach. All changes are in the frontend (`src/frontend/`). No backend changes. No new dependencies (Google Fonts loaded via `<link>` in `index.html`). Changes touch: global styles, index.html (font loading), NavBar, DataTable, StatCard, ConfirmDialog, App.vue (transitions), and a new LoadingSpinner component.

**Tech Stack:** Vue 3, CSS custom properties, Google Fonts, Vue `<Transition>` component

**Design direction:** Refined utilitarian — clean, legible, warm. Not flashy. Optimized for someone scanning inventory tables 50 times a day. Key choices:
- **Font:** DM Sans (geometric, highly legible at small sizes, distinctive but professional)
- **Color:** Warm navy primary instead of generic blue, with an amber accent for actionable elements
- **Tables:** Alternating rows, sticky headers, tighter spacing for density
- **Feedback:** Spinner component, button loading states, modal transitions

---

## File Structure

### New files
- `src/frontend/src/components/LoadingSpinner.vue` — Reusable CSS-only spinner component

### Modified files
- `src/frontend/index.html` — Add Google Fonts `<link>` for DM Sans
- `src/frontend/src/style.css` — Updated color palette, typography, table styles, transitions, focus rings
- `src/frontend/src/App.vue` — Add Vue `<Transition>` wrapper around `<RouterView>`
- `src/frontend/src/components/NavBar.vue` — Active route highlighting, refined spacing
- `src/frontend/src/components/DataTable.vue` — Alternating row colors, use LoadingSpinner
- `src/frontend/src/components/StatCard.vue` — Subtle left-border accent, hover refinement
- `src/frontend/src/components/ConfirmDialog.vue` — Fade transition on overlay
- `src/frontend/src/components/SearchBar.vue` — Search icon prefix
- `src/frontend/src/pages/DashboardPage.vue` — Use LoadingSpinner

---

## Task 1: Load Google Fonts (DM Sans)

**Files:**
- Modify: `src/frontend/index.html`

- [ ] **Step 1: Add Google Fonts link to index.html**

Add `<link>` tags for DM Sans (weights 400, 500, 600, 700) in the `<head>`:

```html
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link
  href="https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700;1,9..40,400&display=swap"
  rel="stylesheet"
/>
```

Insert after the apple-touch-icon `<link>` and before `<title>`.

Also change `<html lang="en">` to `<html lang="de">` since the app is German.

- [ ] **Step 2: Verify font loads**

Run: `frontend-logs` to check no build errors.
Open browser and inspect `body` — font-family should show "DM Sans".

- [ ] **Step 3: Commit**

```bash
git add src/frontend/index.html
git commit -m "feat(frontend): load DM Sans font and set lang=de"
```

---

## Task 2: Update color palette and typography

**Files:**
- Modify: `src/frontend/src/style.css:1-57` (`:root` and `[data-theme="dark"]` blocks)

- [ ] **Step 1: Replace CSS custom properties in `:root`**

Replace the existing `:root` block (lines 11-31) with:

```css
:root {
  --color-bg: #ffffff;
  --color-bg-soft: #f8f9fa;
  --color-text: #1e293b;
  --color-primary: #1e3a5f;
  --color-primary-hover: #152d4a;
  --color-primary-light: rgba(30, 58, 95, 0.08);

  --color-border: #e2e8f0;
  --color-muted: #64748b;
  --color-danger: #dc2626;
  --color-danger-bg: #fef2f2;
  --color-badge-green-bg: #dcfce7;
  --color-badge-green-text: #166534;
  --color-badge-gray-bg: #f1f5f9;
  --color-badge-gray-text: #475569;
  --color-shadow: rgba(15, 23, 42, 0.08);
  --color-overlay: rgba(15, 23, 42, 0.4);
  --color-row-alt: rgba(30, 58, 95, 0.03);
  --font-sans: "DM Sans", system-ui, -apple-system, sans-serif;
  --font-mono: ui-monospace, "Cascadia Code", monospace;
  --max-width: 1200px;
  --radius: 8px;
  --transition: 0.2s ease;
  color-scheme: light;
}
```

- [ ] **Step 2: Replace dark theme block**

Replace the `[data-theme="dark"]` block (lines 33-50) with:

```css
[data-theme="dark"] {
  --color-bg: #0f172a;
  --color-bg-soft: #1e293b;
  --color-text: #e2e8f0;
  --color-primary: #7dd3fc;
  --color-primary-hover: #bae6fd;
  --color-primary-light: rgba(125, 211, 252, 0.08);

  --color-border: #334155;
  --color-muted: #94a3b8;
  --color-danger: #f87171;
  --color-danger-bg: #450a0a;
  --color-badge-green-bg: #064e3b;
  --color-badge-green-text: #6ee7b7;
  --color-badge-gray-bg: #1e293b;
  --color-badge-gray-text: #cbd5e1;
  --color-shadow: rgba(0, 0, 0, 0.3);
  --color-overlay: rgba(0, 0, 0, 0.6);
  --color-row-alt: rgba(125, 211, 252, 0.04);
  color-scheme: dark;
}
```

- [ ] **Step 3: Update body styles**

Replace the `body` block (lines 52-57) with:

```css
body {
  font-family: var(--font-sans);
  color: var(--color-text);
  background: var(--color-bg);
  line-height: 1.6;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}
```

- [ ] **Step 4: Update button transition and border-radius to use variables**

In the `button, .btn` rule, replace both `border-radius: 6px;` (line 91) and `transition: background 0.15s;` (line 96). The full rule should become:

```css
button,
.btn {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 1rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  background: var(--color-bg);
  color: var(--color-text);
  font-size: 0.875rem;
  cursor: pointer;
  transition: background var(--transition), box-shadow var(--transition), transform var(--transition);
}
```

Note: Use specific transition properties (not `all`) to avoid unintended color/border transitions on danger buttons.

- [ ] **Step 5: Verify button styling**

The `.btn-primary` stays with `--color-primary` (navy). No change needed — the new navy looks professional.

- [ ] **Step 6: Update card border-radius to use variable**

In `.card` (line 197), change `border-radius: 8px;` to `border-radius: var(--radius);`.

- [ ] **Step 7: Update input focus ring for new primary color**

In the `input:focus, select:focus, textarea:focus` rule (line 164), change:
```css
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.15);
```
to:
```css
  box-shadow: 0 0 0 3px var(--color-primary-light);
```

- [ ] **Step 8: Update form error focus ring**

In `.form-group.error input:focus` (line 401), change:
```css
  box-shadow: 0 0 0 2px rgba(220, 38, 38, 0.15);
```
to:
```css
  box-shadow: 0 0 0 3px rgba(220, 38, 38, 0.15);
```

- [ ] **Step 9: Verify in browser**

Check both light and dark mode. Confirm:
- Text is legible with good contrast
- Primary color feels professional (navy, not generic blue)
- Cards, buttons, inputs all use new radius variable
- Focus rings visible

- [ ] **Step 10: Commit**

```bash
git add src/frontend/src/style.css
git commit -m "feat(frontend): update color palette and typography to DM Sans + warm navy"
```

---

## Task 3: Improve table readability

**Files:**
- Modify: `src/frontend/src/style.css:167-191` (table styles)
- Modify: `src/frontend/src/components/DataTable.vue`

- [ ] **Step 1: Update global table styles in style.css**

Replace the table styles (lines 167-191) with:

```css
/* Tables */
table {
  width: 100%;
  border-collapse: collapse;
}

th,
td {
  padding: 0.625rem 0.75rem;
  text-align: left;
  font-size: 0.875rem;
}

th {
  font-weight: 600;
  color: var(--color-muted);
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  border-bottom: 2px solid var(--color-border);
  position: sticky;
  top: 0;
  background: var(--color-bg);
  z-index: 1;
}

td {
  border-bottom: 1px solid var(--color-border);
}

tbody tr:nth-child(even) {
  background: var(--color-row-alt);
}

tbody tr:hover {
  background: var(--color-primary-light);
}
```

This adds: alternating row colors, sticky headers, stronger header border, hover highlight.

- [ ] **Step 2: Remove the old `tr:hover` rule**

The old `tr:hover` on line 189-191 should be removed as part of step 1 (it's replaced by the `tbody tr:hover` rule).

- [ ] **Step 3: Verify tables**

Navigate to any item list page. Confirm:
- Alternating row shading (subtle)
- Header row is sticky when scrolling
- Hover highlights the row clearly
- Both light/dark modes look correct

- [ ] **Step 4: Commit**

```bash
git add src/frontend/src/style.css
git commit -m "feat(frontend): improve table readability with alternating rows and sticky headers"
```

---

## Task 4: Create LoadingSpinner component

**Files:**
- Create: `src/frontend/src/components/LoadingSpinner.vue`

- [ ] **Step 1: Create the spinner component**

```vue
<script setup>
defineProps({
  size: { type: String, default: "2rem" },
});
</script>

<template>
  <div class="spinner-container">
    <div class="spinner" :style="{ width: size, height: size }"></div>
  </div>
</template>

<style scoped>
.spinner-container {
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 2rem;
}

.spinner {
  border: 3px solid var(--color-border);
  border-top-color: var(--color-primary);
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
```

- [ ] **Step 2: Use spinner in DataTable.vue**

In `src/frontend/src/components/DataTable.vue`, add the import:

```js
import LoadingSpinner from "./LoadingSpinner.vue";
```

Replace the loading text `<div v-if="loading" class="dt-empty">Laden...</div>` (line 31) with:

```html
<LoadingSpinner v-if="loading" />
```

Replace the table loading row (lines 54-55):

```html
<tr v-if="loading">
  <td :colspan="columns.length" style="text-align: center; padding: 2rem">Laden...</td>
</tr>
```

with:

```html
<tr v-if="loading">
  <td :colspan="columns.length" style="padding: 0">
    <LoadingSpinner />
  </td>
</tr>
```

- [ ] **Step 3: Use spinner in DashboardPage.vue**

In `src/frontend/src/pages/DashboardPage.vue`, add the import:

```js
import LoadingSpinner from "../components/LoadingSpinner.vue";
```

Replace the loading div (line 35):

```html
<div v-if="loading" style="text-align: center; padding: 2rem">Laden...</div>
```

with:

```html
<LoadingSpinner v-if="loading" />
```

- [ ] **Step 4: Verify spinner renders**

Navigate to Dashboard — should see spinner briefly while data loads.
Navigate to any item list — should see spinner in table area.

- [ ] **Step 5: Commit**

```bash
git add src/frontend/src/components/LoadingSpinner.vue src/frontend/src/components/DataTable.vue src/frontend/src/pages/DashboardPage.vue
git commit -m "feat(frontend): add LoadingSpinner component, replace text loading indicators"
```

---

## Task 5: Add route transitions

**Files:**
- Modify: `src/frontend/src/App.vue`
- Modify: `src/frontend/src/style.css` (add transition classes at end)

- [ ] **Step 1: Wrap RouterView in Transition**

In `src/frontend/src/App.vue`, replace the template (lines 8-14) with:

```html
<template>
  <NavBar />
  <main class="container">
    <RouterView v-slot="{ Component, route }">
      <Transition name="fade" mode="out-in">
        <component :is="Component" :key="route.path" />
      </Transition>
    </RouterView>
  </main>
  <div class="app-version">v{{ version }}</div>
</template>
```

Note: `:key="route.path"` ensures transitions fire when navigating between routes that use the same component (e.g., `/instrumente/1` to `/instrumente/2`).

- [ ] **Step 2: Add transition CSS to style.css**

Append to the end of `src/frontend/src/style.css`:

```css
/* ── Transitions ──────────────────────────────────── */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.15s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.slide-fade-enter-active,
.slide-fade-leave-active {
  transition: all 0.2s ease;
}

.slide-fade-enter-from {
  opacity: 0;
  transform: translateY(8px);
}

.slide-fade-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}
```

- [ ] **Step 3: Verify route change fades**

Click between Dashboard and any item list. Should see a quick, subtle fade (150ms). Not distracting but smoother than instant swap.

- [ ] **Step 4: Commit**

```bash
git add src/frontend/src/App.vue src/frontend/src/style.css
git commit -m "feat(frontend): add fade transition on route changes"
```

---

## Task 6: Add modal transitions

**Files:**
- Modify: `src/frontend/src/components/ConfirmDialog.vue`

- [ ] **Step 1: Wrap ConfirmDialog in Transition**

Replace the template in `src/frontend/src/components/ConfirmDialog.vue` with:

```html
<template>
  <Transition name="fade">
    <div v-if="open" class="overlay" @click.self="$emit('cancel')">
      <div class="dialog">
        <h3>{{ title }}</h3>
        <p style="margin-top: 0.5rem">{{ message }}</p>
        <div class="dialog-actions">
          <button @click="$emit('cancel')">Abbrechen</button>
          <button class="btn-danger" @click="$emit('confirm')">Löschen</button>
        </div>
      </div>
    </div>
  </Transition>
</template>
```

Note: A single `<Transition>` on the overlay is sufficient. The dialog inherits the fade since it's a child of the overlay. Nested transitions with `appear` would only fire on initial mount, not on subsequent open/close cycles.

- [ ] **Step 2: Verify modal animation**

Open any delete confirmation. Overlay should fade in, dialog should slide up slightly. Closing should reverse.

- [ ] **Step 3: Commit**

```bash
git add src/frontend/src/components/ConfirmDialog.vue
git commit -m "feat(frontend): add fade/slide transitions to confirm dialog"
```

---

## Task 7: Refine NavBar active state and spacing

**Files:**
- Modify: `src/frontend/src/components/NavBar.vue`

- [ ] **Step 1: Update active link styling**

In the `<style scoped>` section of NavBar.vue, replace the `.links a.router-link-active` rule (lines 157-160) with:

```css
.links a.router-link-active {
  color: var(--color-primary);
  font-weight: 600;
  background: var(--color-primary-light);
  border-left: 3px solid var(--color-primary);
  padding-left: calc(1.25rem - 3px);
}
```

This gives the active nav item a clear left-border indicator (common in sidebar navs) plus a subtle background highlight.

- [ ] **Step 2: Add smooth transition to nav links**

Add after the `.links > a:hover` rule (around line 153):

```css
.links > a {
  transition: all var(--transition);
}
```

- [ ] **Step 3: Verify navigation highlighting**

Click through different sections. The active page should have a clear left-border highlight in the sidebar. Hover should be smooth.

- [ ] **Step 4: Commit**

```bash
git add src/frontend/src/components/NavBar.vue
git commit -m "feat(frontend): refine NavBar active state with left-border indicator"
```

---

## Task 8: Refine StatCard with accent border

**Files:**
- Modify: `src/frontend/src/components/StatCard.vue`

- [ ] **Step 1: Update StatCard styles**

Replace the `<style scoped>` block in StatCard.vue with:

```css
<style scoped>
.stat-card {
  text-align: center;
  display: block;
  color: inherit;
  border-left: 4px solid var(--color-primary);
  transition: all var(--transition);
}
a.stat-card {
  text-decoration: none;
}
a.stat-card:hover {
  box-shadow: 0 4px 16px var(--color-shadow);
  transform: translateY(-2px);
}
.stat-value {
  font-size: 2rem;
  font-weight: 700;
  color: var(--color-primary);
}
.stat-title {
  font-size: 0.875rem;
  color: var(--color-muted);
  margin-top: 0.25rem;
}
</style>
```

Changes: left border accent for visual weight, hover lift on clickable cards.

- [ ] **Step 2: Verify dashboard cards**

Check Dashboard. Cards should have a navy left border. Clickable cards should lift on hover.

- [ ] **Step 3: Commit**

```bash
git add src/frontend/src/components/StatCard.vue
git commit -m "feat(frontend): add accent border and hover lift to StatCard"
```

---

## Task 9: Add search icon to SearchBar

**Files:**
- Modify: `src/frontend/src/components/SearchBar.vue`

- [ ] **Step 1: Add SVG search icon**

Replace the full content of SearchBar.vue with:

```vue
<script setup>
const model = defineModel({ type: String, default: "" });
defineProps({ placeholder: { type: String, default: "Suchen..." } });
</script>

<template>
  <div class="search-wrapper">
    <svg class="search-icon" viewBox="0 0 20 20" fill="currentColor" width="16" height="16">
      <path
        fill-rule="evenodd"
        d="M9 3.5a5.5 5.5 0 1 0 0 11 5.5 5.5 0 0 0 0-11ZM2 9a7 7 0 1 1 12.45 4.39l3.58 3.58a.75.75 0 1 1-1.06 1.06l-3.58-3.58A7 7 0 0 1 2 9Z"
        clip-rule="evenodd"
      />
    </svg>
    <input
      type="search"
      :placeholder="placeholder"
      :value="model"
      class="search-input"
      @input="model = $event.target.value"
    />
  </div>
</template>

<style scoped>
.search-wrapper {
  position: relative;
  max-width: 100%;
}

.search-icon {
  position: absolute;
  left: 0.75rem;
  top: 50%;
  transform: translateY(-50%);
  color: var(--color-muted);
  pointer-events: none;
}

.search-input {
  padding-left: 2.25rem;
  max-width: 100%;
}
</style>
```

- [ ] **Step 2: Verify search input**

Navigate to any item list. Search input should show a magnifying glass icon on the left.

- [ ] **Step 3: Commit**

```bash
git add src/frontend/src/components/SearchBar.vue
git commit -m "feat(frontend): add search icon to SearchBar component"
```

---

## Task 10: Add keyboard focus rings globally

**Files:**
- Modify: `src/frontend/src/style.css`

- [ ] **Step 1: Add focus-visible styles**

Add after the button hover rules (around line 102) in style.css:

```css
button:focus-visible,
.btn:focus-visible,
a:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}
```

And add after the `.view-toggle button.active` rule (around line 389):

```css
.view-toggle button:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: -2px;
}
```

- [ ] **Step 2: Verify focus rings**

Tab through the page with keyboard. All buttons and links should show a clear focus ring.

- [ ] **Step 3: Commit**

```bash
git add src/frontend/src/style.css
git commit -m "feat(frontend): add focus-visible rings for keyboard navigation"
```

---

## Task 11: Final visual pass and cleanup

- [ ] **Step 1: Check all pages in light mode**

Navigate through: Dashboard, Instrumente, a detail page, Musiker, Leihen, Rechnungen, Einstellungen. Verify consistent styling.

- [ ] **Step 2: Check all pages in dark mode**

Toggle to dark mode. Same navigation pass. Verify colors, contrast, and readability.

- [ ] **Step 3: Check mobile layout**

Resize browser to 375px width. Verify hamburger menu, card layouts, modals all still work.

- [ ] **Step 4: Run linters**

```bash
cd src/frontend && npx eslint src/ && npx prettier --check src/
```

- [ ] **Step 5: Run frontend tests**

```bash
cd src/frontend && npx vitest run
```

- [ ] **Step 6: Run pre-commit**

```bash
pre-commit run --all-files
```

- [ ] **Step 7: Final commit if any fixes needed**

```bash
git add -A
git commit -m "fix(frontend): lint and test fixes from design polish"
```
