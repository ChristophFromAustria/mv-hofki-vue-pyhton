<script setup>
import MarkdownText from "./MarkdownText.vue";
import NotesEditorDialog from "./NotesEditorDialog.vue";

defineProps({
  label: { type: String, required: true },
  value: { type: String, default: null },
  maxLength: { type: Number, required: true },
  saving: Boolean,
  saved: Boolean,
  error: { type: String, default: "" },
  editing: Boolean,
});
const emit = defineEmits(["start", "cancel", "save"]);
</script>

<template>
  <div class="notes-block">
    <div class="notes-block-header">
      <h3>{{ label }}</h3>
      <button
        type="button"
        class="notes-block-edit-btn"
        :aria-label="`„${label}“ bearbeiten`"
        :disabled="saving"
        @click="emit('start')"
      >
        <span aria-hidden="true">✎</span>
      </button>
      <span class="notes-block-status" role="status" aria-live="polite">{{
        saving ? "Speichert …" : saved ? "Gespeichert" : ""
      }}</span>
    </div>

    <MarkdownText :text="value" />

    <NotesEditorDialog
      :open="editing"
      :title="`${label} bearbeiten`"
      :value="value"
      :max-length="maxLength"
      :saving="saving"
      :error="error"
      @save="(v) => emit('save', v)"
      @cancel="emit('cancel')"
    />
  </div>
</template>

<style scoped>
.notes-block {
  margin-top: var(--space-5);
  padding-top: var(--space-4);
  border-top: 1px solid var(--color-border);
  max-width: 60rem;
}

.notes-block-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-2);
}

.notes-block-header h3 {
  font-size: 0.9rem;
  font-weight: 500;
  color: var(--color-muted);
  flex: 1 1 auto;
}

.notes-block-edit-btn {
  display: inline-grid;
  place-items: center;
  width: 44px;
  height: 44px;
  padding: 0;
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-muted);
  cursor: pointer;
}

.notes-block-edit-btn:hover,
.notes-block-edit-btn:focus-visible {
  border-color: var(--color-border);
  color: var(--color-primary);
}

.notes-block-status {
  font-size: 0.8125rem;
  color: var(--color-success);
}
</style>
