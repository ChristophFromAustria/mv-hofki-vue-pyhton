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
  const order = [
    "note",
    "rest",
    "barline",
    "clef",
    "time_sig",
    "time_signature",
    "dynamic",
    "ornament",
    "accidental",
    "other",
  ];
  return Object.keys(categoryCounts.value).sort(
    (a, b) =>
      (order.indexOf(a) === -1 ? 99 : order.indexOf(a)) -
      (order.indexOf(b) === -1 ? 99 : order.indexOf(b)),
  );
});

const allHidden = computed(() => {
  return (
    sortedCategories.value.length > 0 &&
    sortedCategories.value.every((c) => props.hiddenCategories.has(c))
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

function toggleAll() {
  if (allHidden.value) {
    emit("update:hiddenCategories", new Set());
  } else {
    emit("update:hiddenCategories", new Set(sortedCategories.value));
  }
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
          <span class="filter-label">Notenlinien</span>
          <input
            type="checkbox"
            :checked="showStaves"
            @change="emit('update:showStaves', $event.target.checked)"
          />
        </label>
        <label class="filter-item">
          <span class="filter-label">Gefilterte ausblenden</span>
          <input
            type="checkbox"
            :checked="hideFiltered"
            @change="emit('update:hideFiltered', $event.target.checked)"
          />
        </label>
      </div>
      <hr class="filter-divider" />
      <div class="filter-section">
        <div class="filter-heading">Symbolkategorien</div>
        <label class="filter-item">
          <span class="filter-label">Alle</span>
          <input type="checkbox" :checked="!allHidden" @change="toggleAll()" />
        </label>
        <label v-for="cat in sortedCategories" :key="cat" class="filter-item">
          <span class="filter-label">
            {{ CATEGORY_LABELS[cat] || cat }}
            <span class="filter-count">({{ categoryCounts[cat] }})</span>
          </span>
          <input
            type="checkbox"
            :checked="!hiddenCategories.has(cat)"
            @change="toggleCategory(cat)"
          />
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
  justify-content: space-between;
  gap: 0.5rem;
  font-size: 0.8rem;
  color: var(--color-muted);
  cursor: pointer;
  padding: 0.15rem 0;
}

.filter-label {
  flex: 1;
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
