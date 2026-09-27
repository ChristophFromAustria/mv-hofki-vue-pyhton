<script setup>
import { ref, computed, onMounted, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { get } from "../lib/api.js";
import {
  ACTIVE_FILTERS,
  activeFilterQueryValue,
  DEFAULT_ACTIVE_FILTER,
  buildMusicianQuery,
  parseActiveFilter,
  parseRegisterFilter,
  registerLabels,
} from "../lib/musicians.js";
import { sortRegisters } from "../lib/registers.js";
import DataTable from "../components/DataTable.vue";
import SearchBar from "../components/SearchBar.vue";

const route = useRoute();
const router = useRouter();
const items = ref([]);
const total = ref(0);
const loading = ref(true);
const error = ref("");
const registers = ref([]);
const search = ref(typeof route.query.search === "string" ? route.query.search : "");
const active = ref(parseActiveFilter(route.query.active));
const registerId = ref(parseRegisterFilter(route.query.register));
const limit = 50;
const offset = ref(0);

const columns = [
  { key: "last_name", label: "Nachname" },
  { key: "first_name", label: "Vorname" },
  { key: "registers_label", label: "Register" },
  { key: "city", label: "Ort" },
  { key: "phone", label: "Telefon" },
  { key: "is_extern_label", label: "Extern" },
];

let requestSeq = 0;
async function load() {
  const seq = ++requestSeq;
  loading.value = true;
  error.value = "";
  try {
    const query = buildMusicianQuery({
      active: active.value,
      registerId: registerId.value,
      search: search.value,
      limit,
      offset: offset.value,
    });
    const data = await get(`/musicians?${query}`);
    if (seq !== requestSeq) return;
    items.value = data.items.map((m) => ({
      ...m,
      registers_label: registerLabels(m),
      is_extern_label: m.is_extern ? "Ja" : "Nein",
    }));
    total.value = data.total;
  } catch (e) {
    if (seq !== requestSeq) return;
    items.value = [];
    total.value = 0;
    error.value = e.message;
  } finally {
    if (seq === requestSeq) loading.value = false;
  }
}

/** Keep the filters in the URL so "Zurück" from a detail page restores them. */
function syncQuery() {
  const query = {};
  const activeQuery = activeFilterQueryValue(active.value);
  if (activeQuery) query.active = activeQuery;
  if (registerId.value) query.register = registerId.value;
  if (search.value.trim()) query.search = search.value.trim();
  router.replace({ query });
}

onMounted(async () => {
  load();
  try {
    registers.value = sortRegisters(await get("/registers"));
  } catch {
    registers.value = [];
  }
});

function applyFilters() {
  offset.value = 0;
  syncQuery();
  load();
}

watch([active, registerId], applyFilters);

let searchTimeout;
watch(search, () => {
  clearTimeout(searchTimeout);
  searchTimeout = setTimeout(applyFilters, 300);
});

const filtersChanged = computed(
  () => !!search.value.trim() || !!registerId.value || active.value !== DEFAULT_ACTIVE_FILTER,
);

function resetFilters() {
  search.value = "";
  active.value = DEFAULT_ACTIVE_FILTER;
  registerId.value = "";
}

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

    <div class="toolbar musician-toolbar">
      <SearchBar v-model="search" placeholder="Suche (Name, Ort, E-Mail …)" class="grow" />
      <div class="view-toggle" role="group" aria-label="Status">
        <button
          v-for="f in ACTIVE_FILTERS"
          :key="f.value"
          type="button"
          :class="{ active: active === f.value }"
          :aria-pressed="active === f.value"
          @click="active = f.value"
        >
          {{ f.label }}
        </button>
      </div>
      <label class="sr-only" for="register-filter">Register</label>
      <select id="register-filter" v-model="registerId" class="register-filter">
        <option value="">Alle Register</option>
        <option v-for="r in registers" :key="r.id" :value="String(r.id)">{{ r.label }}</option>
      </select>
    </div>

    <div v-if="error" class="alert alert-danger list-alert" role="alert">
      Musiker konnten nicht geladen werden: {{ error }}
      <button type="button" class="btn-sm" @click="load">Erneut versuchen</button>
    </div>

    <p v-else-if="!loading && !items.length && filtersChanged" class="empty-note">
      Keine Musiker für diese Filter.
      <button type="button" class="btn-sm" @click="resetFilters">Filter zurücksetzen</button>
    </p>

    <DataTable
      v-if="!error"
      :columns="columns"
      :rows="items"
      :loading="loading"
      :card-breakpoint="480"
      @row-click="goTo"
    >
      <template #last_name="{ row, value }">
        <span :class="{ 'text-muted': row.is_active === false }">{{ value }}</span>
        <span v-if="row.is_active === false" class="badge badge-gray inactive-badge">inaktiv</span>
      </template>
      <template #first_name="{ row, value }">
        <span :class="{ 'text-muted': row.is_active === false }">{{ value }}</span>
      </template>
    </DataTable>

    <div v-if="total > limit" class="pagination">
      <span>{{ offset + 1 }}–{{ Math.min(offset + limit, total) }} von {{ total }}</span>
      <div class="cluster">
        <button
          class="btn-sm"
          :disabled="offset === 0"
          @click="
            offset -= limit;
            load();
          "
        >
          Zurück
        </button>
        <button
          class="btn-sm"
          :disabled="offset + limit >= total"
          @click="
            offset += limit;
            load();
          "
        >
          Weiter
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.musician-toolbar {
  flex-wrap: wrap;
}

.musician-toolbar .view-toggle button {
  min-height: 44px;
}

.register-filter {
  width: auto;
  min-width: 12rem;
  min-height: 44px;
}

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

@media (max-width: 480px) {
  .register-filter {
    flex: 1 1 100%;
  }
}
</style>
