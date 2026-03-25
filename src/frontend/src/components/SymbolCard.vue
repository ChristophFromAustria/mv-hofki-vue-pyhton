<script setup>
import { computed } from "vue";

const props = defineProps({
  template: { type: Object, required: true },
});

const emit = defineEmits(["edit"]);

const variantClass = computed(() => {
  const c = props.template.variant_count;
  if (c === 0) return "vc-none";
  if (c >= 6) return "vc-good";
  return "vc-few";
});

const categoryLabels = {
  note: "Noten",
  rest: "Pausen",
  accidental: "Vorzeichen",
  clef: "Schlüssel",
  time_sig: "Taktarten",
  time_signature: "Taktarten",
  barline: "Taktstriche",
  dynamic: "Dynamik",
  ornament: "Verzierungen",
  other: "Sonstige",
};
</script>

<template>
  <div class="symbol-card" @click="emit('edit', template)">
    <span class="category-badge">{{ categoryLabels[template.category] || template.category }}</span>
    <span class="display-name">{{ template.display_name }}</span>
    <div class="card-footer">
      <span :class="['variant-count', variantClass]">
        {{ template.variant_count }}
        {{ template.variant_count === 1 ? "Variante" : "Varianten" }}
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
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.08);
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
}

.variant-count {
  display: inline-block;
  font-size: 0.75rem;
  font-weight: 600;
  padding: 2px 6px;
  border-radius: 3px;
}

.vc-none {
  background: #fef2f2;
  color: #dc2626;
}

.vc-few {
  background: #fefce8;
  color: #a16207;
}

.vc-good {
  background: #f0fdf4;
  color: #16a34a;
}
</style>
