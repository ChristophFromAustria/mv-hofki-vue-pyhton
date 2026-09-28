<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from "vue";
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
const keepEditingBtn = ref(null);
const draft = ref("");
const original = ref("");
const tab = ref("edit"); // edit | preview
const showDiscardConfirm = ref(false);
const discardTitleId = `notes-discard-${Math.random().toString(36).slice(2, 7)}`;

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
// On phones the dialog is fullscreen. The on-screen keyboard only shrinks the
// *visual* viewport (100dvh stays the same on iOS), so the browser would scroll
// the page and push the header/toolbar out of view. Pin the dialog to the
// visible area instead and follow it while the keyboard moves.
const viewportStyle = ref({});
let trackedViewport = null;

function updateViewport() {
  const vv = window.visualViewport;
  const isPhone = window.matchMedia?.("(max-width: 640px)").matches;
  viewportStyle.value = vv && isPhone ? { height: `${vv.height}px`, top: `${vv.offsetTop}px` } : {};
}

function trackViewport(on) {
  const vv = window.visualViewport;
  if (on && vv && !trackedViewport) {
    trackedViewport = vv;
    vv.addEventListener("resize", updateViewport);
    vv.addEventListener("scroll", updateViewport);
  } else if (!on && trackedViewport) {
    trackedViewport.removeEventListener("resize", updateViewport);
    trackedViewport.removeEventListener("scroll", updateViewport);
    trackedViewport = null;
  }
  if (on) updateViewport();
}

onBeforeUnmount(() => trackViewport(false));

watch(
  () => props.open,
  (open) => {
    trackViewport(open);
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

// Focus follows the UI back to whatever the person can now act on: the
// "Weiter bearbeiten" button when the discard prompt appears, the textarea
// when editing resumes (via "Weiter bearbeiten" or the Vorschau→Bearbeiten tab).
watch(showDiscardConfirm, async (shown) => {
  if (!shown) return;
  await nextTick();
  keepEditingBtn.value?.focus();
});

watch(tab, async (value) => {
  if (value !== "edit") return;
  await nextTick();
  textarea.value?.focus();
});

// A dialog can close itself natively without our @cancel.prevent running —
// e.g. a second Escape press with no fresh user activation bypasses it. If
// that happens with unsaved text, reopen and show the discard prompt instead
// of silently losing the draft; otherwise just tell the parent to clear
// editingKey. `props.open` is still true here only for that unrequested
// close — our own close() call (triggered by open turning false) always
// runs after the prop has already flipped.
function onNativeClose() {
  if (!props.open) return;
  if (isDirty.value) {
    showDiscardConfirm.value = true;
    nextTick(() => dialog.value?.showModal());
  } else {
    emit("cancel");
  }
}

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
  { key: "link", label: "Link", hint: "Link ([Text](https://))", svg: true, action: applyLink },
];

function trySave() {
  if (!canSave.value) return;
  const trimmed = draft.value.trim();
  emit("save", trimmed ? draft.value : null);
}

function onKeydown(e) {
  if (showDiscardConfirm.value) return;
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

async function keepEditing() {
  showDiscardConfirm.value = false;
  // The edit UI (including the textarea) was unmounted while the discard
  // prompt was shown — the `tab` watcher above won't fire since `tab` itself
  // never changed, so refocus explicitly once it's back.
  await nextTick();
  textarea.value?.focus();
}
</script>

<template>
  <dialog
    ref="dialog"
    class="notes-dialog"
    :style="viewportStyle"
    @cancel.prevent="requestClose"
    @close="onNativeClose"
    @keydown="onKeydown"
  >
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
            <svg
              v-if="btn.svg"
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              aria-hidden="true"
            >
              <path d="M10 13a5 5 0 0 0 7.07 0l2.83-2.83a5 5 0 0 0-7.07-7.07L11.5 4.5" />
              <path d="M14 11a5 5 0 0 0-7.07 0L4.1 13.83a5 5 0 0 0 7.07 7.07l1.36-1.36" />
            </svg>
            <template v-else>{{ btn.glyph }}</template>
          </button>
        </div>

        <div class="view-toggle notes-tabs">
          <button
            type="button"
            :class="{ active: tab === 'edit' }"
            :aria-pressed="tab === 'edit'"
            @click="tab = 'edit'"
          >
            Bearbeiten
          </button>
          <button
            type="button"
            :class="{ active: tab === 'preview' }"
            :aria-pressed="tab === 'preview'"
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

      <div
        v-else
        class="notes-discard-confirm"
        role="alertdialog"
        :aria-labelledby="discardTitleId"
      >
        <p :id="discardTitleId">Änderungen verwerfen?</p>
        <div class="notes-actions">
          <button type="button" class="btn-danger" @click="discard">Verwerfen</button>
          <button ref="keepEditingBtn" type="button" class="btn-primary" @click="keepEditing">
            Weiter bearbeiten
          </button>
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
  /* Fullscreen; height/top follow the visual viewport (see viewportStyle). */
  .notes-dialog {
    position: fixed;
    top: 0;
    left: 0;
    right: auto;
    bottom: auto;
    width: 100vw;
    height: 100dvh;
    max-width: 100vw;
    max-height: none;
    margin: 0;
    border-radius: 0;
  }

  .notes-dialog-inner {
    padding: var(--space-3);
  }
}
</style>
