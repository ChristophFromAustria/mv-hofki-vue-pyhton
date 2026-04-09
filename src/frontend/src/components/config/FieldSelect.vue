<script setup>
defineProps({ entry: { type: Object, required: true } });
const emit = defineEmits(["update", "reset"]);
</script>

<template>
  <label class="select-row">
    <span class="field-name">
      {{ entry.label }}
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
    <select :value="entry.value" @change="emit('update', entry.key, $event.target.value)">
      <option v-for="opt in entry.options" :key="opt.value" :value="opt.value">
        {{ opt.label }}
      </option>
    </select>
    <span v-if="entry.is_modified" class="default-hint">
      Standard:
      {{
        entry.options?.find((o) => o.value === entry.default_value)?.label || entry.default_value
      }}
    </span>
  </label>
</template>

<style scoped>
.select-row {
  display: block;
  font-size: 0.85rem;
  color: var(--color-muted);
}
.select-row select {
  display: block;
  width: 100%;
  margin-top: 0.25rem;
  padding: 0.4rem 0.5rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  background: var(--color-bg);
  color: var(--color-text);
  font-family: inherit;
  font-size: 0.85rem;
}
.field-name {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 0.25rem;
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
