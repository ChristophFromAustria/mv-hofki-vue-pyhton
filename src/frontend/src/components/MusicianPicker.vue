<script setup>
import { ref } from "vue";
import RemotePicker from "./RemotePicker.vue";
import MusicianCreateDialog from "./MusicianCreateDialog.vue";
import { fetchMusicianOptions, MUSICIAN_SCOPES } from "../lib/pickers.js";

// Musician search field: active/all switch, and (with `creatable`) a
// "create new musician" entry that opens a small dialog and selects the
// new person right away.
const model = defineModel({ type: Number, default: null });
defineProps({
  label: { type: String, required: true },
  placeholder: { type: String, default: "Name …" },
  defaultScope: { type: String, default: "active" },
  creatable: Boolean,
});

const selectedLabel = ref("");
const createText = ref("");
const creating = ref(false);

function startCreate(text) {
  createText.value = text;
  creating.value = true;
}

function onCreated(musician) {
  creating.value = false;
  selectedLabel.value = `${musician.last_name} ${musician.first_name}`;
  model.value = musician.id;
}
</script>

<template>
  <RemotePicker
    v-model="model"
    :fetch-options="fetchMusicianOptions"
    :scopes="MUSICIAN_SCOPES"
    :default-scope="defaultScope"
    :label="label"
    :placeholder="placeholder"
    :selected-label="selectedLabel"
    :create-label="creatable ? (t) => `„${t}“ als neuen Musiker anlegen …` : null"
    @select="(o) => (selectedLabel = o.label)"
    @create="startCreate"
  />
  <MusicianCreateDialog
    v-if="creatable"
    :open="creating"
    :initial-text="createText"
    @created="onCreated"
    @cancel="creating = false"
  />
</template>
