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
const limit = 50;
const offset = ref(0);

const columns = [
  { key: "last_name", label: "Nachname" },
  { key: "first_name", label: "Vorname" },
  { key: "city", label: "Ort" },
  { key: "phone", label: "Telefon" },
  { key: "is_extern_label", label: "Extern" },
];

async function load() {
  loading.value = true;
  try {
    const params = new URLSearchParams();
    params.set("limit", limit);
    params.set("offset", offset.value);
    if (search.value) params.set("search", search.value);
    const data = await get(`/musicians?${params}`);
    items.value = data.items.map((m) => ({
      ...m,
      is_extern_label: m.is_extern ? "Ja" : "Nein",
    }));
    total.value = data.total;
  } finally {
    loading.value = false;
  }
}

onMounted(load);

let searchTimeout;
watch(search, () => {
  clearTimeout(searchTimeout);
  searchTimeout = setTimeout(() => {
    offset.value = 0;
    load();
  }, 300);
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
      <SearchBar v-model="search" placeholder="Suche (Name, Ort, E-Mail...)" class="grow" />
    </div>

    <DataTable
      :columns="columns"
      :rows="items"
      :loading="loading"
      :card-breakpoint="480"
      @row-click="goTo"
    />

    <div v-if="total > limit" class="pagination">
      <span>{{ offset + 1 }}–{{ Math.min(offset + limit, total) }} von {{ total }}</span>
      <div style="display: flex; gap: 0.5rem">
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
