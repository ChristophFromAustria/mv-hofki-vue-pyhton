<script setup>
import { computed } from "vue";
import { renderMarkdown } from "../lib/markdown.js";

const props = defineProps({
  text: { type: String, default: null },
});

const isEmpty = computed(() => !props.text || !String(props.text).trim());
const html = computed(() => renderMarkdown(props.text));
</script>

<template>
  <div class="markdown-text" :class="{ 'is-empty': isEmpty }">
    <template v-if="isEmpty">—</template>
    <div v-else v-html="html" />
  </div>
</template>

<style scoped>
.markdown-text {
  font-size: 0.9rem;
  line-height: 1.6;
  max-width: 60rem;
  overflow-wrap: anywhere;
}

.markdown-text.is-empty {
  color: var(--color-muted);
}

.markdown-text :deep(p) {
  margin: 0 0 var(--space-3);
}

.markdown-text :deep(p:last-child) {
  margin-bottom: 0;
}

.markdown-text :deep(ul),
.markdown-text :deep(ol) {
  margin: 0 0 var(--space-3);
  padding-left: 1.25rem;
}

.markdown-text :deep(li) {
  margin-bottom: var(--space-1);
}

.markdown-text :deep(h1),
.markdown-text :deep(h2),
.markdown-text :deep(h3),
.markdown-text :deep(h4) {
  font-weight: 600;
  margin: var(--space-4) 0 var(--space-2);
  line-height: 1.3;
}

.markdown-text :deep(h1:first-child),
.markdown-text :deep(h2:first-child),
.markdown-text :deep(h3:first-child),
.markdown-text :deep(h4:first-child) {
  margin-top: 0;
}

/* Headings stay modest so they never outrank the page's own headings. */
.markdown-text :deep(h1) {
  font-size: 1.1rem;
}
.markdown-text :deep(h2) {
  font-size: 1.05rem;
}
.markdown-text :deep(h3),
.markdown-text :deep(h4) {
  font-size: 1rem;
}

.markdown-text :deep(a) {
  color: var(--color-primary);
  text-decoration: underline;
}

.markdown-text :deep(a:hover) {
  color: var(--color-primary-hover);
}

.markdown-text :deep(strong) {
  font-weight: 600;
}

.markdown-text :deep(code) {
  font-family: var(--font-mono);
  font-size: 0.85em;
  background: var(--color-bg-soft);
  padding: 0.1em 0.3em;
  border-radius: var(--radius-sm);
}
</style>
