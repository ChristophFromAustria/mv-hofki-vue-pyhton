<script setup>
defineProps({
  allExpanded: Boolean,
  disabled: Boolean,
});
defineEmits(["expand-all", "collapse-all"]);
</script>

<template>
  <button
    type="button"
    class="group-toggle-all"
    :disabled="disabled"
    :aria-label="allExpanded ? 'Alle Gruppen zuklappen' : 'Alle Gruppen aufklappen'"
    :title="allExpanded ? 'Alle Gruppen zuklappen' : 'Alle Gruppen aufklappen'"
    @click="$emit(allExpanded ? 'collapse-all' : 'expand-all')"
  >
    <span aria-hidden="true">{{ allExpanded ? "⊟" : "⊞" }}</span>
  </button>
</template>

<style scoped>
.group-toggle-all {
  display: inline-grid;
  place-items: center;
  width: 44px;
  height: 44px;
  padding: 0;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-muted);
  font-size: 1.25rem;
  line-height: 1;
  cursor: pointer;
}

.group-toggle-all:hover:not(:disabled) {
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.group-toggle-all:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}

.group-toggle-all:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
