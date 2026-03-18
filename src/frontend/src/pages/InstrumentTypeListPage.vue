<script setup>
import { ref, onMounted } from "vue";
import { get, post, put, del } from "../lib/api.js";
import ConfirmDialog from "../components/ConfirmDialog.vue";

const items = ref([]);
const editing = ref(null);
const form = ref({ label: "", label_short: "" });
const deleteTarget = ref(null);

async function load() {
  items.value = await get("/instrument-types");
}

onMounted(load);

function startEdit(item) {
  editing.value = item.id;
  form.value = { label: item.label, label_short: item.label_short };
}

function startCreate() {
  editing.value = "new";
  form.value = { label: "", label_short: "" };
}

async function save() {
  try {
    if (editing.value === "new") {
      await post("/instrument-types", form.value);
    } else {
      await put(`/instrument-types/${editing.value}`, form.value);
    }
    editing.value = null;
    await load();
  } catch (e) {
    alert("Fehler: " + e.message);
  }
}

async function remove() {
  try {
    await del(`/instrument-types/${deleteTarget.value}`);
    deleteTarget.value = null;
    await load();
  } catch (e) {
    alert("Fehler: " + e.message);
    deleteTarget.value = null;
  }
}
</script>

<template>
  <div>
    <div class="page-header">
      <h1>Instrumententypen</h1>
      <button class="btn btn-primary" @click="startCreate">Neuer Typ</button>
    </div>

    <table>
      <thead>
        <tr>
          <th>Bezeichnung</th>
          <th>Kürzel</th>
          <th style="width: 120px"></th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="editing === 'new'">
          <td><input v-model="form.label" placeholder="Bezeichnung" /></td>
          <td>
            <input v-model="form.label_short" placeholder="Kürzel" style="width: 80px" />
          </td>
          <td>
            <div style="display: flex; gap: 0.25rem">
              <button class="btn-sm btn-primary" @click="save">OK</button>
              <button class="btn-sm" @click="editing = null">X</button>
            </div>
          </td>
        </tr>
        <tr v-for="item in items" :key="item.id">
          <template v-if="editing === item.id">
            <td><input v-model="form.label" /></td>
            <td>
              <input v-model="form.label_short" style="width: 80px" />
            </td>
            <td>
              <div style="display: flex; gap: 0.25rem">
                <button class="btn-sm btn-primary" @click="save">OK</button>
                <button class="btn-sm" @click="editing = null">X</button>
              </div>
            </td>
          </template>
          <template v-else>
            <td>{{ item.label }}</td>
            <td>{{ item.label_short }}</td>
            <td>
              <div style="display: flex; gap: 0.25rem">
                <button class="btn-sm" @click="startEdit(item)">Bearbeiten</button>
                <button class="btn-sm btn-danger" @click="deleteTarget = item.id">X</button>
              </div>
            </td>
          </template>
        </tr>
      </tbody>
    </table>

    <ConfirmDialog
      :open="!!deleteTarget"
      title="Typ löschen"
      message="Soll dieser Instrumententyp wirklich gelöscht werden?"
      @confirm="remove"
      @cancel="deleteTarget = null"
    />
  </div>
</template>
