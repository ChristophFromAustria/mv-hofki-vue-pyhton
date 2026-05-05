<script setup>
import { ref, onMounted, watch, computed } from "vue";
import { useRouter } from "vue-router";
import { get } from "../lib/api.js";
import { CATEGORIES } from "../lib/categories.js";
import DataTable from "../components/DataTable.vue";
import SearchBar from "../components/SearchBar.vue";
import ItemFormModal from "../components/ItemFormModal.vue";

const props = defineProps({
  category: { type: String, required: true },
});

const router = useRouter();
const cat = computed(() => CATEGORIES[props.category]);
const items = ref([]);
const total = ref(0);
const loading = ref(true);
const search = ref("");
const limit = 50;
const offset = ref(0);
const viewMode = ref(localStorage.getItem(props.category + "-view-mode") || "list");
const showCreateModal = ref(false);
const currencies = ref([]);

watch(viewMode, (v) => localStorage.setItem(props.category + "-view-mode", v));

const columns = computed(() => {
  switch (props.category) {
    case "instrument":
      return [
        { key: "display_nr", label: "Inv.-Nr." },
        { key: "type_label", label: "Typ" },
        { key: "manufacturer", label: "Hersteller" },
        { key: "serial_nr", label: "Seriennr." },
        { key: "owner", label: "Eigentümer" },
        { key: "status_label", label: "Status" },
      ];
    case "clothing":
      return [
        { key: "display_nr", label: "Inv.-Nr." },
        { key: "type_label", label: "Typ" },
        { key: "size", label: "Größe" },
        { key: "gender", label: "Geschlecht" },
        { key: "owner", label: "Eigentümer" },
        { key: "status_label", label: "Status" },
      ];
    case "sheet_music":
      return [
        { key: "display_nr", label: "Inv.-Nr." },
        { key: "label", label: "Titel" },
        { key: "composer", label: "Komponist" },
        { key: "arranger", label: "Arrangeur" },
        { key: "genre_label", label: "Gattung" },
      ];
    case "general_item":
      return [
        { key: "display_nr", label: "Inv.-Nr." },
        { key: "label", label: "Bezeichnung" },
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
  };
  if (props.category === "instrument") {
    mapped.type_label = i.instrument_type?.label || "";
  } else if (props.category === "clothing") {
    mapped.type_label = i.clothing_type?.label || "";
  } else if (props.category === "sheet_music") {
    mapped.genre_label = i.genre?.label || "";
  }
  if (cat.value.hasLoans) {
    mapped.status_label = i.active_loan ? "Ausgeliehen" : "Verfügbar";
  }
  return mapped;
}

async function load() {
  loading.value = true;
  try {
    const params = new URLSearchParams();
    params.set("category", props.category);
    params.set("limit", limit);
    params.set("offset", offset.value);
    if (search.value) params.set("search", search.value);
    const data = await get(`/items?${params}`);
    items.value = data.items.map(mapItem);
    total.value = data.total;
  } finally {
    loading.value = false;
  }
}

onMounted(async () => {
  currencies.value = await get("/currencies");
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

// Reload when category changes (same component, different route)
watch(
  () => props.category,
  () => {
    search.value = "";
    offset.value = 0;
    viewMode.value = localStorage.getItem(props.category + "-view-mode") || "list";
    load();
  },
);

function goTo(row) {
  router.push(cat.value.routeBase + "/" + row.id);
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

function onModalSave() {
  load();
}
</script>

<template>
  <div>
    <div class="page-header">
      <h1>{{ cat.label }}</h1>
      <button class="btn btn-primary" @click="showCreateModal = true">
        {{ cat.labelSingular }} anlegen
      </button>
    </div>

    <div class="toolbar">
      <SearchBar v-model="search" placeholder="Suche..." class="grow" />
      <div class="view-toggle">
        <button :class="{ active: viewMode === 'list' }" @click="viewMode = 'list'">Liste</button>
        <button :class="{ active: viewMode === 'card' }" @click="viewMode = 'card'">Karten</button>
      </div>
    </div>

    <DataTable
      v-if="viewMode === 'list'"
      :columns="columns"
      :rows="items"
      :loading="loading"
      :card-breakpoint="640"
      @row-click="goTo"
    />

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
          <h3>{{ item.label }}</h3>
          <p>{{ item.display_nr }} {{ item.manufacturer ? "· " + item.manufacturer : "" }}</p>
        </div>
        <div v-if="cat.hasLoans" class="instrument-card-footer">
          <span :class="item.active_loan ? 'badge badge-green' : 'badge badge-gray'">
            {{ item.active_loan ? "Ausgeliehen" : "Verfügbar" }}
          </span>
        </div>
      </div>
    </div>

    <div v-if="total > limit" class="pagination">
      <span>{{ offset + 1 }}–{{ Math.min(offset + limit, total) }} von {{ total }}</span>
      <div style="display: flex; gap: 0.5rem">
        <button class="btn-sm" :disabled="offset === 0" @click="prevPage">Zurück</button>
        <button class="btn-sm" :disabled="offset + limit >= total" @click="nextPage">Weiter</button>
      </div>
    </div>

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
</style>
