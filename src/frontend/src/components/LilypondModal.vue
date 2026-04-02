<script setup>
import { ref, computed } from "vue";

const props = defineProps({
  open: { type: Boolean, default: false },
  lilypondCode: { type: String, default: "" },
  pdfPath: { type: String, default: null },
  pngPaths: { type: Array, default: () => [] },
});

const emit = defineEmits(["close"]);

const BASE = (import.meta.env.VITE_BASE_PATH || "").replace(/\/$/, "");
const activeTab = ref("preview");

const pngWidth = ref(0);
const pngHeight = ref(0);

function assetUrl(path) {
  if (!path) return null;
  const relative = path.replace(/^data\/scans\//, "");
  return `${BASE}/scans/${relative}`;
}

const previewUrl = computed(() => {
  if (!props.pngPaths.length) return null;
  return assetUrl(props.pngPaths[0]);
});

function onPngLoad(e) {
  pngWidth.value = e.target.naturalWidth;
  pngHeight.value = e.target.naturalHeight;
}

// Crop overlay: 165/210 of width, 123/148 of height, centered
const cropRect = computed(() => {
  if (!pngWidth.value || !pngHeight.value) return null;
  const ratioX = 165.0 / 210.0;
  const ratioY = 123.0 / 148.0;
  const w = pngWidth.value * ratioX;
  const h = pngHeight.value * ratioY;
  const x = (pngWidth.value - w) / 2;
  const y = (pngHeight.value - h) / 2;
  return { x, y, w, h };
});
</script>

<template>
  <div v-if="open" class="modal-backdrop" @click.self="emit('close')">
    <div class="modal modal-lilypond">
      <div class="modal-header">
        <h2>LilyPond</h2>
        <div class="tab-bar">
          <button
            class="tab-btn"
            :class="{ active: activeTab === 'preview' }"
            @click="activeTab = 'preview'"
          >
            Vorschau
          </button>
          <button
            class="tab-btn"
            :class="{ active: activeTab === 'code' }"
            @click="activeTab = 'code'"
          >
            Code
          </button>
        </div>
        <button class="close-btn" title="Schließen" @click="emit('close')">✕</button>
      </div>

      <div class="modal-body">
        <!-- Preview tab -->
        <div v-if="activeTab === 'preview'" class="preview-container">
          <div v-if="previewUrl" class="preview-wrap">
            <img :src="previewUrl" alt="Vorschau" class="preview-img" @load="onPngLoad" />
            <svg
              v-if="cropRect"
              class="crop-overlay"
              :viewBox="`0 0 ${pngWidth} ${pngHeight}`"
              preserveAspectRatio="xMidYMid meet"
            >
              <rect
                :x="cropRect.x"
                :y="cropRect.y"
                :width="cropRect.w"
                :height="cropRect.h"
                fill="none"
                stroke="#06b6d4"
                stroke-width="2"
                stroke-dasharray="8 4"
                opacity="0.8"
              />
            </svg>
          </div>
          <div v-else class="preview-empty">Keine Vorschau verfügbar</div>
        </div>

        <!-- Code tab -->
        <div v-if="activeTab === 'code'">
          <pre class="ly-code">{{ lilypondCode }}</pre>
        </div>
      </div>

      <div class="modal-footer">
        <a v-if="pdfPath" :href="assetUrl(pdfPath)" target="_blank" class="btn btn-primary">
          PDF öffnen
        </a>
        <button class="btn" @click="emit('close')">Schließen</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: var(--color-overlay);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 550;
}

.modal-lilypond {
  background: var(--color-bg);
  border-radius: var(--radius);
  width: 100%;
  max-width: 800px;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
}

.modal-header {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 1rem 1.5rem 0.75rem;
  border-bottom: 1px solid var(--color-border);
}

.modal-header h2 {
  margin: 0;
  font-size: 1.1rem;
}

.tab-bar {
  display: flex;
  gap: 0.25rem;
}

.tab-btn {
  padding: 0.3rem 0.75rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  background: var(--color-bg-soft);
  color: var(--color-muted);
  font-size: 0.85rem;
  cursor: pointer;
}

.tab-btn.active {
  background: var(--color-primary);
  border-color: var(--color-primary);
  color: #fff;
}

.close-btn {
  margin-left: auto;
  background: none;
  border: none;
  font-size: 1.2rem;
  cursor: pointer;
  color: var(--color-muted);
  padding: 0.25rem;
  line-height: 1;
}

.close-btn:hover {
  color: var(--color-text);
}

.modal-body {
  padding: 1rem 1.5rem;
  overflow-y: auto;
  flex: 1;
}

.preview-container {
  display: flex;
  justify-content: center;
}

.preview-wrap {
  position: relative;
  display: inline-block;
}

.preview-img {
  max-width: 100%;
  max-height: 65vh;
  display: block;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
}

.crop-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

.preview-empty {
  text-align: center;
  padding: 3rem;
  color: var(--color-muted);
}

.ly-code {
  background: #1a1a2e;
  color: #e0e0e0;
  padding: 1rem;
  border-radius: var(--radius);
  font-family: "Fira Code", "Cascadia Code", monospace;
  font-size: 0.8rem;
  line-height: 1.5;
  overflow-x: auto;
  white-space: pre;
  margin: 0;
}

.modal-footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 0.5rem;
  padding: 0.75rem 1.5rem;
  border-top: 1px solid var(--color-border);
}
</style>
