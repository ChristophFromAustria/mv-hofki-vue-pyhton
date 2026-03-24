<script setup>
import { computed } from "vue";

const props = defineProps({
  imagePath: { type: String, default: null },
  staves: { type: Array, default: () => [] },
  symbols: { type: Array, default: () => [] },
  adjustments: {
    type: Object,
    default: () => ({ brightness: 0, contrast: 1.0, rotation: 0 }),
  },
  selectedSymbolId: { type: Number, default: null },
});

const emit = defineEmits(["select-symbol"]);

const BASE = (import.meta.env.VITE_BASE_PATH || "").replace(/\/$/, "");

const imageUrl = computed(() => {
  if (!props.imagePath) return null;
  return `${BASE}/${props.imagePath}`;
});

const imageFilter = computed(() => {
  const b = props.adjustments.brightness || 0;
  const c = props.adjustments.contrast ?? 1.0;
  // CSS brightness: 0 = black, 1 = normal. brightness(val) where val > 1 brightens.
  // Map -50..50 to roughly 0.5..1.5 for brightness filter
  const brightnessVal = 1 + b / 100;
  return `brightness(${brightnessVal}) contrast(${c})`;
});

const imageRotation = computed(() => {
  const r = props.adjustments.rotation || 0;
  if (r === 0) return "";
  return `rotate(${r}deg)`;
});

function symbolColor(symbol) {
  const conf = symbol.confidence ?? 0;
  if (conf >= 0.85) return "#22c55e";
  if (conf >= 0.4) return "#f97316";
  return "#ef4444";
}

function isSelected(symbol) {
  return symbol.id === props.selectedSymbolId;
}

function selectSymbol(symbol) {
  emit("select-symbol", symbol);
}
</script>

<template>
  <div class="canvas-wrap">
    <div v-if="!imagePath" class="no-image">
      <p>Kein Bild vorhanden</p>
    </div>

    <div v-else class="image-container" :style="{ transform: imageRotation }">
      <img :src="imageUrl" :style="{ filter: imageFilter }" class="scan-image" alt="Scan" />

      <!-- SVG overlay for bounding boxes -->
      <svg class="overlay-svg" xmlns="http://www.w3.org/2000/svg">
        <!-- Staff bounding boxes (subtle blue outline) -->
        <rect
          v-for="staff in staves"
          :key="`staff-${staff.id}`"
          :x="staff.x"
          :y="staff.y"
          :width="staff.width"
          :height="staff.height"
          fill="none"
          stroke="#3b82f6"
          stroke-width="1.5"
          stroke-dasharray="4 2"
          opacity="0.5"
        />

        <!-- Symbol bounding boxes -->
        <g
          v-for="symbol in symbols"
          :key="`sym-${symbol.id}`"
          class="symbol-box"
          style="cursor: pointer"
          @click="selectSymbol(symbol)"
        >
          <rect
            :x="symbol.x"
            :y="symbol.y"
            :width="symbol.width"
            :height="symbol.height"
            fill="none"
            :stroke="symbolColor(symbol)"
            :stroke-width="isSelected(symbol) ? 3 : 1.5"
            :opacity="isSelected(symbol) ? 1 : 0.7"
          />
          <rect
            v-if="isSelected(symbol)"
            :x="symbol.x - 2"
            :y="symbol.y - 2"
            :width="symbol.width + 4"
            :height="symbol.height + 4"
            fill="none"
            stroke="#fff"
            stroke-width="1"
            opacity="0.8"
          />
        </g>
      </svg>
    </div>
  </div>
</template>

<style scoped>
.canvas-wrap {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: auto;
  background: #1a1a1a;
  display: flex;
  align-items: flex-start;
  justify-content: center;
}

.no-image {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #aaa;
}

.image-container {
  position: relative;
  display: inline-block;
}

.scan-image {
  display: block;
  max-width: 100%;
  height: auto;
}

.overlay-svg {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

.symbol-box {
  pointer-events: all;
}
</style>
