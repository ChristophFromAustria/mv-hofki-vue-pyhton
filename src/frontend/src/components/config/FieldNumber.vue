<script setup>
defineProps({ entry: { type: Object, required: true } });
const emit = defineEmits(["update", "reset"]);
</script>

<template>
  <label class="number-row">
    <span class="field-name">
      {{ entry.label }}
      <span class="field-value-group">
        <strong>{{ entry.value }}</strong>
        <span v-if="entry.is_modified" class="default-hint">(Std: {{ entry.default_value }})</span>
        <span v-if="entry.is_modified" class="modified-dot" title="Geändert"></span>
        <button
          v-if="entry.is_modified"
          class="reset-btn"
          title="Zurücksetzen"
          @click.prevent="emit('reset', entry.key)"
        >
          ↺
        </button>
      </span>
    </span>
    <input
      type="range"
      :value="entry.value"
      :min="entry.min"
      :max="entry.max"
      :step="entry.step"
      @input="emit('update', entry.key, Number($event.target.value))"
    />
  </label>
</template>

<style scoped>
.number-row {
  display: block;
  font-size: 0.85rem;
  color: var(--color-muted);
}
.field-name {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 0.25rem;
}
.field-name strong {
  color: var(--color-text);
}
.field-value-group {
  display: flex;
  align-items: baseline;
  gap: 0.35rem;
}
.number-row input[type="range"] {
  width: 100%;
  margin-top: 0.2rem;
  accent-color: var(--color-primary);
}
.modified-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-primary);
  flex-shrink: 0;
}
.default-hint {
  font-size: 0.75rem;
  color: var(--color-muted);
  font-weight: normal;
}
.reset-btn {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 0.85rem;
  color: var(--color-muted);
  padding: 0 0.15rem;
  line-height: 1;
}
.reset-btn:hover {
  color: var(--color-primary);
}
</style>
