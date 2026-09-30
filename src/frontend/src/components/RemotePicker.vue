<script setup>
import { computed, onBeforeUnmount, ref, watch } from "vue";

const props = defineProps({
  modelValue: { type: Number, default: null },
  fetchOptions: { type: Function, required: true },
  label: { type: String, required: true },
  placeholder: { type: String, default: "Suchen …" },
  selectedLabel: { type: String, default: "" },
  debounceMs: { type: Number, default: 250 },
  // Optional search scopes, e.g. [{ value: "active", label: "Nur aktive" },
  // { value: "all", label: "Alle" }]: shown as a switch above the results
  // and passed to fetchOptions(text, { scope }).
  scopes: { type: Array, default: null },
  defaultScope: { type: String, default: "" },
});
const emit = defineEmits(["update:modelValue", "select"]);

const baseId = `remote-picker-${Math.random().toString(36).slice(2, 9)}`;
const query = ref(props.modelValue != null ? props.selectedLabel : "");
const options = ref([]);
const open = ref(false);
const activeIndex = ref(-1);
const loading = ref(false);
const error = ref("");
const selected = ref(null);
const scope = ref(props.defaultScope || props.scopes?.[0]?.value || "");
let timer = null;
let seq = 0;

watch(
  () => [props.modelValue, props.selectedLabel],
  ([value, label]) => {
    if (value == null) {
      selected.value = null;
      query.value = "";
    } else if (!selected.value || selected.value.id !== value) {
      selected.value = null;
      query.value = label || "";
    }
  },
);

async function search(text) {
  const my = ++seq;
  loading.value = true;
  error.value = "";
  try {
    const result = props.scopes
      ? await props.fetchOptions(text.trim(), { scope: scope.value })
      : await props.fetchOptions(text.trim());
    if (my !== seq) return;
    options.value = result;
    activeIndex.value = -1;
  } catch (e) {
    if (my !== seq) return;
    options.value = [];
    error.value = e?.message || "Suche fehlgeschlagen.";
  } finally {
    if (my === seq) loading.value = false;
  }
}

function schedule() {
  clearTimeout(timer);
  timer = setTimeout(() => search(query.value), props.debounceMs);
}

function onFocus() {
  open.value = true;
  if (!selected.value && props.modelValue == null) schedule();
}

function onInput() {
  open.value = true;
  if (selected.value || props.modelValue != null) {
    selected.value = null;
    emit("update:modelValue", null);
  }
  schedule();
}

function choose(option) {
  selected.value = option;
  query.value = option.label;
  open.value = false;
  activeIndex.value = -1;
  emit("update:modelValue", option.id);
  emit("select", option);
}

function setScope(value) {
  if (scope.value === value) return;
  scope.value = value;
  clearTimeout(timer);
  search(query.value);
}

function clear() {
  selected.value = null;
  query.value = "";
  options.value = [];
  emit("update:modelValue", null);
}

function onKeydown(e) {
  const count = options.value.length;
  if (e.key === "ArrowDown") {
    e.preventDefault();
    open.value = true;
    if (count) activeIndex.value = Math.min(count - 1, activeIndex.value + 1);
    else schedule();
  } else if (e.key === "ArrowUp") {
    e.preventDefault();
    if (count) activeIndex.value = Math.max(0, activeIndex.value - 1);
  } else if (e.key === "Enter") {
    if (open.value && activeIndex.value >= 0 && options.value[activeIndex.value]) {
      e.preventDefault();
      choose(options.value[activeIndex.value]);
    }
  } else if (e.key === "Escape" && open.value) {
    e.preventDefault();
    e.stopPropagation();
    open.value = false;
  }
}

function onFocusOut(e) {
  if (e.currentTarget.contains(e.relatedTarget)) return;
  open.value = false;
  activeIndex.value = -1;
  if (!selected.value && props.modelValue == null) query.value = "";
}

onBeforeUnmount(() => clearTimeout(timer));

const expanded = computed(
  () =>
    open.value &&
    (loading.value || !!error.value || options.value.length > 0 || query.value.trim() !== ""),
);
const showClear = computed(() => props.modelValue != null);
</script>

<template>
  <div class="remote-picker" @focusout="onFocusOut">
    <label :for="`${baseId}-input`">{{ label }}</label>
    <div class="remote-picker-control">
      <input
        :id="`${baseId}-input`"
        v-model="query"
        type="text"
        role="combobox"
        autocomplete="off"
        aria-autocomplete="list"
        :aria-expanded="String(expanded)"
        :aria-controls="`${baseId}-list`"
        :aria-activedescendant="activeIndex >= 0 ? `${baseId}-opt-${activeIndex}` : undefined"
        :aria-busy="loading ? 'true' : undefined"
        :placeholder="placeholder"
        @focus="onFocus"
        @input="onInput"
        @keydown="onKeydown"
      />
      <button
        v-if="showClear"
        type="button"
        class="remote-picker-clear"
        aria-label="Auswahl entfernen"
        @click="clear"
      >
        ✕
      </button>
    </div>
    <div v-show="expanded" class="remote-picker-popup">
      <div
        v-if="scopes"
        class="view-toggle remote-picker-scopes"
        role="group"
        aria-label="Suchumfang"
      >
        <button
          v-for="s in scopes"
          :key="s.value"
          type="button"
          :class="{ active: scope === s.value }"
          :aria-pressed="scope === s.value ? 'true' : 'false'"
          @mousedown.prevent
          @click="setScope(s.value)"
        >
          {{ s.label }}
        </button>
      </div>
      <ul :id="`${baseId}-list`" role="listbox" :aria-label="label">
        <li
          v-for="(o, i) in options"
          :id="`${baseId}-opt-${i}`"
          :key="o.id"
          role="option"
          :aria-selected="String(i === activeIndex)"
          :class="{ active: i === activeIndex }"
          @mousedown.prevent
          @click="choose(o)"
        >
          <span>{{ o.label }}</span>
          <span v-if="o.description" class="remote-picker-desc">{{ o.description }}</span>
        </li>
      </ul>
      <p v-if="loading" class="remote-picker-status">Suche …</p>
      <p v-else-if="error" class="remote-picker-status form-error" role="alert">{{ error }}</p>
      <p v-else-if="!options.length" class="remote-picker-status">Keine Treffer</p>
    </div>
  </div>
</template>

<style scoped>
.remote-picker {
  position: relative;
}

.remote-picker label {
  display: block;
}

.remote-picker-control {
  position: relative;
  display: flex;
  align-items: center;
}

.remote-picker-control input {
  min-height: 44px;
  padding-right: 2.75rem;
}

.remote-picker-clear {
  position: absolute;
  right: 0;
  width: 44px;
  height: 44px;
  padding: 0;
  border: none;
  background: transparent;
  color: var(--color-muted);
  cursor: pointer;
}

.remote-picker-popup {
  position: absolute;
  z-index: 20;
  left: 0;
  right: 0;
  max-height: 18rem;
  overflow-y: auto;
  margin-top: var(--space-1);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  background: var(--color-bg);
  box-shadow: var(--shadow-float);
}

.remote-picker-scopes {
  display: flex;
  margin: var(--space-2) var(--space-3) 0;
}

.remote-picker-scopes button {
  flex: 1;
  min-height: 44px;
}

.remote-picker-popup ul {
  margin: 0;
  padding: var(--space-1) 0;
  list-style: none;
}

.remote-picker-popup li {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  min-height: 44px;
  padding: 0 var(--space-3);
  cursor: pointer;
}

.remote-picker-popup li.active,
.remote-picker-popup li:hover {
  background: var(--color-primary-light);
}

.remote-picker-desc {
  font-size: 0.8125rem;
  color: var(--color-muted);
}

.remote-picker-status {
  margin: 0;
  padding: var(--space-2) var(--space-3);
  color: var(--color-muted);
}
</style>
