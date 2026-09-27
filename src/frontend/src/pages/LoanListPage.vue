<script setup>
import { computed, ref, watch } from "vue";
import { get, post, put } from "../lib/api.js";
import { CATEGORIES } from "../lib/categories.js";
import { fetchLoanableItemOptions, fetchMusicianOptions } from "../lib/pickers.js";
import { useListQuery } from "../composables/useListQuery.js";
import { useGroupCollapse } from "../composables/useGroupCollapse.js";
import DataTable from "../components/DataTable.vue";
import SearchBar from "../components/SearchBar.vue";
import FilterBar from "../components/FilterBar.vue";
import GroupSelect from "../components/GroupSelect.vue";
import InfiniteLoader from "../components/InfiniteLoader.vue";
import RemotePicker from "../components/RemotePicker.vue";

const GROUP_OPTIONS = [
  { key: "musician", label: "Musiker" },
  { key: "item_category", label: "Inventar-Art" },
  { key: "status", label: "Status" },
];

const showForm = ref(false);
const form = ref({ item_id: null, musician_id: null, start_date: "" });
const formErrors = ref({});
const formError = ref("");
const returningLoanId = ref(null);
const returnDate = ref("");
const actionError = ref("");
const filterMusicianLabel = ref("");

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
} = useListQuery({
  endpoint: "/loans",
  filters: {
    search: { type: "string", default: "", debounce: true },
    active: { type: "bool", default: true },
    item_category: { type: "string", default: "" },
    musician_id: { type: "number", default: null },
    group_by: { type: "string", default: "" },
  },
  defaultSort: "-start_date",
});

const collapseKey = computed(() => `loans:${state.group_by || "none"}`);
const { collapsed, toggle: toggleGroup } = useGroupCollapse(collapseKey);

const filterDefs = computed(() => [
  {
    key: "active",
    label: "Status",
    type: "segmented",
    options: [
      { value: true, label: "Offen" },
      { value: false, label: "Zurückgegeben" },
      { value: null, label: "Alle" },
    ],
  },
  {
    key: "item_category",
    label: "Inventar-Art",
    type: "select",
    options: ["instrument", "clothing", "general_item"].map((c) => ({
      value: c,
      label: CATEGORIES[c].label,
    })),
  },
]);

const filtered = computed(() => activeFilterCount.value > 0 || !!state.search.trim());

const columns = [
  { key: "item", label: "Gegenstand" },
  { key: "display_nr", label: "Inv.-Nr." },
  { key: "musician", label: "Musiker" },
  { key: "start_date", label: "Von", sortKey: "start_date" },
  { key: "end_date", label: "Bis", sortKey: "end_date" },
  { key: "status", label: "Status" },
  { key: "actions", label: "" },
];

// Musician filter label: fetched whenever the id changes to one we have not
// already shown (a picker @select already knows the label, see below).
const lastMusicianId = ref(null);

watch(
  () => state.musician_id,
  async (id) => {
    if (id == null) {
      filterMusicianLabel.value = "";
      lastMusicianId.value = null;
      return;
    }
    if (id === lastMusicianId.value) return;
    lastMusicianId.value = id;
    try {
      const m = await get(`/musicians/${id}`);
      filterMusicianLabel.value = `${m.last_name} ${m.first_name}`;
    } catch {
      filterMusicianLabel.value = "";
    }
  },
  { immediate: true },
);

function itemRouteBase(category) {
  return CATEGORIES[category]?.routeBase || "/instrumente";
}

function validateForm() {
  formErrors.value = {};
  if (!form.value.item_id) formErrors.value.item_id = "Pflichtfeld";
  if (!form.value.musician_id) formErrors.value.musician_id = "Pflichtfeld";
  if (!form.value.start_date) formErrors.value.start_date = "Pflichtfeld";
  return Object.keys(formErrors.value).length === 0;
}

async function createLoan() {
  formError.value = "";
  if (!validateForm()) return;
  try {
    await post("/loans", form.value);
    showForm.value = false;
    form.value = { item_id: null, musician_id: null, start_date: "" };
    formErrors.value = {};
    await reload();
  } catch (e) {
    formError.value = e.message;
  }
}

async function returnToday(id) {
  actionError.value = "";
  try {
    await put(`/loans/${id}/return`);
    returningLoanId.value = null;
    await reload();
  } catch (e) {
    actionError.value = `Rückgabe fehlgeschlagen: ${e.message}`;
  }
}

async function returnWithDate(id) {
  if (!returnDate.value) return;
  actionError.value = "";
  try {
    await put(`/loans/${id}/return`, { end_date: returnDate.value });
    returningLoanId.value = null;
    returnDate.value = "";
    await reload();
  } catch (e) {
    actionError.value = `Rückgabe fehlgeschlagen: ${e.message}`;
  }
}
</script>

<template>
  <div>
    <div class="page-header">
      <h1>Leihregister</h1>
      <button class="btn btn-primary" @click="showForm = !showForm">Neue Ausleihe</button>
    </div>

    <div v-if="showForm" class="card" style="margin-bottom: 1.5rem; max-width: 600px">
      <h3 style="margin-bottom: 1rem">Neue Ausleihe</h3>
      <form @submit.prevent="createLoan">
        <div class="grid grid-3">
          <div class="form-group" :class="{ error: formErrors.item_id }">
            <RemotePicker
              v-model="form.item_id"
              :fetch-options="fetchLoanableItemOptions"
              label="Gegenstand *"
              placeholder="Nummer oder Bezeichnung …"
            />
            <span v-if="formErrors.item_id" class="form-error">{{ formErrors.item_id }}</span>
          </div>
          <div class="form-group" :class="{ error: formErrors.musician_id }">
            <RemotePicker
              v-model="form.musician_id"
              :fetch-options="fetchMusicianOptions"
              label="Musiker *"
              placeholder="Name …"
            />
            <span v-if="formErrors.musician_id" class="form-error">{{
              formErrors.musician_id
            }}</span>
          </div>
          <div class="form-group" :class="{ error: formErrors.start_date }">
            <label>Datum *</label>
            <input v-model="form.start_date" type="date" />
            <span v-if="formErrors.start_date" class="form-error">{{ formErrors.start_date }}</span>
          </div>
        </div>
        <div style="display: flex; gap: 0.5rem; margin-top: 0.5rem">
          <button type="submit" class="btn-primary">Ausleihen</button>
          <button type="button" @click="showForm = false">Abbrechen</button>
        </div>
        <p v-if="formError" class="form-error" role="alert">{{ formError }}</p>
      </form>
    </div>

    <div class="toolbar">
      <SearchBar
        v-model="state.search"
        placeholder="Suche (Gegenstand, Nummer, Musiker …)"
        class="grow"
      />
      <RemotePicker
        class="loan-musician-filter"
        :model-value="state.musician_id"
        :selected-label="filterMusicianLabel"
        :fetch-options="(t) => fetchMusicianOptions(t, { activeOnly: false })"
        label="Musiker"
        placeholder="Alle Musiker"
        @update:model-value="setFilter('musician_id', $event)"
        @select="
          (o) => {
            filterMusicianLabel = o.label;
            lastMusicianId = o.id;
          }
        "
      />
      <GroupSelect
        :options="GROUP_OPTIONS"
        :model-value="state.group_by"
        @update:model-value="setFilter('group_by', $event)"
      />
    </div>

    <p v-if="!loading && !error" class="list-count">
      {{ itemTotal }} {{ itemTotal === 1 ? "Leihe" : "Leihen" }}
    </p>

    <FilterBar
      :defs="filterDefs"
      :state="state"
      :defaults="defaults"
      @change="setFilter"
      @reset="resetFilters"
    />

    <div v-if="error && !items.length" class="alert alert-danger list-alert" role="alert">
      Leihen konnten nicht geladen werden: {{ error }}
      <button type="button" class="btn-sm" @click="reload">Erneut versuchen</button>
      <button type="button" class="btn-sm" @click="resetFilters">Filter zurücksetzen</button>
    </div>

    <template v-else>
      <p v-if="actionError" class="form-error" role="alert">{{ actionError }}</p>

      <DataTable
        :columns="columns"
        :rows="items"
        :loading="loading"
        :sort="sort"
        :card-breakpoint="640"
        :groups="groups"
        :collapsed-groups="collapsed"
        :empty-text="filtered ? 'Keine Leihen für diese Filter.' : 'Noch keine Leihen.'"
        @update:sort="setSort"
        @toggle-group="toggleGroup"
      >
        <template #item="{ row }">
          <router-link :to="itemRouteBase(row.item.category) + '/' + row.item.id">
            {{ row.item.label }}
          </router-link>
        </template>
        <template #display_nr="{ row }">
          {{ row.item.display_nr }}
        </template>
        <template #musician="{ row }">
          <router-link :to="`/musiker/${row.musician.id}`">
            {{ row.musician.first_name }} {{ row.musician.last_name }}
          </router-link>
        </template>
        <template #end_date="{ row }">
          {{ row.end_date || "—" }}
        </template>
        <template #status="{ row }">
          <span :class="row.end_date ? 'badge badge-gray' : 'badge badge-green'">
            {{ row.end_date ? "Zurückgegeben" : "Ausgeliehen" }}
          </span>
        </template>
        <template #actions="{ row }">
          <template v-if="!row.end_date">
            <div
              v-if="returningLoanId === row.id"
              style="display: flex; gap: 0.25rem; align-items: center; flex-wrap: wrap"
            >
              <input
                v-model="returnDate"
                type="date"
                style="max-width: 160px; padding: 0.2rem 0.4rem; font-size: 1rem"
                @click.stop
              />
              <button
                class="btn-sm btn-primary"
                :disabled="!returnDate"
                @click.stop="returnWithDate(row.id)"
              >
                OK
              </button>
              <button class="btn-sm" @click.stop="returningLoanId = null">X</button>
            </div>
            <div v-else style="display: flex; gap: 0.25rem">
              <button class="btn-sm" @click.stop="returnToday(row.id)">Heute</button>
              <button class="btn-sm" @click.stop="returningLoanId = row.id">Datum</button>
            </div>
          </template>
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
.loan-musician-filter {
  min-width: 14rem;
}

.list-count {
  font-variant-numeric: tabular-nums;
  color: var(--color-muted);
  margin: 0 0 var(--space-2);
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
