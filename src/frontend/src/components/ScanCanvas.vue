<script setup>
import { computed, ref, onMounted, watch } from "vue";

const props = defineProps({
  imagePath: { type: String, default: null },
  correctedImagePath: { type: String, default: null },
  processedImagePath: { type: String, default: null },
  staves: { type: Array, default: () => [] },
  symbols: { type: Array, default: () => [] },
  adjustments: {
    type: Object,
    default: () => ({ brightness: 0, contrast: 1.0, rotation: 0, threshold: 128 }),
  },
  selectedSymbolId: { type: Number, default: null },
  showStaves: { type: Boolean, default: true },
  showSymbols: { type: Boolean, default: true },
  captureMode: { type: Boolean, default: false },
  viewMode: { type: String, default: "original" },
});

const emit = defineEmits(["select-symbol", "capture-box"]);

const BASE = (import.meta.env.VITE_BASE_PATH || "").replace(/\/$/, "");

function resolveImageUrl(path) {
  if (!path) return null;
  const relative = path.replace(/^data\/scans\//, "");
  return `${BASE}/scans/${relative}`;
}

const activeImageUrl = computed(() => {
  if (props.viewMode === "corrected" && props.correctedImagePath) {
    return resolveImageUrl(props.correctedImagePath);
  }
  if (props.viewMode === "binary" && props.processedImagePath) {
    return resolveImageUrl(props.processedImagePath);
  }
  return resolveImageUrl(props.imagePath);
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
  if (!e.ctrlKey) return; // only zoom with Ctrl held
  e.preventDefault();
  if (e.deltaY < 0) zoomIn();
  else zoomOut();
}

// Threshold preview via canvas
const wrapEl = ref(null);
const previewCanvas = ref(null);
const imgData = ref(null); // cached original ImageData

function fitZoomToContainer(imgW, imgH) {
  const el = wrapEl.value;
  if (!el || !imgW || !imgH) return;
  const availW = el.clientWidth;
  const availH = el.clientHeight;
  const scaleW = availW / imgW;
  const scaleH = availH / imgH;
  const fitScale = Math.min(scaleW, scaleH);
  // Pick the largest ZOOM_STEPS entry that still fits, or fall back to the smallest
  let best = ZOOM_STEPS[0];
  for (const step of ZOOM_STEPS) {
    if (step <= fitScale) best = step;
    else break;
  }
  zoom.value = best;
}

function loadImage() {
  if (!activeImageUrl.value) return;
  const img = new Image();
  img.crossOrigin = "anonymous";
  img.onload = () => {
    naturalWidth.value = img.naturalWidth;
    naturalHeight.value = img.naturalHeight;
    fitZoomToContainer(img.naturalWidth, img.naturalHeight);
    const canvas = previewCanvas.value;
    if (!canvas) return;
    canvas.width = img.naturalWidth;
    canvas.height = img.naturalHeight;
    const ctx = canvas.getContext("2d");
    ctx.drawImage(img, 0, 0);
    imgData.value = ctx.getImageData(0, 0, canvas.width, canvas.height);
    // Only apply client-side threshold on original view
    if (props.viewMode === "original") {
      applyThreshold();
    }
  };
  img.src = activeImageUrl.value;
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

watch(() => activeImageUrl.value, loadImage);
watch(
  () => props.adjustments.threshold,
  () => {
    if (props.viewMode === "original") applyThreshold();
  },
);
onMounted(loadImage);

// Staff line helpers
function parseLinePositions(staff) {
  try {
    return JSON.parse(staff.line_positions_json || "[]");
  } catch {
    return [];
  }
}

function findStaffForY(y) {
  for (const staff of props.staves) {
    if (y >= staff.y_top && y <= staff.y_bottom) return staff;
  }
  return null;
}

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

// Persistent selection box (adjustable after initial draw)
const selBox = ref(null); // { x, y, width, height } or null
const draggingEdge = ref(null); // "top" | "bottom" | "left" | "right" | "topLeft" | "topRight" | "bottomLeft" | "bottomRight" | null

const HANDLE_SIZE = 8; // size in image coords for edge/corner hit detection

function toImageCoords(e) {
  const svg = svgEl.value;
  if (!svg) return { x: 0, y: 0 };
  const rect = svg.getBoundingClientRect();
  const x = ((e.clientX - rect.left) / rect.width) * naturalWidth.value;
  const y = ((e.clientY - rect.top) / rect.height) * naturalHeight.value;
  return { x: Math.round(x), y: Math.round(y) };
}

function hitTestEdge(pt) {
  if (!selBox.value) return null;
  const b = selBox.value;
  const g = HANDLE_SIZE / zoom.value; // scale grip to zoom
  const inX = pt.x >= b.x - g && pt.x <= b.x + b.width + g;
  const inY = pt.y >= b.y - g && pt.y <= b.y + b.height + g;
  const nearLeft = Math.abs(pt.x - b.x) < g;
  const nearRight = Math.abs(pt.x - (b.x + b.width)) < g;
  const nearTop = Math.abs(pt.y - b.y) < g;
  const nearBottom = Math.abs(pt.y - (b.y + b.height)) < g;

  if (nearTop && nearLeft) return "topLeft";
  if (nearTop && nearRight) return "topRight";
  if (nearBottom && nearLeft) return "bottomLeft";
  if (nearBottom && nearRight) return "bottomRight";
  if (nearTop && inX) return "top";
  if (nearBottom && inX) return "bottom";
  if (nearLeft && inY) return "left";
  if (nearRight && inY) return "right";
  return null;
}

function onMouseDown(e) {
  if (!props.captureMode) return;
  const pt = toImageCoords(e);

  // Check if clicking on an edge of the existing selection box
  if (selBox.value) {
    const edge = hitTestEdge(pt);
    if (edge) {
      draggingEdge.value = edge;
      return;
    }
  }

  // Start new selection (replaces any existing)
  drawing.value = true;
  draggingEdge.value = null;
  drawStart.value = pt;
  drawEnd.value = pt;
}

function onMouseMove(e) {
  const pt = toImageCoords(e);

  if (draggingEdge.value && selBox.value) {
    const b = { ...selBox.value };
    const edge = draggingEdge.value;
    if (edge.includes("top")) {
      const newY = Math.min(pt.y, b.y + b.height - 2);
      b.height += b.y - newY;
      b.y = newY;
    }
    if (edge.includes("bottom")) {
      b.height = Math.max(2, pt.y - b.y);
    }
    if (edge.includes("Left") || edge === "left") {
      const newX = Math.min(pt.x, b.x + b.width - 2);
      b.width += b.x - newX;
      b.x = newX;
    }
    if (edge.includes("Right") || edge === "right") {
      b.width = Math.max(2, pt.x - b.x);
    }
    selBox.value = b;
    return;
  }

  if (!drawing.value) return;
  drawEnd.value = pt;
}

function onMouseUp() {
  if (draggingEdge.value) {
    draggingEdge.value = null;
    return;
  }
  if (!drawing.value) return;
  drawing.value = false;
  const x = Math.min(drawStart.value.x, drawEnd.value.x);
  const y = Math.min(drawStart.value.y, drawEnd.value.y);
  const w = Math.abs(drawEnd.value.x - drawStart.value.x);
  const h = Math.abs(drawEnd.value.y - drawStart.value.y);
  if (w > 3 && h > 3) {
    selBox.value = { x, y, width: w, height: h };
  }
}

function confirmCapture() {
  if (!selBox.value) return;
  const b = selBox.value;
  const staff = findStaffForY(b.y + b.height / 2);
  let heightInLines = null;
  if (staff && staff.line_spacing > 0) {
    heightInLines = Math.round((b.height / staff.line_spacing) * 10) / 10; // round to 0.1
  }
  emit("capture-box", { x: b.x, y: b.y, width: b.width, height: b.height, heightInLines });
  selBox.value = null;
}

function cancelCapture() {
  selBox.value = null;
}

// Clear selection when capture mode is turned off
watch(
  () => props.captureMode,
  (val) => {
    if (!val) {
      selBox.value = null;
      drawing.value = false;
    }
  },
);

/**
 * Crop a region from the current canvas (with threshold already applied)
 * and return it as a PNG Blob.
 */
function cropRegion(box) {
  const canvas = previewCanvas.value;
  if (!canvas) return Promise.reject(new Error("Canvas nicht verfügbar"));

  const tmp = document.createElement("canvas");
  tmp.width = box.width;
  tmp.height = box.height;
  const ctx = tmp.getContext("2d");
  ctx.drawImage(canvas, box.x, box.y, box.width, box.height, 0, 0, box.width, box.height);

  return new Promise((resolve, reject) => {
    tmp.toBlob(
      (b) => (b ? resolve(b) : reject(new Error("Canvas export fehlgeschlagen"))),
      "image/png",
    );
  });
}

defineExpose({ cropRegion, zoomIn, zoomOut, zoom });
</script>

<template>
  <div ref="wrapEl" class="canvas-wrap" @wheel="onWheel">
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
        <!-- Staff regions and individual lines -->
        <template v-if="showStaves">
          <g v-for="staff in staves" :key="`staff-${staff.id}`">
            <!-- Staff region background tint -->
            <rect
              x="0"
              :y="staff.y_top"
              :width="naturalWidth"
              :height="staff.y_bottom - staff.y_top"
              fill="#3b82f6"
              opacity="0.04"
            />
            <!-- Individual staff lines -->
            <line
              v-for="(lineY, li) in parseLinePositions(staff)"
              :key="`line-${staff.id}-${li}`"
              x1="0"
              :y1="lineY"
              :x2="naturalWidth"
              :y2="lineY"
              stroke="#3b82f6"
              stroke-width="1.5"
              opacity="0.5"
            />
            <!-- Staff label -->
            <text
              x="4"
              :y="staff.y_top + 14"
              fill="#3b82f6"
              font-size="14"
              font-weight="600"
              opacity="0.7"
            >
              System {{ staff.staff_index + 1 }}
            </text>
            <!-- Top/bottom boundary dashes -->
            <line
              x1="0"
              :y1="staff.y_top"
              :x2="naturalWidth"
              :y2="staff.y_top"
              stroke="#3b82f6"
              stroke-width="1"
              stroke-dasharray="6 4"
              opacity="0.3"
            />
            <line
              x1="0"
              :y1="staff.y_bottom"
              :x2="naturalWidth"
              :y2="staff.y_bottom"
              stroke="#3b82f6"
              stroke-width="1"
              stroke-dasharray="6 4"
              opacity="0.3"
            />
          </g>
        </template>

        <!-- Symbol bounding boxes -->
        <template v-if="showSymbols">
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
        </template>

        <!-- Drawing rectangle (while dragging) -->
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

        <!-- Adjustable selection box (after initial draw) -->
        <template v-if="selBox && !drawing">
          <!-- Fill -->
          <rect
            :x="selBox.x"
            :y="selBox.y"
            :width="selBox.width"
            :height="selBox.height"
            fill="rgba(251, 191, 36, 0.12)"
            stroke="#f59e0b"
            stroke-width="2"
          />
          <!-- Edge handles (invisible wider hit areas) -->
          <line
            :x1="selBox.x"
            :y1="selBox.y"
            :x2="selBox.x + selBox.width"
            :y2="selBox.y"
            stroke="transparent"
            stroke-width="8"
            style="cursor: n-resize; pointer-events: all"
          />
          <line
            :x1="selBox.x"
            :y1="selBox.y + selBox.height"
            :x2="selBox.x + selBox.width"
            :y2="selBox.y + selBox.height"
            stroke="transparent"
            stroke-width="8"
            style="cursor: s-resize; pointer-events: all"
          />
          <line
            :x1="selBox.x"
            :y1="selBox.y"
            :x2="selBox.x"
            :y2="selBox.y + selBox.height"
            stroke="transparent"
            stroke-width="8"
            style="cursor: w-resize; pointer-events: all"
          />
          <line
            :x1="selBox.x + selBox.width"
            :y1="selBox.y"
            :x2="selBox.x + selBox.width"
            :y2="selBox.y + selBox.height"
            stroke="transparent"
            stroke-width="8"
            style="cursor: e-resize; pointer-events: all"
          />
          <!-- Corner handles (visible dots) -->
          <circle
            :cx="selBox.x"
            :cy="selBox.y"
            r="4"
            fill="#f59e0b"
            style="cursor: nw-resize; pointer-events: all"
          />
          <circle
            :cx="selBox.x + selBox.width"
            :cy="selBox.y"
            r="4"
            fill="#f59e0b"
            style="cursor: ne-resize; pointer-events: all"
          />
          <circle
            :cx="selBox.x"
            :cy="selBox.y + selBox.height"
            r="4"
            fill="#f59e0b"
            style="cursor: sw-resize; pointer-events: all"
          />
          <circle
            :cx="selBox.x + selBox.width"
            :cy="selBox.y + selBox.height"
            r="4"
            fill="#f59e0b"
            style="cursor: se-resize; pointer-events: all"
          />
        </template>
      </svg>

      <!-- Confirm/cancel buttons for selection box -->
      <div
        v-if="selBox && !drawing"
        class="capture-confirm"
        :style="{
          left: (selBox.x + selBox.width / 2) * zoom - 60 + 'px',
          top: (selBox.y + selBox.height) * zoom + 8 + 'px',
        }"
      >
        <button class="capture-btn confirm" @click="confirmCapture">Bestätigen</button>
        <button class="capture-btn cancel" @click="cancelCapture">Verwerfen</button>
      </div>

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

.capture-confirm {
  position: absolute;
  display: flex;
  gap: 0.4rem;
  z-index: 10;
  pointer-events: all;
}

.capture-btn {
  padding: 0.3rem 0.6rem;
  border: none;
  border-radius: 4px;
  font-size: 0.8rem;
  cursor: pointer;
  font-weight: 500;
}

.capture-btn.confirm {
  background: #f59e0b;
  color: #000;
}

.capture-btn.confirm:hover {
  background: #d97706;
}

.capture-btn.cancel {
  background: rgba(0, 0, 0, 0.6);
  color: #fff;
}

.capture-btn.cancel:hover {
  background: rgba(0, 0, 0, 0.8);
}
</style>
