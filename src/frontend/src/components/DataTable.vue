<script setup>
import { computed, ref, onMounted, onUnmounted } from "vue";
import LoadingSpinner from "./LoadingSpinner.vue";
import SortSelect from "./SortSelect.vue";

const props = defineProps({
  columns: { type: Array, default: () => [] },
  rows: { type: Array, default: () => [] },
  loading: Boolean,
  cardBreakpoint: { type: Number, default: 0 },
  sort: { type: String, default: "" },
  emptyText: { type: String, default: "Keine Einträge" },
});
const emit = defineEmits(["row-click", "update:sort"]);

const useCards = ref(false);

const sortKeyOf = (s) => s.replace(/^[-+]/, "");
const sortOptions = computed(() =>
  props.columns.filter((c) => c.sortKey).map((c) => ({ key: c.sortKey, label: c.label })),
);
function ariaSort(col) {
  if (!col.sortKey) return undefined;
  if (sortKeyOf(props.sort) !== col.sortKey) return "none";
  return props.sort.startsWith("-") ? "descending" : "ascending";
}
function toggleSort(col) {
  const active = sortKeyOf(props.sort) === col.sortKey;
  emit("update:sort", active && !props.sort.startsWith("-") ? `-${col.sortKey}` : col.sortKey);
}

// Spalten mit `hideEmptyInCard` erscheinen in der Kartenansicht nur mit Wert.
function cardColumns(row) {
  return props.columns.filter(
    (col) => !col.hideEmptyInCard || (row[col.key] !== "" && row[col.key] != null),
  );
}

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
</script>

<template>
  <!-- Card layout for mobile when cardBreakpoint is set -->
  <div v-if="useCards" class="dt-cards">
    <SortSelect
      v-if="sortOptions.length"
      class="dt-sort"
      :options="sortOptions"
      :model-value="sort"
      @update:model-value="emit('update:sort', $event)"
    />
    <LoadingSpinner v-if="loading" />
    <div v-else-if="!rows?.length" class="dt-empty">{{ emptyText }}</div>
    <div v-for="row in rows" :key="row.id" class="dt-card" @click="$emit('row-click', row)">
      <div v-for="col in cardColumns(row)" :key="col.key" class="dt-card-row">
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
          <th v-for="col in columns" :key="col.key" :class="col.class" :aria-sort="ariaSort(col)">
            <button v-if="col.sortKey" type="button" class="th-sort" @click="toggleSort(col)">
              {{ col.label
              }}<span v-if="ariaSort(col) !== 'none'" aria-hidden="true" class="th-sort-arrow">{{
                ariaSort(col) === "descending" ? "▼" : "▲"
              }}</span>
            </button>
            <template v-else>{{ col.label }}</template>
          </th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="loading">
          <td :colspan="columns.length" style="padding: 0">
            <LoadingSpinner />
          </td>
        </tr>
        <tr v-else-if="!rows?.length">
          <td
            :colspan="columns.length"
            style="text-align: center; padding: 2rem; color: var(--color-muted)"
          >
            {{ emptyText }}
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

.th-sort {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  min-height: 44px;
  padding: 0;
  border: none;
  background: transparent;
  color: inherit;
  font: inherit;
  font-weight: inherit;
  cursor: pointer;
}

.th-sort:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}

.th-sort-arrow {
  font-size: 0.7em;
  color: var(--color-muted);
}

.dt-sort {
  align-self: flex-end;
}
</style>
