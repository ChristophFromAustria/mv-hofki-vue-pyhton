<script setup>
import { computed, ref, onMounted, onUnmounted } from "vue";
import LoadingSpinner from "./LoadingSpinner.vue";
import SortSelect from "./SortSelect.vue";
import GroupHeader from "./GroupHeader.vue";
import HighlightText from "./HighlightText.vue";
import { buildSegments } from "../lib/grouping.js";
import { displayNrParts, highlightParts } from "../lib/highlight.js";

const props = defineProps({
  columns: { type: Array, default: () => [] },
  rows: { type: Array, default: () => [] },
  loading: Boolean,
  cardBreakpoint: { type: Number, default: 0 },
  sort: { type: String, default: "" },
  emptyText: { type: String, default: "Keine Einträge" },
  groups: { type: Array, default: null },
  collapsedGroups: { type: Set, default: () => new Set() },
  selectable: { type: Boolean, default: false },
  selectedIds: { type: Array, default: () => [] },
  rowLabel: { type: Function, default: (r) => r.label ?? "" },
  // Search term to mark in columns with `highlight` (true, or "display-nr"
  // for inventory numbers typed as "tu 2").
  highlight: { type: String, default: "" },
  // (row) => { label, parts } | null — where a row was found when no column
  // shows it; rendered under the column with `hint: true` (or as a card row).
  rowHint: { type: Function, default: null },
});
const emit = defineEmits(["row-click", "update:sort", "toggle-group", "toggle-select"]);

const useCards = ref(false);

const segments = computed(() => buildSegments(props.rows, props.groups, props.collapsedGroups));
const selectedSet = computed(() => new Set(props.selectedIds));
const colspan = computed(() => props.columns.length + (props.selectable ? 1 : 0));

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

function cellParts(row, col) {
  if (!col.highlight || !props.highlight) return null;
  const value = row[col.key];
  if (value == null || value === "") return null;
  return col.highlight === "display-nr"
    ? displayNrParts(String(value), props.highlight)
    : highlightParts(String(value), props.highlight);
}

const hintOf = (row) => (props.rowHint ? props.rowHint(row) : null);

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
    <template v-for="seg in segments" :key="seg.key">
      <div v-if="seg.type === 'group'" class="group-heading" role="heading" aria-level="2">
        <GroupHeader
          :label="seg.label"
          :count="seg.count"
          :collapsed="seg.collapsed"
          @toggle="emit('toggle-group', seg.groupKey)"
        />
      </div>
      <div
        v-else
        class="dt-card"
        :class="{ 'dt-card--selectable': selectable }"
        @click="$emit('row-click', seg.row)"
      >
        <label v-if="selectable" class="dt-card-select" @click.stop>
          <input
            type="checkbox"
            :checked="selectedSet.has(seg.row.id)"
            :aria-label="`„${rowLabel(seg.row)}“ auswählen`"
            @change="emit('toggle-select', seg.row)"
          />
        </label>
        <div v-for="col in cardColumns(seg.row)" :key="col.key" class="dt-card-row">
          <span class="dt-card-label">{{ col.label }}</span>
          <span class="dt-card-value">
            <slot :name="col.key" :row="seg.row" :value="seg.row[col.key]">
              <HighlightText v-if="cellParts(seg.row, col)" :parts="cellParts(seg.row, col)" />
              <template v-else>{{ seg.row[col.key] }}</template>
            </slot>
          </span>
        </div>
        <p v-if="hintOf(seg.row)" class="search-hint dt-card-hint">
          <span class="search-hint-label">{{ `Treffer in ${hintOf(seg.row).label}: ` }}</span>
          <HighlightText :parts="hintOf(seg.row).parts" />
        </p>
      </div>
    </template>
  </div>

  <!-- Standard table with horizontal scroll -->
  <div v-else class="table-scroll">
    <table>
      <thead>
        <tr>
          <th v-if="selectable" class="dt-select"><span class="sr-only">Auswahl</span></th>
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
          <td :colspan="colspan" style="padding: 0">
            <LoadingSpinner />
          </td>
        </tr>
        <tr v-else-if="!rows?.length">
          <td
            :colspan="colspan"
            style="text-align: center; padding: 2rem; color: var(--color-muted)"
          >
            {{ emptyText }}
          </td>
        </tr>
        <template v-for="seg in segments" v-else :key="seg.key">
          <tr v-if="seg.type === 'group'" class="dt-group">
            <th :colspan="colspan" scope="rowgroup">
              <GroupHeader
                :label="seg.label"
                :count="seg.count"
                :collapsed="seg.collapsed"
                @toggle="emit('toggle-group', seg.groupKey)"
              />
            </th>
          </tr>
          <tr v-else style="cursor: pointer" @click="$emit('row-click', seg.row)">
            <td v-if="selectable" class="dt-select" @click.stop>
              <label class="dt-select-hit">
                <input
                  type="checkbox"
                  :checked="selectedSet.has(seg.row.id)"
                  :aria-label="`„${rowLabel(seg.row)}“ auswählen`"
                  @change="emit('toggle-select', seg.row)"
                />
              </label>
            </td>
            <td v-for="col in columns" :key="col.key" :class="col.class">
              <slot :name="col.key" :row="seg.row" :value="seg.row[col.key]">
                <HighlightText v-if="cellParts(seg.row, col)" :parts="cellParts(seg.row, col)" />
                <template v-else>{{ seg.row[col.key] }}</template>
              </slot>
              <span v-if="col.hint && hintOf(seg.row)" class="search-hint">
                <span class="search-hint-label">{{ `Treffer in ${hintOf(seg.row).label}: ` }}</span>
                <HighlightText :parts="hintOf(seg.row).parts" />
              </span>
            </td>
          </tr>
        </template>
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
  position: relative;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 0.75rem 1rem;
  background: var(--color-bg);
  cursor: pointer;
}

.dt-card--selectable {
  padding-right: 3rem;
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

.dt-card-hint {
  margin: 0;
  padding-top: 0.25rem;
  border-top: 1px solid var(--color-border);
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

.dt-group th {
  padding: 0;
  background: var(--color-bg-soft);
}

.group-heading {
  margin: 0;
  font: inherit;
}

.dt-select {
  width: 44px;
  text-align: center;
}

.dt-select input,
.dt-card-select input {
  width: 22px;
  height: 22px;
  margin: 0;
}

.dt-select-hit {
  display: grid;
  place-items: center;
  width: 44px;
  height: 44px;
  margin: 0 auto;
  cursor: pointer;
}

.dt-card-select {
  position: absolute;
  top: var(--space-2);
  right: var(--space-2);
  display: grid;
  place-items: center;
  width: 44px;
  height: 44px;
  cursor: pointer;
}
</style>
