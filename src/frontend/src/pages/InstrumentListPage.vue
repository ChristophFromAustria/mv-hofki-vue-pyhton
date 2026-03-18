<script setup>
import { ref, onMounted, watch } from "vue";
import { useRouter } from "vue-router";
import { get } from "../lib/api.js";
import DataTable from "../components/DataTable.vue";
import SearchBar from "../components/SearchBar.vue";

const router = useRouter();
const items = ref([]);
const total = ref(0);
const loading = ref(true);
const search = ref("");
const typeFilter = ref("");
const types = ref([]);
const limit = 50;
const offset = ref(0);

const columns = [
  { key: "inventory_nr", label: "Inv.-Nr." },
  { key: "type_label", label: "Typ" },
  { key: "manufacturer", label: "Hersteller" },
  { key: "serial_nr", label: "Seriennr." },
  { key: "owner", label: "Eigentümer" },
];

async function load() {
  loading.value = true;
  try {
    const params = new URLSearchParams();
    params.set("limit", limit);
    params.set("offset", offset.value);
    if (search.value) params.set("search", search.value);
    if (typeFilter.value) params.set("type_id", typeFilter.value);
    const data = await get(`/instruments?${params}`);
    items.value = data.items.map((i) => ({
      ...i,
      type_label: i.instrument_type?.label || "",
    }));
    total.value = data.total;
  } finally {
    loading.value = false;
  }
}

onMounted(async () => {
  types.value = await get("/instrument-types");
  await load();
});

let searchTimeout;
watch(search, () => {
  clearTimeout(searchTimeout);
  searchTimeout = setTimeout(() => {
    offset.value = 0;
    load();
  }, 300);
});

watch(typeFilter, () => {
  offset.value = 0;
  load();
});

function goTo(row) {
  router.push(`/instrumente/${row.id}`);
}
function prevPage() {
  if (offset.value > 0) {
    offset.value -= limit;
    load();
  }
}
function nextPage() {
  if (offset.value + limit < total.value) {
    offset.value += limit;
    load();
  }
}
</script>

<template>
  <div>
    <div class="page-header">
      <h1>Instrumente</h1>
      <router-link to="/instrumente/neu" class="btn btn-primary"> Neues Instrument </router-link>
    </div>

    <div class="toolbar">
      <SearchBar v-model="search" placeholder="Suche (Hersteller, Seriennr...)" class="grow" />
      <select v-model="typeFilter" style="max-width: 200px">
        <option value="">Alle Typen</option>
        <option v-for="t in types" :key="t.id" :value="t.id">
          {{ t.label }}
        </option>
      </select>
    </div>

    <DataTable :columns="columns" :rows="items" :loading="loading" @row-click="goTo" />

    <div v-if="total > limit" class="pagination">
      <span>{{ offset + 1 }}–{{ Math.min(offset + limit, total) }} von {{ total }}</span>
      <div style="display: flex; gap: 0.5rem">
        <button class="btn-sm" :disabled="offset === 0" @click="prevPage">Zurück</button>
        <button class="btn-sm" :disabled="offset + limit >= total" @click="nextPage">Weiter</button>
      </div>
    </div>
  </div>
</template>
