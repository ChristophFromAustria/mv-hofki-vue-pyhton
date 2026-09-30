<script setup>
// An on/off switch that acts immediately (role="switch"). The accessible name
// stays the same (`label`); aria-checked carries the state, the visible text
// says it in words (`onText` / `offText`).
defineProps({
  checked: Boolean,
  label: { type: String, required: true },
  onText: { type: String, default: "Ein" },
  offText: { type: String, default: "Aus" },
  disabled: Boolean,
});
defineEmits(["toggle"]);
</script>

<template>
  <button
    type="button"
    role="switch"
    class="toggle-switch"
    :class="{ 'is-on': checked }"
    :aria-checked="checked ? 'true' : 'false'"
    :aria-label="label"
    :disabled="disabled"
    @click="$emit('toggle')"
  >
    <span class="toggle-track" aria-hidden="true"><span class="toggle-thumb" /></span>
    <span class="toggle-text" aria-hidden="true">{{ checked ? onText : offText }}</span>
  </button>
</template>

<style scoped>
.toggle-switch {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  min-height: 44px;
  padding: 0;
  border: none;
  background: transparent;
  color: var(--color-text);
  font: inherit;
  cursor: pointer;
}

.toggle-switch:disabled {
  cursor: default;
  opacity: 0.7;
}

.toggle-track {
  position: relative;
  flex-shrink: 0;
  width: 40px;
  height: 24px;
  border-radius: 12px;
  background: var(--color-muted);
  transition: background-color 0.2s cubic-bezier(0.16, 1, 0.3, 1);
}

.toggle-thumb {
  position: absolute;
  top: 3px;
  left: 3px;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: var(--color-bg);
  transition: transform 0.2s cubic-bezier(0.16, 1, 0.3, 1);
}

.is-on .toggle-track {
  background: var(--color-success);
}

.is-on .toggle-thumb {
  transform: translateX(16px);
}

.toggle-switch:focus-visible {
  outline: none;
}

.toggle-switch:focus-visible .toggle-track {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}

.toggle-text {
  font-weight: 500;
}

@media (prefers-reduced-motion: reduce) {
  .toggle-track,
  .toggle-thumb {
    transition: none;
  }
}
</style>
