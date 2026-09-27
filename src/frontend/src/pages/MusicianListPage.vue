<script setup>
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { get } from "../lib/api.js";
import { registerLabels } from "../lib/musicians.js";
import { sortRegisters } from "../lib/registers.js";
import { useListQuery } from "../composables/useListQuery.js";
import DataTable from "../components/DataTable.vue";
import SearchBar from "../components/SearchBar.vue";
import FilterBar from "../components/FilterBar.vue";
import InfiniteLoader from "../components/InfiniteLoader.vue";

const router = useRouter();
const registers = ref([]);

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
} = useListQuery({
  endpoint: "/musicians",
  filters: {
    search: { type: "string", default: "", debounce: true },
    is_active: { type: "bool", default: true },
    register_id__in: { type: "list", default: [] },
    is_extern: { type: "bool", default: null },
  },
  defaultSort: "last_name",
  mapItem: (m) => ({
    ...m,
    registers_label: registerLabels(m),
    is_extern_label: m.is_extern ? "Ja" : "Nein",
  }),
});

const filterDefs = computed(() => [
  {
    key: "is_active",
    label: "Status",
    type: "segmented",
    options: [
      { value: true, label: "Aktiv" },
      { value: false, label: "Inaktiv" },
      { value: null, label: "Alle" },
    ],
  },
  {
    key: "register_id__in",
    label: "Register",
    type: "multiselect",
    options: registers.value.map((r) => ({ value: String(r.id), label: r.label })),
  },
  {
    key: "is_extern",
    label: "Herkunft",
    type: "segmented",
    options: [
      { value: null, label: "Alle" },
      { value: false, label: "Verein" },
      { value: true, label: "Extern" },
    ],
  },
]);

const filtered = computed(() => activeFilterCount.value > 0 || !!state.search.trim());

const columns = [
  { key: "last_name", label: "Nachname", sortKey: "last_name" },
  { key: "first_name", label: "Vorname", sortKey: "first_name" },
  { key: "registers_label", label: "Register" },
  { key: "city", label: "Ort" },
  { key: "phone", label: "Telefon" },
  { key: "is_extern_label", label: "Extern" },
];

onMounted(async () => {
  try {
    registers.value = sortRegisters(await get("/registers"));
  } catch {
    registers.value = [];
  }
});

function goTo(row) {
  router.push(`/musiker/${row.id}`);
}
</script>

<template>
  <div>
    <div class="page-header">
      <h1>Musiker</h1>
      <router-link to="/musiker/neu" class="btn btn-primary"> Neuer Musiker </router-link>
    </div>

    <div class="toolbar">
      <SearchBar v-model="state.search" placeholder="Suche (Name, Ort, E-Mail …)" class="grow" />
    </div>

    <FilterBar
      :defs="filterDefs"
      :state="state"
      :defaults="defaults"
      @change="setFilter"
      @reset="resetFilters"
    />

    <div v-if="error && !items.length" class="alert alert-danger list-alert" role="alert">
      Musiker konnten nicht geladen werden: {{ error }}
      <button type="button" class="btn-sm" @click="reload">Erneut versuchen</button>
    </div>

    <template v-else>
      <DataTable
        :columns="columns"
        :rows="items"
        :loading="loading"
        :card-breakpoint="480"
        :sort="sort"
        :empty-text="filtered ? 'Keine Musiker für diese Filter.' : 'Noch keine Musiker erfasst.'"
        @update:sort="setSort"
        @row-click="goTo"
      >
        <template #last_name="{ row, value }">
          <span :class="{ 'text-muted': row.is_active === false }">{{ value }}</span>
          <span v-if="row.is_active === false" class="badge badge-gray inactive-badge"
            >inaktiv</span
          >
        </template>
        <template #first_name="{ row, value }">
          <span :class="{ 'text-muted': row.is_active === false }">{{ value }}</span>
        </template>
      </DataTable>

      <p v-if="!loading && !items.length && filtered" class="empty-note">
        <button type="button" class="btn-sm" @click="resetFilters">Filter zurücksetzen</button>
      </p>

      <InfiniteLoader
        :has-more="hasMore"
        :loading="loadingMore"
        :error="items.length ? error : ''"
        :count="items.length"
        :total="total"
        @load-more="loadMore"
      />
    </template>
  </div>
</template>

<style scoped>
.inactive-badge {
  margin-left: var(--space-2);
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
</style>
