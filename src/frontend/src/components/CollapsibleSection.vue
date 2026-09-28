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
  <section class="page-section collapsible-section" :class="{ 'is-open': open }">
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
  flex: 1 1 auto;
  min-width: 0;
  margin: 0;
}

/* Tighter than a plain .page-section: detail pages stack many of these. */
.collapsible-section {
  padding-block: var(--space-3);
}

.collapsible-section:first-of-type {
  padding-top: 0;
}

.collapsible-section .section-header {
  align-items: center;
  margin-bottom: 0;
}

.collapsible-section.is-open .section-header {
  margin-bottom: var(--space-3);
}

/* The whole header row is the hit area (easier on phones); the negative
   margin keeps the text aligned with the content below. */
.collapsible-toggle {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: var(--space-2);
  width: calc(100% + 2 * var(--space-2));
  min-height: 44px;
  margin-inline: calc(-1 * var(--space-2));
  padding: var(--space-2);
  border: none;
  border-radius: var(--radius-sm);
  background: transparent;
  color: inherit;
  font: inherit;
  font-weight: 600;
  text-align: left;
  cursor: pointer;
}

.collapsible-toggle:hover {
  background: var(--color-bg-soft);
}

.collapsible-toggle:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 0;
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
