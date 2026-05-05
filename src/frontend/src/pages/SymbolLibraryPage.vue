<script setup>
import { ref, computed, watch, onMounted } from "vue";
import { get, post, put, del } from "../lib/api.js";
import LoadingSpinner from "../components/LoadingSpinner.vue";
import SymbolCard from "../components/SymbolCard.vue";
import ConfirmDialog from "../components/ConfirmDialog.vue";

const CATEGORIES = [
  { key: "", label: "Alle" },
  { key: "note", label: "Noten" },
  { key: "rest", label: "Pausen" },
  { key: "accidental", label: "Vorzeichen" },
  { key: "clef", label: "Schlüssel" },
  { key: "time_signature", label: "Taktarten" },
  { key: "barline", label: "Taktstriche" },
  { key: "dynamic", label: "Dynamik" },
  { key: "ornament", label: "Verzierungen" },
  { key: "other", label: "Sonstige" },
];

const PAGE_SIZE = 24;

const activeCategory = ref("");
const currentPage = ref(1);
const templates = ref([]);
const total = ref(0);
const loading = ref(false);
const error = ref(null);

const showCreate = ref(false);
const createForm = ref({ name: "", display_name: "", category: "note" });

const editingTemplate = ref(null);
const editForm = ref({ display_name: "", musicxml_element: "", lilypond_token: "" });
const variants = ref([]);
const loadingVariants = ref(false);
const confirmDeleteOpen = ref(false);
const confirmVariantDeleteOpen = ref(false);
const deleteVariantTarget = ref(null);
const rendering = ref(null); // "musicxml" | "lilypond" | null
const renderError = ref(null);
const previewVariant = ref(null);
const previewImageUrl = ref(null);
const previewNatW = ref(0);
const previewNatH = ref(0);
const cropDrawing = ref(false);
const cropStart = ref({ x: 0, y: 0 });
const cropEnd = ref({ x: 0, y: 0 });
const cropRect = ref(null);
const svgOverlay = ref(null);

const BASE = (import.meta.env.VITE_BASE_PATH || "").replace(/\/$/, "");

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)));

async function fetchTemplates() {
  loading.value = true;
  error.value = null;
  try {
    const offset = (currentPage.value - 1) * PAGE_SIZE;
    let path = `/scanner/library/templates?limit=${PAGE_SIZE}&offset=${offset}`;
    if (activeCategory.value) {
      path += `&category=${encodeURIComponent(activeCategory.value)}`;
    }
    const data = await get(path);
    templates.value = data.items;
    total.value = data.total;
  } catch (e) {
    error.value = e.message;
  } finally {
    loading.value = false;
  }
}

function selectCategory(key) {
  activeCategory.value = key;
  currentPage.value = 1;
}

function prevPage() {
  if (currentPage.value > 1) currentPage.value--;
}

function nextPage() {
  if (currentPage.value < totalPages.value) currentPage.value++;
}

async function createTemplate() {
  if (!createForm.value.display_name.trim()) return;
  const name = createForm.value.display_name.trim().toLowerCase().replace(/\s+/g, "_");
  await post("/scanner/library/templates", {
    category: createForm.value.category,
    name,
    display_name: createForm.value.display_name.trim(),
  });
  showCreate.value = false;
  createForm.value = { name: "", display_name: "", category: "note" };
  await fetchTemplates();
}

async function openEdit(tpl) {
  editingTemplate.value = tpl;
  editForm.value = {
    display_name: tpl.display_name,
    musicxml_element: tpl.musicxml_element || "",
    lilypond_token: tpl.lilypond_token || "",
  };
  renderError.value = null;
  loadingVariants.value = true;
  try {
    variants.value = await get(`/scanner/library/templates/${tpl.id}/variants`);
  } finally {
    loadingVariants.value = false;
  }
}

function closeEdit() {
  editingTemplate.value = null;
  variants.value = [];
}

async function saveTemplate() {
  if (!editingTemplate.value) return;
  await put(`/scanner/library/templates/${editingTemplate.value.id}`, {
    display_name: editForm.value.display_name,
    musicxml_element: editForm.value.musicxml_element || null,
    lilypond_token: editForm.value.lilypond_token || null,
  });
  closeEdit();
  await fetchTemplates();
}

async function deleteTemplate() {
  if (!editingTemplate.value) return;
  await del(`/scanner/library/templates/${editingTemplate.value.id}`);
  confirmDeleteOpen.value = false;
  closeEdit();
  await fetchTemplates();
}

function confirmDeleteVariant(v) {
  deleteVariantTarget.value = v;
  confirmVariantDeleteOpen.value = true;
}

async function deleteVariant() {
  if (!deleteVariantTarget.value || !editingTemplate.value) return;
  const vid = deleteVariantTarget.value.id;
  await del(`/scanner/library/templates/${editingTemplate.value.id}/variants/${vid}`);
  deleteVariantTarget.value = null;
  confirmVariantDeleteOpen.value = false;
  variants.value = await get(`/scanner/library/templates/${editingTemplate.value.id}/variants`);
}

const _cacheBust = Date.now();
function variantImageUrl(variant) {
  const relative = variant.image_path.replace(/^data\/symbol_library\//, "");
  return `${BASE}/symbol-library/${relative}?v=${_cacheBust}`;
}

async function renderMusicxml() {
  if (!editingTemplate.value) return;
  rendering.value = "musicxml";
  renderError.value = null;
  try {
    await post(`/scanner/library/templates/${editingTemplate.value.id}/render-musicxml`, {
      code: editForm.value.musicxml_element,
    });
    variants.value = await get(`/scanner/library/templates/${editingTemplate.value.id}/variants`);
    await fetchTemplates();
  } catch (e) {
    renderError.value = `MusicXML-Rendering fehlgeschlagen: ${e.message}`;
  } finally {
    rendering.value = null;
  }
}

async function renderLilypond() {
  if (!editingTemplate.value) return;
  rendering.value = "lilypond";
  renderError.value = null;
  try {
    await post(`/scanner/library/templates/${editingTemplate.value.id}/render-lilypond`, {
      code: editForm.value.lilypond_token,
    });
    variants.value = await get(`/scanner/library/templates/${editingTemplate.value.id}/variants`);
    await fetchTemplates();
  } catch (e) {
    renderError.value = `LilyPond-Rendering fehlgeschlagen: ${e.message}`;
  } finally {
    rendering.value = null;
  }
}

function openPreview(v) {
  previewVariant.value = v;
  previewImageUrl.value = variantImageUrl(v);
  cropRect.value = null;
  cropDrawing.value = false;
  // Load natural dimensions
  const img = new Image();
  img.onload = () => {
    previewNatW.value = img.naturalWidth;
    previewNatH.value = img.naturalHeight;
  };
  img.src = previewImageUrl.value;
}

function closePreview() {
  previewVariant.value = null;
  previewImageUrl.value = null;
  cropRect.value = null;
}

function toSvgCoords(e) {
  const svg = svgOverlay.value;
  if (!svg) return { x: 0, y: 0 };
  const rect = svg.getBoundingClientRect();
  const x = Math.round(((e.clientX - rect.left) / rect.width) * previewNatW.value);
  const y = Math.round(((e.clientY - rect.top) / rect.height) * previewNatH.value);
  return { x: Math.max(0, x), y: Math.max(0, y) };
}

function onCropMouseDown(e) {
  // Only start crop on the SVG overlay
  if (!svgOverlay.value || !svgOverlay.value.contains(e.target)) return;
  e.preventDefault();
  cropDrawing.value = true;
  const pt = toSvgCoords(e);
  cropStart.value = pt;
  cropEnd.value = pt;
  cropRect.value = null;
}

function onCropMouseMove(e) {
  if (!cropDrawing.value) return;
  e.preventDefault();
  cropEnd.value = toSvgCoords(e);
}

function onCropMouseUp() {
  if (!cropDrawing.value) return;
  cropDrawing.value = false;
  const x = Math.min(cropStart.value.x, cropEnd.value.x);
  const y = Math.min(cropStart.value.y, cropEnd.value.y);
  const w = Math.abs(cropEnd.value.x - cropStart.value.x);
  const h = Math.abs(cropEnd.value.y - cropStart.value.y);
  if (w > 5 && h > 5) {
    cropRect.value = { x, y, width: w, height: h };
  }
}

// Computed SVG drawing rect (for both live drawing and finalized crop)
const drawingRect = computed(() => {
  if (cropRect.value) return cropRect.value;
  if (!cropDrawing.value) return null;
  return {
    x: Math.min(cropStart.value.x, cropEnd.value.x),
    y: Math.min(cropStart.value.y, cropEnd.value.y),
    width: Math.abs(cropEnd.value.x - cropStart.value.x),
    height: Math.abs(cropEnd.value.y - cropStart.value.y),
  };
});

const cropPreviewDataUrl = ref(null);

// Generate a preview of the cropped area using canvas
function updateCropPreview() {
  if (!cropRect.value || !previewImageUrl.value) {
    cropPreviewDataUrl.value = null;
    return;
  }
  const img = new Image();
  img.crossOrigin = "anonymous";
  img.onload = () => {
    const c = cropRect.value;
    const canvas = document.createElement("canvas");
    canvas.width = c.width;
    canvas.height = c.height;
    const ctx = canvas.getContext("2d");
    ctx.drawImage(img, c.x, c.y, c.width, c.height, 0, 0, c.width, c.height);
    cropPreviewDataUrl.value = canvas.toDataURL("image/png");
  };
  img.src = previewImageUrl.value;
}

watch(cropRect, updateCropPreview);

async function applyCrop() {
  if (!cropPreviewDataUrl.value || !editingTemplate.value || !previewVariant.value) return;
  // Convert data URL to blob
  const resp = await fetch(cropPreviewDataUrl.value);
  const blob = await resp.blob();
  const formData = new FormData();
  formData.append("file", blob, "cropped.png");
  formData.append("source_line_spacing", String(previewVariant.value.source_line_spacing || 0));

  const BASE_URL = (import.meta.env.VITE_BASE_PATH || "").replace(/\/$/, "");
  const url = `${BASE_URL}/api/v1/scanner/library/templates/${editingTemplate.value.id}/variants/upload`;
  const uploadResp = await fetch(url, { method: "POST", body: formData });
  if (!uploadResp.ok) {
    const text = await uploadResp.text();
    alert(`Zuschneiden fehlgeschlagen: ${text}`);
    return;
  }
  variants.value = await get(`/scanner/library/templates/${editingTemplate.value.id}/variants`);
  await fetchTemplates();
  closePreview();
}

watch([activeCategory, currentPage], fetchTemplates);
onMounted(fetchTemplates);
</script>

<template>
  <div>
    <div class="page-header">
      <h1>Symbol-Bibliothek</h1>
      <div class="header-right">
        <span class="total-count">{{ total }} Vorlagen</span>
        <button class="btn btn-primary btn-sm" @click="showCreate = true">+ Neue Vorlage</button>
      </div>
    </div>

    <!-- Category filter tabs -->
    <div class="category-tabs">
      <button
        v-for="cat in CATEGORIES"
        :key="cat.key"
        :class="['tab-btn', { active: activeCategory === cat.key }]"
        @click="selectCategory(cat.key)"
      >
        {{ cat.label }}
      </button>
    </div>

    <!-- Loading / error -->
    <LoadingSpinner v-if="loading" />

    <div v-else-if="error" class="error-state">
      <p>Fehler: {{ error }}</p>
      <button class="btn" @click="fetchTemplates">Erneut versuchen</button>
    </div>

    <div v-else-if="templates.length === 0" class="empty-state">
      <p>Keine Vorlagen in dieser Kategorie gefunden.</p>
    </div>

    <template v-else>
      <!-- Template grid -->
      <div class="template-grid">
        <SymbolCard v-for="tpl in templates" :key="tpl.id" :template="tpl" @edit="openEdit" />
      </div>

      <!-- Pagination -->
      <div v-if="totalPages > 1" class="pagination">
        <button class="btn btn-sm btn-secondary" :disabled="currentPage <= 1" @click="prevPage">
          ← Zurück
        </button>
        <span class="page-info">Seite {{ currentPage }} / {{ totalPages }}</span>
        <button
          class="btn btn-sm btn-secondary"
          :disabled="currentPage >= totalPages"
          @click="nextPage"
        >
          Weiter →
        </button>
      </div>
    </template>

    <!-- Create template dialog -->
    <div v-if="showCreate" class="modal-backdrop" @click.self="showCreate = false">
      <div class="modal">
        <h2>Neue Vorlage erstellen</h2>
        <label>
          Name
          <input v-model="createForm.display_name" type="text" placeholder="z.B. Viertelnote" />
        </label>
        <label>
          Kategorie
          <select v-model="createForm.category">
            <option value="note">Note</option>
            <option value="rest">Pause</option>
            <option value="accidental">Vorzeichen</option>
            <option value="clef">Schlüssel</option>
            <option value="time_sig">Taktart</option>
            <option value="barline">Taktstrich</option>
            <option value="dynamic">Dynamik</option>
            <option value="ornament">Verzierung</option>
            <option value="other">Sonstiges</option>
          </select>
        </label>
        <div class="modal-actions">
          <button class="btn" @click="showCreate = false">Abbrechen</button>
          <button
            class="btn btn-primary"
            :disabled="!createForm.display_name.trim()"
            @click="createTemplate"
          >
            Erstellen
          </button>
        </div>
      </div>
    </div>

    <!-- Edit modal -->
    <div v-if="editingTemplate" class="modal-backdrop" @click.self="closeEdit">
      <div class="modal modal-large">
        <h2>{{ editingTemplate.display_name }} bearbeiten</h2>
        <label>
          Anzeigename
          <input v-model="editForm.display_name" type="text" />
        </label>
        <label>
          MusicXML
          <textarea v-model="editForm.musicxml_element" rows="3" placeholder="<note>...</note>" />
        </label>
        <label>
          LilyPond Token
          <input v-model="editForm.lilypond_token" type="text" placeholder="z.B. c4" />
        </label>

        <!-- Render actions -->
        <div class="render-actions">
          <button
            class="btn btn-sm btn-secondary"
            :disabled="!editForm.musicxml_element.trim() || rendering !== null"
            @click="renderMusicxml"
          >
            {{ rendering === "musicxml" ? "Rendere..." : "MusicXML rendern" }}
          </button>
          <button
            class="btn btn-sm btn-secondary"
            :disabled="!editForm.lilypond_token.trim() || rendering !== null"
            @click="renderLilypond"
          >
            {{ rendering === "lilypond" ? "Rendere..." : "LilyPond rendern" }}
          </button>
        </div>

        <div v-if="renderError" class="render-error">
          <span>{{ renderError }}</span>
          <button class="render-error-close" @click="renderError = null">&times;</button>
        </div>

        <!-- Variants -->
        <div class="variants-section">
          <h3>Varianten ({{ variants.length }})</h3>
          <LoadingSpinner v-if="loadingVariants" />
          <div v-else-if="variants.length === 0" class="empty-variants">
            Keine Varianten vorhanden.
          </div>
          <div v-else class="variants-grid">
            <div v-for="v in variants" :key="v.id" class="variant-item">
              <img
                :src="variantImageUrl(v)"
                alt="Variante"
                class="variant-img"
                @click="openPreview(v)"
              />
              <div class="variant-meta">
                <span class="variant-source">{{ v.source }}</span>
                <button class="btn btn-xs btn-danger" @click="confirmDeleteVariant(v)">×</button>
              </div>
            </div>
          </div>
        </div>

        <div class="modal-actions-spread">
          <button class="btn btn-danger" @click="confirmDeleteOpen = true">Vorlage löschen</button>
          <div class="modal-actions">
            <button class="btn" @click="closeEdit">Abbrechen</button>
            <button
              class="btn btn-primary"
              :disabled="!editForm.display_name.trim()"
              @click="saveTemplate"
            >
              Speichern
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Confirm delete template -->
    <ConfirmDialog
      :open="confirmDeleteOpen"
      title="Vorlage löschen"
      :message="`'${editingTemplate?.display_name}' und alle Varianten wirklich löschen?`"
      @confirm="deleteTemplate"
      @cancel="confirmDeleteOpen = false"
    />

    <!-- Confirm delete variant -->
    <ConfirmDialog
      :open="confirmVariantDeleteOpen"
      title="Variante löschen"
      message="Diese Variante wirklich löschen?"
      @confirm="deleteVariant"
      @cancel="confirmVariantDeleteOpen = false"
    />

    <!-- Image preview / crop lightbox -->
    <div v-if="previewImageUrl" class="lightbox">
      <div class="lightbox-canvas">
        <img :src="previewImageUrl" alt="Vorschau" class="lightbox-img" draggable="false" />
        <svg
          ref="svgOverlay"
          class="lightbox-svg"
          :viewBox="`0 0 ${previewNatW} ${previewNatH}`"
          @mousedown="onCropMouseDown"
          @mousemove="onCropMouseMove"
          @mouseup="onCropMouseUp"
        >
          <rect
            v-if="drawingRect"
            :x="drawingRect.x"
            :y="drawingRect.y"
            :width="drawingRect.width"
            :height="drawingRect.height"
            fill="rgba(245, 158, 11, 0.2)"
            stroke="#f59e0b"
            stroke-width="3"
            stroke-dasharray="8 4"
          />
        </svg>
      </div>
      <!-- Variant info -->
      <div v-if="previewVariant" class="lightbox-info">
        <span>{{ previewNatW }}×{{ previewNatH }} px</span>
        <span v-if="previewVariant.source_line_spacing">
          Linienabstand: {{ previewVariant.source_line_spacing }} px
        </span>
        <span v-if="previewVariant.height_in_lines">
          Höhe: {{ previewVariant.height_in_lines }} Linien
        </span>
        <span class="lightbox-source">{{ previewVariant.source }}</span>
      </div>
      <!-- Crop preview -->
      <div v-if="cropPreviewDataUrl" class="crop-preview">
        <span class="crop-preview-label">Vorschau:</span>
        <img :src="cropPreviewDataUrl" alt="Zugeschnitten" class="crop-preview-img" />
      </div>
      <div class="lightbox-toolbar">
        <span class="lightbox-hint">Bereich auswählen zum Zuschneiden</span>
        <div class="lightbox-actions">
          <button v-if="cropPreviewDataUrl" class="btn btn-sm btn-primary" @click.stop="applyCrop">
            Als neue Variante speichern
          </button>
          <button class="btn btn-sm" @click.stop="closePreview">Schliessen</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.total-count {
  color: var(--color-muted);
  font-size: 0.9rem;
}

.category-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  margin-bottom: 1.5rem;
  border-bottom: 1px solid var(--color-border);
  padding-bottom: 0.75rem;
}

.tab-btn {
  padding: 0.35rem 0.8rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  background: var(--color-bg-soft);
  color: var(--color-text);
  cursor: pointer;
  font-size: 0.875rem;
  transition: all var(--transition);
}

.tab-btn:hover {
  background: var(--color-primary-light);
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.tab-btn.active {
  background: var(--color-primary);
  border-color: var(--color-primary);
  color: #fff;
  font-weight: 600;
}

.empty-state {
  text-align: center;
  padding: 3rem 1rem;
  color: var(--color-muted);
}

.error-state {
  text-align: center;
  padding: 2rem;
  color: var(--color-muted);
}

.template-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 0.75rem;
}

.pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 1rem;
  margin-top: 1.5rem;
  padding-top: 1rem;
  border-top: 1px solid var(--color-border);
}

.page-info {
  font-size: 0.875rem;
  color: var(--color-muted);
}

.modal-backdrop {
  position: fixed;
  inset: 0;
  background: var(--color-overlay);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 500;
}

.modal {
  background: var(--color-bg);
  border-radius: var(--radius);
  padding: 1.5rem;
  width: 100%;
  max-width: 400px;
}

.modal-large {
  max-width: 600px;
  max-height: 80vh;
  overflow-y: auto;
}

.modal h2 {
  margin-bottom: 1rem;
}

.modal label {
  display: block;
  margin-bottom: 0.75rem;
  font-size: 0.9rem;
  color: var(--color-muted);
}

.modal input,
.modal select,
.modal textarea {
  display: block;
  width: 100%;
  margin-top: 0.25rem;
  padding: 0.5rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  background: var(--color-bg);
  color: var(--color-text);
  font-family: inherit;
}

.variants-section {
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid var(--color-border);
}

.variants-section h3 {
  font-size: 0.95rem;
  margin-bottom: 0.75rem;
}

.empty-variants {
  color: var(--color-muted);
  font-size: 0.85rem;
}

.variants-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(100px, 1fr));
  gap: 0.5rem;
}

.variant-item {
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  overflow: hidden;
}

.variant-img {
  width: 100%;
  height: 60px;
  object-fit: contain;
  background: #1a1a1a;
  image-rendering: pixelated;
  cursor: zoom-in;
}

.variant-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.2rem 0.4rem;
  font-size: 0.7rem;
  gap: 0.25rem;
}

.variant-source {
  color: var(--color-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}

.variant-meta .btn-xs {
  flex-shrink: 0;
}

.btn-xs {
  padding: 0.1rem 0.35rem;
  font-size: 0.75rem;
  line-height: 1.4;
}

.modal-actions-spread {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 1rem;
}

.modal-actions {
  display: flex;
  gap: 0.5rem;
}

.render-actions {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
}

.render-error {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  padding: 0.6rem 0.75rem;
  margin-bottom: 0.75rem;
  background: var(--color-danger-light, #3a1c1c);
  border: 1px solid var(--color-danger, #e74c3c);
  border-radius: var(--radius);
  color: var(--color-danger, #e74c3c);
  font-size: 0.85rem;
  line-height: 1.4;
}

.render-error-close {
  flex-shrink: 0;
  background: none;
  border: none;
  color: inherit;
  font-size: 1.1rem;
  cursor: pointer;
  padding: 0;
  line-height: 1;
  opacity: 0.7;
}

.render-error-close:hover {
  opacity: 1;
}

.lightbox {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.85);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  z-index: 600;
  user-select: none;
}

.lightbox-canvas {
  position: relative;
  max-width: 90vw;
  max-height: 80vh;
}

.lightbox-img {
  display: block;
  max-width: 90vw;
  max-height: 80vh;
  object-fit: contain;
  background: #fff;
  border-radius: var(--radius);
}

.lightbox-svg {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  cursor: crosshair;
}

.lightbox-toolbar {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-top: 0.75rem;
  padding: 0.5rem 1rem;
  background: rgba(0, 0, 0, 0.6);
  border-radius: var(--radius);
}

.lightbox-hint {
  color: #aaa;
  font-size: 0.8rem;
}

.lightbox-actions {
  display: flex;
  gap: 0.5rem;
}

.lightbox-info {
  display: flex;
  gap: 1rem;
  margin-top: 0.5rem;
  padding: 0.4rem 0.75rem;
  background: rgba(0, 0, 0, 0.5);
  border-radius: var(--radius);
  color: #ccc;
  font-size: 0.8rem;
}

.lightbox-source {
  color: #888;
}

.crop-preview {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-top: 0.5rem;
  padding: 0.5rem;
  background: rgba(0, 0, 0, 0.5);
  border-radius: var(--radius);
}

.crop-preview-label {
  color: #aaa;
  font-size: 0.8rem;
  white-space: nowrap;
}

.crop-preview-img {
  max-height: 80px;
  max-width: 200px;
  background: #fff;
  border-radius: 3px;
  padding: 4px;
}
</style>
