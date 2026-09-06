<script setup>
/**
 * Per-scan LilyPond layout overrides, edited in a drawer next to the preview.
 *
 * Shows the "LilyPond*" groups of the scanner configuration with the scan's
 * overrides (adjustments.analysis) applied. Changes are emitted a moment
 * after the last edit as `apply-layout` ({ values, reset }); the parent
 * persists them and renders the score again.
 */
import { ref, computed, onMounted, onBeforeUnmount } from "vue";
import { get } from "../lib/api.js";
import FieldNumber from "./config/FieldNumber.vue";
import FieldSelect from "./config/FieldSelect.vue";
import FieldToggle from "./config/FieldToggle.vue";

const props = defineProps({
  open: { type: Boolean, default: false },
  /** Per-scan adjustments; analysis.* may override LilyPond layout values */
  adjustments: { type: Object, default: () => ({}) },
  /** True while the score is being rendered again */
  busy: { type: Boolean, default: false },
});

const emit = defineEmits(["update:open", "apply-layout"]);

const entries = ref([]); // config entries of the LilyPond groups
const globals = ref({});
const loading = ref(false);
const error = ref(null);

async function loadEntries() {
  loading.value = true;
  error.value = null;
  try {
    const data = await get("/scanner/config");
    const analysis = props.adjustments?.analysis;
    globals.value = {};
    entries.value = (data.entries || [])
      .filter((e) => (e.group_path || "").startsWith("LilyPond"))
      .sort((a, b) => a.group_path.localeCompare(b.group_path) || a.sort_order - b.sort_order)
      .map((e) => {
        globals.value[e.key] = e.value;
        const overridden = analysis && analysis.enabled && e.key in analysis;
        const value = overridden ? analysis[e.key] : e.value;
        return { ...e, value, is_modified: overridden && String(value) !== String(e.value) };
      });
  } catch (e) {
    error.value = e.message;
  } finally {
    loading.value = false;
  }
}

// Loaded once when the drawer is mounted. Not on every adjustments change:
// applying a value updates adjustments, and reloading would rebuild the
// drawer under the user's hands.
onMounted(loadEntries);

const groups = computed(() => {
  const map = new Map();
  for (const e of entries.value) {
    const label = (e.group_path || "LilyPond").replace(/^LilyPond\s*/, "") || "Allgemein";
    if (!map.has(label)) map.set(label, []);
    map.get(label).push(e);
  }
  return [...map.entries()].map(([label, items]) => ({ label, entries: items }));
});

const hasOverrides = computed(() => entries.value.some((e) => e.is_modified));

// Changes are applied automatically a moment after the last adjustment
let applyTimer = null;
const APPLY_DELAY_MS = 700;

function scheduleApply() {
  if (applyTimer) clearTimeout(applyTimer);
  applyTimer = setTimeout(() => {
    applyTimer = null;
    applyLayout();
  }, APPLY_DELAY_MS);
}

function update(key, value) {
  const e = entries.value.find((x) => x.key === key);
  if (!e) return;
  e.value = value;
  e.is_modified = String(value) !== String(globals.value[key]);
  scheduleApply();
}

function resetOne(key) {
  update(key, globals.value[key]);
}

function applyLayout() {
  const values = {};
  for (const e of entries.value) {
    if (e.is_modified) values[e.key] = e.value;
  }
  emit("apply-layout", { values, reset: Object.keys(values).length === 0 });
}

function resetAll() {
  if (applyTimer) clearTimeout(applyTimer);
  applyTimer = null;
  for (const e of entries.value) {
    e.value = globals.value[e.key];
    e.is_modified = false;
  }
  emit("apply-layout", { values: {}, reset: true });
}

onBeforeUnmount(() => {
  if (applyTimer) clearTimeout(applyTimer);
});
</script>

<template>
  <button
    type="button"
    class="drawer-toggle"
    :class="{ active: open }"
    :aria-expanded="open"
    aria-controls="lilypond-layout-drawer"
    title="LilyPond-Layout einstellen"
    @click="emit('update:open', !open)"
  >
    <span aria-hidden="true">{{ open ? "◂" : "▸" }}</span>
    Layout
    <span v-if="hasOverrides" class="layout-badge" title="Für diesen Scan angepasst">●</span>
  </button>

  <aside
    id="lilypond-layout-drawer"
    class="layout-drawer"
    :class="{ open }"
    :aria-hidden="!open"
    aria-label="LilyPond-Layout"
  >
    <div class="drawer-head">
      <h3>LilyPond-Layout</h3>
      <button
        type="button"
        class="dialog-close"
        title="Leiste schließen"
        @click="emit('update:open', false)"
      >
        ✕
      </button>
    </div>
    <p v-if="hasOverrides" class="layout-hint">Für diesen Scan angepasst.</p>
    <p v-if="error" class="layout-error">{{ error }}</p>
    <div v-else-if="loading" class="layout-loading">Lade Einstellungen…</div>
    <div v-else class="layout-groups">
      <section v-for="group in groups" :key="group.label" class="layout-group">
        <h4>{{ group.label }}</h4>
        <template v-for="entry in group.entries" :key="entry.key">
          <FieldToggle
            v-if="entry.type === 'toggle'"
            :entry="entry"
            @update="update"
            @reset="resetOne"
          />
          <FieldSelect
            v-else-if="entry.type === 'select'"
            :entry="entry"
            @update="update"
            @reset="resetOne"
          />
          <FieldNumber v-else :entry="entry" @update="update" @reset="resetOne" />
        </template>
      </section>
    </div>
    <div class="layout-actions">
      <span v-if="busy" class="layout-status" role="status">Wird neu gerendert…</span>
      <span v-else class="layout-status">Änderungen werden automatisch gerendert.</span>
      <button
        type="button"
        class="btn btn-sm"
        :disabled="busy || loading || !hasOverrides"
        title="Globale Standardwerte für diesen Scan wiederherstellen"
        @click="resetAll"
      >
        Standardwerte
      </button>
    </div>
    <p class="layout-hint">
      Werte gelten nur für diesen Scan. Globale Standards unter Notenscanner → Konfiguration.
    </p>
  </aside>
</template>

<style scoped>
.drawer-toggle {
  position: absolute;
  top: 0.5rem;
  left: 0.5rem;
  z-index: 3;
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  min-height: 44px;
  padding: 0 0.75rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  background: var(--color-bg);
  color: var(--color-text);
  font-size: 0.85rem;
  cursor: pointer;
}

.drawer-toggle.active,
.drawer-toggle:hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.layout-drawer {
  position: absolute;
  top: 0;
  left: 0;
  bottom: 0;
  z-index: 2;
  width: 340px;
  max-width: 92%;
  padding: 3.5rem 1rem 1rem;
  overflow-y: auto;
  background: var(--color-bg);
  border-right: 1px solid var(--color-border);
  box-shadow: var(--shadow-float);
  transform: translateX(-100%);
  visibility: hidden;
  transition:
    transform var(--transition),
    visibility 0s linear 0.2s;
}

.layout-drawer.open {
  transform: none;
  visibility: visible;
  transition:
    transform var(--transition),
    visibility 0s;
}

@media (prefers-reduced-motion: reduce) {
  .layout-drawer,
  .layout-drawer.open {
    transition: none;
  }
}

.drawer-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.5rem;
}

.drawer-head h3 {
  margin: 0;
  font-size: 0.95rem;
}

.layout-badge {
  font-size: 0.7rem;
  font-weight: 600;
  color: var(--color-warning);
}

.layout-groups {
  display: grid;
  gap: 0.75rem;
}

.layout-group h4 {
  margin: 0.25rem 0;
  font-size: 0.75rem;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--color-muted);
}

.layout-loading {
  padding: 0.5rem 0;
  color: var(--color-muted);
  font-size: 0.85rem;
}

.layout-error {
  margin: 0.5rem 0 0;
  font-size: 0.85rem;
  color: var(--color-danger);
}

.layout-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
  margin-top: 0.75rem;
}

.layout-status {
  font-size: 0.75rem;
  color: var(--color-muted);
}

.layout-hint {
  font-size: 0.75rem;
  color: var(--color-muted);
}
</style>
