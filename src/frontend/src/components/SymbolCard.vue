<script setup>
import { computed } from "vue";
import { symbolCategoryLabel } from "../lib/symbolCategories.js";

const props = defineProps({
  template: { type: Object, required: true },
});

const emit = defineEmits(["edit"]);

const matchingHint = computed(() => {
  const t = props.template;
  const parts = [];
  if (t.min_confidence != null) parts.push(`min. ${Math.round(t.min_confidence * 100)} %`);
  if (t.confidence_weight != null) parts.push(`× ${t.confidence_weight}`);
  if (t.merge_overlapping) parts.push("zusammenführen");
  return parts.join(" · ");
});

const variantClass = computed(() => {
  const c = props.template.variant_count;
  if (c === 0) return "vc-none";
  if (c >= 6) return "vc-good";
  return "vc-few";
});
</script>

<template>
  <div class="symbol-card" @click="emit('edit', template)">
    <span class="category-badge">{{ symbolCategoryLabel(template.category) }}</span>
    <span class="display-name">{{ template.display_name }}</span>
    <div class="card-footer">
      <span :class="['variant-count', variantClass]">
        {{ template.variant_count }}
        {{ template.variant_count === 1 ? "Variante" : "Varianten" }}
      </span>
      <span v-if="matchingHint" class="matching-hint" title="Eigene Erkennungs-Parameter">
        {{ matchingHint }}
      </span>
    </div>
  </div>
</template>

<style scoped>
.symbol-card {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  padding: 0.75rem 1rem;
  background: var(--color-bg);
  transition:
    box-shadow var(--transition),
    background var(--transition);
  cursor: pointer;
}

.symbol-card:hover {
  background: var(--color-bg-soft);
  box-shadow: var(--shadow-float);
}

.category-badge {
  font-size: 0.7rem;
  padding: 2px 6px;
  border-radius: 3px;
  background: var(--color-primary-light);
  color: var(--color-primary);
  font-weight: 600;
  align-self: flex-start;
}

.display-name {
  font-weight: 600;
  font-size: 0.95rem;
}

.card-footer {
  margin-top: auto;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.4rem;
}

.matching-hint {
  font-size: 0.7rem;
  color: var(--color-muted);
  font-variant-numeric: tabular-nums;
}

.variant-count {
  display: inline-block;
  font-size: 0.75rem;
  font-weight: 600;
  padding: 2px 6px;
  border-radius: 3px;
}

.vc-none {
  background: var(--color-danger-bg);
  color: var(--color-danger);
}

.vc-few {
  background: var(--color-warning-bg);
  color: var(--color-warning);
}

.vc-good {
  background: var(--color-success-bg);
  color: var(--color-success);
}
</style>
