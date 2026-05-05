<script setup>
import { ref, onMounted } from "vue";
import { get, post, del } from "../lib/api.js";
import ConfirmDialog from "../components/ConfirmDialog.vue";

const emails = ref([]);
const newEmail = ref("");
const loading = ref(true);
const saving = ref(false);
const error = ref("");
const deleteTarget = ref(null);

async function load() {
  loading.value = true;
  error.value = "";
  try {
    const data = await get("/access/emails");
    emails.value = data.emails;
  } catch (e) {
    error.value = "Fehler beim Laden: " + e.message;
  } finally {
    loading.value = false;
  }
}

onMounted(load);

async function addEmail() {
  if (!newEmail.value.trim()) return;
  saving.value = true;
  error.value = "";
  try {
    const data = await post("/access/emails", { email: newEmail.value.trim() });
    emails.value = data.emails;
    newEmail.value = "";
  } catch (e) {
    error.value = "Fehler: " + e.message;
  } finally {
    saving.value = false;
  }
}

async function removeEmail() {
  const email = deleteTarget.value;
  deleteTarget.value = null;
  if (!email) return;
  saving.value = true;
  error.value = "";
  try {
    const data = await del(`/access/emails/${encodeURIComponent(email)}`);
    emails.value = data.emails;
  } catch (e) {
    error.value = "Fehler: " + e.message;
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <div>
    <div class="page-header">
      <h1>Zugriffsverwaltung</h1>
    </div>

    <p style="margin-bottom: 1rem; color: var(--color-muted)">
      E-Mail-Adressen, die Zugriff auf die App haben.
    </p>

    <div v-if="error" class="alert alert-danger" style="margin-bottom: 1rem">
      {{ error }}
    </div>

    <form
      style="display: flex; gap: 0.5rem; margin-bottom: 1.5rem; flex-wrap: wrap"
      @submit.prevent="addEmail"
    >
      <input
        v-model="newEmail"
        type="email"
        placeholder="neue@email.at"
        :disabled="saving"
        style="flex: 1; min-width: 200px"
      />
      <button class="btn btn-primary" :disabled="saving || !newEmail.trim()" type="submit">
        Hinzufügen
      </button>
    </form>

    <p v-if="loading">Laden...</p>

    <div v-else-if="emails.length" style="overflow-x: auto; -webkit-overflow-scrolling: touch">
      <table>
        <thead>
          <tr>
            <th>E-Mail-Adresse</th>
            <th style="width: 80px"></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="email in emails" :key="email">
            <td>{{ email }}</td>
            <td>
              <button class="btn-sm btn-danger" :disabled="saving" @click="deleteTarget = email">
                X
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <p v-else-if="!loading">Keine E-Mail-Adressen vorhanden.</p>

    <ConfirmDialog
      :open="!!deleteTarget"
      title="Zugriff entfernen"
      :message="`E-Mail-Adresse ${deleteTarget} wirklich entfernen?`"
      @confirm="removeEmail"
      @cancel="deleteTarget = null"
    />
  </div>
</template>
