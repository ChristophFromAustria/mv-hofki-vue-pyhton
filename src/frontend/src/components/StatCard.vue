<script setup>
defineProps({
  title: { type: String, default: "" },
  value: { type: [Number, String], default: 0 },
  to: { type: String, default: "" },
});
</script>

<template>
  <component :is="to ? 'router-link' : 'div'" :to="to || undefined" class="card stat-card">
    <div class="stat-value">{{ value }}</div>
    <div class="stat-title">{{ title }}</div>
  </component>
</template>

<style scoped>
.stat-card {
  text-align: center;
  display: block;
  color: inherit;
}
a.stat-card {
  text-decoration: none;
  transition: box-shadow 0.15s;
}
a.stat-card:hover {
  box-shadow: 0 4px 12px var(--color-shadow);
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
