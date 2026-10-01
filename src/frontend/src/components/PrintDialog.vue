<script setup>
import { computed, nextTick, ref, watch } from "vue";
import {
  DATASHEET_SECTIONS,
  MAX_PRINT_ITEMS,
  datasheetUrl,
  loadSections,
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
const sections = ref(loadSections());
const error = ref("");
const titleId = `print-${Math.random().toString(36).slice(2, 7)}`;

const tooMany = computed(() => props.count > MAX_PRINT_ITEMS);
const what = computed(() =>
  props.itemId != null ? "Datenblatt" : `${props.count} Datenblätter (eines pro Gegenstand)`,
);

watch(
  () => props.open,
  async (open) => {
    if (open) {
      sections.value = loadSections();
      error.value = "";
    }
    await nextTick();
    if (!dialog.value) return;
    if (open && !dialog.value.open) dialog.value.showModal();
    else if (!open && dialog.value.open) dialog.value.close();
  },
  { immediate: true },
);

function toggle(value, on) {
  sections.value = on ? [...sections.value, value] : sections.value.filter((s) => s !== value);
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
  saveSections(sections.value);
  const url = datasheetUrl({
    category: props.category,
    itemId: props.itemId,
    listParams: props.listParams,
    sections: DATASHEET_SECTIONS.map((s) => s.value).filter((s) => sections.value.includes(s)),
  });
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
        <p class="print-lead">
          {{ what }} als PDF – öffnet sich in einem neuen Tab, dort drucken oder speichern.
        </p>
        <fieldset class="print-fields">
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
  margin: 0 0 var(--space-2);
  font-size: 1.1rem;
}

.print-lead {
  margin: 0 0 var(--space-3);
  color: var(--color-muted);
  font-size: 0.875rem;
}

.print-fields {
  margin: 0;
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
</style>
