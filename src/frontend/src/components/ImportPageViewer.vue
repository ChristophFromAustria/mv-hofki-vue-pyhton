<script setup>
import { computed } from "vue";
import { BASE } from "../lib/api.js";

const props = defineProps({
  page: { type: Object, required: true },
  boxes: { type: Array, default: () => [] }, // {key, bbox_2d, kind: "row"|"photo", label}
  selectedKey: { type: String, default: null },
});
const emit = defineEmits(["select"]);

const src = computed(() => `${BASE}${props.page.image_url}`);

function rect(box) {
  const [x1, y1, x2, y2] = box.bbox_2d;
  return { x: x1, y: y1, width: Math.max(1, x2 - x1), height: Math.max(1, y2 - y1) };
}
</script>

<template>
  <figure class="viewer">
    <img
      :src="src"
      :width="page.width"
      :height="page.height"
      :alt="`Seite ${page.page_index + 1} von ${page.source_name}`"
      class="viewer-img"
    />
    <svg
      class="viewer-overlay"
      :viewBox="`0 0 ${page.width} ${page.height}`"
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      <g
        v-for="box in boxes"
        :key="box.key"
        :class="['box', box.kind, { selected: box.key === selectedKey }]"
      >
        <rect v-bind="rect(box)" @click="emit('select', box.key)" />
        <text
          v-if="box.label && box.key === selectedKey"
          :x="rect(box).x"
          :y="Math.max(24, rect(box).y - 8)"
        >
          {{ box.label }}
        </text>
      </g>
    </svg>
    <figcaption class="viewer-caption">
      Seite {{ page.page_index + 1 }} · {{ page.source_name }} ·
      <a :href="src" target="_blank" rel="noopener">Original öffnen</a>
    </figcaption>
  </figure>
</template>

<style scoped>
.viewer {
  position: relative;
  margin: 0;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  background: var(--color-bg-soft);
  overflow: hidden;
}

.viewer-img {
  display: block;
  width: 100%;
  height: auto;
}

.viewer-overlay {
  position: absolute;
  inset: 0;
  width: 100%;
  height: calc(100% - 2rem);
}

.box rect {
  fill: transparent;
  stroke: var(--color-primary);
  stroke-width: 3;
  stroke-opacity: 0.55;
  cursor: pointer;
  transition: stroke-opacity var(--transition);
}

.box.photo rect {
  stroke: var(--color-success);
}

.box rect:hover {
  stroke-opacity: 1;
}

.box.selected rect {
  stroke-opacity: 1;
  stroke-width: 5;
  fill: var(--color-primary);
  fill-opacity: 0.1;
}

.box.photo.selected rect {
  fill: var(--color-success);
  fill-opacity: 0.12;
}

.box text {
  font: 700 22px var(--font-sans);
  fill: var(--color-primary);
  pointer-events: none;
  paint-order: stroke;
  stroke: var(--color-bg);
  stroke-width: 4px;
}

.box.photo text {
  fill: var(--color-success);
}

.viewer-caption {
  height: 2rem;
  display: flex;
  align-items: center;
  padding: 0 0.75rem;
  font-size: 0.8rem;
  color: var(--color-muted);
  gap: 0.25rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
