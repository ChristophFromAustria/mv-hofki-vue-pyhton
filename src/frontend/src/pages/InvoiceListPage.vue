<script setup>
import { ref, onMounted, watch } from "vue";
import { useRouter } from "vue-router";
import { get } from "../lib/api.js";
import { CATEGORIES } from "../lib/categories.js";
import SearchBar from "../components/SearchBar.vue";

const router = useRouter();
const invoices = ref([]);
const total = ref(0);
const totalsByCurrency = ref([]);
const loading = ref(true);
const search = ref("");
const categoryFilter = ref("");
const dateFrom = ref("");
const dateTo = ref("");
const limit = 50;
const offset = ref(0);

const categoryOptions = [
  { value: "", label: "Alle" },
  { value: "instrument", label: "Instrumente" },
  { value: "clothing", label: "Kleidung" },
  { value: "general_item", label: "Allgemein" },
];

async function load() {
  loading.value = true;
  try {
    const params = new URLSearchParams();
    if (categoryFilter.value) params.set("category", categoryFilter.value);
    if (search.value) params.set("search", search.value);
    if (dateFrom.value) params.set("date_from", dateFrom.value);
    if (dateTo.value) params.set("date_to", dateTo.value);
    params.set("limit", limit);
    params.set("offset", offset.value);
    const data = await get(`/invoices?${params}`);
    invoices.value = data.items;
    total.value = data.total;
    totalsByCurrency.value = data.totals_by_currency || [];
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

watch([categoryFilter, dateFrom, dateTo], () => {
  offset.value = 0;
  load();
});

function goToItem(inv) {
  const cat = CATEGORIES[inv.item_category];
  if (cat) {
    router.push(cat.routeBase + "/" + inv.item_id);
  }
}

function formatTotals() {
  return totalsByCurrency.value
    .map(
      (t) =>
        `${Number(t.total).toLocaleString("de-AT", { minimumFractionDigits: 2 })} ${t.abbreviation}`,
    )
    .join(" \u00B7 ");
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
      <h1>Rechnungen</h1>
    </div>

    <div class="toolbar">
      <select v-model="categoryFilter" style="width: 160px">
        <option v-for="opt in categoryOptions" :key="opt.value" :value="opt.value">
          {{ opt.label }}
        </option>
      </select>
      <input v-model="dateFrom" type="date" style="width: 160px" placeholder="Von" />
      <input v-model="dateTo" type="date" style="width: 160px" placeholder="Bis" />
      <SearchBar v-model="search" placeholder="Suche..." class="grow" />
    </div>

    <div v-if="loading" style="padding: 2rem; text-align: center; color: var(--color-muted)">
      Laden...
    </div>

    <table v-else-if="invoices.length">
      <thead>
        <tr>
          <th>Nr.</th>
          <th>Gegenstand</th>
          <th>Bezeichnung</th>
          <th>Datum</th>
          <th>Betrag</th>
          <th>Datei</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="inv in invoices" :key="inv.id" style="cursor: pointer" @click="goToItem(inv)">
          <td>{{ inv.invoice_nr }}</td>
          <td>{{ inv.item_display_nr }} {{ inv.item_label }}</td>
          <td>{{ inv.title }}</td>
          <td>{{ inv.date_issued }}</td>
          <td>{{ inv.amount }} {{ inv.currency?.abbreviation || "" }}</td>
          <td>
            <span v-if="inv.filename" class="badge badge-green">Ja</span>
            <span v-else class="badge badge-gray">Nein</span>
          </td>
        </tr>
      </tbody>
    </table>

    <div v-else style="padding: 2rem; text-align: center; color: var(--color-muted)">
      Keine Rechnungen gefunden.
    </div>

    <div
      v-if="totalsByCurrency.length"
      style="
        margin-top: 1rem;
        padding: 0.75rem 1rem;
        background: var(--color-bg-soft);
        border-radius: 6px;
        font-weight: 600;
      "
    >
      Gesamt: {{ formatTotals() }}
    </div>

    <div v-if="total > limit" class="pagination">
      <span>{{ offset + 1 }}–{{ Math.min(offset + limit, total) }} von {{ total }}</span>
      <div style="display: flex; gap: 0.5rem">
        <button class="btn-sm" :disabled="offset === 0" @click="prevPage">Zurück</button>
        <button class="btn-sm" :disabled="offset + limit >= total" @click="nextPage">Weiter</button>
      </div>
    </div>
  </div>
</template>
