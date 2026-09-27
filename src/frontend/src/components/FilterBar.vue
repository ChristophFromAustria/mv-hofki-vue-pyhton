<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue";

const props = defineProps({
  defs: { type: Array, required: true },
  state: { type: Object, required: true },
  defaults: { type: Object, required: true },
});
const emit = defineEmits(["change", "reset"]);

const panelId = `filter-panel-${Math.random().toString(36).slice(2, 9)}`;
const open = ref(false);
const root = ref(null);

const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const keysOf = (def) => def.keys || [def.key];
const defKey = (def) => keysOf(def).join("+");
const isActive = (def) => keysOf(def).some((k) => !same(props.state[k], props.defaults[k]));
const activeDefs = computed(() => props.defs.filter(isActive));

function optionLabel(def, value) {
  const opt = (def.options || []).find((o) => String(o.value) === String(value));
  return opt ? opt.label : String(value);
}

function formatDate(iso) {
  const [y, m, d] = String(iso).split("-");
  return d ? `${d}.${m}.${y}` : iso;
}

function chipText(def) {
  if (def.type === "multiselect") {
    return `${def.label}: ${props.state[def.key].map((v) => optionLabel(def, v)).join(", ")}`;
  }
  if (def.type === "range" || def.type === "daterange") {
    const fmt = (v) =>
      v === null || v === "" ? "…" : def.type === "daterange" ? formatDate(v) : v;
    const [from, to] = def.keys.map((k) => props.state[k]);
    return `${def.label}: ${fmt(from)}–${fmt(to)}`;
  }
  if (def.type === "toggle") return def.label;
  if (def.type === "text") return `${def.label}: „${props.state[def.key]}“`;
  const v = props.state[def.key];
  return `${def.label}: ${v === null || v === "" ? "Alle" : optionLabel(def, v)}`;
}

function clear(def) {
  for (const k of keysOf(def)) emit("change", k, props.defaults[k]);
}

function toggleMulti(def, value, checked) {
  const current = props.state[def.key];
  emit("change", def.key, checked ? [...current, value] : current.filter((v) => v !== value));
}

// Close an open multiselect when clicking elsewhere.
function onDocumentClick(e) {
  for (const d of root.value?.querySelectorAll("details[open]") || []) {
    if (!d.contains(e.target)) d.removeAttribute("open");
  }
}
onMounted(() => document.addEventListener("click", onDocumentClick));
onBeforeUnmount(() => document.removeEventListener("click", onDocumentClick));
</script>

<template>
  <div ref="root" class="filter-bar">
    <button
      type="button"
      class="btn-sm filter-toggle"
      :aria-expanded="String(open)"
      :aria-controls="panelId"
      @click="open = !open"
    >
      Filter<template v-if="activeDefs.length"> ({{ activeDefs.length }})</template>
    </button>

    <div :id="panelId" class="filter-panel" :class="{ open }">
      <template v-for="def in defs" :key="defKey(def)">
        <div
          v-if="def.type === 'segmented'"
          class="view-toggle"
          role="group"
          :aria-label="def.label"
        >
          <button
            v-for="o in def.options"
            :key="String(o.value)"
            type="button"
            :class="{ active: same(state[def.key], o.value) }"
            :aria-pressed="String(same(state[def.key], o.value))"
            @click="$emit('change', def.key, o.value)"
          >
            {{ o.label }}
          </button>
        </div>

        <label v-else-if="def.type === 'select'" class="filter-field">
          <span class="filter-label">{{ def.label }}</span>
          <select
            :value="state[def.key] ?? ''"
            @change="$emit('change', def.key, $event.target.value)"
          >
            <option value="">Alle</option>
            <option v-for="o in def.options" :key="String(o.value)" :value="String(o.value)">
              {{ o.label }}
            </option>
          </select>
        </label>

        <details v-else-if="def.type === 'multiselect'" class="filter-multi">
          <summary>
            {{ def.label
            }}<template v-if="state[def.key].length"> ({{ state[def.key].length }}) </template>
          </summary>
          <fieldset>
            <legend class="sr-only">{{ def.label }}</legend>
            <label v-for="o in def.options" :key="String(o.value)" class="filter-check">
              <input
                type="checkbox"
                :checked="state[def.key].includes(String(o.value))"
                @change="toggleMulti(def, String(o.value), $event.target.checked)"
              />
              {{ o.label }}
            </label>
            <p v-if="!def.options.length" class="text-muted">Keine Einträge</p>
          </fieldset>
        </details>

        <label v-else-if="def.type === 'text'" class="filter-field">
          <span class="filter-label">{{ def.label }}</span>
          <input
            type="text"
            :value="state[def.key]"
            :placeholder="def.placeholder"
            @input="$emit('change', def.key, $event.target.value)"
          />
        </label>

        <label v-else-if="def.type === 'toggle'" class="filter-check filter-toggle-field">
          <input
            type="checkbox"
            :checked="state[def.key] === true"
            @change="$emit('change', def.key, $event.target.checked ? true : null)"
          />
          {{ def.label }}
        </label>

        <fieldset v-else-if="def.type === 'range' || def.type === 'daterange'" class="filter-range">
          <legend class="filter-label">{{ def.label }}</legend>
          <input
            :type="def.type === 'range' ? 'number' : 'date'"
            :value="state[def.keys[0]] ?? ''"
            :aria-label="`${def.label} von`"
            @change="$emit('change', def.keys[0], $event.target.value)"
          />
          <span aria-hidden="true">–</span>
          <input
            :type="def.type === 'range' ? 'number' : 'date'"
            :value="state[def.keys[1]] ?? ''"
            :aria-label="`${def.label} bis`"
            @change="$emit('change', def.keys[1], $event.target.value)"
          />
        </fieldset>
      </template>
    </div>

    <ul v-if="activeDefs.length" class="filter-chips category-chips" aria-label="Aktive Filter">
      <li v-for="def in activeDefs" :key="defKey(def)" class="category-chip">
        {{ chipText(def)
        }}<button
          type="button"
          class="filter-chip-remove"
          :aria-label="`Filter „${def.label}“ entfernen`"
          @click="clear(def)"
          v-text="'✕'"
        ></button>
      </li>
      <li>
        <button type="button" class="btn-sm filter-reset" @click="$emit('reset')">
          Filter zurücksetzen
        </button>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.filter-bar {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  margin-bottom: var(--space-4);
}

.filter-toggle {
  display: none;
  align-self: flex-start;
  min-height: 44px;
}

.filter-panel {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: var(--space-3);
}

.filter-panel .view-toggle button {
  min-height: 44px;
}

.filter-reset {
  min-height: 44px;
}

.filter-field,
.filter-range {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  margin: 0;
  padding: 0;
  border: none;
}

.filter-range {
  flex-direction: row;
  flex-wrap: wrap;
  align-items: center;
}

.filter-range legend {
  width: 100%;
  padding: 0;
}

.filter-range input {
  width: 8rem;
}

.filter-label {
  font-size: 0.75rem;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  color: var(--color-muted);
}

.filter-field select,
.filter-field input {
  width: auto;
  min-width: 10rem;
  min-height: 44px;
}

.filter-multi {
  position: relative;
}

.filter-multi summary {
  display: flex;
  align-items: center;
  min-height: 44px;
  padding: 0 var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  background: var(--color-bg);
  cursor: pointer;
  list-style: none;
}

.filter-multi summary::-webkit-details-marker {
  display: none;
}

.filter-multi summary::after {
  content: "▾";
  margin-left: var(--space-2);
  color: var(--color-muted);
}

.filter-multi fieldset {
  position: absolute;
  z-index: 20;
  min-width: 14rem;
  max-height: 18rem;
  overflow-y: auto;
  margin: var(--space-1) 0 0;
  padding: var(--space-1) 0;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  background: var(--color-bg);
  box-shadow: var(--shadow-float);
}

.filter-check {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-height: 44px;
  padding: 0 var(--space-3);
  cursor: pointer;
}

.filter-check input {
  width: auto;
}

.filter-toggle-field {
  padding: 0;
}

.filter-chips {
  align-items: center;
}

.filter-chip-remove {
  position: relative;
  padding: 0;
  border: none;
  background: transparent;
  color: inherit;
  cursor: pointer;
  width: 1.25rem;
  height: 1.25rem;
}

.filter-chip-remove::after {
  content: "";
  position: absolute;
  top: 50%;
  left: 50%;
  width: 44px;
  height: 44px;
  transform: translate(-50%, -50%);
}

@media (max-width: 640px) {
  .filter-toggle {
    display: inline-flex;
    align-items: center;
  }

  .filter-panel:not(.open) {
    display: none;
  }

  .filter-panel {
    flex-direction: column;
    align-items: stretch;
  }

  .filter-field select,
  .filter-field input {
    width: 100%;
  }

  .filter-multi fieldset {
    position: static;
    box-shadow: none;
  }
}
</style>
