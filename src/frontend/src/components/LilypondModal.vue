<script setup>
import { ref, computed, watch, defineAsyncComponent } from "vue";

// VexFlow is large; load the editor (and VexFlow) only when the tab is opened.
const LilypondEditor = defineAsyncComponent(() => import("./LilypondEditor.vue"));

const props = defineProps({
  open: { type: Boolean, default: false },
  lilypondCode: { type: String, default: "" },
  pdfPath: { type: String, default: null },
  pngPaths: { type: Array, default: () => [] },
  cacheVersion: { type: String, default: null },
  warnings: { type: Array, default: () => [] },
});

const emit = defineEmits(["close"]);

const BASE = (import.meta.env.VITE_BASE_PATH || "").replace(/\/$/, "");
const activeTab = ref("preview");
const showWarnings = ref(false);

// Browser editor state: edits live only in this dialog for now.
const editedCode = ref(props.lilypondCode);
watch(
  () => props.lilypondCode,
  (code) => {
    editedCode.value = code;
  },
);
const isEdited = computed(() => editedCode.value !== props.lilypondCode);
const editorVisited = ref(false);
watch(activeTab, (tab) => {
  if (tab === "editor") editorVisited.value = true;
});

async function copyCode() {
  try {
    await navigator.clipboard.writeText(editedCode.value);
    copied.value = true;
    setTimeout(() => (copied.value = false), 1500);
  } catch {
    copied.value = false;
  }
}
const copied = ref(false);

const pngWidth = ref(0);
const pngHeight = ref(0);

function assetUrl(path, cacheBust = null) {
  if (!path) return null;
  const relative = path.replace(/^data\/scans\//, "");
  const url = `${BASE}/scans/${relative}`;
  return cacheBust ? `${url}?v=${cacheBust}` : url;
}

const previewUrl = computed(() => {
  if (!props.pngPaths.length) return null;
  return assetUrl(props.pngPaths[0], props.cacheVersion);
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
  <div v-if="open" class="overlay" @click.self="emit('close')">
    <div class="dialog dialog-xl dialog-flush">
      <div class="dialog-header">
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
            :class="{ active: activeTab === 'editor' }"
            @click="activeTab = 'editor'"
          >
            Editor
            <span class="tab-badge">Beta</span>
          </button>
          <button
            class="tab-btn"
            :class="{ active: activeTab === 'code' }"
            @click="activeTab = 'code'"
          >
            Code
            <span v-if="isEdited" class="tab-dot" title="Geändert"></span>
          </button>
        </div>
        <button class="dialog-close" title="Schließen" @click="emit('close')">✕</button>
      </div>

      <div class="dialog-body">
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
                stroke="var(--overlay-measure)"
                stroke-width="2"
                stroke-dasharray="8 4"
                opacity="0.8"
              />
            </svg>
          </div>
          <div v-else class="preview-empty">Keine Vorschau verfügbar</div>
        </div>

        <!-- Warnings (measure fill mismatches etc.) -->
        <div v-if="activeTab === 'preview' && warnings.length" class="warnings">
          <button class="warnings-toggle" @click="showWarnings = !showWarnings">
            {{ showWarnings ? "▾" : "▸" }} {{ warnings.length }} Hinweis{{
              warnings.length === 1 ? "" : "e"
            }}
            zur Taktfüllung
          </button>
          <ul v-if="showWarnings" class="warnings-list">
            <li v-for="(w, i) in warnings" :key="i">{{ w }}</li>
          </ul>
        </div>

        <!-- Editor tab (browser rendering via VexFlow, edits not persisted) -->
        <div v-show="activeTab === 'editor'" class="editor-tab">
          <LilypondEditor v-if="open" v-model:code="editedCode" :original-code="lilypondCode" />
          <p class="editor-note">
            Die Darstellung im Browser ist eine Näherung an den LilyPond-Satz. Änderungen werden in
            den Code übernommen, aber noch nicht gespeichert.
          </p>
        </div>

        <!-- Code tab -->
        <div v-if="activeTab === 'code'">
          <div class="code-bar">
            <span v-if="isEdited" class="code-edited">Enthält Änderungen aus dem Editor</span>
            <span v-else class="code-unchanged">Generierter Code</span>
            <button class="btn btn-sm" type="button" @click="copyCode">
              {{ copied ? "Kopiert" : "Code kopieren" }}
            </button>
          </div>
          <pre class="ly-code">{{ editedCode }}</pre>
        </div>
      </div>

      <div class="dialog-footer">
        <a v-if="pdfPath" :href="assetUrl(pdfPath)" target="_blank" class="btn btn-primary">
          PDF öffnen
        </a>
        <button class="btn" @click="emit('close')">Schließen</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
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
  color: var(--color-on-primary);
}

.tab-badge {
  margin-left: 0.3rem;
  font-size: 0.65rem;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  opacity: 0.8;
}

.tab-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  margin-left: 0.35rem;
  border-radius: 50%;
  background: var(--color-warning);
  vertical-align: middle;
}

.editor-note {
  margin: 0.5rem 0 0;
  font-size: 0.8rem;
  color: var(--color-muted);
}

.code-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
  font-size: 0.8rem;
}

.code-edited {
  color: var(--color-warning);
  font-weight: 600;
}

.code-unchanged {
  color: var(--color-muted);
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

.warnings {
  margin-top: 0.75rem;
  font-size: 0.85rem;
}

.warnings-toggle {
  background: none;
  border: none;
  color: var(--color-warning);
  cursor: pointer;
  padding: 0;
  font-size: 0.85rem;
}

.warnings-list {
  margin: 0.5rem 0 0;
  padding-left: 1.25rem;
  max-height: 8rem;
  overflow-y: auto;
  color: var(--color-muted);
}

.ly-code {
  background: var(--color-canvas-bg);
  color: var(--color-canvas-text);
  padding: 1rem;
  border-radius: var(--radius);
  font-family: var(--font-mono);
  font-size: 0.8rem;
  line-height: 1.5;
  overflow-x: auto;
  white-space: pre;
  margin: 0;
}
</style>
