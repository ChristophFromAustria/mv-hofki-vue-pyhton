<script setup>
import { ref, computed, onMounted } from "vue";
import { get, post, put, del } from "../lib/api.js";
import ConfirmDialog from "../components/ConfirmDialog.vue";

const items = ref([]);
const loading = ref(true);
const loadError = ref("");
const editing = ref(null);
const form = ref({ label: "" });
const formError = ref("");
const deleteTarget = ref(null);
const deleteError = ref("");

async function load() {
  loading.value = true;
  loadError.value = "";
  try {
    items.value = await get("/general-item-categories");
  } catch (e) {
    loadError.value = `Kategorien konnten nicht geladen werden: ${e.message}`;
  } finally {
    loading.value = false;
  }
}

onMounted(load);

function startEdit(item) {
  editing.value = item.id;
  form.value = { label: item.label };
  formError.value = "";
}

function startCreate() {
  editing.value = "new";
  form.value = { label: "" };
  formError.value = "";
}

function cancel() {
  editing.value = null;
  formError.value = "";
}

async function save() {
  if (!form.value.label.trim()) {
    formError.value = "Bitte eine Bezeichnung eingeben.";
    return;
  }
  try {
    if (editing.value === "new") {
      await post("/general-item-categories", form.value);
    } else {
      await put(`/general-item-categories/${editing.value}`, form.value);
    }
    editing.value = null;
    await load();
  } catch (e) {
    formError.value = typeof e.message === "string" ? e.message : "Speichern fehlgeschlagen.";
  }
}

const deleteMessage = computed(() => {
  const t = deleteTarget.value;
  if (!t) return "";
  if (t.item_count === 0) return `Soll die Kategorie „${t.label}“ gelöscht werden?`;
  const n = t.item_count === 1 ? "einem Gegenstand" : `${t.item_count} Gegenständen`;
  return `Die Kategorie „${t.label}“ wird von ${n} entfernt und gelöscht.`;
});

async function remove() {
  try {
    await del(`/general-item-categories/${deleteTarget.value.id}`);
    deleteTarget.value = null;
    deleteError.value = "";
    await load();
  } catch (e) {
    deleteError.value = `Löschen fehlgeschlagen: ${e.message}`;
    deleteTarget.value = null;
  }
}
</script>

<template>
  <div>
    <div class="page-header">
      <h1>Kategorien (Allgemein)</h1>
      <button class="btn btn-primary" @click="startCreate">Neue Kategorie</button>
    </div>

    <p v-if="loadError" class="form-error" role="alert">{{ loadError }}</p>
    <p v-if="deleteError" class="form-error" role="alert">{{ deleteError }}</p>

    <div style="overflow-x: auto; -webkit-overflow-scrolling: touch">
      <table>
        <thead>
          <tr>
            <th>Bezeichnung</th>
            <th class="col-num">Gegenstände</th>
            <th style="width: 160px"></th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="editing === 'new'">
            <td colspan="2">
              <input
                v-model="form.label"
                maxlength="50"
                placeholder="Bezeichnung"
                aria-label="Bezeichnung der neuen Kategorie"
                @keydown.enter.prevent="save"
                @keydown.esc="cancel"
              />
              <span v-if="formError" class="form-error" role="alert">{{ formError }}</span>
            </td>
            <td>
              <div style="display: flex; gap: 0.25rem">
                <button class="btn-sm btn-primary" @click="save">Speichern</button>
                <button class="btn-sm" @click="cancel">Abbrechen</button>
              </div>
            </td>
          </tr>
          <tr v-if="loading">
            <td colspan="3" class="text-muted">Wird geladen …</td>
          </tr>
          <tr v-else-if="!items.length && editing !== 'new'">
            <td colspan="3" class="text-muted">
              Noch keine Kategorien. Lege die erste mit „Neue Kategorie“ an.
            </td>
          </tr>
          <tr v-for="item in items" :key="item.id">
            <template v-if="editing === item.id">
              <td colspan="2">
                <input
                  v-model="form.label"
                  maxlength="50"
                  :aria-label="`Neue Bezeichnung für „${item.label}“`"
                  @keydown.enter.prevent="save"
                  @keydown.esc="cancel"
                />
                <span v-if="formError" class="form-error" role="alert">{{ formError }}</span>
              </td>
              <td>
                <div style="display: flex; gap: 0.25rem">
                  <button class="btn-sm btn-primary" @click="save">Speichern</button>
                  <button class="btn-sm" @click="cancel">Abbrechen</button>
                </div>
              </td>
            </template>
            <template v-else>
              <td>{{ item.label }}</td>
              <td class="col-num">{{ item.item_count }}</td>
              <td>
                <div style="display: flex; gap: 0.25rem">
                  <button class="btn-sm" @click="startEdit(item)">Bearbeiten</button>
                  <button
                    class="btn-sm btn-danger"
                    :aria-label="`„${item.label}“ löschen`"
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

    <ConfirmDialog
      :open="!!deleteTarget"
      title="Kategorie löschen"
      :message="deleteMessage"
      @confirm="remove"
      @cancel="deleteTarget = null"
    />
  </div>
</template>
