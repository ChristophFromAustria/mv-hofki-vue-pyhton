# Mobile Responsive Design Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the entire frontend usable on mobile devices (320px–768px) with horizontal scroll for tables and card-layout fallback for wide tables.

**Architecture:** Add responsive breakpoints to `style.css`, implement a hamburger menu in `NavBar.vue`, enhance `DataTable.vue` with scroll wrapper + optional card mode, and fix all pages with hardcoded widths or non-wrapping layouts.

**Tech Stack:** Vue 3, plain CSS (no framework), CSS media queries, CSS custom properties

---

## File Structure

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `src/frontend/src/style.css` | Add breakpoints, responsive grids, toolbar/pagination wrap, touch-friendly sizing |
| Modify | `src/frontend/src/components/NavBar.vue` | Hamburger menu with slide-out sidebar on mobile |
| Modify | `src/frontend/src/components/DataTable.vue` | Horizontal scroll wrapper + optional card layout via prop |
| Modify | `src/frontend/src/components/SearchBar.vue` | Remove hardcoded `max-width: 300px` |
| Modify | `src/frontend/src/App.vue` | Reduce container padding on mobile |
| Modify | `src/frontend/src/pages/LoanListPage.vue` | Use DataTable with card mode, fix grid-3 form, remove fixed widths |
| Modify | `src/frontend/src/pages/InvoiceListPage.vue` | Remove fixed widths from toolbar filters, wrap toolbar |
| Modify | `src/frontend/src/pages/ItemDetailPage.vue` | Remove fixed widths on date inputs, wrap inline forms |
| Modify | `src/frontend/src/pages/MusicianDetailPage.vue` | Wrap table in scroll container |
| Modify | `src/frontend/src/pages/DashboardPage.vue` | Use responsive grid classes |
| Modify | `src/frontend/src/pages/InstrumentTypeListPage.vue` | Remove fixed widths, wrap action buttons |
| Modify | `src/frontend/src/pages/CurrencyListPage.vue` | Remove fixed widths, wrap action buttons |
| Modify | `src/frontend/src/pages/ClothingTypeListPage.vue` | Wrap table in scroll container |
| Modify | `src/frontend/src/pages/SheetMusicGenreListPage.vue` | Wrap table in scroll container |

---

### Task 1: Responsive Breakpoints & Base Layout

**Files:**
- Modify: `src/frontend/src/style.css:198-237` (grid, toolbar, pagination sections)
- Modify: `src/frontend/src/App.vue:13-17` (container padding)

- [ ] **Step 1: Add CSS custom property for mobile breakpoint and responsive grid rules**

Add at the end of `style.css`:

```css
/* ── Responsive ─────────────────────────────────────── */
@media (max-width: 768px) {
  .grid-2,
  .grid-3,
  .grid-4 {
    grid-template-columns: 1fr;
  }

  .page-header {
    flex-wrap: wrap;
    gap: 0.75rem;
  }

  .toolbar {
    flex-wrap: wrap;
  }

  .toolbar > * {
    flex-shrink: 1;
  }

  .pagination {
    flex-wrap: wrap;
    gap: 0.5rem;
  }

  .detail-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 480px) {
  .page-header h1 {
    font-size: 1.25rem;
  }
}
```

- [ ] **Step 2: Make input font-size 16px to prevent iOS zoom**

In `style.css`, change the input/select/textarea `font-size` from `0.875rem` to `1rem` (lines 125-134):

```css
input,
select,
textarea {
  width: 100%;
  padding: 0.5rem 0.75rem;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  font-size: 1rem;
  font-family: var(--font-sans);
}
```

- [ ] **Step 3: Make .btn-sm touch-friendly**

In `style.css`, change `.btn-sm` (line 108-111):

```css
.btn-sm {
  padding: 0.375rem 0.625rem;
  font-size: 0.8rem;
  min-height: 36px;
}
```

- [ ] **Step 4: Reduce container padding on mobile in App.vue**

Add to the `<style scoped>` block in `App.vue`:

```css
@media (max-width: 768px) {
  .container {
    padding: 1rem 0.75rem;
  }
}
```

- [ ] **Step 5: Verify frontend rebuilds without errors**

Run: `cd /workspaces/mv_hofki/src/frontend && npx vite build`
Expected: Build succeeds

- [ ] **Step 6: Commit**

```bash
git add src/frontend/src/style.css src/frontend/src/App.vue
git commit -m "feat: add responsive breakpoints, touch-friendly sizing, and mobile base layout"
```

---

### Task 2: Hamburger Menu for NavBar

**Files:**
- Modify: `src/frontend/src/components/NavBar.vue`

- [ ] **Step 1: Add mobile menu state and click-outside handling**

In the `<script setup>` of `NavBar.vue`, add after the existing refs:

```js
const menuOpen = ref(false);

function closeMenu() {
  menuOpen.value = false;
  settingsOpen.value = false;
}
```

- [ ] **Step 2: Replace template with responsive navbar**

Replace the entire `<template>` section with:

```html
<template>
  <nav class="navbar">
    <div class="navbar-inner">
      <RouterLink to="/" class="brand" @click="closeMenu">MV Hofkirchen</RouterLink>

      <button class="hamburger" :class="{ open: menuOpen }" @click="menuOpen = !menuOpen">
        <span></span><span></span><span></span>
      </button>

      <div class="links" :class="{ open: menuOpen }">
        <RouterLink to="/" @click="closeMenu">Dashboard</RouterLink>
        <RouterLink to="/instrumente" @click="closeMenu">Instrumente</RouterLink>
        <RouterLink to="/kleidung" @click="closeMenu">Kleidung</RouterLink>
        <RouterLink to="/noten" @click="closeMenu">Noten</RouterLink>
        <RouterLink to="/allgemein" @click="closeMenu">Allgemein</RouterLink>
        <RouterLink to="/musiker" @click="closeMenu">Musiker</RouterLink>
        <RouterLink to="/leihen" @click="closeMenu">Leihregister</RouterLink>
        <RouterLink to="/rechnungen" @click="closeMenu">Rechnungen</RouterLink>
        <div class="dropdown" @mouseenter="settingsOpen = true" @mouseleave="settingsOpen = false">
          <span class="dropdown-trigger" @click="settingsOpen = !settingsOpen">Einstellungen</span>
          <div v-show="settingsOpen" class="dropdown-menu">
            <RouterLink to="/einstellungen/instrumententypen" @click="closeMenu">Instrumententypen</RouterLink>
            <RouterLink to="/einstellungen/kleidungstypen" @click="closeMenu">Kleidungstypen</RouterLink>
            <RouterLink to="/einstellungen/notengenres" @click="closeMenu">Notengenres</RouterLink>
            <RouterLink to="/einstellungen/waehrungen" @click="closeMenu">Währungen</RouterLink>
            <a href="//localhost:7681" target="_blank" class="terminal-link">Terminal</a>
          </div>
        </div>
        <button
          class="theme-toggle"
          :title="isDark ? 'Light Mode' : 'Dark Mode'"
          @click="toggleTheme"
        >
          {{ isDark ? "\u2600" : "\u263E" }}
        </button>
      </div>

      <div v-if="menuOpen" class="menu-backdrop" @click="closeMenu"></div>
    </div>
  </nav>
</template>
```

- [ ] **Step 3: Add responsive styles for hamburger + sidebar**

Replace the entire `<style scoped>` section with:

```css
<style scoped>
.navbar {
  border-bottom: 1px solid var(--color-border);
  background: var(--color-bg);
  position: sticky;
  top: 0;
  z-index: 200;
}

.navbar-inner {
  max-width: var(--max-width);
  margin: 0 auto;
  padding: 0.75rem 1rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.brand {
  font-weight: 700;
  font-size: 1.1rem;
  color: var(--color-text);
}

.links {
  display: flex;
  gap: 1.5rem;
  align-items: center;
}

.links a.router-link-active {
  color: var(--color-primary);
  font-weight: 600;
}

.hamburger {
  display: none;
  flex-direction: column;
  gap: 5px;
  background: none;
  border: none;
  padding: 0.5rem;
  cursor: pointer;
  min-height: 44px;
  min-width: 44px;
  align-items: center;
  justify-content: center;
}

.hamburger span {
  display: block;
  width: 22px;
  height: 2px;
  background: var(--color-text);
  border-radius: 2px;
  transition: transform 0.2s, opacity 0.2s;
}

.hamburger.open span:nth-child(1) {
  transform: translateY(7px) rotate(45deg);
}
.hamburger.open span:nth-child(2) {
  opacity: 0;
}
.hamburger.open span:nth-child(3) {
  transform: translateY(-7px) rotate(-45deg);
}

.menu-backdrop {
  display: none;
}

.dropdown {
  position: relative;
}

.dropdown-trigger {
  cursor: pointer;
  color: var(--color-primary);
}

.dropdown-menu {
  position: absolute;
  right: 0;
  top: 100%;
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: 6px;
  padding: 0.5rem 0;
  min-width: 180px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  z-index: 50;
}

.dropdown-menu a {
  display: block;
  padding: 0.5rem 1rem;
  color: var(--color-text);
}

.dropdown-menu a:hover {
  background: var(--color-bg-soft);
}

.terminal-link {
  border-top: 1px solid var(--color-border);
  margin-top: 0.25rem;
  padding-top: 0.625rem !important;
}

.theme-toggle {
  background: none;
  border: none;
  font-size: 1.2rem;
  cursor: pointer;
  padding: 0.5rem;
  min-height: 44px;
  min-width: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
  color: var(--color-muted);
}

.theme-toggle:hover {
  color: var(--color-text);
  background: none;
}

@media (max-width: 768px) {
  .hamburger {
    display: flex;
  }

  .links {
    position: fixed;
    top: 0;
    right: 0;
    bottom: 0;
    width: 260px;
    max-width: 80vw;
    flex-direction: column;
    align-items: stretch;
    gap: 0;
    background: var(--color-bg);
    border-left: 1px solid var(--color-border);
    padding: 1rem 0;
    transform: translateX(100%);
    transition: transform 0.25s ease;
    z-index: 300;
    overflow-y: auto;
  }

  .links.open {
    transform: translateX(0);
  }

  .links > a,
  .links > .dropdown {
    padding: 0.75rem 1.25rem;
    font-size: 1rem;
  }

  .links > a:hover,
  .dropdown-trigger:hover {
    background: var(--color-bg-soft);
  }

  .dropdown-trigger {
    display: block;
    padding: 0;
  }

  .dropdown-menu {
    position: static;
    box-shadow: none;
    border: none;
    border-radius: 0;
    padding: 0;
    min-width: 0;
  }

  .dropdown-menu a {
    padding: 0.625rem 1.25rem 0.625rem 2.5rem;
    font-size: 0.9rem;
  }

  .terminal-link {
    border-top: none;
    margin-top: 0;
    padding-top: 0.625rem !important;
  }

  .theme-toggle {
    align-self: flex-start;
    margin: 0.5rem 1rem;
  }

  .menu-backdrop {
    display: block;
    position: fixed;
    inset: 0;
    background: var(--color-overlay);
    z-index: 250;
  }
}
</style>
```

- [ ] **Step 4: Verify frontend rebuilds without errors**

Run: `cd /workspaces/mv_hofki/src/frontend && npx vite build`
Expected: Build succeeds

- [ ] **Step 5: Commit**

```bash
git add src/frontend/src/components/NavBar.vue
git commit -m "feat: add responsive hamburger menu with slide-out sidebar for mobile"
```

---

### Task 3: Responsive DataTable with Card Mode

**Files:**
- Modify: `src/frontend/src/components/DataTable.vue`

- [ ] **Step 1: Add cardMode prop and mobile detection**

Replace the entire `<script setup>` block:

```js
import { ref, onMounted, onUnmounted } from "vue";

const props = defineProps({
  columns: { type: Array, default: () => [] },
  rows: { type: Array, default: () => [] },
  loading: Boolean,
  cardBreakpoint: { type: Number, default: 0 },
});
defineEmits(["row-click"]);

const useCards = ref(false);

function checkWidth() {
  useCards.value = props.cardBreakpoint > 0 && window.innerWidth <= props.cardBreakpoint;
}

onMounted(() => {
  checkWidth();
  window.addEventListener("resize", checkWidth);
});

onUnmounted(() => {
  window.removeEventListener("resize", checkWidth);
});
```

`cardBreakpoint` prop: when set to e.g. `640`, the table switches to card layout at that viewport width. When `0` (default), only horizontal scroll is used.

- [ ] **Step 2: Replace template with scroll wrapper + card mode**

Replace the entire `<template>`:

```html
<template>
  <!-- Card layout for mobile when cardBreakpoint is set -->
  <div v-if="useCards" class="dt-cards">
    <div v-if="loading" class="dt-empty">Laden...</div>
    <div v-else-if="!rows?.length" class="dt-empty">Keine Einträge</div>
    <div
      v-for="row in rows"
      :key="row.id"
      class="dt-card"
      @click="$emit('row-click', row)"
    >
      <div v-for="col in columns" :key="col.key" class="dt-card-row">
        <span class="dt-card-label">{{ col.label }}</span>
        <span class="dt-card-value">
          <slot :name="col.key" :row="row" :value="row[col.key]">
            {{ row[col.key] }}
          </slot>
        </span>
      </div>
    </div>
  </div>

  <!-- Standard table with horizontal scroll -->
  <div v-else class="table-scroll">
    <table>
      <thead>
        <tr>
          <th v-for="col in columns" :key="col.key" :class="col.class">{{ col.label }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="loading">
          <td :colspan="columns.length" style="text-align: center; padding: 2rem">Laden...</td>
        </tr>
        <tr v-else-if="!rows?.length">
          <td
            :colspan="columns.length"
            style="text-align: center; padding: 2rem; color: var(--color-muted)"
          >
            Keine Einträge
          </td>
        </tr>
        <tr
          v-for="row in rows"
          :key="row.id"
          style="cursor: pointer"
          @click="$emit('row-click', row)"
        >
          <td v-for="col in columns" :key="col.key" :class="col.class">
            <slot :name="col.key" :row="row" :value="row[col.key]">
              {{ row[col.key] }}
            </slot>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
```

- [ ] **Step 3: Add scoped styles for scroll wrapper and card layout**

Add at the end of the file:

```html
<style scoped>
.table-scroll {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}

.dt-empty {
  text-align: center;
  padding: 2rem;
  color: var(--color-muted);
}

.dt-cards {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.dt-card {
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 0.75rem 1rem;
  background: var(--color-bg);
  cursor: pointer;
}

.dt-card:hover {
  box-shadow: 0 2px 8px var(--color-shadow);
}

.dt-card-row {
  display: flex;
  justify-content: space-between;
  padding: 0.25rem 0;
  font-size: 0.875rem;
}

.dt-card-row + .dt-card-row {
  border-top: 1px solid var(--color-border);
}

.dt-card-label {
  color: var(--color-muted);
  font-weight: 500;
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.025em;
}

.dt-card-value {
  text-align: right;
}
</style>
```

- [ ] **Step 4: Verify frontend rebuilds without errors**

Run: `cd /workspaces/mv_hofki/src/frontend && npx vite build`
Expected: Build succeeds

- [ ] **Step 5: Commit**

```bash
git add src/frontend/src/components/DataTable.vue
git commit -m "feat: add horizontal scroll and card layout mode to DataTable for mobile"
```

---

### Task 4: Fix SearchBar Hardcoded Width

**Files:**
- Modify: `src/frontend/src/components/SearchBar.vue`

- [ ] **Step 1: Remove max-width from SearchBar**

Replace the `<style scoped>` block in `SearchBar.vue`:

```css
<style scoped>
.search-input {
  max-width: 100%;
}
</style>
```

- [ ] **Step 2: Commit**

```bash
git add src/frontend/src/components/SearchBar.vue
git commit -m "fix: remove hardcoded max-width from SearchBar for mobile responsiveness"
```

---

### Task 5: Fix LoanListPage for Mobile

**Files:**
- Modify: `src/frontend/src/pages/LoanListPage.vue`

This page has a raw `<table>` (not DataTable), a `grid-3` form, and `140px` fixed-width date inputs. The table has 7 columns — ideal candidate for card layout on mobile.

- [ ] **Step 1: Wrap the loan form grid in a responsive class**

Change line 91 from `grid grid-3` to just `grid grid-3` (this is already handled by Task 1's media query making `grid-3` single-column on mobile). No change needed here.

- [ ] **Step 2: Remove fixed width from return date input**

On line 176, change:
```html
style="width: 140px; padding: 0.2rem 0.4rem; font-size: 0.8rem"
```
to:
```html
style="max-width: 160px; padding: 0.2rem 0.4rem; font-size: 1rem"
```

- [ ] **Step 3: Wrap the loans table in a scroll container**

On line 135, change:
```html
<table v-else-if="loans.length">
```
to:
```html
<div v-else-if="loans.length" style="overflow-x: auto; -webkit-overflow-scrolling: touch">
<table>
```

And after the closing `</table>` on line 195, add:
```html
</div>
```

- [ ] **Step 4: Make return button group wrap on mobile**

On line 171, change:
```html
style="display: flex; gap: 0.25rem; align-items: center"
```
to:
```html
style="display: flex; gap: 0.25rem; align-items: center; flex-wrap: wrap"
```

- [ ] **Step 5: Verify frontend rebuilds without errors**

Run: `cd /workspaces/mv_hofki/src/frontend && npx vite build`
Expected: Build succeeds

- [ ] **Step 6: Commit**

```bash
git add src/frontend/src/pages/LoanListPage.vue
git commit -m "fix: make LoanListPage mobile-friendly with scroll wrapper and flexible widths"
```

---

### Task 6: Fix InvoiceListPage Toolbar for Mobile

**Files:**
- Modify: `src/frontend/src/pages/InvoiceListPage.vue`

- [ ] **Step 1: Remove fixed widths from toolbar filters**

On line 99, change:
```html
<select v-model="categoryFilter" style="width: 160px">
```
to:
```html
<select v-model="categoryFilter" style="min-width: 120px; flex: 1; max-width: 200px">
```

On line 104, change:
```html
<input v-model="dateFrom" type="date" style="width: 160px" placeholder="Von" />
```
to:
```html
<input v-model="dateFrom" type="date" style="min-width: 120px; flex: 1; max-width: 200px" placeholder="Von" />
```

On line 105, change:
```html
<input v-model="dateTo" type="date" style="width: 160px" placeholder="Bis" />
```
to:
```html
<input v-model="dateTo" type="date" style="min-width: 120px; flex: 1; max-width: 200px" placeholder="Bis" />
```

- [ ] **Step 2: Wrap table in scroll container**

On line 113, change:
```html
<table v-else-if="invoices.length">
```
to:
```html
<div v-else-if="invoices.length" style="overflow-x: auto; -webkit-overflow-scrolling: touch">
<table>
```

And after the closing `</table>` on line 137, add:
```html
</div>
```

- [ ] **Step 3: Verify frontend rebuilds without errors**

Run: `cd /workspaces/mv_hofki/src/frontend && npx vite build`
Expected: Build succeeds

- [ ] **Step 4: Commit**

```bash
git add src/frontend/src/pages/InvoiceListPage.vue
git commit -m "fix: make InvoiceListPage toolbar and table mobile-friendly"
```

---

### Task 7: Fix ItemDetailPage for Mobile

**Files:**
- Modify: `src/frontend/src/pages/ItemDetailPage.vue`

- [ ] **Step 1: Fix return date input width**

On line 318, change:
```html
<input v-model="returnDate" type="date" style="width: 180px" />
```
to:
```html
<input v-model="returnDate" type="date" style="max-width: 180px" />
```

- [ ] **Step 2: Fix loan form layout to wrap on mobile**

On line 332, change:
```html
<form style="display: flex; gap: 0.75rem; align-items: end" @submit.prevent="createLoan">
```
to:
```html
<form style="display: flex; gap: 0.75rem; align-items: end; flex-wrap: wrap" @submit.prevent="createLoan">
```

- [ ] **Step 3: Fix loan date input width**

On line 351, change:
```html
<input v-model="loanForm.start_date" type="date" style="width: 160px" />
```
to:
```html
<input v-model="loanForm.start_date" type="date" style="max-width: 160px" />
```

- [ ] **Step 4: Wrap return date picker to allow wrapping**

On line 315, change:
```html
<div v-else style="display: flex; gap: 0.5rem; align-items: end">
```
to:
```html
<div v-else style="display: flex; gap: 0.5rem; align-items: end; flex-wrap: wrap">
```

- [ ] **Step 5: Wrap all tables on ItemDetailPage in scroll containers**

On line 377, wrap the invoices table:
```html
<div style="overflow-x: auto; -webkit-overflow-scrolling: touch">
```
before `<table v-else>` and `</div>` after its `</table>`.

On line 410, wrap the loan history table:
```html
<div style="overflow-x: auto; -webkit-overflow-scrolling: touch">
```
before `<table>` and `</div>` after its `</table>`.

- [ ] **Step 6: Verify frontend rebuilds without errors**

Run: `cd /workspaces/mv_hofki/src/frontend && npx vite build`
Expected: Build succeeds

- [ ] **Step 7: Commit**

```bash
git add src/frontend/src/pages/ItemDetailPage.vue
git commit -m "fix: make ItemDetailPage mobile-friendly with flexible widths and scroll wrappers"
```

---

### Task 8: Fix Remaining Pages for Mobile

**Files:**
- Modify: `src/frontend/src/pages/MusicianDetailPage.vue`
- Modify: `src/frontend/src/pages/DashboardPage.vue`
- Modify: `src/frontend/src/pages/InstrumentTypeListPage.vue`
- Modify: `src/frontend/src/pages/CurrencyListPage.vue`
- Modify: `src/frontend/src/pages/ClothingTypeListPage.vue`
- Modify: `src/frontend/src/pages/SheetMusicGenreListPage.vue`

- [ ] **Step 1: Wrap MusicianDetailPage table in scroll container**

In `MusicianDetailPage.vue`, on line 67, change:
```html
<table>
```
to:
```html
<div style="overflow-x: auto; -webkit-overflow-scrolling: touch">
<table>
```

And after the closing `</table>` on line 96, add `</div>`.

- [ ] **Step 2: Fix DashboardPage grid classes**

The Dashboard uses `grid grid-3` and `grid grid-4` which are already handled by Task 1's media query. Wrap the instruments-by-type table in a scroll container.

In `DashboardPage.vue`, on line 48, change:
```html
<table>
```
to:
```html
<div style="overflow-x: auto; -webkit-overflow-scrolling: touch">
<table>
```

And after `</table>` on line 63, add `</div>`.

- [ ] **Step 3: Fix InstrumentTypeListPage inline edit widths**

In `InstrumentTypeListPage.vue`, on line 72, change:
```html
<input v-model="form.label_short" placeholder="Kürzel" style="width: 80px" />
```
to:
```html
<input v-model="form.label_short" placeholder="Kürzel" style="max-width: 100px" />
```

On line 85, change:
```html
<input v-model="form.label_short" style="width: 80px" />
```
to:
```html
<input v-model="form.label_short" style="max-width: 100px" />
```

Wrap the table in a scroll container (line 60):
```html
<div style="overflow-x: auto; -webkit-overflow-scrolling: touch">
```
before `<table>` and `</div>` after `</table>` on line 106.

- [ ] **Step 4: Fix CurrencyListPage inline edit widths**

In `CurrencyListPage.vue`, on line 75, change:
```html
<input v-model="form.abbreviation" placeholder="Kürzel" style="width: 80px" />
```
to:
```html
<input v-model="form.abbreviation" placeholder="Kürzel" style="max-width: 100px" />
```

On line 88, change:
```html
<input v-model="form.abbreviation" style="width: 80px" />
```
to:
```html
<input v-model="form.abbreviation" style="max-width: 100px" />
```

Wrap the table in a scroll container (line 60).

- [ ] **Step 5: Wrap ClothingTypeListPage table in scroll container**

In `ClothingTypeListPage.vue`, wrap the `<table>` (line 60) in:
```html
<div style="overflow-x: auto; -webkit-overflow-scrolling: touch">
```
and add `</div>` after `</table>` on line 98.

- [ ] **Step 6: Wrap SheetMusicGenreListPage table in scroll container**

In `SheetMusicGenreListPage.vue`, wrap the `<table>` (line 60) in:
```html
<div style="overflow-x: auto; -webkit-overflow-scrolling: touch">
```
and add `</div>` after `</table>` on line 98.

- [ ] **Step 7: Verify frontend rebuilds without errors**

Run: `cd /workspaces/mv_hofki/src/frontend && npx vite build`
Expected: Build succeeds

- [ ] **Step 6: Commit**

```bash
git add src/frontend/src/pages/MusicianDetailPage.vue \
  src/frontend/src/pages/DashboardPage.vue \
  src/frontend/src/pages/InstrumentTypeListPage.vue \
  src/frontend/src/pages/CurrencyListPage.vue \
  src/frontend/src/pages/ClothingTypeListPage.vue \
  src/frontend/src/pages/SheetMusicGenreListPage.vue
git commit -m "fix: add scroll wrappers and fix hardcoded widths on remaining pages"
```

---

### Task 9: Enable Card Mode on Wide Tables

**Files:**
- Modify: `src/frontend/src/pages/ItemListPage.vue`
- Modify: `src/frontend/src/pages/MusicianListPage.vue`

- [ ] **Step 1: Add cardBreakpoint to ItemListPage DataTable**

In `ItemListPage.vue`, on line 166-172, change:
```html
<DataTable
  v-if="viewMode === 'list'"
  :columns="columns"
  :rows="items"
  :loading="loading"
  @row-click="goTo"
/>
```
to:
```html
<DataTable
  v-if="viewMode === 'list'"
  :columns="columns"
  :rows="items"
  :loading="loading"
  :card-breakpoint="640"
  @row-click="goTo"
/>
```

- [ ] **Step 2: Add cardBreakpoint to MusicianListPage DataTable**

In `MusicianListPage.vue`, on line 69, change:
```html
<DataTable :columns="columns" :rows="items" :loading="loading" @row-click="goTo" />
```
to:
```html
<DataTable :columns="columns" :rows="items" :loading="loading" :card-breakpoint="480" @row-click="goTo" />
```

(MusicianList has 5 columns — card mode only at very narrow screens)

- [ ] **Step 3: Verify frontend rebuilds without errors**

Run: `cd /workspaces/mv_hofki/src/frontend && npx vite build`
Expected: Build succeeds

- [ ] **Step 4: Commit**

```bash
git add src/frontend/src/pages/ItemListPage.vue src/frontend/src/pages/MusicianListPage.vue
git commit -m "feat: enable card layout for DataTables on narrow mobile screens"
```

---

### Task 10: Final Verification

- [ ] **Step 1: Run pre-commit checks**

Run: `cd /workspaces/mv_hofki && pre-commit run --all-files`
Expected: All checks pass

- [ ] **Step 2: Verify full build**

Run: `cd /workspaces/mv_hofki/src/frontend && npx vite build`
Expected: Build succeeds with no warnings

- [ ] **Step 3: Visual check — confirm frontend serves correctly**

Run: `server-logs` and check no errors. Open the app in browser and resize to mobile width to confirm:
- Hamburger menu appears at ≤768px
- Grids collapse to single column
- Tables scroll horizontally
- DataTables with cardBreakpoint show card layout
- Toolbar wraps properly
- No horizontal page overflow

- [ ] **Step 4: Fix any issues found during visual check**

Address any visual regressions.

- [ ] **Step 5: Final commit if fixes were needed**

```bash
git add -A
git commit -m "fix: address visual issues found during mobile responsive review"
```
