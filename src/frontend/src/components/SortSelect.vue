<script setup>
import { computed } from "vue";

const props = defineProps({
  options: { type: Array, required: true },
  modelValue: { type: String, default: "" },
});
const emit = defineEmits(["update:modelValue"]);

const id = `sort-select-${Math.random().toString(36).slice(2, 9)}`;
const key = computed(() => props.modelValue.replace(/^[-+]/, ""));
const desc = computed(() => props.modelValue.startsWith("-"));

function setKey(k) {
  emit("update:modelValue", desc.value ? `-${k}` : k);
}

function flip() {
  emit("update:modelValue", desc.value ? key.value : `-${key.value}`);
}
</script>

<template>
  <div class="sort-select">
    <label :for="id">Sortieren nach</label>
    <select :id="id" :value="key" @change="setKey($event.target.value)">
      <option v-for="o in options" :key="o.key" :value="o.key">{{ o.label }}</option>
    </select>
    <button
      type="button"
      class="btn-sm sort-dir"
      :aria-label="
        desc
          ? 'Absteigend sortiert – auf aufsteigend umschalten'
          : 'Aufsteigend sortiert – auf absteigend umschalten'
      "
      @click="flip"
    >
      <span aria-hidden="true">{{ desc ? "↓" : "↑" }}</span>
    </button>
  </div>
</template>

<style scoped>
.sort-select {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.sort-select label {
  font-size: 0.875rem;
  color: var(--color-muted);
  white-space: nowrap;
}

.sort-select select {
  width: auto;
  min-height: 44px;
}

.sort-dir {
  min-width: 44px;
  min-height: 44px;
}
</style>
