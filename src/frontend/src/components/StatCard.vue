<script setup>
defineProps({
  title: { type: String, default: "" },
  value: { type: [Number, String], default: 0 },
});
</script>

<template>
  <div class="card stat-card">
    <div class="stat-value">{{ value }}</div>
    <div class="stat-title">{{ title }}</div>
  </div>
</template>

<style scoped>
.stat-card {
  text-align: center;
}
.stat-value {
  font-size: 2rem;
  font-weight: 700;
  color: var(--color-primary);
}
.stat-title {
  font-size: 0.875rem;
  color: var(--color-muted);
  margin-top: 0.25rem;
}
</style>
