<script setup>
import { ref, computed, watch, onMounted, nextTick } from "vue";
import { useRoute } from "vue-router";
import { get, post, put, del } from "../lib/api.js";
import LoadingSpinner from "../components/LoadingSpinner.vue";
import SymbolCard from "../components/SymbolCard.vue";
import ConfirmDialog from "../components/ConfirmDialog.vue";
import { mergeSymbolCategories, symbolCategoryLabelSingular } from "../lib/symbolCategories.js";

const PAGE_SIZE = 24;

const activeCategory = ref("");
const currentPage = ref(1);
const templates = ref([]);
const total = ref(0);
const loading = ref(false);
const error = ref(null);

// Known categories with German labels live in lib/symbolCategories.js.
// The actual tab list is merged with the categories the backend reports,
// so newly introduced categories show up automatically.
const serverCategories = ref([]);
const categoryTabs = computed(() => [
  { key: "", label: "Alle", count: total.value },
  ...mergeSymbolCategories(serverCategories.value),
]);
const categoryOptions = computed(() =>
  mergeSymbolCategories(serverCategories.value).map((c) => ({
    key: c.key,
    label: symbolCategoryLabelSingular(c.key),
  })),
);

const showCreate = ref(false);
const createForm = ref({ name: "", display_name: "", category: "note" });

const editingTemplate = ref(null);
const editForm = ref({
  display_name: "",
  musicxml_element: "",
  lilypond_token: "",
  min_confidence: "",
  confidence_weight: "",
  merge_overlapping: false,
});
// Global confidence threshold from the scanner config, shown as the
// placeholder so the officer sees what "leer" means.
const globalConfidenceThreshold = ref(null);
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
const tightening = ref(false);
const tightenMessage = ref(null);

async function tightenVariants() {
  if (tightening.value) return;
  tightening.value = true;
  try {
    const r = await post("/scanner/library/variants/tighten");
    tightenMessage.value = `${r.cropped} von ${r.checked} Varianten zugeschnitten, ${r.unchanged} unverändert${
      r.skipped.length ? `, ${r.skipped.length} übersprungen` : ""
    }`;
    await fetchTemplates();
  } catch (e) {
    tightenMessage.value = `Zuschneiden fehlgeschlagen: ${e.message}`;
  } finally {
    tightening.value = false;
  }
}

const cropDrawing = ref(false);
const cropStart = ref({ x: 0, y: 0 });
const cropEnd = ref({ x: 0, y: 0 });
const cropRect = ref(null);
const svgOverlay = ref(null);

const BASE = (import.meta.env.VITE_BASE_PATH || "").replace(/\/$/, "");

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)));

async function fetchGlobalThreshold() {
  try {
    const data = await get("/scanner/config");
    const entry = (data.entries || []).find((e) => e.key === "confidence_threshold");
    if (entry) {
      const value = entry.value ?? entry.effective_value ?? entry.default_value;
      globalConfidenceThreshold.value = Number(value);
    }
  } catch {
    // Placeholder simply stays generic.
  }
}

async function fetchCategories() {
  try {
    serverCategories.value = await get("/scanner/library/categories");
  } catch {
    // Non-fatal: tabs fall back to the known category list.
  }
}

async function fetchTemplates() {
  loading.value = true;
  error.value = null;
  try {
    const offset = (currentPage.value - 1) * PAGE_SIZE;
    let path = `/scanner/library/templates?limit=${PAGE_SIZE}&offset=${offset}`;
    if (activeCategory.value) {
      path += `&category=${encodeURIComponent(activeCategory.value)}`;
    }
    const [data] = await Promise.all([get(path), fetchCategories()]);
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

function parseOptionalNumber(raw) {
  const text = String(raw ?? "")
    .trim()
    .replace(",", ".");
  if (text === "") return null;
  const n = Number(text);
  return Number.isFinite(n) ? n : NaN;
}

/** Percent input (0–100) → fraction, null when empty, NaN when invalid. */
const parsedMinConfidence = computed(() => {
  const n = parseOptionalNumber(editForm.value.min_confidence);
  if (n === null) return null;
  if (Number.isNaN(n) || n < 0 || n > 100) return NaN;
  return n / 100;
});

const parsedConfidenceWeight = computed(() => {
  const n = parseOptionalNumber(editForm.value.confidence_weight);
  if (n === null) return null;
  if (Number.isNaN(n) || n <= 0 || n > 2) return NaN;
  return n;
});

const matchingParamsValid = computed(
  () => !Number.isNaN(parsedMinConfidence.value) && !Number.isNaN(parsedConfidenceWeight.value),
);

const minConfidencePlaceholder = computed(() =>
  globalConfidenceThreshold.value == null
    ? "global"
    : `global: ${Math.round(globalConfidenceThreshold.value * 100)} %`,
);

async function openEdit(tpl) {
  editingTemplate.value = tpl;
  editForm.value = {
    display_name: tpl.display_name,
    musicxml_element: tpl.musicxml_element || "",
    lilypond_token: tpl.lilypond_token || "",
    min_confidence: tpl.min_confidence == null ? "" : String(Math.round(tpl.min_confidence * 100)),
    confidence_weight: tpl.confidence_weight == null ? "" : String(tpl.confidence_weight),
    merge_overlapping: Boolean(tpl.merge_overlapping),
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
    min_confidence: parsedMinConfidence.value,
    confidence_weight: parsedConfidenceWeight.value,
    merge_overlapping: editForm.value.merge_overlapping,
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

const cacheBust = ref(Date.now());
function variantImageUrl(variant) {
  const relative = variant.image_path.replace(/^data\/symbol_library\//, "");
  return `${BASE}/symbol-library/${relative}?v=${cacheBust.value}`;
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

// ── Variant preview / editor ─────────────────────────────────────────────
// The lightbox shows the variant with padding, its exact hitbox (red) and a
// dash-dotted crosshair on the anchor point: for notes the note-head centre
// that determines the pitch, otherwise the image centre. Modes: crop (new
// variant), pen (paint black/white pixels, saved in place), anchor (click to
// set a manual correction that is stored per variant).
const canvasEl = ref(null);
const previewMode = ref("anchor"); // "crop" | "pen" | "anchor"
const penColor = ref("black");
const brushSize = ref(3);
const zoom = ref(1);
const baseScale = ref(1);
const previewDirty = ref(false);
const previewBusy = ref(false);
const previewError = ref(null);
const anchorDx = ref(0);
const anchorDy = ref(0);
const penDrawing = ref(false);
let lastPenPoint = null;

const PREVIEW_PAD_RATIO = 0.25;
const previewPad = computed(() =>
  Math.max(20, Math.round(Math.max(previewNatW.value, previewNatH.value) * PREVIEW_PAD_RATIO)),
);
const stageW = computed(() => previewNatW.value + 2 * previewPad.value);
const stageH = computed(() => previewNatH.value + 2 * previewPad.value);
const stageScale = computed(() => baseScale.value * zoom.value);
const stageStyle = computed(() => ({
  width: `${stageW.value * stageScale.value}px`,
  height: `${stageH.value * stageScale.value}px`,
}));
const canvasStyle = computed(() => ({
  left: `${previewPad.value * stageScale.value}px`,
  top: `${previewPad.value * stageScale.value}px`,
  width: `${previewNatW.value * stageScale.value}px`,
  height: `${previewNatH.value * stageScale.value}px`,
}));
// Stroke widths in image pixels so overlay lines stay ~1.5 CSS px at any zoom
const hairline = computed(() => 1.5 / Math.max(stageScale.value, 0.01));
const dashPattern = computed(() => {
  const u = 1 / Math.max(stageScale.value, 0.01);
  return `${8 * u} ${4 * u} ${1.5 * u} ${4 * u}`;
});

const anchorStem = computed(() =>
  editingTemplate.value?.category === "note" ? editingTemplate.value?.stem_direction : null,
);
const defaultAnchor = computed(() => {
  const w = previewNatW.value;
  const h = previewNatH.value;
  const ls = previewVariant.value?.source_line_spacing || 0;
  if (anchorStem.value === "up" && ls > 0) return { x: w / 2, y: h - 0.5 * ls };
  if (anchorStem.value === "down" && ls > 0) return { x: w / 2, y: 0.5 * ls };
  return { x: w / 2, y: h / 2 };
});
const anchorPoint = computed(() => ({
  x: defaultAnchor.value.x + (Number(anchorDx.value) || 0),
  y: defaultAnchor.value.y + (Number(anchorDy.value) || 0),
}));
const anchorLabel = computed(() => {
  if (anchorStem.value === "up") return "Notenkopf, Stiel oben (½ Linie über dem unteren Rand)";
  if (anchorStem.value === "down") return "Notenkopf, Stiel unten (½ Linie unter dem oberen Rand)";
  if (editingTemplate.value?.category === "note") return "Notenkopf (Bildmitte)";
  return "Bildmitte";
});
const anchorChanged = computed(
  () =>
    (Number(anchorDx.value) || 0) !== (previewVariant.value?.anchor_dx || 0) ||
    (Number(anchorDy.value) || 0) !== (previewVariant.value?.anchor_dy || 0),
);
const modeHint = computed(() => {
  if (previewMode.value === "pen")
    return penColor.value === "black"
      ? "Schwarz zeichnen, um fehlende Tinte zu ergänzen"
      : "Weiß zeichnen, um Störpixel zu entfernen";
  if (previewMode.value === "anchor") return "Ins Bild klicken, um den Mittelpunkt zu setzen";
  return "Bereich auswählen, um daraus eine neue Variante zu erzeugen";
});

function fitBaseScale() {
  if (!stageW.value || !stageH.value) return;
  const maxW = window.innerWidth * 0.9;
  const maxH = window.innerHeight * 0.58;
  baseScale.value = Math.min(maxW / stageW.value, maxH / stageH.value, 6);
}

function loadPreviewImage() {
  const img = new Image();
  img.crossOrigin = "anonymous";
  img.onload = async () => {
    previewNatW.value = img.naturalWidth;
    previewNatH.value = img.naturalHeight;
    await nextTick();
    const c = canvasEl.value;
    if (!c) return;
    c.width = img.naturalWidth;
    c.height = img.naturalHeight;
    const ctx = c.getContext("2d");
    ctx.drawImage(img, 0, 0);
    previewDirty.value = false;
    fitBaseScale();
  };
  img.onerror = () => {
    previewError.value = "Bild konnte nicht geladen werden";
  };
  img.src = previewImageUrl.value;
}

function onPreviewKey(e) {
  if (e.key === "Escape" && !previewDirty.value) closePreview();
}

function openPreview(v) {
  previewVariant.value = v;
  previewImageUrl.value = variantImageUrl(v);
  cropRect.value = null;
  cropDrawing.value = false;
  previewMode.value = "anchor";
  zoom.value = 1;
  previewError.value = null;
  anchorDx.value = v.anchor_dx || 0;
  anchorDy.value = v.anchor_dy || 0;
  window.addEventListener("keydown", onPreviewKey);
  loadPreviewImage();
}

function closePreview() {
  window.removeEventListener("keydown", onPreviewKey);
  previewVariant.value = null;
  previewImageUrl.value = null;
  cropRect.value = null;
  cropPreviewDataUrl.value = null;
  previewDirty.value = false;
}

function zoomIn() {
  zoom.value = Math.min(zoom.value * 1.5, 12);
}
function zoomOut() {
  zoom.value = Math.max(zoom.value / 1.5, 0.25);
}

/** Pointer position in image pixels (may lie in the padding, i.e. outside 0..W/H). */
function toImgCoords(e) {
  const svg = svgOverlay.value;
  if (!svg) return { x: 0, y: 0 };
  const rect = svg.getBoundingClientRect();
  const x = ((e.clientX - rect.left) / rect.width) * stageW.value - previewPad.value;
  const y = ((e.clientY - rect.top) / rect.height) * stageH.value - previewPad.value;
  return { x, y };
}

function clampToImage(pt) {
  return {
    x: Math.round(Math.min(Math.max(pt.x, 0), previewNatW.value)),
    y: Math.round(Math.min(Math.max(pt.y, 0), previewNatH.value)),
  };
}

function paintTo(pt) {
  const c = canvasEl.value;
  if (!c) return;
  const ctx = c.getContext("2d");
  ctx.strokeStyle = penColor.value === "black" ? "#000000" : "#ffffff";
  ctx.fillStyle = ctx.strokeStyle;
  ctx.lineWidth = brushSize.value;
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  if (lastPenPoint) {
    ctx.beginPath();
    ctx.moveTo(lastPenPoint.x, lastPenPoint.y);
    ctx.lineTo(pt.x, pt.y);
    ctx.stroke();
  } else {
    ctx.beginPath();
    ctx.arc(pt.x, pt.y, brushSize.value / 2, 0, Math.PI * 2);
    ctx.fill();
  }
  lastPenPoint = pt;
  previewDirty.value = true;
}

function onStagePointerDown(e) {
  if (!svgOverlay.value || !svgOverlay.value.contains(e.target)) return;
  e.preventDefault();
  const pt = toImgCoords(e);
  if (previewMode.value === "pen") {
    penDrawing.value = true;
    lastPenPoint = null;
    paintTo(pt);
  } else if (previewMode.value === "anchor") {
    anchorDx.value = Math.round((pt.x - defaultAnchor.value.x) * 2) / 2;
    anchorDy.value = Math.round((pt.y - defaultAnchor.value.y) * 2) / 2;
  } else {
    cropDrawing.value = true;
    const c = clampToImage(pt);
    cropStart.value = c;
    cropEnd.value = c;
    cropRect.value = null;
  }
}

function onStagePointerMove(e) {
  if (previewMode.value === "pen") {
    if (!penDrawing.value) return;
    e.preventDefault();
    paintTo(toImgCoords(e));
  } else if (previewMode.value === "crop") {
    if (!cropDrawing.value) return;
    e.preventDefault();
    cropEnd.value = clampToImage(toImgCoords(e));
  }
}

function onStagePointerUp() {
  if (penDrawing.value) {
    penDrawing.value = false;
    lastPenPoint = null;
    return;
  }
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

// Live drawing rect or finalised crop rect (image coordinates)
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

// Preview of the cropped area, taken from the (possibly edited) canvas
function updateCropPreview() {
  const c = cropRect.value;
  const src = canvasEl.value;
  if (!c || !src) {
    cropPreviewDataUrl.value = null;
    return;
  }
  const canvas = document.createElement("canvas");
  canvas.width = c.width;
  canvas.height = c.height;
  canvas.getContext("2d").drawImage(src, c.x, c.y, c.width, c.height, 0, 0, c.width, c.height);
  cropPreviewDataUrl.value = canvas.toDataURL("image/png");
}

watch(cropRect, updateCropPreview);

const API_BASE = `${BASE}/api/v1/scanner/library`;

async function postImage(url, blob, extra = {}) {
  const formData = new FormData();
  formData.append("file", blob, "variant.png");
  for (const [k, v] of Object.entries(extra)) formData.append(k, String(v));
  const resp = await fetch(url, { method: "POST", body: formData });
  if (!resp.ok) throw new Error(await resp.text());
  return resp.json();
}

async function reloadVariants() {
  if (!editingTemplate.value) return;
  variants.value = await get(`/scanner/library/templates/${editingTemplate.value.id}/variants`);
}

async function applyCrop() {
  if (!cropPreviewDataUrl.value || !editingTemplate.value || !previewVariant.value) return;
  previewBusy.value = true;
  previewError.value = null;
  try {
    const blob = await (await fetch(cropPreviewDataUrl.value)).blob();
    await postImage(`${API_BASE}/templates/${editingTemplate.value.id}/variants/upload`, blob, {
      source_line_spacing: previewVariant.value.source_line_spacing || 0,
    });
    await reloadVariants();
    await fetchTemplates();
    closePreview();
  } catch (e) {
    previewError.value = `Zuschneiden fehlgeschlagen: ${e.message}`;
  } finally {
    previewBusy.value = false;
  }
}

function canvasToBlob() {
  return new Promise((resolve, reject) => {
    canvasEl.value.toBlob((b) => (b ? resolve(b) : reject(new Error("Kein Bild"))), "image/png");
  });
}

async function saveImage() {
  if (!previewDirty.value || !editingTemplate.value || !previewVariant.value) return;
  previewBusy.value = true;
  previewError.value = null;
  try {
    const blob = await canvasToBlob();
    const updated = await postImage(
      `${API_BASE}/templates/${editingTemplate.value.id}/variants/${previewVariant.value.id}/image`,
      blob,
    );
    cacheBust.value = Date.now();
    previewVariant.value = { ...previewVariant.value, ...updated };
    previewImageUrl.value = variantImageUrl(previewVariant.value);
    previewDirty.value = false;
    await reloadVariants();
  } catch (e) {
    previewError.value = `Speichern fehlgeschlagen: ${e.message}`;
  } finally {
    previewBusy.value = false;
  }
}

function discardEdits() {
  loadPreviewImage();
}

function resetAnchor() {
  anchorDx.value = 0;
  anchorDy.value = 0;
}

async function saveAnchor() {
  if (!editingTemplate.value || !previewVariant.value) return;
  previewBusy.value = true;
  previewError.value = null;
  try {
    const dx = Number(anchorDx.value) || 0;
    const dy = Number(anchorDy.value) || 0;
    const updated = await put(
      `/scanner/library/templates/${editingTemplate.value.id}/variants/${previewVariant.value.id}/anchor`,
      { anchor_dx: dx || null, anchor_dy: dy || null },
    );
    previewVariant.value = { ...previewVariant.value, ...updated };
    await reloadVariants();
  } catch (e) {
    previewError.value = `Mittelpunkt konnte nicht gespeichert werden: ${e.message}`;
  } finally {
    previewBusy.value = false;
  }
}

watch([activeCategory, currentPage], fetchTemplates);
const route = useRoute();

/** Deep link from the scan editor: /notenscanner/bibliothek?template=ID&variant=ID */
async function openFromQuery() {
  const templateId = Number(route.query.template);
  if (!templateId) return;
  try {
    const tpl = await get(`/scanner/library/templates/${templateId}`);
    await openEdit(tpl);
    const variantId = Number(route.query.variant);
    const variant = variants.value.find((v) => v.id === variantId);
    if (variant) openPreview(variant);
  } catch (e) {
    error.value = `Vorlage konnte nicht geöffnet werden: ${e.message}`;
  }
}

onMounted(() => {
  fetchTemplates();
  fetchGlobalThreshold();
  openFromQuery();
});
</script>

<template>
  <div>
    <div class="page-header">
      <h1>Symbol-Bibliothek</h1>
      <div class="header-right">
        <span class="total-count">{{ total }} Vorlagen</span>
        <button
          class="btn btn-sm"
          :disabled="tightening"
          title="Alle Noten- und Pausen-Varianten exakt auf die schwarzen Pixel zuschneiden"
          @click="tightenVariants"
        >
          {{ tightening ? "Schneide zu…" : "Varianten zuschneiden" }}
        </button>
        <button class="btn btn-primary btn-sm" @click="showCreate = true">+ Neue Vorlage</button>
      </div>
    </div>

    <p v-if="tightenMessage" class="tighten-message" role="status">{{ tightenMessage }}</p>

    <!-- Category filter tabs -->
    <div class="category-tabs">
      <button
        v-for="cat in categoryTabs"
        :key="cat.key"
        type="button"
        :class="['tab-btn', { active: activeCategory === cat.key }]"
        :aria-pressed="activeCategory === cat.key"
        @click="selectCategory(cat.key)"
      >
        {{ cat.label }}
        <span v-if="cat.key !== ''" class="tab-count">{{ cat.count }}</span>
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
    <div v-if="showCreate" class="overlay" @click.self="showCreate = false">
      <div class="dialog">
        <h2>Neue Vorlage erstellen</h2>
        <label>
          Name
          <input v-model="createForm.display_name" type="text" placeholder="z.B. Viertelnote" />
        </label>
        <label>
          Kategorie
          <select v-model="createForm.category">
            <option v-for="opt in categoryOptions" :key="opt.key" :value="opt.key">
              {{ opt.label }}
            </option>
          </select>
        </label>
        <div class="dialog-actions">
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
    <div v-if="editingTemplate" class="overlay" @click.self="closeEdit">
      <div class="dialog dialog-lg">
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

        <!-- Matching parameters -->
        <fieldset class="matching-params">
          <legend>Erkennung</legend>
          <div class="matching-grid">
            <label>
              Mindest-Konfidenz (%)
              <input
                v-model="editForm.min_confidence"
                type="number"
                inputmode="decimal"
                min="0"
                max="100"
                step="1"
                :placeholder="minConfidencePlaceholder"
                :aria-invalid="Number.isNaN(parsedMinConfidence)"
              />
            </label>
            <label>
              Gewichtung
              <input
                v-model="editForm.confidence_weight"
                type="number"
                inputmode="decimal"
                min="0.05"
                max="2"
                step="0.05"
                placeholder="1,0"
                :aria-invalid="Number.isNaN(parsedConfidenceWeight)"
              />
            </label>
          </div>
          <p class="field-hint">
            Leer bedeutet globaler Wert. Die Gewichtung wird vor dem Schwellwert auf den Rohwert
            angewendet, ein Wert unter 1 lässt die Vorlage knappe Duelle verlieren.
          </p>
          <label class="checkbox-label">
            <input v-model="editForm.merge_overlapping" type="checkbox" />
            Überlappende Treffer dieser Vorlage zu einem Symbol zusammenführen
          </label>
          <p v-if="!matchingParamsValid" class="field-error">
            Mindest-Konfidenz muss zwischen 0 und 100 liegen, Gewichtung zwischen 0 und 2.
          </p>
        </fieldset>

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

        <div class="dialog-actions-spread">
          <button class="btn btn-danger" @click="confirmDeleteOpen = true">Vorlage löschen</button>
          <div class="dialog-actions">
            <button class="btn" @click="closeEdit">Abbrechen</button>
            <button
              class="btn btn-primary"
              :disabled="!editForm.display_name.trim() || !matchingParamsValid"
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

    <!-- Variant preview / editor lightbox -->
    <div
      v-if="previewImageUrl"
      class="lightbox"
      role="dialog"
      aria-modal="true"
      aria-label="Variante ansehen und bearbeiten"
    >
      <div class="lightbox-toolbar">
        <div class="tool-group" role="group" aria-label="Werkzeug">
          <button
            type="button"
            class="btn btn-sm"
            :aria-pressed="previewMode === 'crop'"
            @click="previewMode = 'crop'"
          >
            Zuschneiden
          </button>
          <button
            type="button"
            class="btn btn-sm"
            :aria-pressed="previewMode === 'pen' && penColor === 'black'"
            @click="
              previewMode = 'pen';
              penColor = 'black';
            "
          >
            Stift schwarz
          </button>
          <button
            type="button"
            class="btn btn-sm"
            :aria-pressed="previewMode === 'pen' && penColor === 'white'"
            @click="
              previewMode = 'pen';
              penColor = 'white';
            "
          >
            Stift weiß
          </button>
          <button
            type="button"
            class="btn btn-sm"
            :aria-pressed="previewMode === 'anchor'"
            @click="previewMode = 'anchor'"
          >
            Mittelpunkt setzen
          </button>
        </div>
        <label v-if="previewMode === 'pen'" class="tool-field">
          Pinsel
          <input v-model.number="brushSize" type="range" min="1" max="15" step="1" />
          <span class="tool-value">{{ brushSize }} px</span>
        </label>
        <div class="tool-group" role="group" aria-label="Zoom">
          <button type="button" class="btn btn-sm" aria-label="Verkleinern" @click="zoomOut">
            −
          </button>
          <span class="tool-value">{{ Math.round(zoom * 100) }} %</span>
          <button type="button" class="btn btn-sm" aria-label="Vergrößern" @click="zoomIn">
            +
          </button>
          <button type="button" class="btn btn-sm" @click="zoom = 1">Einpassen</button>
        </div>
      </div>

      <div class="lightbox-stage-wrap">
        <div class="lightbox-stage" :style="stageStyle">
          <canvas ref="canvasEl" class="lightbox-canvas-el" :style="canvasStyle"></canvas>
          <svg
            ref="svgOverlay"
            class="lightbox-svg"
            :class="`mode-${previewMode}`"
            :viewBox="`${-previewPad} ${-previewPad} ${stageW} ${stageH}`"
            @pointerdown="onStagePointerDown"
            @pointermove="onStagePointerMove"
            @pointerup="onStagePointerUp"
            @pointerleave="onStagePointerUp"
          >
            <!-- exact hitbox of the variant -->
            <rect
              class="hitbox"
              x="0"
              y="0"
              :width="previewNatW"
              :height="previewNatH"
              :stroke-width="hairline"
            />
            <!-- dash-dotted crosshair on the anchor point -->
            <line
              class="crosshair"
              :x1="-previewPad"
              :x2="previewNatW + previewPad"
              :y1="anchorPoint.y"
              :y2="anchorPoint.y"
              :stroke-width="hairline"
              :stroke-dasharray="dashPattern"
            />
            <line
              class="crosshair"
              :x1="anchorPoint.x"
              :x2="anchorPoint.x"
              :y1="-previewPad"
              :y2="previewNatH + previewPad"
              :stroke-width="hairline"
              :stroke-dasharray="dashPattern"
            />
            <circle class="anchor-dot" :cx="anchorPoint.x" :cy="anchorPoint.y" :r="hairline * 2" />
            <rect
              v-if="drawingRect"
              :x="drawingRect.x"
              :y="drawingRect.y"
              :width="drawingRect.width"
              :height="drawingRect.height"
              fill="var(--overlay-capture-fill)"
              stroke="var(--overlay-capture)"
              :stroke-width="hairline * 2"
              :stroke-dasharray="dashPattern"
            />
          </svg>
        </div>
      </div>

      <!-- Anchor point -->
      <div class="lightbox-panel">
        <span class="panel-label">Mittelpunkt: {{ anchorLabel }}</span>
        <label class="tool-field">
          dx
          <input v-model.number="anchorDx" class="num-input" type="number" step="0.5" /> px
        </label>
        <label class="tool-field">
          dy
          <input v-model.number="anchorDy" class="num-input" type="number" step="0.5" /> px
        </label>
        <span class="panel-muted">
          = {{ anchorPoint.x.toFixed(1) }} / {{ anchorPoint.y.toFixed(1) }} px
        </span>
        <button
          type="button"
          class="btn btn-sm"
          :disabled="!anchorDx && !anchorDy"
          @click="resetAnchor"
        >
          Zurücksetzen
        </button>
        <button
          type="button"
          class="btn btn-sm btn-primary"
          :disabled="!anchorChanged || previewBusy"
          @click="saveAnchor"
        >
          Mittelpunkt speichern
        </button>
      </div>

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

      <div v-if="cropPreviewDataUrl" class="crop-preview">
        <span class="crop-preview-label">Vorschau:</span>
        <img :src="cropPreviewDataUrl" alt="Zugeschnitten" class="crop-preview-img" />
      </div>

      <p v-if="previewError" class="lightbox-error" role="alert">{{ previewError }}</p>

      <div class="lightbox-toolbar">
        <span class="lightbox-hint">{{ modeHint }}</span>
        <div class="lightbox-actions">
          <button
            v-if="cropPreviewDataUrl"
            type="button"
            class="btn btn-sm btn-primary"
            :disabled="previewBusy"
            @click.stop="applyCrop"
          >
            Als neue Variante speichern
          </button>
          <button v-if="previewDirty" type="button" class="btn btn-sm" @click="discardEdits">
            Verwerfen
          </button>
          <button
            v-if="previewDirty"
            type="button"
            class="btn btn-sm btn-primary"
            :disabled="previewBusy"
            @click="saveImage"
          >
            Bild speichern
          </button>
          <button type="button" class="btn btn-sm" @click.stop="closePreview">Schließen</button>
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
  transition:
    background var(--transition),
    border-color var(--transition),
    color var(--transition);
}

.tab-btn:hover {
  background: var(--color-primary-light);
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.tab-btn.active {
  background: var(--color-primary);
  border-color: var(--color-primary);
  color: var(--color-on-primary);
  font-weight: 600;
}

.tab-count {
  margin-left: 0.35rem;
  font-size: 0.75rem;
  font-variant-numeric: tabular-nums;
  opacity: 0.75;
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

.matching-params {
  margin: 0.75rem 0 0;
  padding: 0.75rem 0.9rem 0.5rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
}

.matching-params legend {
  padding: 0 0.35rem;
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--color-muted);
}

.matching-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 0.75rem;
}

.matching-grid input {
  font-variant-numeric: tabular-nums;
}

.field-hint {
  margin: 0.5rem 0;
  font-size: 0.8rem;
  color: var(--color-muted);
}

.field-error {
  margin: 0.25rem 0 0;
  font-size: 0.8rem;
  color: var(--color-danger);
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  min-height: 44px;
}

.checkbox-label input {
  width: 1.1rem;
  height: 1.1rem;
  margin: 0;
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
  background: var(--color-canvas-bg);
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

.dialog-actions-spread {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 1rem;
}

.dialog-actions-spread .dialog-actions {
  margin-top: 0;
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
  background: var(--color-danger-bg);
  border: 1px solid color-mix(in srgb, var(--color-danger) 30%, transparent);
  border-radius: var(--radius);
  color: var(--color-danger);
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
  background: var(--color-lightbox-bg);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  padding: 1rem;
  z-index: var(--z-overlay-top);
  user-select: none;
}

.lightbox-stage-wrap {
  overflow: auto;
  max-width: 92vw;
  max-height: 60vh;
  border-radius: var(--radius);
  background: var(--color-canvas-chrome);
}

.lightbox-stage {
  position: relative;
  background: var(--color-paper);
  touch-action: none;
}

.lightbox-canvas-el {
  position: absolute;
  image-rendering: pixelated;
  pointer-events: none;
}

.lightbox-svg {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  cursor: crosshair;
  touch-action: none;
}

.lightbox-svg.mode-anchor {
  cursor: cell;
}

.lightbox-svg .hitbox {
  fill: none;
  stroke: var(--color-danger);
}

.lightbox-svg .crosshair {
  stroke: var(--color-primary);
}

.lightbox-svg .anchor-dot {
  fill: var(--color-primary);
}

.lightbox-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 1rem;
  padding: 0.5rem 1rem;
  background: var(--color-canvas-chrome);
  border-radius: var(--radius);
}

.tool-group {
  display: flex;
  align-items: center;
  gap: 0.25rem;
}

.tool-group .btn[aria-pressed="true"] {
  outline: 2px solid var(--color-primary);
  outline-offset: 1px;
}

.tool-field {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  color: var(--color-canvas-text);
  font-size: 0.8rem;
}

.tool-value {
  color: var(--color-canvas-text);
  font-size: 0.8rem;
  font-variant-numeric: tabular-nums;
  min-width: 3.5rem;
  text-align: center;
}

.num-input {
  width: 4.5rem;
}

.lightbox-panel {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.75rem;
  padding: 0.4rem 0.75rem;
  background: var(--color-canvas-chrome);
  border-radius: var(--radius);
  color: var(--color-canvas-text);
  font-size: 0.8rem;
}

.panel-label {
  font-weight: 600;
}

.panel-muted {
  color: var(--color-canvas-fg);
  font-variant-numeric: tabular-nums;
}

.lightbox-hint {
  color: var(--color-canvas-fg);
  font-size: 0.8rem;
}

.lightbox-actions {
  display: flex;
  gap: 0.5rem;
}

.lightbox-info {
  display: flex;
  gap: 1rem;
  padding: 0.4rem 0.75rem;
  background: var(--color-canvas-chrome);
  border-radius: var(--radius);
  color: var(--color-canvas-text);
  font-size: 0.8rem;
}

.lightbox-source {
  color: var(--color-canvas-fg);
}

.lightbox-error {
  margin: 0;
  padding: 0.4rem 0.75rem;
  background: var(--color-danger-bg);
  color: var(--color-danger);
  border-radius: var(--radius);
  font-size: 0.85rem;
}

.crop-preview {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.5rem;
  background: var(--color-canvas-chrome);
  border-radius: var(--radius);
}

.crop-preview-label {
  color: var(--color-canvas-fg);
  font-size: 0.8rem;
  white-space: nowrap;
}

.crop-preview-img {
  max-height: 80px;
  max-width: 200px;
  background: var(--color-paper);
  border-radius: 3px;
  padding: 4px;
}
.tighten-message {
  margin: 0 0 0.75rem;
  font-size: 0.85rem;
  color: var(--color-muted);
}
</style>
