<script setup>
import { ref, onMounted } from "vue";
import { get, post, put, del } from "../lib/api.js";
import ConfirmDialog from "../components/ConfirmDialog.vue";

const items = ref([]);
const editing = ref(null);
const form = ref({ label: "" });
const deleteTarget = ref(null);

async function load() {
  items.value = await get("/sheet-music-genres");
}

onMounted(load);

function startEdit(item) {
  editing.value = item.id;
  form.value = { label: item.label };
}

function startCreate() {
  editing.value = "new";
  form.value = { label: "" };
}

async function save() {
  try {
    if (editing.value === "new") {
      await post("/sheet-music-genres", form.value);
    } else {
      await put(`/sheet-music-genres/${editing.value}`, form.value);
    }
    editing.value = null;
    await load();
  } catch (e) {
    alert("Fehler: " + e.message);
  }
}

async function remove() {
  try {
    await del(`/sheet-music-genres/${deleteTarget.value}`);
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
      <h1>Notengenres</h1>
      <button class="btn btn-primary" @click="startCreate">Neues Genre</button>
    </div>

    <div style="overflow-x: auto; -webkit-overflow-scrolling: touch">
      <table>
        <thead>
          <tr>
            <th>Bezeichnung</th>
            <th style="width: 120px"></th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="editing === 'new'">
            <td><input v-model="form.label" placeholder="Bezeichnung" /></td>
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
                <div style="display: flex; gap: 0.25rem">
                  <button class="btn-sm btn-primary" @click="save">OK</button>
                  <button class="btn-sm" @click="editing = null">X</button>
                </div>
              </td>
            </template>
            <template v-else>
              <td>{{ item.label }}</td>
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
    </div>

    <ConfirmDialog
      :open="!!deleteTarget"
      title="Genre löschen"
      message="Soll dieses Notengenre wirklich gelöscht werden?"
      @confirm="remove"
      @cancel="deleteTarget = null"
    />
  </div>
</template>
