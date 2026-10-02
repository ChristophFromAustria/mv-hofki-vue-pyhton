<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from "vue";
import {
  autoLevels,
  clampCrop,
  exportEdit,
  isNeutral,
  neutralEdit,
  renderEdit,
} from "../lib/imageEdit.js";

// Reusable image editor: rotate, crop, brightness, contrast, white balance
// (warmth) and "Automatisch" (per-channel levels: fixes washed-out, colour-cast
// scans). Emits the result as a JPEG blob; the caller stores it.
const props = defineProps({
  open: Boolean,
  src: { type: String, default: "" },
  title: { type: String, default: "Bild bearbeiten" },
  // The image was edited before: offer to go back to the original.
  canRestore: Boolean,
  saving: Boolean,
  error: { type: String, default: "" },
});
const emit = defineEmits(["save", "restore", "cancel"]);

const PREVIEW_SIDE = 1200;

const dialog = ref(null);
const preview = ref(null);
const loadError = ref("");
const loading = ref(false);
const edit = ref(neutralEdit());
const cropMode = ref(false);
const cropDraft = ref(null);
const titleId = `image-editor-${Math.random().toString(36).slice(2, 7)}`;

let source = null; // the full image
let small = null; // a downscaled copy for the live preview
let frame = 0;

const changed = computed(() => !isNeutral(edit.value));

function reset() {
  edit.value = neutralEdit();
  cropMode.value = false;
  cropDraft.value = null;
}

async function load() {
  loadError.value = "";
  loading.value = true;
  source = null;
  small = null;
  try {
    const img = new Image();
    img.decoding = "async";
    img.src = props.src;
    await img.decode();
    source = img;
    small = renderEdit(img, neutralEdit(), { maxSide: PREVIEW_SIDE });
    draw();
  } catch {
    loadError.value = "Bild konnte nicht geladen werden.";
  } finally {
    loading.value = false;
  }
}

function draw() {
  cancelAnimationFrame(frame);
  frame = requestAnimationFrame(() => {
    if (!small || !preview.value) return;
    const out = renderEdit(small, edit.value, {
      maxSide: PREVIEW_SIDE,
      withCrop: !cropMode.value,
    });
    const target = preview.value;
    target.width = out.width;
    target.height = out.height;
    target.getContext("2d").drawImage(out, 0, 0);
  });
}

watch(
  () => props.open,
  async (open) => {
    if (open) {
      reset();
      load();
    }
    await nextTick();
    if (!dialog.value) return;
    if (open && !dialog.value.open) dialog.value.showModal();
    else if (!open && dialog.value.open) dialog.value.close();
  },
  { immediate: true },
);

watch([edit, cropMode], draw, { deep: true });
onBeforeUnmount(() => cancelAnimationFrame(frame));

// --- rotate -------------------------------------------------------------

/** A crop of the image before turning it by 90° clockwise, after it. */
function turnCrop(c, clockwise) {
  if (!c) return null;
  return clockwise
    ? { x: 1 - (c.y + c.h), y: c.x, w: c.h, h: c.w }
    : { x: c.y, y: 1 - (c.x + c.w), w: c.h, h: c.w };
}

function rotate(clockwise) {
  const e = edit.value;
  e.rotate = (e.rotate + (clockwise ? 90 : 270)) % 360;
  e.crop = turnCrop(e.crop, clockwise);
  if (cropDraft.value) cropDraft.value = turnCrop(cropDraft.value, clockwise);
}

// --- auto ---------------------------------------------------------------

function auto() {
  if (!small) return;
  // Measured on what is shown (rotated and cropped), without colour changes.
  const shown = renderEdit(small, {
    ...neutralEdit(),
    rotate: edit.value.rotate,
    crop: edit.value.crop,
  });
  const ctx = shown.getContext("2d", { willReadFrequently: true });
  edit.value.levels = autoLevels(ctx.getImageData(0, 0, shown.width, shown.height));
}

// --- crop ---------------------------------------------------------------

function startCrop() {
  cropDraft.value = edit.value.crop ? { ...edit.value.crop } : { x: 0.05, y: 0.05, w: 0.9, h: 0.9 };
  cropMode.value = true;
}

function applyCrop() {
  const c = cropDraft.value;
  edit.value.crop = c && (c.w < 0.999 || c.h < 0.999) ? clampCrop(c) : null;
  cropMode.value = false;
}

function removeCrop() {
  edit.value.crop = null;
  cropDraft.value = null;
  cropMode.value = false;
}

let drag = null; // { mode, start: {x, y}, crop }

function point(e) {
  const r = preview.value.getBoundingClientRect();
  return {
    x: Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)),
    y: Math.min(1, Math.max(0, (e.clientY - r.top) / r.height)),
  };
}

function onPointerDown(e) {
  if (!cropMode.value) return;
  e.preventDefault();
  e.currentTarget.setPointerCapture(e.pointerId);
  const p = point(e);
  const handle = e.target.dataset?.handle;
  const c = cropDraft.value;
  const inside = c && p.x >= c.x && p.x <= c.x + c.w && p.y >= c.y && p.y <= c.y + c.h;
  const mode = handle || (inside ? "move" : "new");
  drag = { mode, start: p, crop: c ? { ...c } : null };
  if (mode === "new") cropDraft.value = { x: p.x, y: p.y, w: 0, h: 0 };
}

function onPointerMove(e) {
  if (!drag) return;
  const p = point(e);
  const { mode, start, crop } = drag;
  const dx = p.x - start.x;
  const dy = p.y - start.y;
  if (mode === "move") {
    cropDraft.value = clampCrop({ ...crop, x: crop.x + dx, y: crop.y + dy }, 0);
    return;
  }
  // Resize: the corner opposite the dragged one stays put.
  let x0 = crop?.x ?? start.x;
  let y0 = crop?.y ?? start.y;
  let x1 = crop ? crop.x + crop.w : start.x;
  let y1 = crop ? crop.y + crop.h : start.y;
  if (mode === "new") {
    x0 = start.x;
    y0 = start.y;
    x1 = p.x;
    y1 = p.y;
  } else {
    if (mode.includes("w")) x0 = p.x;
    if (mode.includes("e")) x1 = p.x;
    if (mode.includes("n")) y0 = p.y;
    if (mode.includes("s")) y1 = p.y;
  }
  cropDraft.value = {
    x: Math.min(x0, x1),
    y: Math.min(y0, y1),
    w: Math.abs(x1 - x0),
    h: Math.abs(y1 - y0),
  };
}

function onPointerUp() {
  if (!drag) return;
  drag = null;
  if (cropDraft.value) cropDraft.value = clampCrop(cropDraft.value);
}

const cropStyle = computed(() => {
  const c = cropDraft.value;
  if (!c) return { display: "none" };
  return {
    left: `${c.x * 100}%`,
    top: `${c.y * 100}%`,
    width: `${c.w * 100}%`,
    height: `${c.h * 100}%`,
  };
});

// --- save ---------------------------------------------------------------

async function save() {
  if (!source) return;
  try {
    emit("save", await exportEdit(source, edit.value));
  } catch (e) {
    loadError.value = e.message;
  }
}

const SLIDERS = [
  { key: "brightness", label: "Helligkeit" },
  { key: "contrast", label: "Kontrast" },
  { key: "warmth", label: "Weißabgleich", hint: "kälter ← → wärmer" },
];
</script>

<template>
  <Teleport to="body">
    <dialog
      ref="dialog"
      class="image-editor"
      :aria-labelledby="titleId"
      @cancel.prevent="emit('cancel')"
    >
      <div class="editor-inner">
        <header class="editor-head">
          <h2 :id="titleId">{{ title }}</h2>
          <button type="button" class="editor-close" :disabled="saving" @click="emit('cancel')">
            Schließen
          </button>
        </header>

        <div class="editor-stage">
          <p v-if="loading" class="editor-status">Bild wird geladen …</p>
          <p v-else-if="loadError" class="form-error" role="alert">{{ loadError }}</p>
          <div
            v-show="!loading && !loadError"
            class="editor-canvas-wrap"
            :class="{ 'is-cropping': cropMode }"
            @pointerdown="onPointerDown"
            @pointermove="onPointerMove"
            @pointerup="onPointerUp"
            @pointercancel="onPointerUp"
          >
            <canvas ref="preview" class="editor-canvas" role="img" :aria-label="title" />
            <div v-if="cropMode" class="crop-rect" :style="cropStyle">
              <span class="crop-handle nw" data-handle="nw" aria-hidden="true" />
              <span class="crop-handle ne" data-handle="ne" aria-hidden="true" />
              <span class="crop-handle sw" data-handle="sw" aria-hidden="true" />
              <span class="crop-handle se" data-handle="se" aria-hidden="true" />
            </div>
          </div>
        </div>

        <div class="editor-controls">
          <div v-if="cropMode" class="editor-row">
            <span class="editor-hint">Rahmen ziehen; an den Ecken die Größe ändern.</span>
            <button type="button" class="btn-primary" @click="applyCrop">
              Zuschnitt übernehmen
            </button>
            <button type="button" @click="cropMode = false">Abbrechen</button>
          </div>
          <template v-else>
            <div class="editor-row">
              <button type="button" aria-label="Nach links drehen" @click="rotate(false)">
                ⟲ Links
              </button>
              <button type="button" aria-label="Nach rechts drehen" @click="rotate(true)">
                Rechts ⟳
              </button>
              <button type="button" @click="startCrop">Zuschneiden</button>
              <button v-if="edit.crop" type="button" @click="removeCrop">Zuschnitt aufheben</button>
              <button
                type="button"
                :class="{ 'btn-active': edit.levels }"
                :aria-pressed="edit.levels ? 'true' : 'false'"
                @click="edit.levels ? (edit.levels = null) : auto()"
              >
                Automatisch
              </button>
            </div>
            <div class="editor-sliders">
              <label v-for="s in SLIDERS" :key="s.key" class="editor-slider">
                <span class="editor-slider-label">
                  {{ s.label }}
                  <span class="editor-slider-value"
                    >{{ edit[s.key] > 0 ? "+" : "" }}{{ edit[s.key] }}</span
                  >
                </span>
                <input v-model.number="edit[s.key]" type="range" min="-100" max="100" step="1" />
                <span v-if="s.hint" class="editor-hint">{{ s.hint }}</span>
              </label>
            </div>
          </template>

          <p v-if="error" class="form-error" role="alert">{{ error }}</p>
          <div class="editor-actions">
            <button
              v-if="canRestore"
              type="button"
              class="editor-restore"
              :disabled="saving"
              @click="emit('restore')"
            >
              Original wiederherstellen
            </button>
            <button type="button" :disabled="saving || !changed" @click="reset">
              Zurücksetzen
            </button>
            <button
              type="button"
              class="btn-primary"
              :disabled="saving || !changed || cropMode || !!loadError"
              @click="save"
            >
              {{ saving ? "Speichert …" : "Speichern" }}
            </button>
          </div>
        </div>
      </div>
    </dialog>
  </Teleport>
</template>

<style scoped>
.image-editor {
  border: none;
  border-radius: var(--radius);
  padding: 0;
  width: min(64rem, 100vw - 2rem);
  height: min(92vh, 52rem);
  max-width: none;
  max-height: none;
  background: var(--color-bg);
  color: var(--color-text);
  box-shadow: var(--shadow-dialog);
}

.image-editor::backdrop {
  background: var(--color-overlay);
}

.editor-inner {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.editor-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--color-border);
}

.editor-head h2 {
  margin: 0;
  font-size: 1.1rem;
}

.editor-stage {
  flex: 1;
  min-height: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-3);
  background: var(--color-bg-soft);
}

.editor-canvas-wrap {
  position: relative;
  display: inline-block;
  max-width: 100%;
  max-height: 100%;
  line-height: 0;
  overflow: hidden;
  touch-action: none;
}

.editor-canvas {
  display: block;
  max-width: 100%;
  max-height: calc(92vh - 22rem);
  object-fit: contain;
}

.is-cropping {
  cursor: crosshair;
}

.crop-rect {
  position: absolute;
  border: 2px solid #fff;
  box-shadow: 0 0 0 9999px rgba(0, 0, 0, 0.5);
  cursor: move;
}

/* 44 px touch targets, a small visible square. */
.crop-handle {
  position: absolute;
  width: 44px;
  height: 44px;
}

.crop-handle::after {
  content: "";
  position: absolute;
  left: 15px;
  top: 15px;
  width: 14px;
  height: 14px;
  background: #fff;
  border: 1px solid #1b2735;
}

.crop-handle.nw {
  left: -22px;
  top: -22px;
  cursor: nwse-resize;
}

.crop-handle.ne {
  right: -22px;
  top: -22px;
  cursor: nesw-resize;
}

.crop-handle.sw {
  left: -22px;
  bottom: -22px;
  cursor: nesw-resize;
}

.crop-handle.se {
  right: -22px;
  bottom: -22px;
  cursor: nwse-resize;
}

.editor-controls {
  padding: var(--space-3) var(--space-4);
  border-top: 1px solid var(--color-border);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.editor-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2);
}

.editor-row button,
.editor-actions button,
.editor-close {
  min-height: 44px;
}

.editor-sliders {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-3);
}

.editor-slider {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.editor-slider-label {
  display: flex;
  justify-content: space-between;
  font-size: 0.875rem;
}

.editor-slider-value {
  font-variant-numeric: tabular-nums;
  color: var(--color-muted);
}

.editor-slider input {
  width: 100%;
  min-height: 32px;
}

.editor-hint {
  font-size: 0.8125rem;
  color: var(--color-muted);
}

.editor-status {
  color: var(--color-muted);
}

.editor-actions {
  display: flex;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.editor-restore {
  margin-right: auto;
}

@media (max-width: 640px) {
  .image-editor {
    width: 100vw;
    height: 100dvh;
    max-width: 100vw;
    margin: 0;
    border-radius: 0;
  }

  .editor-sliders {
    grid-template-columns: 1fr;
  }

  .editor-canvas {
    max-height: calc(100dvh - 26rem);
  }
}
</style>
