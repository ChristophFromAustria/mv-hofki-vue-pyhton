<script setup>
import { ref, onMounted, computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import { get, post, put } from "../lib/api.js";
import { sortRegisters } from "../lib/registers.js";
import LoadingSpinner from "../components/LoadingSpinner.vue";

const route = useRoute();
const router = useRouter();
const isEdit = computed(() => !!route.params.id);
const loading = ref(true);
const loadError = ref("");
const saving = ref(false);
const saveError = ref("");
const errors = ref({});
const registers = ref([]);
const registersError = ref("");

const form = ref({
  first_name: "",
  last_name: "",
  phone: "",
  email: "",
  street_address: "",
  postal_code: null,
  city: "",
  is_extern: false,
  is_active: true,
  register_ids: [],
  notes: "",
});

async function loadRegisters() {
  try {
    registers.value = sortRegisters(await get("/registers"));
  } catch (e) {
    registersError.value = "Register konnten nicht geladen werden: " + e.message;
  }
}

async function loadMusician() {
  const data = await get(`/musicians/${route.params.id}`);
  Object.keys(form.value).forEach((key) => {
    if (key === "register_ids") return;
    if (data[key] !== undefined && data[key] !== null) form.value[key] = data[key];
  });
  form.value.register_ids = (data.registers || []).map((r) => r.id);
}

onMounted(async () => {
  try {
    await Promise.all([loadRegisters(), isEdit.value ? loadMusician() : null]);
  } catch (e) {
    loadError.value = e.message;
  } finally {
    loading.value = false;
  }
});

function validate() {
  errors.value = {};
  if (!form.value.first_name?.trim()) errors.value.first_name = "Pflichtfeld";
  if (!form.value.last_name?.trim()) errors.value.last_name = "Pflichtfeld";
  return Object.keys(errors.value).length === 0;
}

function cleanPayload() {
  const data = { ...form.value, register_ids: [...form.value.register_ids] };
  for (const key of Object.keys(data)) {
    if (data[key] === "") data[key] = null;
  }
  return data;
}

async function save() {
  saveError.value = "";
  if (!validate()) return;
  saving.value = true;
  const payload = cleanPayload();
  try {
    if (isEdit.value) {
      await put(`/musicians/${route.params.id}`, payload);
      router.push(`/musiker/${route.params.id}`);
    } else {
      const created = await post("/musicians", payload);
      router.push(`/musiker/${created.id}`);
    }
  } catch (e) {
    saveError.value = "Speichern fehlgeschlagen: " + e.message;
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <div>
    <h1 style="margin-bottom: 1.5rem">
      {{ isEdit ? "Musiker bearbeiten" : "Neuer Musiker" }}
    </h1>

    <LoadingSpinner v-if="loading" />

    <div v-else-if="loadError" class="alert alert-danger" role="alert">
      Musiker konnte nicht geladen werden: {{ loadError }}
    </div>

    <form v-else class="card musician-form" @submit.prevent="save">
      <div class="grid grid-2">
        <div class="form-group" :class="{ error: errors.first_name }">
          <label for="m-first-name">Vorname *</label>
          <input id="m-first-name" v-model="form.first_name" autocomplete="given-name" />
          <span v-if="errors.first_name" class="form-error">{{ errors.first_name }}</span>
        </div>
        <div class="form-group" :class="{ error: errors.last_name }">
          <label for="m-last-name">Nachname *</label>
          <input id="m-last-name" v-model="form.last_name" autocomplete="family-name" />
          <span v-if="errors.last_name" class="form-error">{{ errors.last_name }}</span>
        </div>
        <div class="form-group">
          <label for="m-phone">Telefon</label>
          <input id="m-phone" v-model="form.phone" type="tel" autocomplete="tel" />
        </div>
        <div class="form-group">
          <label for="m-email">E-Mail</label>
          <input id="m-email" v-model="form.email" type="email" autocomplete="email" />
        </div>
        <div class="form-group">
          <label for="m-street">Straße</label>
          <input id="m-street" v-model="form.street_address" autocomplete="street-address" />
        </div>
        <div class="form-group">
          <label for="m-postal">PLZ</label>
          <input
            id="m-postal"
            v-model.number="form.postal_code"
            type="number"
            inputmode="numeric"
            autocomplete="postal-code"
          />
        </div>
        <div class="form-group">
          <label for="m-city">Ort</label>
          <input id="m-city" v-model="form.city" autocomplete="address-level2" />
        </div>
      </div>

      <div class="status-options">
        <label class="checkbox-option">
          <input v-model="form.is_active" type="checkbox" />
          Aktiv
        </label>
        <label class="checkbox-option">
          <input v-model="form.is_extern" type="checkbox" />
          Extern
        </label>
      </div>

      <fieldset class="checkbox-group">
        <legend>Register</legend>
        <p v-if="registersError" class="form-error" role="alert">{{ registersError }}</p>
        <p v-else-if="!registers.length" class="empty-note">
          Noch keine Register angelegt.
          <router-link to="/einstellungen/register">Register verwalten</router-link>
        </p>
        <div v-else class="checkbox-grid">
          <label v-for="r in registers" :key="r.id" class="checkbox-option">
            <input v-model="form.register_ids" type="checkbox" :value="r.id" />
            {{ r.label }}
          </label>
        </div>
      </fieldset>

      <div class="form-group">
        <label for="m-notes">Notizen</label>
        <textarea id="m-notes" v-model="form.notes" rows="5"></textarea>
      </div>

      <div v-if="saveError" class="alert alert-danger" role="alert">{{ saveError }}</div>

      <div class="cluster form-actions">
        <button type="submit" class="btn-primary" :disabled="saving">
          {{ saving ? "Speichern …" : "Speichern" }}
        </button>
        <button type="button" @click="router.back()">Abbrechen</button>
      </div>
    </form>
  </div>
</template>

<style scoped>
.musician-form {
  max-width: 640px;
}

.status-options {
  display: flex;
  flex-wrap: wrap;
  gap: 0 var(--space-6);
  margin-bottom: var(--space-3);
}

.form-actions {
  margin-top: var(--space-4);
}
</style>
