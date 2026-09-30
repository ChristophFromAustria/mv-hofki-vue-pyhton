<script setup>
import { computed, onMounted, ref } from "vue";
import { get } from "../lib/api.js";
import { ACTION_OPTIONS, AREA_OPTIONS } from "../lib/events.js";
import { useListQuery } from "../composables/useListQuery.js";
import EventList from "../components/EventList.vue";
import FilterBar from "../components/FilterBar.vue";
import InfiniteLoader from "../components/InfiniteLoader.vue";
import LoadingSpinner from "../components/LoadingSpinner.vue";
import SearchBar from "../components/SearchBar.vue";

// Protokoll: every recorded change, newest first (docs/konzept-papierkorb-protokoll.md).
const actors = ref([]);

const {
  state,
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
  endpoint: "/events",
  filters: {
    search: { type: "string", default: "", debounce: true },
    area: { type: "string", default: "" },
    actor: { type: "string", default: "" },
    action: { type: "string", default: "" },
    date_from: { type: "string", default: "" },
    date_to: { type: "string", default: "" },
    // From a record's "Verlauf" link; not offered as a filter control.
    item_id: { type: "number", default: null },
    musician_id: { type: "number", default: null },
  },
  defaultSort: "-at",
});

const filterDefs = computed(() => [
  { key: "area", label: "Bereich", type: "select", options: AREA_OPTIONS },
  {
    key: "actor",
    label: "Person",
    type: "select",
    options: actors.value.map((a) => ({ value: a ?? "unknown", label: a ?? "unbekannt" })),
  },
  { key: "action", label: "Aktion", type: "select", options: ACTION_OPTIONS },
  { keys: ["date_from", "date_to"], label: "Zeitraum", type: "daterange" },
]);

const filtered = computed(
  () =>
    activeFilterCount.value > 0 ||
    !!state.search.trim() ||
    state.item_id != null ||
    state.musician_id != null,
);

onMounted(async () => {
  actors.value = await get("/events/actors").catch(() => []);
});

function clearRecord() {
  setFilter("item_id", null);
  setFilter("musician_id", null);
}
</script>

<template>
  <div>
    <div class="page-header">
      <h1>Protokoll</h1>
    </div>

    <div class="toolbar">
      <SearchBar v-model="state.search" placeholder="Suche (Gegenstand, Name …)" class="grow" />
    </div>

    <FilterBar
      :defs="filterDefs"
      :state="state"
      :defaults="defaults"
      @change="setFilter"
      @reset="resetFilters"
    />

    <p v-if="state.item_id != null || state.musician_id != null" class="record-filter">
      Nur {{ state.item_id != null ? "dieser Gegenstand" : "dieser Musiker" }}
      <button type="button" class="btn-sm" @click="clearRecord">Alle anzeigen</button>
    </p>

    <p v-if="!loading && !error" class="list-count">
      {{ total }} {{ total === 1 ? "Eintrag" : "Einträge" }}
    </p>

    <div v-if="error && !items.length" class="alert alert-danger" role="alert">
      Protokoll konnte nicht geladen werden: {{ error }}
      <button type="button" class="btn-sm" @click="reload">Erneut versuchen</button>
    </div>
    <LoadingSpinner v-else-if="loading && !items.length" />
    <p v-else-if="!items.length" class="empty-note">
      {{ filtered ? "Keine Einträge für diese Filter." : "Noch keine Einträge." }}
      <button v-if="filtered" type="button" class="btn-sm" @click="resetFilters">
        Filter zurücksetzen
      </button>
    </p>
    <EventList v-else :events="items" />

    <InfiniteLoader
      :has-more="hasMore"
      :loading="loading || loadingMore"
      :error="items.length ? error : ''"
      :count="items.length"
      :total="total"
      @load-more="loadMore"
    />
  </div>
</template>

<style scoped>
.list-count {
  font-variant-numeric: tabular-nums;
  color: var(--color-muted);
  margin: var(--space-2) 0;
}

.record-filter {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin: var(--space-2) 0 0;
}
</style>
