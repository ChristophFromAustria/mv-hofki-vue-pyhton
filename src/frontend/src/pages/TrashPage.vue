<script setup>
import { computed, onMounted, ref } from "vue";
import { del, get, post } from "../lib/api.js";
import { formatDate } from "../lib/format.js";
import { formatEventTime } from "../lib/events.js";
import { trashLink } from "../lib/trash.js";
import ConfirmDialog from "../components/ConfirmDialog.vue";
import LoadingSpinner from "../components/LoadingSpinner.vue";

// Papierkorb: what was deleted, by whom; restore or delete for good.
// Entries are deleted for good automatically 90 days after deletion.
const entries = ref([]);
const loading = ref(true);
const error = ref("");
const actionError = ref("");
const message = ref(null); // { text, to }
const kind = ref("");
const busyKey = ref("");
const purgeTarget = ref(null);

const keyOf = (e) => `${e.kind}-${e.id}`;
const kinds = computed(() => {
  const seen = new Map();
  for (const e of entries.value) seen.set(e.kind, e.kind_label);
  return [...seen].map(([value, label]) => ({ value, label }));
});
const shown = computed(() =>
  kind.value ? entries.value.filter((e) => e.kind === kind.value) : entries.value,
);

function whoLabel(by) {
  if (!by) return "unbekannt";
  return { "ki-import": "KI-Import", import: "Inventar-Import", system: "System" }[by] || by;
}

async function load() {
  loading.value = true;
  error.value = "";
  try {
    entries.value = await get("/trash");
  } catch (e) {
    error.value = e.message;
  } finally {
    loading.value = false;
  }
}

async function restore(entry) {
  busyKey.value = keyOf(entry);
  actionError.value = "";
  message.value = null;
  try {
    await post(`/trash/${entry.kind}/${entry.id}/restore`, {});
    message.value = { text: `„${entry.label}“ wurde wiederhergestellt.`, to: trashLink(entry) };
    await load();
  } catch (e) {
    actionError.value = `„${entry.label}“ konnte nicht wiederhergestellt werden: ${e.message}`;
  } finally {
    busyKey.value = "";
  }
}

async function purge() {
  const entry = purgeTarget.value;
  purgeTarget.value = null;
  busyKey.value = keyOf(entry);
  actionError.value = "";
  message.value = null;
  try {
    await del(`/trash/${entry.kind}/${entry.id}`);
    message.value = { text: `„${entry.label}“ wurde endgültig gelöscht.`, to: null };
    await load();
  } catch (e) {
    actionError.value = `„${entry.label}“ konnte nicht gelöscht werden: ${e.message}`;
  } finally {
    busyKey.value = "";
  }
}

const purgeMessage = computed(() => {
  const e = purgeTarget.value;
  if (!e) return "";
  const extra =
    e.kind === "item"
      ? " Fotos, Rechnungen und Leihhistorie werden mitgelöscht; die Inventarnummer bleibt gesperrt."
      : e.kind === "musician"
        ? " Die Leihhistorie dieses Musikers wird mitgelöscht."
        : "";
  return `„${e.label}“ endgültig löschen? Das kann nicht rückgängig gemacht werden.${extra}`;
});

onMounted(load);
</script>

<template>
  <div>
    <div class="page-header">
      <div>
        <h1>Papierkorb</h1>
        <p class="page-subtitle">
          Gelöschtes bleibt 90 Tage hier und wird danach automatisch endgültig gelöscht.
        </p>
      </div>
    </div>

    <p v-if="message" class="alert alert-success" role="status">
      {{ message.text }}
      <RouterLink v-if="message.to" :to="message.to">Öffnen</RouterLink>
    </p>
    <p v-if="actionError" class="alert alert-danger" role="alert">{{ actionError }}</p>

    <LoadingSpinner v-if="loading && !entries.length" />
    <div v-else-if="error" class="alert alert-danger" role="alert">
      Papierkorb konnte nicht geladen werden: {{ error }}
      <button type="button" class="btn-sm" @click="load">Erneut versuchen</button>
    </div>
    <p v-else-if="!entries.length" class="empty-note">Der Papierkorb ist leer.</p>

    <template v-else>
      <div class="toolbar">
        <label class="filter-field">
          <span class="filter-label">Art</span>
          <select v-model="kind">
            <option value="">Alle ({{ entries.length }})</option>
            <option v-for="k in kinds" :key="k.value" :value="k.value">{{ k.label }}</option>
          </select>
        </label>
      </div>

      <div class="table-scroll">
        <table class="trash-table">
          <thead>
            <tr>
              <th>Art</th>
              <th>Bezeichnung</th>
              <th>Gelöscht</th>
              <th>Endgültig ab</th>
              <th><span class="sr-only">Aktionen</span></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="e in shown" :key="keyOf(e)">
              <td class="trash-kind">{{ e.kind_label }}</td>
              <td>
                {{ e.label }}
                <span v-if="e.context" class="trash-context">zu {{ e.context }}</span>
              </td>
              <td class="trash-when">
                {{ formatEventTime(e.deleted_at) }}
                <span class="trash-context">{{ whoLabel(e.deleted_by) }}</span>
              </td>
              <td class="trash-when">{{ formatDate(e.purge_at) }}</td>
              <td>
                <div class="trash-actions">
                  <button
                    type="button"
                    class="btn-sm btn-primary"
                    :disabled="busyKey === keyOf(e)"
                    @click="restore(e)"
                  >
                    Wiederherstellen
                  </button>
                  <button
                    type="button"
                    class="btn-sm btn-danger"
                    :disabled="busyKey === keyOf(e)"
                    @click="purgeTarget = e"
                  >
                    Endgültig löschen
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>

    <ConfirmDialog
      :open="purgeTarget !== null"
      title="Endgültig löschen"
      :message="purgeMessage"
      confirm-label="Endgültig löschen"
      @confirm="purge"
      @cancel="purgeTarget = null"
    />
  </div>
</template>

<style scoped>
.trash-kind,
.trash-when {
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}

.trash-context {
  display: block;
  font-size: 0.8125rem;
  color: var(--color-muted);
}

.trash-actions {
  display: flex;
  gap: var(--space-2);
  justify-content: flex-end;
  white-space: nowrap;
}

.trash-actions button {
  min-height: 36px;
}

@media (max-width: 640px) {
  .trash-actions {
    flex-direction: column;
    align-items: stretch;
  }

  .trash-actions button {
    min-height: 44px;
  }
}
</style>
