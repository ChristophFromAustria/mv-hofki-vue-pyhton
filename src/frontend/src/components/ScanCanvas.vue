<script setup>
import { computed, ref, onMounted, watch } from "vue";

const props = defineProps({
  imagePath: { type: String, default: null },
  staves: { type: Array, default: () => [] },
  symbols: { type: Array, default: () => [] },
  adjustments: {
    type: Object,
    default: () => ({ brightness: 0, contrast: 1.0, rotation: 0, threshold: 128 }),
  },
  selectedSymbolId: { type: Number, default: null },
  captureMode: { type: Boolean, default: false },
});

const emit = defineEmits(["select-symbol", "capture-box"]);

const BASE = (import.meta.env.VITE_BASE_PATH || "").replace(/\/$/, "");

const imageUrl = computed(() => {
  if (!props.imagePath) return null;
  return `${BASE}/${props.imagePath}`;
});

// Natural image dimensions
const naturalWidth = ref(0);
const naturalHeight = ref(0);

// Zoom state
const ZOOM_STEPS = [0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0];
const zoom = ref(1.0);

function zoomIn() {
  const idx = ZOOM_STEPS.indexOf(zoom.value);
  if (idx < ZOOM_STEPS.length - 1) zoom.value = ZOOM_STEPS[idx + 1];
}

function zoomOut() {
  const idx = ZOOM_STEPS.indexOf(zoom.value);
  if (idx > 0) zoom.value = ZOOM_STEPS[idx - 1];
}

function onWheel(e) {
  if (e.deltaY < 0) zoomIn();
  else zoomOut();
}

// Threshold preview via canvas
const previewCanvas = ref(null);
const imgData = ref(null); // cached original ImageData

function loadImage() {
  if (!imageUrl.value) return;
  const img = new Image();
  img.crossOrigin = "anonymous";
  img.onload = () => {
    naturalWidth.value = img.naturalWidth;
    naturalHeight.value = img.naturalHeight;
    const canvas = previewCanvas.value;
    if (!canvas) return;
    canvas.width = img.naturalWidth;
    canvas.height = img.naturalHeight;
    const ctx = canvas.getContext("2d");
    ctx.drawImage(img, 0, 0);
    imgData.value = ctx.getImageData(0, 0, canvas.width, canvas.height);
    applyThreshold();
  };
  img.src = imageUrl.value;
}

function applyThreshold() {
  if (!imgData.value || !previewCanvas.value) return;
  const canvas = previewCanvas.value;
  const ctx = canvas.getContext("2d");
  const src = imgData.value;
  const dst = ctx.createImageData(src.width, src.height);
  const t = props.adjustments.threshold ?? 128;
  for (let i = 0; i < src.data.length; i += 4) {
    // Convert to grayscale
    const gray = src.data[i] * 0.299 + src.data[i + 1] * 0.587 + src.data[i + 2] * 0.114;
    const val = gray >= t ? 255 : 0;
    dst.data[i] = val;
    dst.data[i + 1] = val;
    dst.data[i + 2] = val;
    dst.data[i + 3] = 255;
  }
  ctx.putImageData(dst, 0, 0);
}

watch(() => props.imagePath, loadImage);
watch(() => props.adjustments.threshold, applyThreshold);
onMounted(loadImage);

// Symbol helpers
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

// Box drawing state (capture mode)
const drawing = ref(false);
const drawStart = ref({ x: 0, y: 0 });
const drawEnd = ref({ x: 0, y: 0 });
const svgEl = ref(null);

function toImageCoords(e) {
  const svg = svgEl.value;
  if (!svg) return { x: 0, y: 0 };
  const rect = svg.getBoundingClientRect();
  const x = ((e.clientX - rect.left) / rect.width) * naturalWidth.value;
  const y = ((e.clientY - rect.top) / rect.height) * naturalHeight.value;
  return { x: Math.round(x), y: Math.round(y) };
}

function onMouseDown(e) {
  if (!props.captureMode) return;
  drawing.value = true;
  drawStart.value = toImageCoords(e);
  drawEnd.value = drawStart.value;
}

function onMouseMove(e) {
  if (!drawing.value) return;
  drawEnd.value = toImageCoords(e);
}

function onMouseUp() {
  if (!drawing.value) return;
  drawing.value = false;
  const x = Math.min(drawStart.value.x, drawEnd.value.x);
  const y = Math.min(drawStart.value.y, drawEnd.value.y);
  const w = Math.abs(drawEnd.value.x - drawStart.value.x);
  const h = Math.abs(drawEnd.value.y - drawStart.value.y);
  if (w > 3 && h > 3) {
    emit("capture-box", { x, y, width: w, height: h });
  }
}
</script>

<template>
  <div class="canvas-wrap" @wheel.prevent="onWheel">
    <div v-if="!imagePath" class="no-image">
      <p>Kein Bild vorhanden</p>
    </div>

    <div
      v-else
      class="image-container"
      :style="{ width: naturalWidth * zoom + 'px', height: naturalHeight * zoom + 'px' }"
    >
      <canvas
        ref="previewCanvas"
        class="scan-image"
        :style="{ width: naturalWidth * zoom + 'px', height: naturalHeight * zoom + 'px' }"
      />

      <!-- SVG overlay for bounding boxes -->
      <svg
        ref="svgEl"
        class="overlay-svg"
        xmlns="http://www.w3.org/2000/svg"
        :viewBox="`0 0 ${naturalWidth} ${naturalHeight}`"
        :style="{
          cursor: captureMode ? 'crosshair' : 'default',
          pointerEvents: captureMode ? 'all' : 'none',
        }"
        @mousedown="onMouseDown"
        @mousemove="onMouseMove"
        @mouseup="onMouseUp"
      >
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
          style="cursor: pointer; pointer-events: all"
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

        <!-- Drawing rectangle (capture mode) -->
        <rect
          v-if="drawing"
          :x="Math.min(drawStart.x, drawEnd.x)"
          :y="Math.min(drawStart.y, drawEnd.y)"
          :width="Math.abs(drawEnd.x - drawStart.x)"
          :height="Math.abs(drawEnd.y - drawStart.y)"
          fill="rgba(251, 191, 36, 0.15)"
          stroke="#f59e0b"
          stroke-width="2"
          stroke-dasharray="6 3"
        />
      </svg>

      <!-- Zoom indicator -->
      <div class="zoom-indicator">{{ Math.round(zoom * 100) }}%</div>
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
  flex-shrink: 0;
}

.scan-image {
  display: block;
  width: 100%;
  height: 100%;
}

.overlay-svg {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
}

.symbol-box {
  pointer-events: all;
}

.zoom-indicator {
  position: absolute;
  bottom: 0.5rem;
  right: 0.5rem;
  background: rgba(0, 0, 0, 0.6);
  color: #fff;
  font-size: 0.75rem;
  padding: 0.2rem 0.4rem;
  border-radius: 4px;
  pointer-events: none;
  user-select: none;
}
</style>
