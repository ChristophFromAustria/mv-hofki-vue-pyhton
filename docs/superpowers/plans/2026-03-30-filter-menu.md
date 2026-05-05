# Filter-Menu Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the two toggle buttons in the Scan Editor toolbar with a Filter dropdown that exposes category-level visibility, filtered-symbol hiding, and staff-line toggling.

**Architecture:** Add `filtered`/`filter_reason` to the API schema so the frontend receives filter status. Create a `FilterDropdown.vue` component with checkboxes. Wire it into `ScanEditorPage.vue` with a `filteredSymbols` computed that drives `ScanCanvas`. Filtered symbols get a dashed/transparent visual treatment.

**Tech Stack:** Vue 3, Pydantic, existing CSS variables

---

## File Structure

| File | Role |
|------|------|
| `src/backend/mv_hofki/schemas/detected_symbol.py` | Add `filtered` + `filter_reason` to schema |
| `src/frontend/src/components/FilterDropdown.vue` | New dropdown component |
| `src/frontend/src/pages/ScanEditorPage.vue` | Remove toggle buttons, wire FilterDropdown + filteredSymbols |
| `src/frontend/src/components/ScanCanvas.vue` | Dashed/transparent rendering for filtered symbols |

---

### Task 1: Add filtered fields to API schema

**Files:**
- Modify: `src/backend/mv_hofki/schemas/detected_symbol.py:16-34`

- [ ] **Step 1: Add fields to DetectedSymbolRead**

In `src/backend/mv_hofki/schemas/detected_symbol.py`, add after `alternatives` (line 32):

```python
    filtered: bool = False
    filter_reason: str | None = None
```

The full class becomes:

```python
class DetectedSymbolRead(BaseModel):
    id: int
    staff_id: int
    x: int
    y: int
    width: int
    height: int
    snippet_path: str | None
    position_on_staff: int | None
    sequence_order: int
    matched_symbol_id: int | None
    confidence: float | None
    user_verified: bool
    user_corrected_symbol_id: int | None
    matched_symbol: SymbolTemplateRead | None = None
    corrected_symbol: SymbolTemplateRead | None = None
    alternatives: list[AlternativeMatch] = []
    filtered: bool = False
    filter_reason: str | None = None

    model_config = {"from_attributes": True}
```

- [ ] **Step 2: Verify the API returns the new fields**

Run: `cd /workspaces/mv_hofki && server-restart`

Then test with curl (adjust IDs to match an existing scan):

```bash
curl -s http://localhost:8000/api/v1/scanner/scans/1/symbols | python3 -m json.tool | head -30
```

Verify that `filtered` and `filter_reason` fields appear in the response.

- [ ] **Step 3: Run pre-commit**

Run: `cd /workspaces/mv_hofki && pre-commit run --all-files`

- [ ] **Step 4: Commit**

```bash
git add src/backend/mv_hofki/schemas/detected_symbol.py
git commit -m "feat(api): expose filtered/filter_reason in DetectedSymbolRead schema"
```

---

### Task 2: Create FilterDropdown component

**Files:**
- Create: `src/frontend/src/components/FilterDropdown.vue`

- [ ] **Step 1: Create the component**

Create `src/frontend/src/components/FilterDropdown.vue`:

```vue
<script setup>
import { ref, computed, onMounted, onUnmounted } from "vue";

const props = defineProps({
  showStaves: { type: Boolean, default: true },
  hideFiltered: { type: Boolean, default: true },
  symbols: { type: Array, default: () => [] },
  hiddenCategories: { type: Object, default: () => new Set() },
});

const emit = defineEmits(["update:showStaves", "update:hideFiltered", "update:hiddenCategories"]);

const open = ref(false);
const dropdownRef = ref(null);

const CATEGORY_LABELS = {
  note: "Noten",
  rest: "Pausen",
  barline: "Taktstriche",
  clef: "Schlüssel",
  time_sig: "Taktarten",
  time_signature: "Taktarten",
  dynamic: "Dynamik",
  ornament: "Verzierungen",
  accidental: "Vorzeichen",
  other: "Sonstige",
};

const categoryCounts = computed(() => {
  const counts = {};
  for (const sym of props.symbols) {
    const cat = sym.matched_symbol?.category ?? sym.corrected_symbol?.category;
    if (!cat) continue;
    counts[cat] = (counts[cat] || 0) + 1;
  }
  return counts;
});

const sortedCategories = computed(() => {
  const order = ["note", "rest", "barline", "clef", "time_sig", "time_signature", "dynamic", "ornament", "accidental", "other"];
  return Object.keys(categoryCounts.value).sort(
    (a, b) => (order.indexOf(a) === -1 ? 99 : order.indexOf(a)) - (order.indexOf(b) === -1 ? 99 : order.indexOf(b)),
  );
});

function toggleCategory(cat) {
  const next = new Set(props.hiddenCategories);
  if (next.has(cat)) {
    next.delete(cat);
  } else {
    next.add(cat);
  }
  emit("update:hiddenCategories", next);
}

function onClickOutside(e) {
  if (dropdownRef.value && !dropdownRef.value.contains(e.target)) {
    open.value = false;
  }
}

onMounted(() => document.addEventListener("click", onClickOutside, true));
onUnmounted(() => document.removeEventListener("click", onClickOutside, true));
</script>

<template>
  <div ref="dropdownRef" class="filter-dropdown">
    <button class="btn btn-sm" :class="{ 'btn-active': open }" @click="open = !open">
      Filter ▾
    </button>
    <div v-if="open" class="filter-menu">
      <div class="filter-section">
        <div class="filter-heading">Anzeige</div>
        <label class="filter-item">
          <input
            type="checkbox"
            :checked="showStaves"
            @change="emit('update:showStaves', $event.target.checked)"
          />
          Notenlinien
        </label>
        <label class="filter-item">
          <input
            type="checkbox"
            :checked="hideFiltered"
            @change="emit('update:hideFiltered', $event.target.checked)"
          />
          Gefilterte ausblenden
        </label>
      </div>
      <hr class="filter-divider" />
      <div class="filter-section">
        <div class="filter-heading">Symbolkategorien</div>
        <label v-for="cat in sortedCategories" :key="cat" class="filter-item">
          <input
            type="checkbox"
            :checked="!hiddenCategories.has(cat)"
            @change="toggleCategory(cat)"
          />
          {{ CATEGORY_LABELS[cat] || cat }}
          <span class="filter-count">({{ categoryCounts[cat] }})</span>
        </label>
      </div>
    </div>
  </div>
</template>

<style scoped>
.filter-dropdown {
  position: relative;
}

.filter-menu {
  position: absolute;
  top: 100%;
  left: 0;
  margin-top: 0.25rem;
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  padding: 0.75rem;
  min-width: 220px;
  z-index: 100;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
}

.filter-heading {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--color-text);
  margin-bottom: 0.4rem;
}

.filter-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.8rem;
  color: var(--color-muted);
  cursor: pointer;
  padding: 0.15rem 0;
}

.filter-item:hover {
  color: var(--color-text);
}

.filter-item input[type="checkbox"] {
  accent-color: var(--color-primary);
}

.filter-count {
  color: var(--color-muted);
  font-size: 0.75rem;
}

.filter-divider {
  border: none;
  border-top: 1px solid var(--color-border);
  margin: 0.5rem 0;
}

.filter-section {
  margin-bottom: 0.25rem;
}
</style>
```

- [ ] **Step 2: Verify it renders**

The component will be wired in Task 3. For now, verify no syntax errors:

Run: `cd /workspaces/mv_hofki && frontend-logs`

Check for compilation errors in the vite build output. If the frontend watcher is running, it should rebuild without errors even though the component isn't imported yet.

- [ ] **Step 3: Commit**

```bash
git add src/frontend/src/components/FilterDropdown.vue
git commit -m "feat(frontend): add FilterDropdown component"
```

---

### Task 3: Wire FilterDropdown into ScanEditorPage

**Files:**
- Modify: `src/frontend/src/pages/ScanEditorPage.vue`

- [ ] **Step 1: Add import and reactive state**

In `src/frontend/src/pages/ScanEditorPage.vue`:

Add import at line 8 (after SymbolPanel import):

```javascript
import FilterDropdown from "../components/FilterDropdown.vue";
```

Replace line 27-28:

```javascript
const showStaves = ref(true);
const showSymbols = ref(true);
```

with:

```javascript
const showStaves = ref(true);
const hideFiltered = ref(true);
const hiddenCategories = ref(new Set());
```

- [ ] **Step 2: Add filteredSymbols computed**

Add after the `groupedTemplates` computed (after line 402):

```javascript
const filteredSymbols = computed(() => {
  return symbols.value.filter((sym) => {
    if (hideFiltered.value && sym.filtered) return false;
    const cat = sym.matched_symbol?.category ?? sym.corrected_symbol?.category;
    if (cat && hiddenCategories.value.has(cat)) return false;
    return true;
  });
});
```

- [ ] **Step 3: Replace toggle buttons with FilterDropdown in template**

Replace lines 450-465 (the two toggle buttons):

```html
            <button
              class="btn btn-sm"
              :class="{ 'btn-active': showStaves }"
              :title="showStaves ? 'Notenlinien ausblenden' : 'Notenlinien einblenden'"
              @click="showStaves = !showStaves"
            >
              {{ showStaves ? "Linien ausblenden" : "Linien einblenden" }}
            </button>
            <button
              class="btn btn-sm"
              :class="{ 'btn-active': showSymbols }"
              :title="showSymbols ? 'Symbole ausblenden' : 'Symbole einblenden'"
              @click="showSymbols = !showSymbols"
            >
              {{ showSymbols ? "Symbole ausblenden" : "Symbole einblenden" }}
            </button>
```

with:

```html
            <FilterDropdown
              :show-staves="showStaves"
              :hide-filtered="hideFiltered"
              :symbols="symbols"
              :hidden-categories="hiddenCategories"
              @update:show-staves="showStaves = $event"
              @update:hide-filtered="hideFiltered = $event"
              @update:hidden-categories="hiddenCategories = $event"
            />
```

- [ ] **Step 4: Update ScanCanvas props**

In the `<ScanCanvas>` element (around line 512-527), change the `:symbols` and `:show-symbols` props:

Replace:

```html
            :symbols="symbols"
```

with:

```html
            :symbols="filteredSymbols"
```

Replace:

```html
            :show-symbols="showSymbols"
```

with:

```html
            :show-symbols="true"
```

- [ ] **Step 5: Update statusMessage to reflect filtered count**

In the `updateStatus` function (around line 118-135), replace the status text logic:

Replace:

```javascript
  if (total > 0) {
    statusMessage.value = `${label} · ${verified} / ${total} Symbole verifiziert`;
  } else {
    statusMessage.value = label;
  }
```

with:

```javascript
  if (total > 0) {
    const visible = filteredSymbols.value.length;
    const visibleInfo = visible < total ? ` · ${visible} / ${total} sichtbar` : "";
    statusMessage.value = `${label} · ${verified} / ${total} verifiziert${visibleInfo}`;
  } else {
    statusMessage.value = label;
  }
```

- [ ] **Step 6: Verify in browser**

Run: `cd /workspaces/mv_hofki && frontend-logs`

Check for build errors. Open the scan editor in the browser and verify:
- The "Filter" button appears in the toolbar where the two toggle buttons were
- Clicking it opens the dropdown
- Checkboxes work (Notenlinien, Gefilterte ausblenden, categories)
- Unchecking a category hides those symbols on the canvas
- Status bar shows filtered count when categories are hidden

- [ ] **Step 7: Run pre-commit**

Run: `cd /workspaces/mv_hofki && pre-commit run --all-files`

- [ ] **Step 8: Commit**

```bash
git add src/frontend/src/pages/ScanEditorPage.vue
git commit -m "feat(frontend): wire FilterDropdown into ScanEditorPage, replace toggle buttons"
```

---

### Task 4: Dashed rendering for filtered symbols in ScanCanvas

**Files:**
- Modify: `src/frontend/src/components/ScanCanvas.vue:422-453`

- [ ] **Step 1: Update the symbol SVG rendering**

In `src/frontend/src/components/ScanCanvas.vue`, replace the symbol bounding boxes template (lines 422-453):

```html
        <!-- Symbol bounding boxes -->
        <template v-if="showSymbols">
          <g
            v-for="symbol in symbols"
            :key="`sym-${symbol.id}`"
            class="symbol-box"
            style="cursor: pointer; pointer-events: all"
            @click="selectSymbol(symbol)"
          >
            <rect
              :x="symbol.x"
              :y="symbol.y"
              :width="symbol.width"
              :height="symbol.height"
              fill="none"
              :stroke="symbolColor(symbol)"
              :stroke-width="isSelected(symbol) ? 3 : 1.5"
              :opacity="isSelected(symbol) ? 1 : 0.7"
            />
            <rect
              v-if="isSelected(symbol)"
              :x="symbol.x - 2"
              :y="symbol.y - 2"
              :width="symbol.width + 4"
              :height="symbol.height + 4"
              fill="none"
              stroke="#fff"
              stroke-width="1"
              opacity="0.8"
            />
          </g>
        </template>
```

with:

```html
        <!-- Symbol bounding boxes -->
        <template v-if="showSymbols">
          <g
            v-for="symbol in symbols"
            :key="`sym-${symbol.id}`"
            class="symbol-box"
            style="cursor: pointer; pointer-events: all"
            @click="selectSymbol(symbol)"
          >
            <rect
              :x="symbol.x"
              :y="symbol.y"
              :width="symbol.width"
              :height="symbol.height"
              fill="none"
              :stroke="symbolColor(symbol)"
              :stroke-width="isSelected(symbol) ? 3 : 1.5"
              :stroke-dasharray="symbol.filtered ? '4,3' : 'none'"
              :opacity="symbol.filtered ? 0.4 : isSelected(symbol) ? 1 : 0.7"
            />
            <rect
              v-if="isSelected(symbol)"
              :x="symbol.x - 2"
              :y="symbol.y - 2"
              :width="symbol.width + 4"
              :height="symbol.height + 4"
              fill="none"
              stroke="#fff"
              stroke-width="1"
              opacity="0.8"
            />
          </g>
        </template>
```

The changes are two new attributes on the inner `<rect>`:
- `:stroke-dasharray="symbol.filtered ? '4,3' : 'none'"` — dashed border for filtered symbols
- `:opacity="symbol.filtered ? 0.4 : isSelected(symbol) ? 1 : 0.7"` — reduced opacity for filtered symbols

- [ ] **Step 2: Verify in browser**

Open the scan editor, uncheck "Gefilterte ausblenden" in the Filter dropdown. Filtered symbols should now appear with dashed borders and reduced opacity.

- [ ] **Step 3: Run pre-commit**

Run: `cd /workspaces/mv_hofki && pre-commit run --all-files`

- [ ] **Step 4: Commit**

```bash
git add src/frontend/src/components/ScanCanvas.vue
git commit -m "feat(frontend): dashed/transparent rendering for filtered symbols"
```
