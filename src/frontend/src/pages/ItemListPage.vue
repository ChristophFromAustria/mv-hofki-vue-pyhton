<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { get, post } from "../lib/api.js";
import { CATEGORIES } from "../lib/categories.js";
import { hasMultipleQuantities, quantityCell, quantityLabel } from "../lib/quantity.js";
import { toggleId, mergeIds } from "../lib/bulkSelection.js";
import { useListQuery } from "../composables/useListQuery.js";
import { useGroupCollapse } from "../composables/useGroupCollapse.js";
import { buildSegments } from "../lib/grouping.js";
import DataTable from "../components/DataTable.vue";
import SearchBar from "../components/SearchBar.vue";
import FilterBar from "../components/FilterBar.vue";
import GroupSelect from "../components/GroupSelect.vue";
import GroupToggleAll from "../components/GroupToggleAll.vue";
import GroupHeader from "../components/GroupHeader.vue";
import ItemCard from "../components/ItemCard.vue";
import InfiniteLoader from "../components/InfiniteLoader.vue";
import SortSelect from "../components/SortSelect.vue";
import LoadingSpinner from "../components/LoadingSpinner.vue";
import CategoryChips from "../components/CategoryChips.vue";
import ItemFormModal from "../components/ItemFormModal.vue";
import BulkCategoryBar from "../components/BulkCategoryBar.vue";
import CategoryPickDialog from "../components/CategoryPickDialog.vue";

const props = defineProps({
  category: { type: String, required: true },
});

const router = useRouter();
const cat = computed(() => CATEGORIES[props.category]);
const viewMode = ref(localStorage.getItem(props.category + "-view-mode") || "card");
const showCreateModal = ref(false);
const currencies = ref([]);

const selecting = ref(false);
const selectedIds = ref([]);
const pickMode = ref(null); // "add" | "remove" | null
const bulkBusy = ref(false);
const bulkMessage = ref("");
const bulkError = ref("");

function startSelecting() {
  selecting.value = true;
  selectedIds.value = [];
  bulkMessage.value = "";
  bulkError.value = "";
}

function stopSelecting() {
  selecting.value = false;
  selectedIds.value = [];
  pickMode.value = null;
}

function toggleSelect(row) {
  selectedIds.value = toggleId(selectedIds.value, row.id);
}

function selectAllLoaded() {
  selectedIds.value = mergeIds(selectedIds.value, items.value);
}

async function applyBulk(ids) {
  const mode = pickMode.value;
  pickMode.value = null;
  bulkBusy.value = true;
  bulkError.value = "";
  bulkMessage.value = "Wird gespeichert …";
  try {
    const body = {
      item_ids: selectedIds.value,
      add_ids: mode === "add" ? ids : [],
      remove_ids: mode === "remove" ? ids : [],
    };
    const { updated } = await post("/items/bulk-categories", body);
    bulkMessage.value = `${updated} ${updated === 1 ? "Gegenstand" : "Gegenstände"} aktualisiert.`;
    selectedIds.value = [];
    await reload();
  } catch (e) {
    bulkMessage.value = "";
    bulkError.value = `Speichern fehlgeschlagen: ${e.message}`;
  } finally {
    bulkBusy.value = false;
  }
}

watch(viewMode, (v) => localStorage.setItem(props.category + "-view-mode", v));

const QUANTITY_COLUMN = {
  key: "quantity_cell",
  label: "Menge",
  class: "col-num",
  hideEmptyInCard: true,
};

const STATUS_OPTIONS = [
  { value: "", label: "Alle" },
  { value: "verfuegbar", label: "Verfügbar" },
  { value: "verliehen", label: "Ausgeliehen" },
];

const search = { type: "string", default: "", debounce: true };
const GROUP_DEFAULTS = { instrument: "type" };
const GROUP_OPTIONS = {
  instrument: [
    { key: "type", label: "Typ" },
    { key: "status", label: "Status" },
    { key: "owner", label: "Eigentümer" },
  ],
  clothing: [
    { key: "type", label: "Typ" },
    { key: "size", label: "Größe" },
    { key: "status", label: "Status" },
  ],
  sheet_music: [{ key: "genre", label: "Gattung" }],
  general_item: [
    { key: "category", label: "Kategorie" },
    { key: "room", label: "Raum" },
    { key: "status", label: "Status" },
  ],
};
const groupBy = (category) => ({ type: "string", default: GROUP_DEFAULTS[category] || "" });
const FILTERS = {
  instrument: {
    search,
    instrument_type_id__in: { type: "list", default: [] },
    status: { type: "string", default: "" },
    owner: { type: "string", default: "" },
    construction_year__gte: { type: "number", default: null },
    construction_year__lte: { type: "number", default: null },
    group_by: groupBy("instrument"),
  },
  clothing: {
    search,
    clothing_type_id__in: { type: "list", default: [] },
    size: { type: "string", default: "" },
    gender: { type: "string", default: "" },
    status: { type: "string", default: "" },
    group_by: groupBy("clothing"),
  },
  sheet_music: {
    search,
    genre_id__in: { type: "list", default: [] },
    difficulty: { type: "string", default: "" },
    storage_location__ilike: { type: "string", default: "", debounce: true },
    group_by: groupBy("sheet_music"),
  },
  general_item: {
    search,
    category_id__in: { type: "list", default: [] },
    without_category: { type: "bool", default: null },
    storage_location__ilike: { type: "string", default: "", debounce: true },
    status: { type: "string", default: "" },
    group_by: groupBy("general_item"),
  },
};

const TYPE_ENDPOINTS = {
  instrument: "/instrument-types",
  clothing: "/clothing-types",
  sheet_music: "/sheet-music-genres",
  general_item: "/general-item-categories",
};

const typeOptions = ref([]);
const facets = ref({});

const list = useListQuery({
  endpoint: "/items",
  filters: FILTERS[props.category],
  defaultSort: "number",
  baseParams: () => ({ category: props.category }),
  mapItem,
});
const {
  state,
  sort,
  setSort,
  setFilter,
  defaults,
  activeFilterCount,
  items,
  total,
  groups,
  itemTotal,
  loading,
  loadingMore,
  error,
  hasMore,
  loadMore,
  reload,
  resetFilters,
} = list;

const collapseKey = computed(() => `${props.category}:${state.group_by || "none"}`);
const {
  collapsed,
  toggle: toggleGroup,
  expandAll,
  collapseAll,
  allExpanded,
} = useGroupCollapse(collapseKey, groups);
const cardSegments = computed(() => buildSegments(items.value, groups.value, collapsed.value));

const toOptions = (values) => (values || []).map((v) => ({ value: v, label: v }));
const typeChoice = computed(() =>
  typeOptions.value.map((t) => ({ value: String(t.id), label: t.label })),
);

const filterDefs = computed(() => {
  switch (props.category) {
    case "instrument":
      return [
        {
          key: "instrument_type_id__in",
          label: "Typ",
          type: "multiselect",
          options: typeChoice.value,
        },
        { key: "status", label: "Status", type: "segmented", options: STATUS_OPTIONS },
        {
          key: "owner",
          label: "Eigentümer",
          type: "select",
          options: toOptions(facets.value.owners),
        },
        {
          keys: ["construction_year__gte", "construction_year__lte"],
          label: "Baujahr",
          type: "range",
        },
      ];
    case "clothing":
      return [
        {
          key: "clothing_type_id__in",
          label: "Typ",
          type: "multiselect",
          options: typeChoice.value,
        },
        { key: "size", label: "Größe", type: "select", options: toOptions(facets.value.sizes) },
        {
          key: "gender",
          label: "Geschlecht",
          type: "select",
          options: toOptions(facets.value.genders),
        },
        { key: "status", label: "Status", type: "segmented", options: STATUS_OPTIONS },
      ];
    case "sheet_music":
      return [
        { key: "genre_id__in", label: "Gattung", type: "multiselect", options: typeChoice.value },
        {
          key: "difficulty",
          label: "Schwierigkeitsgrad",
          type: "select",
          options: toOptions(facets.value.difficulties),
        },
        {
          key: "storage_location__ilike",
          label: "Lagerort",
          type: "text",
          placeholder: "enthält …",
        },
      ];
    default:
      return [
        {
          key: "category_id__in",
          label: "Kategorie",
          type: "multiselect",
          options: typeChoice.value,
        },
        { key: "without_category", label: "Ohne Kategorie", type: "toggle" },
        {
          key: "storage_location__ilike",
          label: "Lagerort",
          type: "text",
          placeholder: "enthält …",
        },
        { key: "status", label: "Status", type: "segmented", options: STATUS_OPTIONS },
      ];
  }
});

const filtered = computed(() => activeFilterCount.value > 0 || !!state.search.trim());
const sortOptions = computed(() =>
  columns.value.filter((c) => c.sortKey).map((c) => ({ key: c.sortKey, label: c.label })),
);

// Die Spalte „Menge“ erscheint nur, wenn auf der Seite ein Eintrag mehr als ein Stück hat.
const showQuantity = computed(() => hasMultipleQuantities(items.value));

const columns = computed(() => {
  const base = baseColumns.value;
  if (!showQuantity.value) return base;
  // Direkt nach der Bezeichnung (Typ/Titel), also an Position 2.
  return [...base.slice(0, 2), QUANTITY_COLUMN, ...base.slice(2)];
});

const baseColumns = computed(() => {
  switch (props.category) {
    case "instrument":
      return [
        { key: "display_nr", label: "Inv.-Nr.", sortKey: "number" },
        { key: "type_label", label: "Typ", sortKey: "type" },
        { key: "manufacturer", label: "Hersteller", sortKey: "manufacturer" },
        { key: "serial_nr", label: "Seriennr." },
        {
          key: "construction_year",
          label: "Baujahr",
          sortKey: "construction_year",
          class: "col-num",
          hideEmptyInCard: true,
        },
        { key: "owner", label: "Eigentümer" },
        { key: "status_label", label: "Status" },
        { key: "borrower", label: "Ausgeliehen an", sortKey: "borrower", hideEmptyInCard: true },
      ];
    case "clothing":
      return [
        { key: "display_nr", label: "Inv.-Nr.", sortKey: "number" },
        { key: "type_label", label: "Typ", sortKey: "type" },
        { key: "size", label: "Größe", sortKey: "size" },
        { key: "gender", label: "Geschlecht" },
        { key: "owner", label: "Eigentümer" },
        { key: "status_label", label: "Status" },
        { key: "borrower", label: "Ausgeliehen an", sortKey: "borrower", hideEmptyInCard: true },
      ];
    case "sheet_music":
      return [
        { key: "display_nr", label: "Inv.-Nr.", sortKey: "number" },
        { key: "label", label: "Titel", sortKey: "label" },
        { key: "composer", label: "Komponist", sortKey: "composer" },
        { key: "arranger", label: "Arrangeur" },
        { key: "genre_label", label: "Gattung" },
      ];
    case "general_item":
      return [
        { key: "display_nr", label: "Inv.-Nr.", sortKey: "number" },
        { key: "label", label: "Bezeichnung", sortKey: "label" },
        { key: "categories", label: "Kategorien", hideEmptyInCard: true },
        {
          key: "storage_location",
          label: "Lagerort",
          sortKey: "storage_location",
          hideEmptyInCard: true,
        },
        { key: "manufacturer", label: "Hersteller" },
        { key: "owner", label: "Eigentümer" },
        { key: "status_label", label: "Status" },
        { key: "borrower", label: "Ausgeliehen an", sortKey: "borrower", hideEmptyInCard: true },
      ];
    default:
      return [];
  }
});

function mapItem(i) {
  const mapped = {
    ...i,
    display_nr: i.display_nr || "",
    quantity_cell: quantityCell(i),
    quantity_label: quantityLabel(i),
  };
  if (props.category === "instrument") {
    mapped.type_label = i.instrument_type?.label || "";
  } else if (props.category === "clothing") {
    mapped.type_label = i.clothing_type?.label || "";
  } else if (props.category === "sheet_music") {
    mapped.genre_label = i.genre?.label || "";
  } else if (props.category === "general_item") {
    mapped.categories = i.categories?.length ? i.categories : null;
  }
  if (cat.value.hasLoans) {
    mapped.status_label = i.active_loan ? "Ausgeliehen" : "Verfügbar";
    mapped.borrower = i.active_loan?.musician_name || "";
  }
  return mapped;
}

onMounted(async () => {
  const [cur, types, facetData] = await Promise.all([
    get("/currencies").catch(() => []),
    get(TYPE_ENDPOINTS[props.category]).catch(() => []),
    get(`/items/facets?category=${props.category}`).catch(() => ({})),
  ]);
  currencies.value = cur;
  typeOptions.value = types;
  facets.value = facetData;
});

function goTo(row) {
  if (selecting.value) toggleSelect(row);
  else router.push(cat.value.routeBase + "/" + row.id);
}

function onModalSave() {
  reload();
}
</script>

<template>
  <div>
    <div class="page-header">
      <h1>{{ cat.label }}</h1>
      <div class="header-actions">
        <router-link v-if="cat.key === 'instrument'" to="/import" class="btn btn-secondary">
          KI-Import
        </router-link>
        <button
          v-if="cat.hasCategories && !selecting"
          type="button"
          class="btn btn-secondary"
          @click="startSelecting"
        >
          Auswählen
        </button>
        <button class="btn btn-primary" @click="showCreateModal = true">
          {{ cat.labelSingular }} anlegen
        </button>
      </div>
    </div>

    <div class="toolbar">
      <SearchBar
        v-model="state.search"
        :placeholder="
          cat.hasLoans ? 'Suche (Bezeichnung, Nummer, Person …)' : 'Suche (Bezeichnung, Nummer …)'
        "
        class="grow"
      />
      <GroupSelect
        :options="GROUP_OPTIONS[category]"
        :model-value="state.group_by"
        @update:model-value="setFilter('group_by', $event)"
      />
      <GroupToggleAll
        v-if="groups"
        :all-expanded="allExpanded"
        @expand-all="expandAll"
        @collapse-all="collapseAll"
      />
      <div class="view-toggle">
        <button :class="{ active: viewMode === 'list' }" @click="viewMode = 'list'">Liste</button>
        <button :class="{ active: viewMode === 'card' }" @click="viewMode = 'card'">Karten</button>
      </div>
    </div>

    <p v-if="!loading && !error" class="list-count">
      {{ itemTotal }} {{ itemTotal === 1 ? cat.labelSingular : cat.label }}
    </p>

    <FilterBar
      :defs="filterDefs"
      :state="state"
      :defaults="defaults"
      @change="setFilter"
      @reset="resetFilters"
    />

    <div v-if="error && !items.length" class="alert alert-danger list-alert" role="alert">
      {{ cat.label }} konnten nicht geladen werden: {{ error }}
      <button type="button" class="btn-sm" @click="reload">Erneut versuchen</button>
      <button type="button" class="btn-sm" @click="resetFilters">Filter zurücksetzen</button>
    </div>

    <template v-else>
      <template v-if="viewMode === 'list'">
        <DataTable
          :columns="columns"
          :rows="items"
          :loading="loading"
          :card-breakpoint="640"
          :sort="sort"
          :groups="groups"
          :collapsed-groups="collapsed"
          :selectable="selecting"
          :selected-ids="selectedIds"
          :empty-text="filtered ? 'Keine Einträge für diese Filter.' : 'Noch keine Einträge.'"
          @update:sort="setSort"
          @row-click="goTo"
          @toggle-group="toggleGroup"
          @toggle-select="toggleSelect"
        >
          <template #categories="{ value }">
            <CategoryChips :categories="value || []" />
          </template>
        </DataTable>

        <p v-if="!loading && !items.length && filtered" class="empty-note">
          <button type="button" class="btn-sm" @click="resetFilters">Filter zurücksetzen</button>
        </p>
      </template>

      <template v-else>
        <SortSelect
          v-if="sortOptions.length"
          class="grid-sort"
          :options="sortOptions"
          :model-value="sort"
          @update:model-value="setSort"
        />

        <LoadingSpinner v-if="loading" />

        <div v-else class="item-grid">
          <template v-for="seg in cardSegments" :key="seg.key">
            <div
              v-if="seg.type === 'group'"
              class="group-heading item-grid-group"
              role="heading"
              aria-level="2"
            >
              <GroupHeader
                :label="seg.label"
                :count="seg.count"
                :collapsed="seg.collapsed"
                @toggle="toggleGroup(seg.groupKey)"
              />
            </div>
            <ItemCard
              v-else
              :item="seg.row"
              :has-loans="cat.hasLoans"
              :to="`${cat.routeBase}/${seg.row.id}`"
              :selecting="selecting"
              :selected="selectedIds.includes(seg.row.id)"
              @toggle-select="toggleSelect(seg.row)"
            />
          </template>
        </div>

        <p v-if="!loading && !items.length" class="empty-note">
          {{ filtered ? "Keine Einträge für diese Filter." : "Noch keine Einträge." }}
          <button v-if="filtered" type="button" class="btn-sm" @click="resetFilters">
            Filter zurücksetzen
          </button>
        </p>
      </template>

      <InfiniteLoader
        :has-more="hasMore"
        :loading="loading || loadingMore"
        :error="items.length ? error : ''"
        :count="items.length"
        :total="total"
        @load-more="loadMore"
      />
    </template>

    <BulkCategoryBar
      v-if="selecting"
      :count="selectedIds.length"
      :busy="bulkBusy"
      :message="bulkMessage"
      :error="bulkError"
      @select-all="selectAllLoaded"
      @add="pickMode = 'add'"
      @remove="pickMode = 'remove'"
      @done="stopSelecting"
    />
    <CategoryPickDialog
      v-if="cat.hasCategories"
      :open="pickMode !== null"
      :mode="pickMode || 'add'"
      :categories="typeOptions"
      @confirm="applyBulk"
      @cancel="pickMode = null"
    />

    <ItemFormModal
      :open="showCreateModal"
      :category="category"
      :item-id="null"
      :currencies="currencies"
      @save="onModalSave"
      @close="showCreateModal = false"
    />
  </div>
</template>

<style scoped>
:deep(td.col-num),
:deep(th.col-num) {
  text-align: right;
  width: 1%;
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}

.header-actions {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

.list-count {
  font-variant-numeric: tabular-nums;
  color: var(--color-muted);
  margin: 0 0 var(--space-2);
}

.item-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: var(--space-4);
}

.group-heading {
  margin: 0;
  font: inherit;
}

.item-grid-group {
  grid-column: 1 / -1;
}

.item-grid-group :deep(.group-header) {
  border-radius: var(--radius-sm);
}

@media (max-width: 640px) {
  .item-grid {
    grid-template-columns: 1fr;
    gap: var(--space-2);
  }
}

.list-alert {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  flex-wrap: wrap;
  margin-bottom: var(--space-4);
}

.empty-note {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
  margin-bottom: var(--space-4);
}

.grid-sort {
  margin-bottom: var(--space-3);
  justify-content: flex-end;
}
</style>
