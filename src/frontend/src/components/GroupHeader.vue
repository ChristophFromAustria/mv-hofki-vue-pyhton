<script setup>
defineProps({
  label: { type: String, required: true },
  count: { type: Number, default: null },
  collapsed: Boolean,
});
defineEmits(["toggle"]);
</script>

<template>
  <button
    type="button"
    class="group-header"
    :aria-expanded="String(!collapsed)"
    @click="$emit('toggle')"
  >
    <span class="group-chevron" aria-hidden="true">{{ collapsed ? "▸" : "▾" }}</span>
    <span class="group-label">{{ label }}</span>
    <span v-if="count !== null" class="group-count">{{ count }}</span>
  </button>
</template>

<style scoped>
.group-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  width: 100%;
  min-height: 44px;
  padding: 0 var(--space-2);
  border: none;
  border-bottom: 1px solid var(--color-border);
  background: var(--color-bg-soft);
  color: var(--color-text);
  font: inherit;
  font-weight: 600;
  text-align: left;
  cursor: pointer;
}

.group-header:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: -2px;
}

.group-chevron {
  width: 1em;
  color: var(--color-muted);
}

.group-count {
  margin-left: auto;
  font-weight: 500;
  font-variant-numeric: tabular-nums;
  color: var(--color-muted);
}
</style>
