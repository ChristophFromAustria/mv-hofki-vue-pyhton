<script setup>
defineProps({ entry: { type: Object, required: true } });
const emit = defineEmits(["update", "reset"]);
</script>

<template>
  <label class="toggle-row">
    <input
      type="checkbox"
      class="toggle-checkbox"
      :checked="entry.value"
      @change="emit('update', entry.key, $event.target.checked)"
    />
    <span>{{ entry.label }}</span>
    <span v-if="entry.is_modified" class="modified-dot" title="Geändert"></span>
    <button
      v-if="entry.is_modified"
      class="reset-btn"
      title="Zurücksetzen"
      @click.prevent="emit('reset', entry.key)"
    >
      ↺
    </button>
  </label>
</template>

<style scoped>
.toggle-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
  font-size: 0.9rem;
}
.toggle-checkbox {
  width: 1.1rem;
  height: 1.1rem;
  accent-color: var(--color-primary);
  cursor: pointer;
}
.modified-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-primary);
  flex-shrink: 0;
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
