<script setup>
import { ref, onMounted } from "vue";
import { useRouter } from "vue-router";
import { get, post, del } from "../lib/api.js";
import { sessionStatus, formatDateTime } from "../lib/importStatus.js";
import LoadingSpinner from "../components/LoadingSpinner.vue";
import ConfirmDialog from "../components/ConfirmDialog.vue";

const router = useRouter();
const sessions = ref([]);
const loading = ref(true);
const error = ref(null);
const creating = ref(false);
const confirmOpen = ref(false);
const deleteTarget = ref(null);

async function load() {
  loading.value = true;
  error.value = null;
  try {
    const data = await get("/import/sessions?limit=200");
    sessions.value = data.items;
  } catch (e) {
    error.value = e.message;
  } finally {
    loading.value = false;
  }
}

async function createSession() {
  creating.value = true;
  error.value = null;
  try {
    const session = await post("/import/sessions", {});
    router.push({ name: "import-session", params: { id: session.id } });
  } catch (e) {
    error.value = e.message;
  } finally {
    creating.value = false;
  }
}

function open(session) {
  router.push({ name: "import-session", params: { id: session.id } });
}

function confirmDelete(session) {
  deleteTarget.value = session;
  confirmOpen.value = true;
}

async function deleteSession() {
  if (!deleteTarget.value) return;
  try {
    await del(`/import/sessions/${deleteTarget.value.id}`);
  } catch (e) {
    error.value = e.message;
  } finally {
    confirmOpen.value = false;
    deleteTarget.value = null;
    await load();
  }
}

onMounted(load);
</script>

<template>
  <div>
    <div class="page-header">
      <div>
        <h1>KI-Import</h1>
        <p class="page-subtitle">
          Gescannte Inventarlisten und Fotoblätter hochladen, vom Modell auslesen lassen, prüfen und
          in den Bestand übernehmen.
        </p>
      </div>
      <button class="btn btn-primary" :disabled="creating" @click="createSession">
        + Neuer Import
      </button>
    </div>

    <div v-if="error" class="alert alert-danger" role="alert">{{ error }}</div>

    <LoadingSpinner v-if="loading" />

    <div v-else-if="sessions.length === 0" class="empty-state">
      <p>Noch kein Import angelegt.</p>
      <button class="btn btn-primary" :disabled="creating" @click="createSession">
        Ersten Import starten
      </button>
    </div>

    <div v-else class="table-scroll">
      <table class="ledger-table sessions-table">
        <thead>
          <tr>
            <th>Bezeichnung</th>
            <th>Status</th>
            <th class="num">Seiten</th>
            <th>Angelegt</th>
            <th><span class="sr-only">Aktionen</span></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="s in sessions" :key="s.id" class="row-link" @click="open(s)">
            <td>
              <router-link :to="{ name: 'import-session', params: { id: s.id } }">
                {{ s.title || `Import #${s.id}` }}
              </router-link>
            </td>
            <td>
              <span :class="['badge', sessionStatus(s.status).badge]">
                {{ sessionStatus(s.status).label }}
              </span>
            </td>
            <td class="num">{{ s.page_count }}</td>
            <td class="nowrap">{{ formatDateTime(s.created_at) }}</td>
            <td class="actions">
              <button
                v-if="s.status !== 'imported'"
                class="btn btn-danger btn-sm"
                @click.stop="confirmDelete(s)"
              >
                Löschen
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <ConfirmDialog
      :open="confirmOpen"
      title="Import löschen"
      :message="`'${deleteTarget?.title || 'Import #' + deleteTarget?.id}' mit allen Seiten löschen? Die archivierten Dateien bleiben erhalten.`"
      @confirm="deleteSession"
      @cancel="confirmOpen = false"
    />
  </div>
</template>

<style scoped>
.sessions-table {
  max-width: none;
}

.row-link {
  cursor: pointer;
}

.nowrap {
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}

.actions {
  text-align: right;
  white-space: nowrap;
}

.empty-state {
  text-align: center;
  padding: 3rem 1rem;
  color: var(--color-muted);
}

.empty-state .btn {
  margin-top: 1rem;
}
</style>
