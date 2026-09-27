<script setup>
defineProps({
  options: { type: Array, required: true },
  modelValue: { type: String, default: "" },
});
defineEmits(["update:modelValue"]);
const id = `group-select-${Math.random().toString(36).slice(2, 9)}`;
</script>

<template>
  <div class="group-select">
    <label :for="id">Gruppieren nach</label>
    <select :id="id" :value="modelValue" @change="$emit('update:modelValue', $event.target.value)">
      <option value="">Keine</option>
      <option v-for="o in options" :key="o.key" :value="o.key">{{ o.label }}</option>
    </select>
  </div>
</template>

<style scoped>
.group-select {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.group-select label {
  font-size: 0.875rem;
  color: var(--color-muted);
  white-space: nowrap;
}

.group-select select {
  width: auto;
  min-height: 44px;
}
</style>
