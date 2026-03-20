<script setup>
import { ref, onMounted, watch } from "vue";
import { get, post, put } from "../lib/api.js";
import { CATEGORIES } from "../lib/categories.js";

const loans = ref([]);
const loanableItems = ref([]);
const musicians = ref([]);
const loading = ref(true);
const activeOnly = ref(true);
const showForm = ref(false);

const form = ref({ item_id: null, musician_id: null, start_date: "" });
const formErrors = ref({});
const returningLoanId = ref(null);
const returnDate = ref("");

function itemRouteBase(category) {
  return CATEGORIES[category]?.routeBase || "/instrumente";
}

async function load() {
  loading.value = true;
  try {
    loans.value = await get(`/loans?active=${activeOnly.value}`);
  } finally {
    loading.value = false;
  }
}

onMounted(async () => {
  const [instruments, clothing, generalItems, m] = await Promise.all([
    get("/items?category=instrument&limit=200"),
    get("/items?category=clothing&limit=200"),
    get("/items?category=general_item&limit=200"),
    get("/musicians?limit=200"),
  ]);
  loanableItems.value = [...instruments.items, ...clothing.items, ...generalItems.items];
  musicians.value = m.items;
  await load();
});

watch(activeOnly, load);

function validateForm() {
  formErrors.value = {};
  if (!form.value.item_id) formErrors.value.item_id = "Pflichtfeld";
  if (!form.value.musician_id) formErrors.value.musician_id = "Pflichtfeld";
  if (!form.value.start_date) formErrors.value.start_date = "Pflichtfeld";
  return Object.keys(formErrors.value).length === 0;
}

async function createLoan() {
  if (!validateForm()) return;
  try {
    await post("/loans", form.value);
    showForm.value = false;
    form.value = { item_id: null, musician_id: null, start_date: "" };
    formErrors.value = {};
    await load();
  } catch (e) {
    alert("Fehler: " + e.message);
  }
}

async function returnToday(id) {
  await put(`/loans/${id}/return`);
  returningLoanId.value = null;
  await load();
}

async function returnWithDate(id) {
  if (!returnDate.value) return;
  await put(`/loans/${id}/return`, { end_date: returnDate.value });
  returningLoanId.value = null;
  returnDate.value = "";
  await load();
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
            <label>Gegenstand *</label>
            <select v-model.number="form.item_id">
              <option :value="null" disabled>Auswählen...</option>
              <option v-for="i in loanableItems" :key="i.id" :value="i.id">
                {{ i.display_nr }} {{ i.label }}
              </option>
            </select>
            <span v-if="formErrors.item_id" class="form-error">{{ formErrors.item_id }}</span>
          </div>
          <div class="form-group" :class="{ error: formErrors.musician_id }">
            <label>Musiker *</label>
            <select v-model.number="form.musician_id">
              <option :value="null" disabled>Auswählen...</option>
              <option v-for="m in musicians" :key="m.id" :value="m.id">
                {{ m.last_name }} {{ m.first_name }}
              </option>
            </select>
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
      </form>
    </div>

    <div class="toolbar">
      <label style="display: flex; align-items: center; gap: 0.5rem; font-size: 0.875rem">
        <input v-model="activeOnly" type="checkbox" style="width: auto" />
        Nur aktive Leihen
      </label>
    </div>

    <div v-if="loading" style="text-align: center; padding: 2rem">Laden...</div>
    <div v-else-if="loans.length" style="overflow-x: auto; -webkit-overflow-scrolling: touch">
      <table>
        <thead>
          <tr>
            <th>Gegenstand</th>
            <th>Inv.-Nr.</th>
            <th>Musiker</th>
            <th>Von</th>
            <th>Bis</th>
            <th>Status</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="l in loans" :key="l.id">
            <td>
              <router-link :to="itemRouteBase(l.item.category) + '/' + l.item.id">
                {{ l.item.label }}
              </router-link>
            </td>
            <td>{{ l.item.display_nr }}</td>
            <td>
              <router-link :to="`/musiker/${l.musician.id}`">
                {{ l.musician.first_name }} {{ l.musician.last_name }}
              </router-link>
            </td>
            <td>{{ l.start_date }}</td>
            <td>{{ l.end_date || "—" }}</td>
            <td>
              <span :class="l.end_date ? 'badge badge-gray' : 'badge badge-green'">
                {{ l.end_date ? "Zurückgegeben" : "Ausgeliehen" }}
              </span>
            </td>
            <td>
              <template v-if="!l.end_date">
                <div
                  v-if="returningLoanId === l.id"
                  style="display: flex; gap: 0.25rem; align-items: center; flex-wrap: wrap"
                >
                  <input
                    v-model="returnDate"
                    type="date"
                    style="max-width: 160px; padding: 0.2rem 0.4rem; font-size: 1rem"
                  />
                  <button
                    class="btn-sm btn-primary"
                    :disabled="!returnDate"
                    @click="returnWithDate(l.id)"
                  >
                    OK
                  </button>
                  <button class="btn-sm" @click="returningLoanId = null">X</button>
                </div>
                <div v-else style="display: flex; gap: 0.25rem">
                  <button class="btn-sm" @click="returnToday(l.id)">Heute</button>
                  <button class="btn-sm" @click="returningLoanId = l.id">Datum</button>
                </div>
              </template>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <p v-else style="text-align: center; padding: 2rem; color: var(--color-muted)">
      Keine Leihen vorhanden
    </p>
  </div>
</template>
