<script setup>
defineProps({
  count: { type: Number, default: 0 },
  busy: Boolean,
  message: { type: String, default: "" },
  error: { type: String, default: "" },
});
defineEmits(["add", "remove", "select-all", "done"]);
</script>

<template>
  <div class="bulk-bar" role="region" aria-label="Sammelauswahl">
    <p class="bulk-count">{{ count }} ausgewählt</p>
    <div class="bulk-actions">
      <button type="button" class="btn-sm" :disabled="busy" @click="$emit('select-all')">
        Alle geladenen auswählen
      </button>
      <button
        type="button"
        class="btn-sm btn-primary"
        :disabled="busy || !count"
        @click="$emit('add')"
      >
        Kategorien hinzufügen
      </button>
      <button type="button" class="btn-sm" :disabled="busy || !count" @click="$emit('remove')">
        Kategorien entfernen
      </button>
      <button type="button" class="btn-sm" :disabled="busy" @click="$emit('done')">Fertig</button>
    </div>
    <p v-if="error" class="form-error" role="alert">{{ error }}</p>
    <p v-else-if="message" class="bulk-message" role="status">{{ message }}</p>
  </div>
</template>

<style scoped>
.bulk-bar {
  position: sticky;
  bottom: 0;
  z-index: 15;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2) var(--space-4);
  margin-top: var(--space-4);
  padding: var(--space-3) var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  background: var(--color-bg);
  box-shadow: var(--shadow-float);
}

.bulk-count {
  margin: 0;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.bulk-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.bulk-actions .btn-sm {
  min-height: 44px;
}

.bulk-message,
.bulk-bar .form-error {
  flex-basis: 100%;
  margin: 0;
}
</style>
