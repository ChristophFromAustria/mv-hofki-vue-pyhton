<script setup>
import { ref, computed, watch, nextTick } from "vue";
import { scanTitle } from "../lib/images.js";

const props = defineProps({
  scans: { type: Array, default: () => [] },
  canManage: { type: Boolean, default: false },
});

const emit = defineEmits(["delete", "edit"]);

const dialogEl = ref(null);
const currentIndex = ref(0);
const zoomed = ref(false);
const confirmingDelete = ref(false);

const current = computed(() => props.scans[currentIndex.value] || null);
const currentTitle = computed(() =>
  current.value ? scanTitle(current.value, currentIndex.value) : "",
);

// Keep the index valid when the list changes (e.g. after a delete).
watch(
  () => props.scans.length,
  (len) => {
    if (!len) {
      close();
    } else if (currentIndex.value >= len) {
      currentIndex.value = len - 1;
    }
  },
);

watch(currentIndex, () => {
  zoomed.value = false;
  confirmingDelete.value = false;
});

async function open(index) {
  currentIndex.value = index;
  zoomed.value = false;
  confirmingDelete.value = false;
  await nextTick();
  if (dialogEl.value && !dialogEl.value.open) dialogEl.value.showModal();
}

function close() {
  if (dialogEl.value?.open) dialogEl.value.close();
}

function prev() {
  if (currentIndex.value > 0) currentIndex.value--;
}

function next() {
  if (currentIndex.value < props.scans.length - 1) currentIndex.value++;
}

function onKeydown(e) {
  if (e.target.closest?.("input, textarea, select")) return;
  if (e.key === "ArrowLeft") {
    e.preventDefault();
    prev();
  } else if (e.key === "ArrowRight") {
    e.preventDefault();
    next();
  }
}

function onDialogClick(e) {
  // Click on the backdrop (outside the dialog box) closes it.
  if (e.target === dialogEl.value) close();
}

// The editor is a dialog of its own: close the viewer first.
function editCurrent() {
  if (!current.value) return;
  const scan = current.value;
  close();
  emit("edit", scan);
}

function confirmDelete() {
  if (!current.value) return;
  emit("delete", current.value.id);
  confirmingDelete.value = false;
}
</script>

<template>
  <div class="scan-docs">
    <ul class="scan-grid">
      <li v-for="(scan, i) in scans" :key="scan.id">
        <button
          type="button"
          class="scan-tile"
          :aria-label="`${scanTitle(scan, i)} groß anzeigen`"
          @click="open(i)"
        >
          <img :src="scan.url" alt="" loading="lazy" class="scan-thumb" />
          <span class="scan-caption">{{ scanTitle(scan, i) }}</span>
        </button>
      </li>
    </ul>

    <dialog
      ref="dialogEl"
      class="scan-dialog"
      aria-labelledby="scan-dialog-title"
      @keydown="onKeydown"
      @click="onDialogClick"
      @close="zoomed = false"
    >
      <div v-if="current" class="scan-dialog-inner">
        <header class="scan-dialog-header">
          <div class="scan-dialog-heading">
            <h2 id="scan-dialog-title">{{ currentTitle }}</h2>
            <span class="text-muted scan-dialog-count">
              Seite {{ currentIndex + 1 }} von {{ scans.length }}
            </span>
          </div>
          <button type="button" class="dialog-close" aria-label="Schließen" @click="close">
            &times;
          </button>
        </header>

        <div class="scan-dialog-stage" :class="{ zoomed }">
          <button
            type="button"
            class="scan-image-btn"
            :aria-label="zoomed ? 'An Fenster anpassen' : 'In Originalgröße anzeigen'"
            @click="zoomed = !zoomed"
          >
            <img :src="current.url" :alt="currentTitle" class="scan-dialog-img" />
          </button>
        </div>

        <footer class="scan-dialog-footer">
          <div class="cluster">
            <button
              type="button"
              class="scan-nav-btn"
              :disabled="currentIndex === 0"
              aria-label="Vorherige Seite"
              @click="prev"
            >
              ‹ Zurück
            </button>
            <button
              type="button"
              class="scan-nav-btn"
              :disabled="currentIndex >= scans.length - 1"
              aria-label="Nächste Seite"
              @click="next"
            >
              Weiter ›
            </button>
            <button type="button" class="scan-nav-btn" @click="zoomed = !zoomed">
              {{ zoomed ? "Anpassen" : "Originalgröße" }}
            </button>
            <a :href="current.url" target="_blank" rel="noopener" class="btn scan-nav-btn">
              In neuem Tab öffnen
            </a>
          </div>
          <div v-if="canManage" class="cluster">
            <template v-if="confirmingDelete">
              <span class="text-danger">Scan wirklich löschen?</span>
              <button type="button" class="btn-danger scan-nav-btn" @click="confirmDelete">
                Ja, löschen
              </button>
              <button type="button" class="scan-nav-btn" @click="confirmingDelete = false">
                Abbrechen
              </button>
            </template>
            <template v-else>
              <button type="button" class="scan-nav-btn" @click="editCurrent">Bearbeiten</button>
              <button
                type="button"
                class="btn-danger scan-nav-btn"
                @click="confirmingDelete = true"
              >
                Löschen
              </button>
            </template>
          </div>
        </footer>
      </div>
    </dialog>
  </div>
</template>

<style scoped>
.scan-grid {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(10rem, 1fr));
  gap: var(--space-4);
}

.scan-tile {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: var(--space-2);
  width: 100%;
  height: 100%;
  padding: var(--space-2);
  text-align: left;
  background: var(--color-bg);
}

.scan-tile:hover {
  background: var(--color-bg-soft);
}

.scan-thumb {
  width: 100%;
  aspect-ratio: 3 / 4;
  object-fit: cover;
  object-position: top;
  border-radius: var(--radius-sm);
  background: var(--color-paper);
  border: 1px solid var(--color-border);
}

.scan-caption {
  font-size: 0.8rem;
  line-height: 1.35;
  overflow-wrap: anywhere;
}

.scan-dialog {
  padding: 0;
  border: none;
  border-radius: var(--radius);
  background: var(--color-bg);
  color: var(--color-text);
  box-shadow: var(--shadow-dialog);
  width: min(1100px, calc(100vw - 2rem));
  max-width: none;
  height: calc(100dvh - 2rem);
  max-height: none;
}

.scan-dialog::backdrop {
  background: var(--color-lightbox-bg);
}

.scan-dialog-inner {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.scan-dialog-header {
  display: flex;
  align-items: flex-start;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--color-border);
}

.scan-dialog-heading {
  min-width: 0;
}

.scan-dialog-heading h2 {
  font-size: 1rem;
  font-weight: 600;
  line-height: 1.35;
  overflow-wrap: anywhere;
}

.scan-dialog-count {
  font-size: 0.8rem;
  font-variant-numeric: tabular-nums;
}

.scan-dialog-header .dialog-close {
  min-width: 44px;
  min-height: 44px;
}

.scan-dialog-stage {
  flex: 1;
  min-height: 0;
  overflow: auto;
  background: var(--color-canvas-bg);
  display: flex;
  align-items: center;
  justify-content: center;
}

.scan-dialog-stage.zoomed {
  align-items: flex-start;
  justify-content: flex-start;
}

.scan-image-btn {
  padding: 0;
  border: none;
  border-radius: 0;
  background: none;
  cursor: zoom-in;
  max-width: 100%;
  max-height: 100%;
}

.scan-image-btn:hover {
  background: none;
}

.zoomed .scan-image-btn {
  cursor: zoom-out;
  max-width: none;
  max-height: none;
}

.scan-dialog-img {
  display: block;
  max-width: 100%;
  max-height: calc(100dvh - 12rem);
  object-fit: contain;
  background: var(--color-paper);
}

.zoomed .scan-dialog-img {
  max-width: none;
  max-height: none;
}

.scan-dialog-footer {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2) var(--space-4);
  padding: var(--space-3) var(--space-4);
  border-top: 1px solid var(--color-border);
}

.scan-nav-btn {
  min-height: 44px;
}

@media (max-width: 480px) {
  .scan-grid {
    grid-template-columns: repeat(2, 1fr);
    gap: var(--space-2);
  }

  .scan-dialog {
    width: 100vw;
    height: 100dvh;
    border-radius: 0;
  }
}
</style>
