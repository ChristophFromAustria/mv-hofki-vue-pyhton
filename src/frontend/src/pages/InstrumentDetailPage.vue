<script setup>
import { ref, computed, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import { get, post, put, del } from "../lib/api.js";
import ConfirmDialog from "../components/ConfirmDialog.vue";

const route = useRoute();
const router = useRouter();
const instrument = ref(null);
const loans = ref([]);
const musicians = ref([]);
const showDelete = ref(false);

// Loan form state
const loanForm = ref({ musician_id: null, start_date: "" });
const loanSaving = ref(false);
const loanErrors = ref({});

// Return state
const showReturnDatePicker = ref(false);
const returnDate = ref("");

const activeLoan = computed(() => loans.value.find((l) => !l.end_date));

async function reload() {
  instrument.value = await get(`/instruments/${route.params.id}`);
  loans.value = await get(`/loans?instrument_id=${route.params.id}`);
}

onMounted(async () => {
  musicians.value = (await get("/musicians?limit=200")).items;
  await reload();
});

async function remove() {
  await del(`/instruments/${route.params.id}`);
  router.push("/instrumente");
}

function validateLoan() {
  loanErrors.value = {};
  if (!loanForm.value.musician_id) loanErrors.value.musician_id = "Pflichtfeld";
  if (!loanForm.value.start_date) loanErrors.value.start_date = "Pflichtfeld";
  return Object.keys(loanErrors.value).length === 0;
}

async function createLoan() {
  if (!validateLoan()) return;
  loanSaving.value = true;
  try {
    await post("/loans", {
      instrument_id: parseInt(route.params.id),
      ...loanForm.value,
    });
    loanForm.value = { musician_id: null, start_date: "" };
    loanErrors.value = {};
    await reload();
  } catch (e) {
    alert("Fehler: " + e.message);
  } finally {
    loanSaving.value = false;
  }
}

async function returnToday() {
  await put(`/loans/${activeLoan.value.id}/return`);
  showReturnDatePicker.value = false;
  await reload();
}

async function returnWithDate() {
  if (!returnDate.value) return;
  await put(`/loans/${activeLoan.value.id}/return`, { end_date: returnDate.value });
  showReturnDatePicker.value = false;
  returnDate.value = "";
  await reload();
}
</script>

<template>
  <div v-if="instrument">
    <div class="page-header">
      <h1>{{ instrument.instrument_type.label }} #{{ instrument.inventory_nr }}</h1>
      <div style="display: flex; gap: 0.5rem">
        <router-link :to="`/instrumente/${instrument.id}/bearbeiten`" class="btn">
          Bearbeiten
        </router-link>
        <button class="btn-danger" @click="showDelete = true">Löschen</button>
      </div>
    </div>

    <div class="card" style="margin-bottom: 1.5rem">
      <dl class="detail-grid">
        <dt>Inventarnummer</dt>
        <dd>{{ instrument.inventory_nr }}</dd>
        <dt>Typ</dt>
        <dd>
          {{ instrument.instrument_type.label }} ({{ instrument.instrument_type.label_short }})
        </dd>
        <dt>Bezeichnungszusatz</dt>
        <dd>{{ instrument.label_addition || "—" }}</dd>
        <dt>Hersteller</dt>
        <dd>{{ instrument.manufacturer || "—" }}</dd>
        <dt>Seriennummer</dt>
        <dd>{{ instrument.serial_nr || "—" }}</dd>
        <dt>Baujahr</dt>
        <dd>{{ instrument.construction_year || "—" }}</dd>
        <dt>Eigentümer</dt>
        <dd>{{ instrument.owner }}</dd>
        <dt>Händler</dt>
        <dd>{{ instrument.distributor || "—" }}</dd>
        <dt>Anschaffungsdatum</dt>
        <dd>{{ instrument.acquisition_date || "—" }}</dd>
        <dt>Anschaffungskosten</dt>
        <dd>
          {{
            instrument.acquisition_cost != null
              ? `${instrument.acquisition_cost} ${instrument.currency.abbreviation}`
              : "—"
          }}
        </dd>
        <dt>Behältnis</dt>
        <dd>{{ instrument.container || "—" }}</dd>
        <dt>Besonderheiten</dt>
        <dd>{{ instrument.particularities || "—" }}</dd>
        <dt>Notizen</dt>
        <dd>{{ instrument.notes || "—" }}</dd>
      </dl>
    </div>

    <!-- Loan management section -->
    <div class="card" style="margin-bottom: 1.5rem">
      <h2 style="font-size: 1.1rem; margin-bottom: 1rem">Ausleihe</h2>

      <!-- Currently loaned out -->
      <div v-if="activeLoan">
        <p style="margin-bottom: 0.75rem">
          Ausgeliehen an
          <router-link :to="`/musiker/${activeLoan.musician.id}`">
            <strong
              >{{ activeLoan.musician.first_name }} {{ activeLoan.musician.last_name }}</strong
            >
          </router-link>
          seit {{ activeLoan.start_date }}
        </p>
        <div v-if="!showReturnDatePicker" style="display: flex; gap: 0.5rem">
          <button class="btn-primary" @click="returnToday">Heute zurückgeben</button>
          <button class="btn" @click="showReturnDatePicker = true">Datum wählen</button>
        </div>
        <div v-else style="display: flex; gap: 0.5rem; align-items: end">
          <div class="form-group" style="margin: 0">
            <label>Rückgabedatum</label>
            <input v-model="returnDate" type="date" style="width: 180px" />
          </div>
          <button class="btn-primary" :disabled="!returnDate" @click="returnWithDate">
            Zurückgeben
          </button>
          <button class="btn" @click="showReturnDatePicker = false">Abbrechen</button>
        </div>
      </div>

      <!-- Available — loan form -->
      <div v-else>
        <p style="margin-bottom: 0.75rem; color: var(--color-muted)">
          <span class="badge badge-green">Verfügbar</span>
        </p>
        <form style="display: flex; gap: 0.75rem; align-items: end" @submit.prevent="createLoan">
          <div
            class="form-group"
            style="margin: 0; flex: 1"
            :class="{ error: loanErrors.musician_id }"
          >
            <label>Musiker</label>
            <select v-model.number="loanForm.musician_id">
              <option :value="null" disabled>Auswählen...</option>
              <option v-for="m in musicians" :key="m.id" :value="m.id">
                {{ m.last_name }} {{ m.first_name }}
              </option>
            </select>
            <span v-if="loanErrors.musician_id" class="form-error">{{
              loanErrors.musician_id
            }}</span>
          </div>
          <div class="form-group" style="margin: 0" :class="{ error: loanErrors.start_date }">
            <label>Datum</label>
            <input v-model="loanForm.start_date" type="date" style="width: 160px" />
            <span v-if="loanErrors.start_date" class="form-error">{{ loanErrors.start_date }}</span>
          </div>
          <button type="submit" class="btn-primary" :disabled="loanSaving">Ausleihen</button>
        </form>
      </div>
    </div>

    <!-- Loan history -->
    <div v-if="loans.length" class="card">
      <h2 style="font-size: 1.1rem; margin-bottom: 1rem">Leihhistorie</h2>
      <table>
        <thead>
          <tr>
            <th>Musiker</th>
            <th>Von</th>
            <th>Bis</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="l in loans" :key="l.id">
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
          </tr>
        </tbody>
      </table>
    </div>

    <ConfirmDialog
      :open="showDelete"
      title="Instrument löschen"
      message="Soll dieses Instrument wirklich gelöscht werden?"
      @confirm="remove"
      @cancel="showDelete = false"
    />
  </div>
</template>
