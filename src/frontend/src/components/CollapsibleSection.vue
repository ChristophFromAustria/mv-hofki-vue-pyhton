<script setup>
import { useSectionCollapse } from "../composables/useSectionCollapse.js";

const props = defineProps({
  scope: { type: String, required: true },
  section: { type: String, required: true },
  title: { type: String, required: true },
  summary: { type: String, default: "" },
});

const { open, toggle } = useSectionCollapse(props.scope, props.section);
const panelId = `section-${props.scope}-${props.section}`;
</script>

<template>
  <section class="page-section collapsible-section">
    <div class="section-header">
      <h2 class="collapsible-heading">
        <button
          type="button"
          class="collapsible-toggle"
          :aria-expanded="String(open)"
          :aria-controls="open ? panelId : undefined"
          @click="toggle"
        >
          <span class="collapsible-chevron" aria-hidden="true">{{ open ? "▾" : "▸" }}</span>
          <span>{{ title }}</span>
          <span v-if="!open && summary" class="section-summary">{{ summary }}</span>
        </button>
      </h2>
      <div v-if="$slots.actions" class="collapsible-actions">
        <slot name="actions" />
      </div>
    </div>
    <div v-if="open" :id="panelId" class="collapsible-body">
      <slot />
    </div>
  </section>
</template>

<style scoped>
/* .section-header h2 in style.css already sets font-size/font-weight/line-height
   for this h2 — do not give .collapsible-heading its own font-size here: a scoped
   class selector plus the Vue data-v attribute outranks that global tag+class
   selector, so an "inherit" here would win and reset the heading to the wrong size.
   The button below picks up the h2's resulting font via `font: inherit`. */
.collapsible-heading {
  margin: 0;
}

.collapsible-toggle {
  display: inline-flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: var(--space-2);
  min-height: 44px;
  padding: 0;
  border: none;
  background: transparent;
  color: inherit;
  font: inherit;
  font-weight: 600;
  text-align: left;
  cursor: pointer;
}

.collapsible-toggle:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}

.collapsible-chevron {
  width: 1em;
  color: var(--color-muted);
}

.section-summary {
  font-weight: 400;
  font-size: 0.875rem;
  color: var(--color-muted);
  font-variant-numeric: tabular-nums;
}

.collapsible-actions {
  display: flex;
  gap: var(--space-2);
}
</style>
