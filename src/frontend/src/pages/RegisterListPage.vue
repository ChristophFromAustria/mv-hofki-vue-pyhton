<script setup>
import { ref, computed, onMounted, nextTick } from "vue";
import { get, post, put, del } from "../lib/api.js";
import { sortRegisters, reorderUpdates, nextSortOrder } from "../lib/registers.js";
import ConfirmDialog from "../components/ConfirmDialog.vue";
import LoadingSpinner from "../components/LoadingSpinner.vue";

const items = ref([]);
const loading = ref(true);
const loadError = ref("");
const actionError = ref("");
const editing = ref(null); // null | "new" | register id
const form = ref({ label: "", expects_instrument: true });
const formError = ref("");
const saving = ref(false);
const reordering = ref(false);
const deleteTarget = ref(null);

const deleteMessage = computed(() =>
  deleteTarget.value
    ? `Soll das Register „${deleteTarget.value.label}“ wirklich gelöscht werden?`
    : "",
);

async function load() {
  loadError.value = "";
  try {
    items.value = sortRegisters(await get("/registers"));
  } catch (e) {
    loadError.value = e.message;
  } finally {
    loading.value = false;
  }
}

onMounted(load);

async function focusLabel() {
  await nextTick();
  document.getElementById("register-label-input")?.focus();
}

function startEdit(item) {
  actionError.value = "";
  formError.value = "";
  editing.value = item.id;
  form.value = { label: item.label, expects_instrument: !!item.expects_instrument };
  focusLabel();
}

function startCreate() {
  actionError.value = "";
  formError.value = "";
  editing.value = "new";
  form.value = { label: "", expects_instrument: true };
  focusLabel();
}

function cancelEdit() {
  editing.value = null;
  formError.value = "";
}

async function save() {
  const label = form.value.label.trim();
  if (!label) {
    formError.value = "Bitte eine Bezeichnung eingeben.";
    return;
  }
  saving.value = true;
  formError.value = "";
  try {
    if (editing.value === "new") {
      await post("/registers", {
        label,
        expects_instrument: form.value.expects_instrument,
        sort_order: nextSortOrder(items.value),
      });
    } else {
      const current = items.value.find((r) => r.id === editing.value);
      await put(`/registers/${editing.value}`, {
        label,
        expects_instrument: form.value.expects_instrument,
        sort_order: current?.sort_order,
      });
    }
    editing.value = null;
    await load();
  } catch (e) {
    formError.value = "Speichern fehlgeschlagen: " + e.message;
  } finally {
    saving.value = false;
  }
}

async function move(index, delta) {
  const updates = reorderUpdates(items.value, index, delta);
  if (!updates.length) return;
  actionError.value = "";
  reordering.value = true;
  try {
    for (const u of updates) {
      const r = items.value.find((x) => x.id === u.id);
      await put(`/registers/${u.id}`, {
        label: r.label,
        expects_instrument: r.expects_instrument,
        sort_order: u.sort_order,
      });
    }
  } catch (e) {
    actionError.value = "Reihenfolge konnte nicht gespeichert werden: " + e.message;
  } finally {
    await load();
    reordering.value = false;
  }
}

async function remove() {
  const target = deleteTarget.value;
  deleteTarget.value = null;
  actionError.value = "";
  try {
    await del(`/registers/${target.id}`);
    await load();
  } catch (e) {
    actionError.value = `„${target.label}“ kann nicht gelöscht werden: ${e.message}`;
  }
}
</script>

<template>
  <div>
    <div class="page-header">
      <div>
        <h1>Register</h1>
        <p class="page-subtitle">
          Stimmgruppen der Kapelle. Die Reihenfolge gilt für Listen und Auswahlfelder.
        </p>
      </div>
      <button class="btn btn-primary" :disabled="editing === 'new'" @click="startCreate">
        Neues Register
      </button>
    </div>

    <LoadingSpinner v-if="loading" />

    <div v-else-if="loadError" class="alert alert-danger" role="alert">
      Register konnten nicht geladen werden: {{ loadError }}
    </div>

    <template v-else>
      <div v-if="actionError" class="alert alert-danger page-alert" role="alert">
        {{ actionError }}
      </div>

      <form @submit.prevent="save">
        <div class="table-scroll">
          <table class="register-table">
            <thead>
              <tr>
                <th class="col-order">Reihenfolge</th>
                <th>Bezeichnung</th>
                <th>Braucht Instrument</th>
                <th class="col-actions"><span class="sr-only">Aktionen</span></th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="editing === 'new'" class="editing-row">
                <td class="col-order text-muted">neu</td>
                <td class="col-label">
                  <label class="sr-only" for="register-label-input">Bezeichnung</label>
                  <input
                    id="register-label-input"
                    v-model="form.label"
                    placeholder="Bezeichnung"
                    @keydown.esc="cancelEdit"
                  />
                  <span v-if="formError" class="form-error" role="alert">{{ formError }}</span>
                </td>
                <td class="col-flag">
                  <label class="checkbox-option">
                    <input v-model="form.expects_instrument" type="checkbox" />
                    <span class="mobile-label">Braucht Instrument</span>
                    <span class="desktop-label">Ja</span>
                  </label>
                </td>
                <td class="col-actions">
                  <div class="cluster">
                    <button type="submit" class="btn-sm btn-primary" :disabled="saving">
                      Speichern
                    </button>
                    <button type="button" class="btn-sm" @click="cancelEdit">Abbrechen</button>
                  </div>
                </td>
              </tr>

              <tr v-if="!items.length && editing !== 'new'">
                <td colspan="4" class="empty-cell">Noch keine Register angelegt.</td>
              </tr>

              <tr
                v-for="(item, index) in items"
                :key="item.id"
                :class="{ 'editing-row': editing === item.id }"
              >
                <td class="col-order">
                  <div class="order-controls">
                    <button
                      type="button"
                      class="btn-sm order-btn"
                      :disabled="index === 0 || reordering || editing !== null"
                      :aria-label="`${item.label} nach oben verschieben`"
                      @click="move(index, -1)"
                    >
                      ↑
                    </button>
                    <button
                      type="button"
                      class="btn-sm order-btn"
                      :disabled="index === items.length - 1 || reordering || editing !== null"
                      :aria-label="`${item.label} nach unten verschieben`"
                      @click="move(index, 1)"
                    >
                      ↓
                    </button>
                  </div>
                </td>
                <template v-if="editing === item.id">
                  <td class="col-label">
                    <label class="sr-only" for="register-label-input">Bezeichnung</label>
                    <input
                      id="register-label-input"
                      v-model="form.label"
                      @keydown.esc="cancelEdit"
                    />
                    <span v-if="formError" class="form-error" role="alert">{{ formError }}</span>
                  </td>
                  <td class="col-flag">
                    <label class="checkbox-option">
                      <input v-model="form.expects_instrument" type="checkbox" />
                      <span class="mobile-label">Braucht Instrument</span>
                      <span class="desktop-label">Ja</span>
                    </label>
                  </td>
                  <td class="col-actions">
                    <div class="cluster">
                      <button type="submit" class="btn-sm btn-primary" :disabled="saving">
                        Speichern
                      </button>
                      <button type="button" class="btn-sm" @click="cancelEdit">Abbrechen</button>
                    </div>
                  </td>
                </template>
                <template v-else>
                  <td class="col-label">{{ item.label }}</td>
                  <td class="col-flag">
                    <span class="mobile-label">Braucht Instrument:</span>
                    <span v-if="item.expects_instrument" class="badge badge-blue">Ja</span>
                    <span v-else class="text-muted">Nein</span>
                  </td>
                  <td class="col-actions">
                    <div class="cluster">
                      <button
                        type="button"
                        class="btn-sm"
                        :disabled="editing !== null"
                        @click="startEdit(item)"
                      >
                        Bearbeiten
                      </button>
                      <button
                        type="button"
                        class="btn-sm btn-danger"
                        :disabled="editing !== null"
                        :aria-label="`${item.label} löschen`"
                        @click="deleteTarget = item"
                      >
                        Löschen
                      </button>
                    </div>
                  </td>
                </template>
              </tr>
            </tbody>
          </table>
        </div>
      </form>
    </template>

    <ConfirmDialog
      :open="!!deleteTarget"
      title="Register löschen"
      :message="deleteMessage"
      @confirm="remove"
      @cancel="deleteTarget = null"
    />
  </div>
</template>

<style scoped>
.page-alert {
  margin-bottom: var(--space-4);
}

.register-table td {
  vertical-align: middle;
}

.col-order {
  width: 7rem;
}

.col-actions {
  width: 1%;
  white-space: nowrap;
}

.col-actions .cluster {
  flex-wrap: nowrap;
}

.mobile-label {
  display: none;
}

.order-controls {
  display: flex;
  gap: var(--space-1);
}

.order-btn {
  min-width: 44px;
  min-height: 44px;
  justify-content: center;
  font-size: 1rem;
}

.register-table .btn-sm {
  min-height: 44px;
}

.editing-row td {
  background: var(--color-primary-light);
}

.empty-cell {
  text-align: center;
  padding: var(--space-6);
  color: var(--color-muted);
}

.register-table input:not([type="checkbox"]) {
  min-width: 12rem;
}

/* Phone: each register becomes a compact card row with the same actions */
@media (max-width: 640px) {
  .register-table thead {
    display: none;
  }

  .register-table,
  .register-table tbody {
    display: block;
  }

  .register-table tr {
    display: grid;
    grid-template-columns: auto 1fr;
    grid-template-areas:
      "order label"
      "order flag"
      "actions actions";
    column-gap: var(--space-3);
    padding: var(--space-3) 0;
    border-bottom: 1px solid var(--color-border);
  }

  .register-table td {
    border: none;
    padding: var(--space-1) 0;
    width: auto;
  }

  .register-table .col-order {
    grid-area: order;
    align-self: center;
  }

  .register-table .col-label {
    grid-area: label;
    font-weight: 500;
  }

  .register-table .col-flag {
    grid-area: flag;
    font-size: 0.8rem;
  }

  .register-table .col-actions {
    grid-area: actions;
    padding-top: var(--space-2);
  }

  .register-table .empty-cell {
    grid-column: 1 / -1;
  }

  .register-table input:not([type="checkbox"]) {
    min-width: 0;
  }

  .mobile-label {
    display: inline;
    color: var(--color-muted);
    margin-right: var(--space-1);
  }

  .desktop-label {
    display: none;
  }
}
</style>
