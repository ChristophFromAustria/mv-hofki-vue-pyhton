<script setup>
import { computed, nextTick, ref, watch } from "vue";
import MarkdownText from "./MarkdownText.vue";

const props = defineProps({
  open: Boolean,
  title: { type: String, required: true },
  value: { type: String, default: null },
  maxLength: { type: Number, required: true },
  saving: Boolean,
  error: { type: String, default: "" },
});
const emit = defineEmits(["save", "cancel"]);

const dialog = ref(null);
const textarea = ref(null);
const draft = ref("");
const original = ref("");
const tab = ref("edit"); // edit | preview
const showDiscardConfirm = ref(false);

const isDirty = computed(() => draft.value !== original.value);
const length = computed(() => draft.value.length);
const overLimit = computed(() => length.value > props.maxLength);
const nearLimit = computed(() => !overLimit.value && length.value >= props.maxLength * 0.9);
const counterText = computed(
  () => `${length.value.toLocaleString("de-AT")} / ${props.maxLength.toLocaleString("de-AT")}`,
);
const overLimitMessage = computed(
  () => `Höchstens ${props.maxLength.toLocaleString("de-AT")} Zeichen`,
);
const canSave = computed(() => !props.saving && !overLimit.value);

// Reset state synchronously so it can never race with a user action that
// lands in the same tick as a delayed re-open (see CategoryPickDialog for
// the same pattern) — only the DOM calls (showModal/focus/close) need to
// wait for the dialog element to exist / re-render.
watch(
  () => props.open,
  (open) => {
    if (open) {
      draft.value = props.value ?? "";
      original.value = draft.value;
      tab.value = "edit";
      showDiscardConfirm.value = false;
    }
    nextTick(() => {
      if (!dialog.value) return;
      if (open) {
        if (!dialog.value.open) dialog.value.showModal();
        textarea.value?.focus();
      } else if (dialog.value.open) {
        dialog.value.close();
      }
    });
  },
  { immediate: true },
);

function selectionOf(ta) {
  return { start: ta.selectionStart, end: ta.selectionEnd };
}

async function focusSelection(start, end) {
  await nextTick();
  const ta = textarea.value;
  if (!ta) return;
  ta.focus();
  ta.setSelectionRange(start, end);
}

function wrapSelection(marker) {
  const ta = textarea.value;
  if (!ta) return;
  const { start, end } = selectionOf(ta);
  const selected = draft.value.slice(start, end);
  draft.value = draft.value.slice(0, start) + marker + selected + marker + draft.value.slice(end);
  focusSelection(start + marker.length, start + marker.length + selected.length);
}

function currentLineRange(pos) {
  const text = draft.value;
  const lineStart = text.lastIndexOf("\n", pos - 1) + 1;
  return lineStart;
}

function applyHeading() {
  const ta = textarea.value;
  if (!ta) return;
  const { start } = selectionOf(ta);
  const lineStart = currentLineRange(start);
  draft.value = draft.value.slice(0, lineStart) + "## " + draft.value.slice(lineStart);
  focusSelection(start + 3, start + 3);
}

function applyLinePrefix(prefixFor) {
  const ta = textarea.value;
  if (!ta) return;
  const { start, end } = selectionOf(ta);
  const text = draft.value;
  const segStart = text.lastIndexOf("\n", start - 1) + 1;
  let segEnd = text.indexOf("\n", end);
  if (segEnd === -1) segEnd = text.length;
  const segment = text.slice(segStart, segEnd);
  const lines = segment.split("\n");
  const prefixed = lines.map((line, i) => prefixFor(i + 1) + line).join("\n");
  draft.value = text.slice(0, segStart) + prefixed + text.slice(segEnd);
  focusSelection(segStart, segStart + prefixed.length);
}

function applyLink() {
  const ta = textarea.value;
  if (!ta) return;
  const { start, end } = selectionOf(ta);
  const selected = draft.value.slice(start, end) || "Text";
  const before = draft.value.slice(0, start);
  const after = draft.value.slice(end);
  draft.value = `${before}[${selected}](https://)${after}`;
  const urlStart = start + selected.length + 3;
  focusSelection(urlStart, urlStart + 8);
}

const toolbarButtons = [
  { key: "bold", label: "Fett", hint: "Fett (**)", glyph: "B", action: () => wrapSelection("**") },
  {
    key: "italic",
    label: "Kursiv",
    hint: "Kursiv (*)",
    glyph: "I",
    action: () => wrapSelection("*"),
  },
  {
    key: "heading",
    label: "Überschrift",
    hint: "Überschrift (##)",
    glyph: "H",
    action: applyHeading,
  },
  {
    key: "list",
    label: "Aufzählung",
    hint: "Aufzählung (-)",
    glyph: "•",
    action: () => applyLinePrefix(() => "- "),
  },
  {
    key: "ordered",
    label: "Nummerierte Liste",
    hint: "Nummerierte Liste (1. …)",
    glyph: "1.",
    action: () => applyLinePrefix((n) => `${n}. `),
  },
  { key: "link", label: "Link", hint: "Link ([Text](https://))", glyph: "🔗", action: applyLink },
];

function trySave() {
  if (!canSave.value) return;
  const trimmed = draft.value.trim();
  emit("save", trimmed ? draft.value : null);
}

function onKeydown(e) {
  if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
    e.preventDefault();
    trySave();
  }
}

function requestClose() {
  if (props.saving) return;
  if (isDirty.value) {
    showDiscardConfirm.value = true;
  } else {
    emit("cancel");
  }
}

function discard() {
  showDiscardConfirm.value = false;
  emit("cancel");
}

function keepEditing() {
  showDiscardConfirm.value = false;
}
</script>

<template>
  <dialog ref="dialog" class="notes-dialog" @cancel.prevent="requestClose" @keydown="onKeydown">
    <div class="notes-dialog-inner">
      <h2>{{ title }}</h2>

      <template v-if="!showDiscardConfirm">
        <div class="notes-toolbar" role="toolbar" aria-label="Formatierung">
          <button
            v-for="btn in toolbarButtons"
            :key="btn.key"
            type="button"
            class="notes-toolbar-btn"
            :aria-label="btn.label"
            :title="btn.hint"
            :disabled="tab === 'preview'"
            @click="btn.action"
          >
            {{ btn.glyph }}
          </button>
        </div>

        <div class="view-toggle notes-tabs">
          <button
            type="button"
            :class="{ active: tab === 'edit' }"
            aria-label="Bearbeiten"
            @click="tab = 'edit'"
          >
            Bearbeiten
          </button>
          <button
            type="button"
            :class="{ active: tab === 'preview' }"
            aria-label="Vorschau"
            @click="tab = 'preview'"
          >
            Vorschau
          </button>
        </div>

        <div class="notes-content">
          <textarea
            v-if="tab === 'edit'"
            ref="textarea"
            v-model="draft"
            class="notes-textarea"
            :aria-label="title"
          />
          <div v-else class="notes-preview">
            <MarkdownText :text="draft" />
          </div>
        </div>

        <div class="notes-footer-row">
          <span
            class="notes-counter"
            :class="{ 'is-warning': nearLimit, 'is-danger': overLimit }"
            aria-live="polite"
            >{{ counterText }}</span
          >
        </div>
        <p v-if="overLimit" class="form-error" role="alert">{{ overLimitMessage }}</p>
        <p v-else-if="error" class="form-error" role="alert">{{ error }}</p>

        <div class="notes-actions">
          <button type="button" class="notes-cancel" :disabled="saving" @click="requestClose">
            Abbrechen
          </button>
          <button
            type="button"
            class="btn-primary notes-save"
            :disabled="!canSave"
            @click="trySave"
          >
            {{ saving ? "Speichert …" : "Speichern" }}
          </button>
        </div>
      </template>

      <div v-else class="notes-discard-confirm">
        <p>Änderungen verwerfen?</p>
        <div class="notes-actions">
          <button type="button" class="btn-danger" @click="discard">Verwerfen</button>
          <button type="button" class="btn-primary" @click="keepEditing">Weiter bearbeiten</button>
        </div>
      </div>
    </div>
  </dialog>
</template>

<style scoped>
.notes-dialog {
  border: none;
  border-radius: var(--radius);
  padding: 0;
  width: min(56rem, 100vw - 2rem);
  height: min(80vh, 48rem);
  max-width: none;
  max-height: none;
  background: var(--color-bg);
  color: var(--color-text);
  box-shadow: var(--shadow-dialog);
}

.notes-dialog::backdrop {
  background: var(--color-overlay);
}

.notes-dialog-inner {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: var(--space-4) var(--space-5);
  gap: var(--space-3);
}

.notes-dialog h2 {
  font-size: 1.1rem;
  font-weight: 600;
  margin: 0;
}

.notes-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.notes-toolbar-btn {
  min-width: 44px;
  min-height: 44px;
  padding: 0 var(--space-2);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-bg);
  color: var(--color-text);
  cursor: pointer;
}

.notes-toolbar-btn:hover {
  background: var(--color-bg-soft);
}

.notes-tabs {
  align-self: flex-start;
}

.notes-tabs button {
  min-height: 44px;
}

.notes-content {
  flex: 1;
  min-height: 0;
  display: flex;
}

.notes-textarea {
  flex: 1;
  width: 100%;
  resize: none;
  font-family: var(--font-sans);
  font-size: 0.95rem;
  line-height: 1.6;
}

.notes-preview {
  flex: 1;
  width: 100%;
  overflow-y: auto;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  padding: var(--space-3) var(--space-4);
}

.notes-footer-row {
  display: flex;
  justify-content: flex-end;
}

.notes-counter {
  font-size: 0.8125rem;
  color: var(--color-muted);
  font-variant-numeric: tabular-nums;
}

.notes-counter.is-warning {
  color: var(--color-warning);
}

.notes-counter.is-danger {
  color: var(--color-danger);
}

.notes-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
}

.notes-actions button {
  min-height: 44px;
}

.notes-discard-confirm {
  margin: auto 0;
  padding: var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  background: var(--color-bg-soft);
}

.notes-discard-confirm p {
  margin: 0 0 var(--space-3);
  font-weight: 500;
}

@media (max-width: 640px) {
  .notes-dialog {
    width: 100vw;
    height: 100dvh;
    max-width: 100vw;
    max-height: 100dvh;
    inset: 0;
    margin: 0;
    border-radius: 0;
  }
}
</style>
