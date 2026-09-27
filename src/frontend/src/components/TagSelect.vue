<script setup>
import { computed, ref } from "vue";

const props = defineProps({
  modelValue: { type: Array, default: () => [] },
  options: { type: Array, default: () => [] },
  label: { type: String, required: true },
  createOption: { type: Function, default: null },
});
const emit = defineEmits(["update:modelValue"]);

const baseId = `tag-select-${Math.random().toString(36).slice(2, 9)}`;
const query = ref("");
const open = ref(false);
const activeIndex = ref(-1);
const error = ref("");
const busy = ref(false);

const norm = (s) => s.trim().toLocaleLowerCase("de-AT");
const byLabel = (a, b) => a.label.localeCompare(b.label, "de-AT");

const selected = computed(() =>
  props.modelValue.map((id) => props.options.find((o) => o.id === id)).filter(Boolean),
);

const exactOption = computed(() => {
  const q = norm(query.value);
  return q ? props.options.find((o) => norm(o.label) === q) || null : null;
});

const entries = computed(() => {
  const q = norm(query.value);
  const list = props.options
    .filter((o) => !props.modelValue.includes(o.id))
    .filter((o) => !q || norm(o.label).includes(q))
    .sort(byLabel)
    .map((o) => ({ type: "option", key: `o${o.id}`, option: o }));
  if (props.createOption && q && !exactOption.value) {
    list.push({ type: "create", key: "create", label: query.value.trim() });
  }
  return list;
});

const expanded = computed(() => open.value && entries.value.length > 0);

function emitIds(ids) {
  emit("update:modelValue", ids);
}

function pick(option) {
  if (!props.modelValue.includes(option.id)) emitIds([...props.modelValue, option.id]);
  query.value = "";
  activeIndex.value = -1;
}

function remove(id) {
  emitIds(props.modelValue.filter((x) => x !== id));
}

async function create(label) {
  if (busy.value) return;
  busy.value = true;
  error.value = "";
  try {
    const option = await props.createOption(label);
    emitIds([...props.modelValue, option.id]);
    query.value = "";
    activeIndex.value = -1;
  } catch (e) {
    error.value = e?.message || "Kategorie konnte nicht angelegt werden.";
  } finally {
    busy.value = false;
  }
}

function choose(entry) {
  if (entry.type === "option") pick(entry.option);
  else create(entry.label);
}

function onInput() {
  open.value = true;
  activeIndex.value = -1;
  error.value = "";
}

function onKeydown(e) {
  const count = entries.value.length;
  switch (e.key) {
    case "ArrowDown":
      e.preventDefault();
      open.value = true;
      if (count) activeIndex.value = Math.min(count - 1, activeIndex.value + 1);
      break;
    case "ArrowUp":
      e.preventDefault();
      if (count) activeIndex.value = Math.max(0, activeIndex.value - 1);
      break;
    case "Enter": {
      if (activeIndex.value < 0 && !query.value.trim()) return; // let the form submit
      e.preventDefault();
      if (activeIndex.value >= 0 && entries.value[activeIndex.value]) {
        choose(entries.value[activeIndex.value]);
      } else if (exactOption.value) {
        pick(exactOption.value);
      } else if (props.createOption && query.value.trim()) {
        create(query.value.trim());
      }
      break;
    }
    case "Escape":
      if (expanded.value) {
        e.preventDefault();
        e.stopPropagation();
      }
      open.value = false;
      activeIndex.value = -1;
      break;
    case "Backspace":
      if (!query.value && props.modelValue.length) {
        remove(props.modelValue[props.modelValue.length - 1]);
      }
      break;
  }
}

function onFocusOut(e) {
  if (!e.currentTarget.contains(e.relatedTarget)) {
    open.value = false;
    activeIndex.value = -1;
  }
}
</script>

<template>
  <div class="tag-select" @focusout="onFocusOut">
    <label :for="`${baseId}-input`">{{ label }}</label>
    <div class="tag-select-control">
      <ul v-if="selected.length" class="category-chips">
        <li v-for="o in selected" :key="o.id" class="category-chip">
          {{ o.label }}
          <button
            type="button"
            class="tag-select-remove"
            :aria-label="`„${o.label}“ entfernen`"
            @click="remove(o.id)"
          >
            ✕
          </button>
        </li>
      </ul>
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
        :aria-busy="busy ? 'true' : undefined"
        placeholder="Kategorie suchen oder anlegen …"
        @focus="open = true"
        @input="onInput"
        @keydown="onKeydown"
      />
    </div>
    <ul v-show="expanded" :id="`${baseId}-list`" role="listbox" class="tag-select-list">
      <li
        v-for="(entry, i) in entries"
        :id="`${baseId}-opt-${i}`"
        :key="entry.key"
        role="option"
        :aria-selected="String(i === activeIndex)"
        :class="{ active: i === activeIndex, create: entry.type === 'create' }"
        @mousedown.prevent
        @click="choose(entry)"
      >
        <template v-if="entry.type === 'option'">{{ entry.option.label }}</template>
        <template v-else>„{{ entry.label }}“ als neue Kategorie anlegen</template>
      </li>
    </ul>
    <span v-if="error" class="form-error" role="alert">{{ error }}</span>
  </div>
</template>

<style scoped>
.tag-select {
  position: relative;
}

.tag-select-control {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-1);
  min-height: 44px;
  padding: var(--space-1) var(--space-2);
  border: 1px solid var(--color-border);
  border-radius: 6px;
  background: var(--color-bg);
}

.tag-select-control:focus-within {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px var(--color-focus-ring);
}

.tag-select-control input {
  flex: 1 1 10rem;
  min-width: 8rem;
  min-height: 36px;
  border: none;
  padding: 0 var(--space-1);
  background: transparent;
  box-shadow: none;
}

.tag-select-control input:focus {
  box-shadow: none;
}

.tag-select-remove {
  position: relative;
  display: inline-grid;
  place-items: center;
  width: 1.25rem;
  height: 1.25rem;
  padding: 0;
  border: none;
  border-radius: 9999px;
  background: transparent;
  color: inherit;
  font-size: 0.75rem;
  cursor: pointer;
}

/* 44 px touch target without enlarging the chip */
.tag-select-remove::after {
  content: "";
  position: absolute;
  top: 50%;
  left: 50%;
  width: 44px;
  height: 44px;
  transform: translate(-50%, -50%);
}

.tag-select-remove:hover,
.tag-select-remove:focus-visible {
  background: var(--color-primary-light);
}

.tag-select-list {
  position: absolute;
  z-index: 20;
  left: 0;
  right: 0;
  max-height: 16rem;
  margin: var(--space-1) 0 0;
  padding: var(--space-1) 0;
  overflow-y: auto;
  list-style: none;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  background: var(--color-bg);
  box-shadow: var(--shadow-float);
}

.tag-select-list li {
  display: flex;
  align-items: center;
  min-height: 44px;
  padding: 0 var(--space-3);
  cursor: pointer;
}

.tag-select-list li.active,
.tag-select-list li:hover {
  background: var(--color-primary-light);
}

.tag-select-list li.create {
  color: var(--color-primary);
  font-weight: 500;
}
</style>
