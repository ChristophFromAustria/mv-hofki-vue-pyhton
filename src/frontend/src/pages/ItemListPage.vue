<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { get } from "../lib/api.js";
import { CATEGORIES } from "../lib/categories.js";
import { hasMultipleQuantities, quantityCell, quantityLabel } from "../lib/quantity.js";
import { useListQuery } from "../composables/useListQuery.js";
import DataTable from "../components/DataTable.vue";
import SearchBar from "../components/SearchBar.vue";
import FilterBar from "../components/FilterBar.vue";
import InfiniteLoader from "../components/InfiniteLoader.vue";
import SortSelect from "../components/SortSelect.vue";
import LoadingSpinner from "../components/LoadingSpinner.vue";
import CategoryChips from "../components/CategoryChips.vue";
import ItemFormModal from "../components/ItemFormModal.vue";

const props = defineProps({
  category: { type: String, required: true },
});

const router = useRouter();
const cat = computed(() => CATEGORIES[props.category]);
const viewMode = ref(localStorage.getItem(props.category + "-view-mode") || "card");
const showCreateModal = ref(false);
const currencies = ref([]);

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
  { value: "verliehen", label: "Verliehen" },
];

const search = { type: "string", default: "", debounce: true };
const FILTERS = {
  instrument: {
    search,
    instrument_type_id__in: { type: "list", default: [] },
    status: { type: "string", default: "" },
    owner: { type: "string", default: "" },
    construction_year__gte: { type: "number", default: null },
    construction_year__lte: { type: "number", default: null },
  },
  clothing: {
    search,
    clothing_type_id__in: { type: "list", default: [] },
    size: { type: "string", default: "" },
    gender: { type: "string", default: "" },
    status: { type: "string", default: "" },
  },
  sheet_music: {
    search,
    genre_id__in: { type: "list", default: [] },
    difficulty: { type: "string", default: "" },
    storage_location__ilike: { type: "string", default: "", debounce: true },
  },
  general_item: {
    search,
    category_id__in: { type: "list", default: [] },
    without_category: { type: "bool", default: null },
    storage_location__ilike: { type: "string", default: "", debounce: true },
    status: { type: "string", default: "" },
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
  loading,
  loadingMore,
  error,
  hasMore,
  loadMore,
  reload,
  resetFilters,
} = list;

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
      ];
    case "clothing":
      return [
        { key: "display_nr", label: "Inv.-Nr.", sortKey: "number" },
        { key: "type_label", label: "Typ", sortKey: "type" },
        { key: "size", label: "Größe", sortKey: "size" },
        { key: "gender", label: "Geschlecht" },
        { key: "owner", label: "Eigentümer" },
        { key: "status_label", label: "Status" },
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
  }
  return mapped;
}

onMounted(async () => {
  const [cur, types, facetData] = await Promise.all([
    get("/currencies"),
    get(TYPE_ENDPOINTS[props.category]).catch(() => []),
    get(`/items/facets?category=${props.category}`).catch(() => ({})),
  ]);
  currencies.value = cur;
  typeOptions.value = types;
  facets.value = facetData;
});

function goTo(row) {
  router.push(cat.value.routeBase + "/" + row.id);
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
        <button class="btn btn-primary" @click="showCreateModal = true">
          {{ cat.labelSingular }} anlegen
        </button>
      </div>
    </div>

    <div class="toolbar">
      <SearchBar v-model="state.search" placeholder="Suche..." class="grow" />
      <div class="view-toggle">
        <button :class="{ active: viewMode === 'list' }" @click="viewMode = 'list'">Liste</button>
        <button :class="{ active: viewMode === 'card' }" @click="viewMode = 'card'">Karten</button>
      </div>
    </div>

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
    </div>

    <template v-else>
      <DataTable
        v-if="viewMode === 'list'"
        :columns="columns"
        :rows="items"
        :loading="loading"
        :card-breakpoint="640"
        :sort="sort"
        :empty-text="filtered ? 'Keine Einträge für diese Filter.' : 'Noch keine Einträge.'"
        @update:sort="setSort"
        @row-click="goTo"
      >
        <template #categories="{ value }">
          <CategoryChips :categories="value || []" />
        </template>
      </DataTable>

      <template v-else>
        <SortSelect
          v-if="sortOptions.length"
          class="grid-sort"
          :options="sortOptions"
          :model-value="sort"
          @update:model-value="setSort"
        />

        <LoadingSpinner v-if="loading" />

        <div v-else class="instrument-grid">
          <div v-for="item in items" :key="item.id" class="instrument-card" @click="goTo(item)">
            <div class="instrument-card-img">
              <img
                v-if="item.profile_image_url"
                :src="item.profile_image_url"
                style="width: 100%; height: 120px; object-fit: cover"
              />
              <div v-else class="card-placeholder">
                <span>{{ item.display_nr }}</span>
              </div>
            </div>
            <div class="instrument-card-body">
              <h3>
                {{ item.label }}
                <span v-if="item.quantity_label" class="card-quantity">{{
                  item.quantity_label
                }}</span>
              </h3>
              <p>{{ item.display_nr }} {{ item.manufacturer ? "· " + item.manufacturer : "" }}</p>
              <CategoryChips v-if="item.categories?.length" :categories="item.categories" />
            </div>
            <div v-if="cat.hasLoans" class="instrument-card-footer">
              <span :class="item.active_loan ? 'badge badge-green' : 'badge badge-gray'">
                {{ item.active_loan ? "Ausgeliehen" : "Verfügbar" }}
              </span>
            </div>
          </div>
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
        :loading="loadingMore"
        :error="items.length ? error : ''"
        :count="items.length"
        :total="total"
        @load-more="loadMore"
      />
    </template>

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

.card-quantity {
  margin-left: var(--space-1);
  font-weight: 500;
  color: var(--color-muted);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.header-actions {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

.card-placeholder {
  width: 100%;
  height: 120px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-bg-soft);
  color: var(--color-muted);
  font-size: 1.2rem;
  font-weight: 600;
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
