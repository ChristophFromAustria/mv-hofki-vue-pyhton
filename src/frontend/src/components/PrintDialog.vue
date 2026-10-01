<script setup>
import { computed, nextTick, ref, watch } from "vue";
import { get } from "../lib/api.js";
import {
  CUSTOM_FIELDS,
  DATASHEET_SECTIONS,
  MAX_PRINT_ITEMS,
  datasheetUrl,
  labelUrl,
  loadLabelSettings,
  loadSections,
  saveLabelSettings,
  saveSections,
} from "../lib/printing.js";

// "Drucken …": a PDF opens in a new tab, to print or save from there.
// One item (itemId) or all items the list shows (listParams + count).
const props = defineProps({
  open: Boolean,
  category: { type: String, required: true },
  itemId: { type: Number, default: null },
  listParams: { type: Object, default: null },
  count: { type: Number, default: 1 },
  title: { type: String, default: "Drucken" },
});
const emit = defineEmits(["close"]);

const dialog = ref(null);
const kind = ref("datasheet"); // datasheet | labels
const sections = ref(loadSections());
const label = ref(loadLabelSettings());
const presets = ref([]);
const publicUrl = ref("");
const error = ref("");
const titleId = `print-${Math.random().toString(36).slice(2, 7)}`;

const tooMany = computed(() => props.count > MAX_PRINT_ITEMS);
const single = computed(() => props.itemId != null);
const what = computed(() => {
  if (kind.value === "labels") return single.value ? "Etikett" : `${props.count} Etiketten`;
  return single.value ? "Datenblatt" : `${props.count} Datenblätter (eines pro Gegenstand)`;
});
const preset = computed(() => presets.value.find((p) => p.key === label.value.template));
const isCustom = computed(() => label.value.template === "custom");
const perPage = computed(() => {
  if (isCustom.value) {
    const { cols, rows } = label.value.custom;
    return cols > 0 && rows > 0 ? cols * rows : 1;
  }
  return preset.value?.per_page || 1;
});
const isSheet = computed(() => perPage.value > 1);

async function loadPresets() {
  if (presets.value.length) return;
  try {
    const info = await get("/print/label-presets");
    presets.value = info.presets;
    publicUrl.value = info.public_url;
  } catch (e) {
    error.value = "Etikettenformate konnten nicht geladen werden: " + e.message;
  }
}

watch(
  () => props.open,
  async (open) => {
    if (open) {
      sections.value = loadSections();
      label.value = loadLabelSettings();
      error.value = "";
    }
    await nextTick();
    if (!dialog.value) return;
    if (open && !dialog.value.open) dialog.value.showModal();
    else if (!open && dialog.value.open) dialog.value.close();
  },
  { immediate: true },
);

watch(kind, (value) => {
  if (value === "labels") loadPresets();
});

function toggle(value, on) {
  sections.value = on ? [...sections.value, value] : sections.value.filter((s) => s !== value);
}

function setCustom(key, raw) {
  const n = Number(raw);
  label.value.custom[key] = Number.isFinite(n) ? n : 0;
}

function print() {
  error.value = "";
  if (!props.count) {
    error.value = "Keine Gegenstände für diese Filter.";
    return;
  }
  if (tooMany.value) {
    error.value = `Höchstens ${MAX_PRINT_ITEMS} auf einmal – bitte die Liste weiter filtern.`;
    return;
  }
  const target = { category: props.category, itemId: props.itemId, listParams: props.listParams };
  let url;
  if (kind.value === "labels") {
    const start = Number(label.value.start) || 1;
    if (isSheet.value && (start < 1 || start > perPage.value)) {
      error.value = `„Beginnen bei“: 1 bis ${perPage.value}.`;
      return;
    }
    const settings = { ...label.value, start: isSheet.value ? start : 1 };
    saveLabelSettings(settings);
    url = labelUrl({ ...target, settings });
  } else {
    saveSections(sections.value);
    url = datasheetUrl({
      ...target,
      sections: DATASHEET_SECTIONS.map((s) => s.value).filter((s) => sections.value.includes(s)),
    });
  }
  window.open(url, "_blank", "noopener");
  emit("close");
}
</script>

<template>
  <Teleport to="body">
    <dialog
      ref="dialog"
      class="dialog dialog-md print-dialog"
      :aria-labelledby="titleId"
      @cancel.prevent="emit('close')"
    >
      <form novalidate @submit.prevent="print">
        <h2 :id="titleId">{{ title }}</h2>

        <div class="view-toggle print-kind" role="group" aria-label="Was drucken?">
          <button
            type="button"
            :class="{ active: kind === 'datasheet' }"
            :aria-pressed="kind === 'datasheet' ? 'true' : 'false'"
            @click="kind = 'datasheet'"
          >
            Datenblatt
          </button>
          <button
            type="button"
            :class="{ active: kind === 'labels' }"
            :aria-pressed="kind === 'labels' ? 'true' : 'false'"
            @click="kind = 'labels'"
          >
            Etiketten
          </button>
        </div>

        <p class="print-lead">
          {{ what }} als PDF – öffnet sich in einem neuen Tab, dort drucken oder speichern.
        </p>

        <fieldset v-if="kind === 'datasheet'" class="print-fields">
          <legend>Auf dem Datenblatt</legend>
          <label class="print-option print-fixed">
            <input type="checkbox" checked disabled />
            Nummer, Bezeichnung, QR-Code und Stammdaten
          </label>
          <label v-for="s in DATASHEET_SECTIONS" :key="s.value" class="print-option">
            <input
              type="checkbox"
              :checked="sections.includes(s.value)"
              @change="toggle(s.value, $event.target.checked)"
            />
            {{ s.label }}
          </label>
        </fieldset>

        <template v-else>
          <div class="form-group">
            <label for="print-template">Format</label>
            <select id="print-template" v-model="label.template">
              <option v-for="p in presets" :key="p.key" :value="p.key">{{ p.label }}</option>
              <option value="custom">Eigene Maße …</option>
            </select>
          </div>

          <fieldset v-if="isCustom" class="print-fields print-custom">
            <legend>Eigene Maße</legend>
            <label v-for="f in CUSTOM_FIELDS" :key="f.key" class="print-custom-field">
              <span>{{ f.label }}</span>
              <input
                type="number"
                :min="f.min"
                :max="f.max"
                :step="f.step"
                :value="label.custom[f.key]"
                inputmode="decimal"
                @input="setCustom(f.key, $event.target.value)"
              />
            </label>
          </fieldset>

          <div v-if="isSheet" class="form-group">
            <label for="print-start">Beginnen bei Etikett Nr.</label>
            <input
              id="print-start"
              v-model="label.start"
              type="number"
              min="1"
              :max="perPage"
              inputmode="numeric"
              class="input-narrow"
            />
            <span class="print-hint">
              1–{{ perPage }}, zeilenweise von links oben – für angebrochene Bögen.
            </span>
          </div>

          <label class="print-option">
            <input v-model="label.logo" type="checkbox" />
            Vereinslogo
          </label>
          <label class="print-option">
            <input v-model="label.frame" type="checkbox" />
            Rahmen um jedes Etikett (zum Ausrichten, Testdruck)
          </label>

          <p v-if="publicUrl" class="print-hint print-url">
            Die QR-Codes führen zu <strong>{{ publicUrl }}</strong
            >. Vor dem Bekleben vieler Gegenstände die endgültige Adresse klären.
          </p>
        </template>

        <p v-if="error" class="form-error" role="alert">{{ error }}</p>
        <div class="dialog-actions">
          <button type="button" @click="emit('close')">Abbrechen</button>
          <button type="submit" class="btn-primary" :disabled="tooMany || !count">
            PDF öffnen
          </button>
        </div>
        <p v-if="tooMany" class="form-error print-limit">
          {{ count }} Gegenstände – höchstens {{ MAX_PRINT_ITEMS }} auf einmal. Bitte die Liste
          weiter filtern.
        </p>
      </form>
    </dialog>
  </Teleport>
</template>

<style scoped>
.print-dialog {
  border: none;
}

.print-dialog::backdrop {
  background: var(--color-overlay);
}

.print-dialog h2 {
  margin: 0 0 var(--space-3);
  font-size: 1.1rem;
}

.print-kind {
  display: flex;
  margin-bottom: var(--space-3);
}

.print-kind button {
  flex: 1;
  min-height: 44px;
}

.print-lead {
  margin: 0 0 var(--space-3);
  color: var(--color-muted);
  font-size: 0.875rem;
}

.print-fields {
  margin: 0 0 var(--space-3);
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
}

.print-fields legend {
  padding: 0 var(--space-1);
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--color-muted);
}

.print-option {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-height: 44px;
}

.print-option input {
  width: auto;
}

.print-fixed {
  color: var(--color-muted);
}

.print-custom {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-2) var(--space-3);
}

.print-custom-field {
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: 0.8125rem;
}

.print-hint {
  display: block;
  margin-top: var(--space-1);
  font-size: 0.8125rem;
  color: var(--color-muted);
}

.print-url {
  margin: var(--space-2) 0 0;
  overflow-wrap: anywhere;
}

.dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
  margin-top: var(--space-4);
}

.dialog-actions button {
  min-height: 44px;
}

.print-limit {
  margin-top: var(--space-2);
}

@media (max-width: 640px) {
  .print-custom {
    grid-template-columns: 1fr;
  }
}
</style>
