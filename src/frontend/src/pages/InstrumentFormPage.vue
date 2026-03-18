<script setup>
import { ref, onMounted, computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import { get, post, put } from "../lib/api.js";

const route = useRoute();
const router = useRouter();
const isEdit = computed(() => !!route.params.id);
const saving = ref(false);
const types = ref([]);
const currencies = ref([]);
const errors = ref({});

const form = ref({
  label_addition: "",
  manufacturer: "",
  serial_nr: "",
  construction_year: "",
  acquisition_date: "",
  acquisition_cost: null,
  currency_id: null,
  distributor: "",
  container: "",
  particularities: "",
  owner: "",
  notes: "",
  instrument_type_id: null,
});

onMounted(async () => {
  const [t, c] = await Promise.all([get("/instrument-types"), get("/currencies")]);
  types.value = t;
  currencies.value = c;

  if (isEdit.value) {
    const data = await get(`/instruments/${route.params.id}`);
    Object.keys(form.value).forEach((key) => {
      if (data[key] !== undefined && data[key] !== null) form.value[key] = data[key];
    });
  } else {
    form.value.owner = "MV Hofkirchen";
    form.value.currency_id = c.find((x) => x.abbreviation === "€")?.id || c[0]?.id;
  }
});

function validate() {
  errors.value = {};
  if (!form.value.instrument_type_id) errors.value.instrument_type_id = "Pflichtfeld";
  if (!form.value.owner?.trim()) errors.value.owner = "Pflichtfeld";
  if (!form.value.currency_id) errors.value.currency_id = "Pflichtfeld";
  return Object.keys(errors.value).length === 0;
}

function cleanPayload() {
  const data = { ...form.value };
  // Convert empty strings to null for optional fields
  for (const key of Object.keys(data)) {
    if (data[key] === "") data[key] = null;
  }
  return data;
}

async function save() {
  if (!validate()) return;
  saving.value = true;
  const payload = cleanPayload();
  try {
    if (isEdit.value) {
      await put(`/instruments/${route.params.id}`, payload);
      router.push(`/instrumente/${route.params.id}`);
    } else {
      const created = await post("/instruments", payload);
      router.push(`/instrumente/${created.id}`);
    }
  } catch (e) {
    alert("Fehler: " + e.message);
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <div>
    <h1 style="margin-bottom: 1.5rem">
      {{ isEdit ? "Instrument bearbeiten" : "Neues Instrument" }}
    </h1>

    <form class="card" style="max-width: 700px" @submit.prevent="save">
      <div class="grid grid-2">
        <div class="form-group" :class="{ error: errors.instrument_type_id }">
          <label>Instrumententyp *</label>
          <select v-model.number="form.instrument_type_id">
            <option v-for="t in types" :key="t.id" :value="t.id">
              {{ t.label }}
            </option>
          </select>
          <span v-if="errors.instrument_type_id" class="form-error">{{
            errors.instrument_type_id
          }}</span>
        </div>
        <div class="form-group">
          <label>Bezeichnungszusatz</label>
          <input v-model="form.label_addition" />
        </div>
        <div class="form-group">
          <label>Hersteller</label>
          <input v-model="form.manufacturer" />
        </div>
        <div class="form-group">
          <label>Seriennummer</label>
          <input v-model="form.serial_nr" />
        </div>
        <div class="form-group">
          <label>Baujahr</label>
          <input v-model="form.construction_year" type="date" />
        </div>
        <div class="form-group" :class="{ error: errors.owner }">
          <label>Eigentümer *</label>
          <input v-model="form.owner" />
          <span v-if="errors.owner" class="form-error">{{ errors.owner }}</span>
        </div>
        <div class="form-group">
          <label>Händler</label>
          <input v-model="form.distributor" />
        </div>
        <div class="form-group">
          <label>Anschaffungsdatum</label>
          <input v-model="form.acquisition_date" type="date" />
        </div>
        <div class="form-group" :class="{ error: errors.currency_id }">
          <label>Anschaffungskosten</label>
          <div style="display: flex; gap: 0.5rem">
            <input
              v-model.number="form.acquisition_cost"
              type="number"
              step="0.01"
              style="flex: 1"
            />
            <select v-model.number="form.currency_id" style="width: 100px">
              <option v-for="c in currencies" :key="c.id" :value="c.id">
                {{ c.abbreviation }}
              </option>
            </select>
          </div>
          <span v-if="errors.currency_id" class="form-error">{{ errors.currency_id }}</span>
        </div>
        <div class="form-group">
          <label>Behältnis</label>
          <input v-model="form.container" />
        </div>
        <div class="form-group">
          <label>Besonderheiten</label>
          <input v-model="form.particularities" />
        </div>
      </div>
      <div class="form-group">
        <label>Notizen</label>
        <textarea v-model="form.notes" rows="2"></textarea>
      </div>

      <div style="display: flex; gap: 0.5rem; margin-top: 1rem">
        <button type="submit" class="btn-primary" :disabled="saving">
          {{ saving ? "Speichern..." : "Speichern" }}
        </button>
        <button type="button" @click="router.back()">Abbrechen</button>
      </div>
    </form>
  </div>
</template>
