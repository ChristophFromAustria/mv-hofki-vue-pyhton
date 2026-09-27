<script setup>
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { get } from "../lib/api.js";
import { CATEGORIES } from "../lib/categories.js";
import { useListQuery } from "../composables/useListQuery.js";
import DataTable from "../components/DataTable.vue";
import SearchBar from "../components/SearchBar.vue";
import FilterBar from "../components/FilterBar.vue";
import InfiniteLoader from "../components/InfiniteLoader.vue";

const router = useRouter();
const currencies = ref([]);

const {
  state,
  sort,
  setSort,
  setFilter,
  defaults,
  activeFilterCount,
  items,
  total,
  lastResponse,
  loading,
  loadingMore,
  error,
  hasMore,
  loadMore,
  reload,
  resetFilters,
} = useListQuery({
  endpoint: "/invoices",
  filters: {
    search: { type: "string", default: "", debounce: true },
    item_category: { type: "string", default: "" },
    date_issued__gte: { type: "date", default: "" },
    date_issued__lte: { type: "date", default: "" },
    currency_id: { type: "number", default: null },
  },
  defaultSort: "-date_issued",
});

const filterDefs = computed(() => [
  {
    key: "item_category",
    label: "Inventar-Art",
    type: "select",
    options: ["instrument", "clothing", "general_item"].map((c) => ({
      value: c,
      label: CATEGORIES[c].label,
    })),
  },
  { keys: ["date_issued__gte", "date_issued__lte"], label: "Datum", type: "daterange" },
  {
    key: "currency_id",
    label: "Währung",
    type: "select",
    options: currencies.value.map((c) => ({ value: String(c.id), label: c.abbreviation })),
  },
]);

const filtered = computed(() => activeFilterCount.value > 0 || !!state.search.trim());
const totalsByCurrency = computed(() => lastResponse.value?.totals_by_currency || []);

const columns = [
  { key: "invoice_nr", label: "Nr.", class: "col-num" },
  { key: "item", label: "Gegenstand" },
  { key: "title", label: "Bezeichnung" },
  { key: "invoice_issuer", label: "Aussteller", sortKey: "invoice_issuer", hideEmptyInCard: true },
  { key: "date_issued", label: "Datum", sortKey: "date_issued" },
  { key: "amount", label: "Betrag", sortKey: "amount", class: "col-num" },
  { key: "filename", label: "Datei" },
];

function formatAmount(inv) {
  const n = Number(inv.amount).toLocaleString("de-AT", { minimumFractionDigits: 2 });
  return `${n} ${inv.currency?.abbreviation || ""}`;
}

function formatTotals() {
  return totalsByCurrency.value
    .map(
      (t) =>
        `${Number(t.total).toLocaleString("de-AT", { minimumFractionDigits: 2 })} ${t.abbreviation}`,
    )
    .join(" · ");
}

onMounted(async () => {
  try {
    currencies.value = await get("/currencies");
  } catch {
    currencies.value = [];
  }
});

function goToItem(inv) {
  const cat = CATEGORIES[inv.item_category];
  if (cat) router.push(cat.routeBase + "/" + inv.item_id);
}
</script>

<template>
  <div>
    <div class="page-header">
      <h1>Rechnungen</h1>
    </div>

    <div class="toolbar">
      <SearchBar v-model="state.search" placeholder="Suche (Titel, Aussteller …)" class="grow" />
    </div>

    <FilterBar
      :defs="filterDefs"
      :state="state"
      :defaults="defaults"
      @change="setFilter"
      @reset="resetFilters"
    />

    <div v-if="error && !items.length" class="alert alert-danger list-alert" role="alert">
      Rechnungen konnten nicht geladen werden: {{ error }}
      <button type="button" class="btn-sm" @click="reload">Erneut versuchen</button>
      <button type="button" class="btn-sm" @click="resetFilters">Filter zurücksetzen</button>
    </div>

    <template v-else>
      <p v-if="totalsByCurrency.length" class="invoice-totals">
        Gesamt ({{ total }} {{ total === 1 ? "Rechnung" : "Rechnungen" }}): {{ formatTotals() }}
      </p>

      <DataTable
        :columns="columns"
        :rows="items"
        :loading="loading"
        :card-breakpoint="640"
        :sort="sort"
        :empty-text="filtered ? 'Keine Rechnungen für diese Filter.' : 'Noch keine Rechnungen.'"
        @update:sort="setSort"
        @row-click="goToItem"
      >
        <template #item="{ row }">{{ row.item_display_nr }} {{ row.item_label }}</template>
        <template #amount="{ row }">{{ formatAmount(row) }}</template>
        <template #filename="{ row }">
          <span :class="row.filename ? 'badge badge-green' : 'badge badge-gray'">
            {{ row.filename ? "Ja" : "Nein" }}
          </span>
        </template>
      </DataTable>

      <p v-if="!loading && !items.length && filtered" class="empty-note">
        <button type="button" class="btn-sm" @click="resetFilters">Filter zurücksetzen</button>
      </p>

      <InfiniteLoader
        :has-more="hasMore"
        :loading="loading || loadingMore"
        :error="items.length ? error : ''"
        :count="items.length"
        :total="total"
        @load-more="loadMore"
      />
    </template>
  </div>
</template>

<style scoped>
.invoice-totals {
  margin: 0 0 var(--space-3);
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius);
  background: var(--color-bg-soft);
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

:deep(td.col-num),
:deep(th.col-num) {
  text-align: right;
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}
</style>
