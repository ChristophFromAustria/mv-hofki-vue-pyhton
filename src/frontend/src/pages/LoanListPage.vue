<script setup>
import { ref, onMounted, watch } from "vue";
import { get, post, put } from "../lib/api.js";

const loans = ref([]);
const instruments = ref([]);
const musicians = ref([]);
const loading = ref(true);
const activeOnly = ref(true);
const showForm = ref(false);

const form = ref({ instrument_id: null, musician_id: null, start_date: "" });

async function load() {
  loading.value = true;
  try {
    loans.value = await get(`/loans?active=${activeOnly.value}`);
  } finally {
    loading.value = false;
  }
}

onMounted(async () => {
  const [i, m] = await Promise.all([get("/instruments?limit=200"), get("/musicians?limit=200")]);
  instruments.value = i.items;
  musicians.value = m.items;
  await load();
});

watch(activeOnly, load);

async function createLoan() {
  try {
    await post("/loans", form.value);
    showForm.value = false;
    form.value = { instrument_id: null, musician_id: null, start_date: "" };
    await load();
  } catch (e) {
    alert("Fehler: " + e.message);
  }
}

async function returnLoan(id) {
  await put(`/loans/${id}/return`);
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
          <div class="form-group">
            <label>Instrument *</label>
            <select v-model.number="form.instrument_id" required>
              <option :value="null" disabled>Auswählen...</option>
              <option v-for="i in instruments" :key="i.id" :value="i.id">
                #{{ i.inventory_nr }} {{ i.instrument_type?.label }}
              </option>
            </select>
          </div>
          <div class="form-group">
            <label>Musiker *</label>
            <select v-model.number="form.musician_id" required>
              <option :value="null" disabled>Auswählen...</option>
              <option v-for="m in musicians" :key="m.id" :value="m.id">
                {{ m.last_name }} {{ m.first_name }}
              </option>
            </select>
          </div>
          <div class="form-group">
            <label>Datum *</label>
            <input v-model="form.start_date" type="date" required />
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
    <table v-else-if="loans.length">
      <thead>
        <tr>
          <th>Instrument</th>
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
            <router-link :to="`/instrumente/${l.instrument.id}`">
              {{ l.instrument.instrument_type.label }}
            </router-link>
          </td>
          <td>{{ l.instrument.inventory_nr }}</td>
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
            <button v-if="!l.end_date" class="btn-sm" @click="returnLoan(l.id)">Rückgabe</button>
          </td>
        </tr>
      </tbody>
    </table>
    <p v-else style="text-align: center; padding: 2rem; color: var(--color-muted)">
      Keine Leihen vorhanden
    </p>
  </div>
</template>
