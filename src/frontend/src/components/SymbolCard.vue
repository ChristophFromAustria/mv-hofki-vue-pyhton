<script setup>
defineProps({
  template: { type: Object, required: true },
});
</script>

<template>
  <div class="symbol-card">
    <div class="card-header">
      <span class="display-name">{{ template.display_name }}</span>
      <span class="category-badge">{{ template.category }}</span>
    </div>
    <div class="card-footer">
      <span class="variant-count">
        {{ template.variant_count }}
        {{ template.variant_count === 1 ? "Variante" : "Varianten" }}
      </span>
      <span v-if="template.is_seed" class="seed-badge">Vorlage</span>
    </div>
  </div>
</template>

<style scoped>
.symbol-card {
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  padding: 0.75rem 1rem;
  background: var(--color-bg);
  transition:
    box-shadow var(--transition),
    background var(--transition);
  cursor: default;
}

.symbol-card:hover {
  background: var(--color-bg-soft);
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.08);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
}

.display-name {
  font-weight: 600;
  font-size: 0.95rem;
}

.category-badge {
  font-size: 0.7rem;
  padding: 2px 6px;
  border-radius: 3px;
  background: var(--color-primary-light);
  color: var(--color-primary);
  font-weight: 600;
  white-space: nowrap;
  text-transform: capitalize;
}

.card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.variant-count {
  font-size: 0.8rem;
  color: var(--color-muted);
}

.seed-badge {
  font-size: 0.7rem;
  padding: 2px 5px;
  border-radius: 3px;
  background: #f3f4f6;
  color: #6b7280;
  border: 1px solid #d1d5db;
}
</style>
