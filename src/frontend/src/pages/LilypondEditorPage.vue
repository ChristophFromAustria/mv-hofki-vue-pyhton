<script setup>
/**
 * LilyPond page of a scan: rendered preview with layout overrides, the
 * browser notation editor and the source code. Edits are saved as the scan's
 * version through "Speichern & rendern"; "Auf Analyse zurücksetzen" discards
 * them and generates the code from the analysis again.
 */
import { ref, computed, watch, defineAsyncComponent, onMounted, onBeforeUnmount } from "vue";
import { RouterLink, useRouter, onBeforeRouteLeave } from "vue-router";
import { get } from "../lib/api.js";
import { fetchScan, saveScanAdjustments, parseAdjustments, scanAssetUrl } from "../lib/scans.js";
import { useLilypondScore } from "../composables/useLilypondScore.js";
import LoadingSpinner from "../components/LoadingSpinner.vue";
import ConfirmDialog from "../components/ConfirmDialog.vue";
import LilypondLayoutDrawer from "../components/LilypondLayoutDrawer.vue";

// VexFlow is large; load the editor (and VexFlow) only when the tab is opened.
const LilypondEditor = defineAsyncComponent(() => import("../components/LilypondEditor.vue"));

const props = defineProps({
  projectId: { type: String, required: true },
  scanId: { type: String, required: true },
});

const router = useRouter();
const score = useLilypondScore(props.scanId);

const scan = ref(null);
const staves = ref([]);
const adjustments = ref({});
const hasAnalysis = ref(false);
const loading = ref(true);
const error = ref(null);

const analysisRoute = computed(() => ({
  name: "scan-analysis",
  params: { id: props.projectId, scanId: props.scanId },
}));
const projectRoute = computed(() => ({
  name: "scanner-project-detail",
  params: { id: props.projectId },
}));

async function load() {
  loading.value = true;
  error.value = null;
  try {
    const [scanData, stavesData, measuresData] = await Promise.all([
      fetchScan(props.scanId),
      get(`/scanner/scans/${props.scanId}/staves`).catch(() => []),
      get(`/scanner/scans/${props.scanId}/measures`).catch(() => []),
    ]);
    scan.value = scanData;
    staves.value = stavesData || [];
    adjustments.value = parseAdjustments(scanData.adjustments_json, {});
    hasAnalysis.value = (measuresData || []).length > 0;
    if (scanData.has_lilypond_edit || hasAnalysis.value) {
      await score.generate(false);
    }
  } catch (e) {
    error.value = e.message;
  } finally {
    loading.value = false;
  }
}

/** Nothing to show yet: neither an analysis nor a saved editor version. */
const needsAnalysis = computed(
  () => !!scan.value && !scan.value.has_lilypond_edit && !hasAnalysis.value,
);

// ── Tabs ─────────────────────────────────────────────────────────────────
const TABS = ["preview", "editor", "code"];
const activeTab = ref("preview");
try {
  const stored = localStorage.getItem("lilypondEditorTab");
  if (TABS.includes(stored)) activeTab.value = stored;
} catch {
  // storage unavailable, keep default
}
const editorVisited = ref(activeTab.value === "editor");
watch(activeTab, (tab) => {
  if (tab === "editor") editorVisited.value = true;
  try {
    localStorage.setItem("lilypondEditorTab", tab);
  } catch {
    // ignore
  }
});

// ── Editor state ─────────────────────────────────────────────────────────
// The edited code lives in the page until "Speichern & rendern".
const editedCode = ref("");
watch(score.code, (code) => {
  editedCode.value = code;
});
const isEdited = computed(() => editedCode.value !== score.code.value);
const busy = computed(() => score.generating.value || score.rendering.value);

async function saveAndRender() {
  if (!isEdited.value) return;
  const ok = await score.renderEdited(editedCode.value);
  if (ok) {
    activeTab.value = "preview";
    if (scan.value) scan.value.has_lilypond_edit = true;
  }
}

const confirmResetOpen = ref(false);
async function resetToAnalysis() {
  confirmResetOpen.value = false;
  const ok = await score.generate(true);
  if (ok && scan.value) scan.value.has_lilypond_edit = false;
}

const copied = ref(false);
async function copyCode() {
  try {
    await navigator.clipboard.writeText(editedCode.value);
    copied.value = true;
    setTimeout(() => (copied.value = false), 1500);
  } catch {
    copied.value = false;
  }
}

// ── Layout overrides (preview drawer) ────────────────────────────────────
const layoutOpen = ref(false);
const layoutError = ref(null);

/**
 * Layout values become per-scan overrides (adjustments.analysis) and the
 * score is rendered again.
 */
async function onApplyLayout({ values, reset }) {
  const analysis = { ...(adjustments.value.analysis || {}) };
  for (const key of Object.keys(analysis)) {
    if (key.startsWith("ly_")) delete analysis[key];
  }
  if (!reset) Object.assign(analysis, values);
  analysis.enabled = Object.keys(analysis).some((k) => k !== "enabled");
  adjustments.value = { ...adjustments.value, analysis };
  layoutError.value = null;
  try {
    await saveScanAdjustments(props.scanId, adjustments.value);
  } catch (e) {
    layoutError.value = `Einstellungen konnten nicht gespeichert werden: ${e.message}`;
    return;
  }
  await score.generate(false);
}

// ── Preview ──────────────────────────────────────────────────────────────
const showWarnings = ref(false);
const pngWidth = ref(0);
const pngHeight = ref(0);

const bustStamp = computed(() => `${scan.value?.updated_at || ""}-${score.renderStamp.value}`);
const previewUrl = computed(() =>
  score.pngPaths.value.length ? scanAssetUrl(score.pngPaths.value[0], bustStamp.value) : null,
);
const pdfUrl = computed(() => scanAssetUrl(score.pdfPath.value, bustStamp.value));

function onPngLoad(e) {
  pngWidth.value = e.target.naturalWidth;
  pngHeight.value = e.target.naturalHeight;
}

// Crop overlay: 165/210 of width, 123/148 of height, centered
const cropRect = computed(() => {
  if (!pngWidth.value || !pngHeight.value) return null;
  const w = pngWidth.value * (165.0 / 210.0);
  const h = pngHeight.value * (123.0 / 148.0);
  return { x: (pngWidth.value - w) / 2, y: (pngHeight.value - h) / 2, w, h };
});

// ── Unsaved changes guard ────────────────────────────────────────────────
const confirmLeaveOpen = ref(false);
const pendingRoute = ref(null);
let leaveConfirmed = false;

onBeforeRouteLeave((to) => {
  if (!isEdited.value || leaveConfirmed) return true;
  pendingRoute.value = to;
  confirmLeaveOpen.value = true;
  return false;
});

function discardAndLeave() {
  confirmLeaveOpen.value = false;
  leaveConfirmed = true;
  const to = pendingRoute.value;
  pendingRoute.value = null;
  if (to) router.push(to);
}

function onBeforeUnload(e) {
  if (!isEdited.value) return;
  e.preventDefault();
  e.returnValue = "";
}

onMounted(() => {
  window.addEventListener("beforeunload", onBeforeUnload);
  load();
});
onBeforeUnmount(() => {
  window.removeEventListener("beforeunload", onBeforeUnload);
});
</script>

<template>
  <div class="page-layout">
    <!-- Toolbar -->
    <header class="toolbar">
      <div class="toolbar-group">
        <RouterLink :to="projectRoute" class="btn btn-sm">← Zurück</RouterLink>
        <h1 class="page-title">
          LilyPond
          <span v-if="scan" class="page-meta">Seite {{ scan.page_number }}</span>
          <span
            v-if="score.source.value === 'edited'"
            class="source-badge"
            title="Diese Fassung wurde im Editor bearbeitet und gespeichert"
            >Bearbeitet</span
          >
        </h1>
      </div>

      <nav class="tab-bar" aria-label="Ansicht">
        <button
          type="button"
          class="tab-btn"
          :class="{ active: activeTab === 'preview' }"
          @click="activeTab = 'preview'"
        >
          Vorschau
        </button>
        <button
          type="button"
          class="tab-btn"
          :class="{ active: activeTab === 'editor' }"
          @click="activeTab = 'editor'"
        >
          Editor
          <span class="tab-badge">Beta</span>
        </button>
        <button
          type="button"
          class="tab-btn"
          :class="{ active: activeTab === 'code' }"
          @click="activeTab = 'code'"
        >
          Code
          <span v-if="isEdited" class="tab-dot" title="Geändert"></span>
        </button>
      </nav>

      <div class="toolbar-group toolbar-actions">
        <RouterLink
          :to="analysisRoute"
          class="btn btn-sm"
          title="Scan analysieren oder korrigieren"
        >
          Analyse-Modus
        </RouterLink>
        <span class="toolbar-separator"></span>
        <button
          type="button"
          class="btn btn-sm"
          :class="{ 'btn-primary': isEdited }"
          :disabled="busy || !isEdited"
          :title="isEdited ? 'Bearbeiteten Code mit LilyPond rendern' : 'Keine Änderungen'"
          @click="saveAndRender"
        >
          {{ score.rendering.value ? "Speichert…" : "Speichern & rendern" }}
        </button>
        <button
          v-if="score.source.value === 'edited'"
          type="button"
          class="btn btn-sm"
          :disabled="busy"
          title="Bearbeitete Fassung verwerfen und aus den Analysedaten neu erzeugen"
          @click="confirmResetOpen = true"
        >
          Auf Analyse zurücksetzen
        </button>
        <a
          v-if="pdfUrl"
          :href="pdfUrl"
          target="_blank"
          class="btn btn-sm"
          :class="{ 'btn-primary': !isEdited }"
        >
          PDF öffnen
        </a>
      </div>
    </header>

    <!-- Body -->
    <div v-if="loading" class="page-state">
      <LoadingSpinner />
    </div>

    <div v-else-if="error" class="page-state">
      <p class="state-error">Fehler: {{ error }}</p>
      <button class="btn" @click="load">Erneut laden</button>
    </div>

    <div v-else-if="needsAnalysis" class="page-state">
      <h2>Noch keine Analyse</h2>
      <p class="state-text">
        Für diesen Scan wurden noch keine Takte erkannt. Führen Sie zuerst die Analyse durch, dann
        kann LilyPond-Code erzeugt werden.
      </p>
      <RouterLink :to="analysisRoute" class="btn btn-primary">Zur Analyse</RouterLink>
    </div>

    <template v-else>
      <p v-if="score.error.value" class="page-error" role="alert">
        LilyPond-Fehler: {{ score.error.value }}
      </p>
      <p v-if="layoutError" class="page-error" role="alert">{{ layoutError }}</p>

      <!-- Preview: image plus a layout drawer sliding in from the left -->
      <section v-if="activeTab === 'preview'" class="tab-panel preview-area">
        <LilypondLayoutDrawer
          v-model:open="layoutOpen"
          :adjustments="adjustments"
          :busy="score.generating.value"
          @apply-layout="onApplyLayout"
        />

        <div class="preview-scroll">
          <div v-if="score.generating.value && !previewUrl" class="preview-empty">
            Wird gerendert…
          </div>
          <div v-else-if="previewUrl" class="preview-wrap">
            <img :src="previewUrl" alt="LilyPond-Vorschau" class="preview-img" @load="onPngLoad" />
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

          <!-- Warnings (measure fill mismatches etc.) -->
          <div v-if="score.warnings.value.length" class="warnings">
            <button type="button" class="warnings-toggle" @click="showWarnings = !showWarnings">
              {{ showWarnings ? "▾" : "▸" }} {{ score.warnings.value.length }} Hinweis{{
                score.warnings.value.length === 1 ? "" : "e"
              }}
              zur Taktfüllung
            </button>
            <ul v-if="showWarnings" class="warnings-list">
              <li v-for="(w, i) in score.warnings.value" :key="i">{{ w }}</li>
            </ul>
          </div>
        </div>
      </section>

      <!-- Editor (browser rendering via VexFlow) -->
      <section v-show="activeTab === 'editor'" class="tab-panel editor-panel">
        <LilypondEditor
          v-if="editorVisited"
          v-model:code="editedCode"
          :original-code="score.code.value"
          :staff-image-url="scanAssetUrl(scan?.image_path)"
          :staves="staves"
        />
        <p class="editor-note">
          Die Darstellung im Browser ist eine Näherung an den LilyPond-Satz. Änderungen werden in
          den Code übernommen. „Speichern & rendern" sichert die bearbeitete Fassung und erneuert
          PDF und Vorschau. Die Analyse selbst bleibt unverändert; „Auf Analyse zurücksetzen"
          verwirft die bearbeitete Fassung wieder.
        </p>
      </section>

      <!-- Code -->
      <section v-if="activeTab === 'code'" class="tab-panel code-panel">
        <div class="code-bar">
          <span v-if="isEdited" class="code-edited">Enthält Änderungen aus dem Editor</span>
          <span v-else-if="score.source.value === 'edited'" class="code-unchanged"
            >Gespeicherte bearbeitete Fassung</span
          >
          <span v-else class="code-unchanged">Generierter Code</span>
          <button class="btn btn-sm" type="button" @click="copyCode">
            {{ copied ? "Kopiert" : "Code kopieren" }}
          </button>
        </div>
        <pre class="ly-code">{{ editedCode }}</pre>
      </section>
    </template>

    <!-- Dialogs inside the root: App.vue's <Transition> needs a single root element -->
    <ConfirmDialog
      :open="confirmResetOpen"
      title="Auf Analyse zurücksetzen"
      confirm-label="Zurücksetzen"
      message="Die im Editor bearbeitete Fassung wird verworfen und der LilyPond-Code aus den aktuellen Analysedaten neu erzeugt. Fortfahren?"
      @confirm="resetToAnalysis"
      @cancel="confirmResetOpen = false"
    />
    <ConfirmDialog
      :open="confirmLeaveOpen"
      title="Ungespeicherte Änderungen"
      confirm-label="Verwerfen"
      message="Die Änderungen im Editor wurden noch nicht gespeichert. Seite trotzdem verlassen?"
      @confirm="discardAndLeave"
      @cancel="confirmLeaveOpen = false"
    />
  </div>
</template>

<style scoped>
.page-layout {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 60px);
  overflow: hidden;
  /* Break out of App.vue .container max-width and padding */
  width: 100vw;
  margin-left: calc(-50vw + 50%);
  padding: 0;
}

.toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem 1rem;
  padding: 0.5rem 1rem;
  border-bottom: 1px solid var(--color-border);
  background: var(--color-bg-soft);
  flex-shrink: 0;
}

.toolbar-group {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.toolbar-actions {
  margin-left: auto;
  flex-wrap: wrap;
}

.toolbar-separator {
  width: 1px;
  height: 1.2rem;
  background: var(--color-border);
}

.page-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
}

.page-meta {
  font-size: 0.8rem;
  font-weight: 400;
  color: var(--color-muted);
}

.source-badge {
  padding: 1px 6px;
  border-radius: 3px;
  background: var(--color-warning-bg);
  color: var(--color-warning);
  font-size: 0.65rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.tab-bar {
  display: flex;
  gap: 0.25rem;
}

.tab-btn {
  min-height: 2.25rem;
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

.page-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 1rem;
  padding: 2rem;
  text-align: center;
}

.page-state h2 {
  margin: 0;
  font-size: 1.1rem;
}

.state-text {
  max-width: 32rem;
  margin: 0;
  color: var(--color-muted);
}

.state-error,
.page-error {
  margin: 0;
  color: var(--color-danger);
}

.page-error {
  padding: 0.5rem 1rem;
  font-size: 0.85rem;
  border-bottom: 1px solid var(--color-border);
}

.tab-panel {
  flex: 1;
  min-height: 0;
}

.preview-area {
  position: relative;
  overflow: hidden;
  display: flex;
}

.preview-scroll {
  flex: 1;
  overflow: auto;
  /* Room for the drawer toggle sitting in the top-left corner */
  padding: 3.75rem 1rem 1rem;
}

.preview-wrap {
  position: relative;
  display: inline-block;
}

.preview-img {
  display: block;
  max-width: 100%;
  max-height: calc(100dvh - 60px - 7rem);
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

.editor-panel {
  /* The editor caps its score at --score-max-height; leave room for its toolbars */
  --score-max-height: calc(100dvh - 60px - 15rem);
  overflow: auto;
  padding: 0.75rem 1rem 1rem;
}

.editor-note {
  margin: 0.5rem 0 0;
  font-size: 0.8rem;
  color: var(--color-muted);
}

.code-panel {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 0.75rem 1rem 1rem;
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

.ly-code {
  flex: 1;
  min-height: 0;
  margin: 0;
  padding: 1rem;
  overflow: auto;
  background: var(--color-canvas-bg);
  color: var(--color-canvas-text);
  border-radius: var(--radius);
  font-family: var(--font-mono);
  font-size: 0.8rem;
  line-height: 1.5;
  white-space: pre;
}

@media (max-width: 768px) {
  .toolbar-actions {
    margin-left: 0;
  }
}
</style>
