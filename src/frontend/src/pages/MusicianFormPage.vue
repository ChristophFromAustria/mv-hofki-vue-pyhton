<script setup>
import { ref, onMounted, computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import { get, post, put } from "../lib/api.js";

const route = useRoute();
const router = useRouter();
const isEdit = computed(() => !!route.params.id);
const saving = ref(false);
const errors = ref({});

const form = ref({
  first_name: "",
  last_name: "",
  phone: "",
  email: "",
  street_address: "",
  postal_code: null,
  city: "",
  is_extern: false,
  notes: "",
});

onMounted(async () => {
  if (isEdit.value) {
    const data = await get(`/musicians/${route.params.id}`);
    Object.keys(form.value).forEach((key) => {
      if (data[key] !== undefined && data[key] !== null) form.value[key] = data[key];
    });
  }
});

function validate() {
  errors.value = {};
  if (!form.value.first_name?.trim()) errors.value.first_name = "Pflichtfeld";
  if (!form.value.last_name?.trim()) errors.value.last_name = "Pflichtfeld";
  return Object.keys(errors.value).length === 0;
}

function cleanPayload() {
  const data = { ...form.value };
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
      await put(`/musicians/${route.params.id}`, payload);
      router.push(`/musiker/${route.params.id}`);
    } else {
      const created = await post("/musicians", payload);
      router.push(`/musiker/${created.id}`);
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
      {{ isEdit ? "Musiker bearbeiten" : "Neuer Musiker" }}
    </h1>

    <form class="card" style="max-width: 600px" @submit.prevent="save">
      <div class="grid grid-2">
        <div class="form-group" :class="{ error: errors.first_name }">
          <label>Vorname *</label>
          <input v-model="form.first_name" />
          <span v-if="errors.first_name" class="form-error">{{ errors.first_name }}</span>
        </div>
        <div class="form-group" :class="{ error: errors.last_name }">
          <label>Nachname *</label>
          <input v-model="form.last_name" />
          <span v-if="errors.last_name" class="form-error">{{ errors.last_name }}</span>
        </div>
        <div class="form-group">
          <label>Telefon</label>
          <input v-model="form.phone" />
        </div>
        <div class="form-group">
          <label>E-Mail</label>
          <input v-model="form.email" type="email" />
        </div>
        <div class="form-group">
          <label>Straße</label>
          <input v-model="form.street_address" />
        </div>
        <div class="form-group">
          <label>PLZ</label>
          <input v-model.number="form.postal_code" type="number" />
        </div>
        <div class="form-group">
          <label>Ort</label>
          <input v-model="form.city" />
        </div>
        <div
          class="form-group"
          style="display: flex; align-items: end; gap: 0.5rem; padding-bottom: 0.25rem"
        >
          <input id="is_extern" v-model="form.is_extern" type="checkbox" style="width: auto" />
          <label for="is_extern" style="margin: 0">Extern</label>
        </div>
      </div>
      <div class="form-group">
        <label>Notizen</label>
        <textarea v-model="form.notes" rows="3"></textarea>
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
