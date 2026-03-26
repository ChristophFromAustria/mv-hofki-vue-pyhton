<script setup>
import { ref, computed, onMounted, onUnmounted } from "vue";
import { RouterLink } from "vue-router";
import { get, post, put } from "../lib/api.js";
import LoadingSpinner from "../components/LoadingSpinner.vue";
import ImageAdjustBar from "../components/ImageAdjustBar.vue";
import ScanCanvas from "../components/ScanCanvas.vue";
import SymbolPanel from "../components/SymbolPanel.vue";
import ScannerConfigModal from "../components/ScannerConfigModal.vue";
import AnalysisLogModal from "../components/AnalysisLogModal.vue";

const props = defineProps({
  projectId: { type: String, required: true },
  scanId: { type: String, required: true },
});

const scan = ref(null);
const staves = ref([]);
const symbols = ref([]);
const loading = ref(true);
const error = ref(null);
const processing = ref(false);
const statusMessage = ref("");

const adjustments = ref({ brightness: 0, contrast: 1.0, rotation: 0, threshold: 128 });
const showStaves = ref(true);
const showSymbols = ref(true);
const selectedSymbol = ref(null);
const showCorrectPicker = ref(false);
const libraryTemplates = ref([]);

const showConfig = ref(false);
const sessionConfig = ref(null);
const imageInfo = ref(null); // { width, height, type }
const showAnalysisLog = ref(false);
const analysisLogRef = ref(null);

const captureMode = ref(false);
const captureBox = ref(null);
const showCaptureDialog = ref(false);
const heightEditable = ref(false);
const captureForm = ref({
  template_id: null,
  name: "",
  category: "note",
  musicxml_element: "",
  height_in_lines: 4.0,
});

async function fetchScanData() {
  loading.value = true;
  error.value = null;
  try {
    const [, stavesData, symbolsData] = await Promise.all([
      get(`/scanner/scans/${props.scanId}/status`).catch(() => null),
      get(`/scanner/scans/${props.scanId}/staves`),
      get(`/scanner/scans/${props.scanId}/symbols`),
    ]);

    // Get actual scan data through project/part lookup
    // We fetch from the project-level parts list to find this scan's image_path
    const partsData = await get(`/scanner/projects/${props.projectId}/parts`);
    let foundScan = null;
    for (const part of partsData) {
      const scansData = await get(`/scanner/projects/${props.projectId}/parts/${part.id}/scans`);
      foundScan = scansData.find((s) => String(s.id) === String(props.scanId));
      if (foundScan) break;
    }
    scan.value = foundScan;
    staves.value = stavesData || [];
    symbols.value = symbolsData || [];

    // Resolve image info (dimensions + file type)
    if (foundScan?.image_path) {
      const ext = foundScan.original_filename?.split(".").pop()?.toUpperCase() || "?";
      loadImageDimensions(foundScan.image_path, ext);
    }

    if (foundScan?.adjustments_json) {
      try {
        adjustments.value = JSON.parse(foundScan.adjustments_json);
      } catch {
        // ignore parse errors
      }
    }

    updateStatus();
  } catch (e) {
    error.value = e.message;
  } finally {
    loading.value = false;
  }
}

function loadImageDimensions(imagePath, ext) {
  const BASE = (import.meta.env.VITE_BASE_PATH || "").replace(/\/$/, "");
  const img = new Image();
  img.onload = () => {
    imageInfo.value = { width: img.naturalWidth, height: img.naturalHeight, type: ext };
  };
  img.src = `${BASE}/scans/${imagePath.replace(/^data\/scans\//, "")}`;
}

function updateStatus() {
  if (!scan.value) return;
  const total = symbols.value.length;
  const verified = symbols.value.filter((s) => s.user_verified).length;
  const statusLabels = {
    uploaded: "Hochgeladen – noch nicht analysiert",
    processing: "Wird verarbeitet...",
    review: "Bereit zur Überprüfung",
    completed: "Abgeschlossen",
  };
  const label = statusLabels[scan.value.status] || scan.value.status;
  if (total > 0) {
    statusMessage.value = `${label} · ${verified} / ${total} Symbole verifiziert`;
  } else {
    statusMessage.value = label;
  }
}

async function startAnalysis() {
  if (processing.value) return;
  processing.value = true;
  statusMessage.value = "Analyse wird gestartet...";
  try {
    // Save current adjustments to the scan first
    if (scan.value) {
      const partsData = await get(`/scanner/projects/${props.projectId}/parts`);
      for (const part of partsData) {
        const scansData = await get(`/scanner/projects/${props.projectId}/parts/${part.id}/scans`);
        const found = scansData.find((s) => String(s.id) === String(props.scanId));
        if (found) {
          await put(`/scanner/projects/${props.projectId}/parts/${part.id}/scans/${props.scanId}`, {
            adjustments_json: JSON.stringify(adjustments.value),
          });
          break;
        }
      }
    }
    // Open the log modal and start SSE stream
    showAnalysisLog.value = true;
    // Wait for the component to mount before calling startStream
    await new Promise((r) => setTimeout(r, 50));
    if (analysisLogRef.value) {
      analysisLogRef.value.startStream(props.scanId);
    }
  } catch (e) {
    processing.value = false;
    statusMessage.value = `Fehler: ${e.message}`;
  }
}

async function onAnalysisDone() {
  processing.value = false;
  await fetchScanData();
}

function onAnalysisLogClose() {
  showAnalysisLog.value = false;
  if (!processing.value) return;
  // If still running when user closes modal, just let it finish in background
  processing.value = false;
  statusMessage.value = "Analyse läuft im Hintergrund...";
}

function onAdjust(adj) {
  adjustments.value = adj;
}

function onCaptureBox(box) {
  captureBox.value = box;
  heightEditable.value = false;
  // Pre-fill height_in_lines from auto-calculation if available
  if (box.heightInLines != null) {
    captureForm.value.height_in_lines = box.heightInLines;
  } else {
    captureForm.value.height_in_lines = 4.0;
  }
  captureForm.value.template_id = null;
  captureForm.value.name = "";
  captureForm.value.category = "note";
  captureForm.value.musicxml_element = "";
  showCaptureDialog.value = true;
}

function onTemplateSelect() {
  if (captureForm.value.template_id !== null) {
    const tpl = libraryTemplates.value.find((t) => t.id === captureForm.value.template_id);
    if (tpl) {
      captureForm.value.category = tpl.category;
      captureForm.value.musicxml_element = tpl.musicxml_element || "";
    }
  }
}

async function saveCapturedTemplate() {
  if (!captureBox.value) return;
  const isNew = captureForm.value.template_id === null;
  if (isNew && !captureForm.value.name.trim()) return;

  const payload = {
    scan_id: parseInt(props.scanId),
    ...captureBox.value,
    category: captureForm.value.category,
    musicxml_element: captureForm.value.musicxml_element || null,
    height_in_lines: captureForm.value.height_in_lines,
  };

  if (isNew) {
    payload.name = captureForm.value.name.trim();
  } else {
    payload.template_id = captureForm.value.template_id;
  }

  await post("/scanner/library/templates/capture", payload);
  showCaptureDialog.value = false;
  captureMode.value = false;
  captureForm.value = {
    template_id: null,
    name: "",
    category: "note",
    musicxml_element: "",
    height_in_lines: 4.0,
  };
  const data = await get("/scanner/library/templates?limit=200");
  libraryTemplates.value = data.items || [];
}

function onSelectSymbol(symbol) {
  selectedSymbol.value = symbol;
}

async function onVerify(symbol) {
  await put(`/scanner/symbols/${symbol.id}/verify`, {});
  const idx = symbols.value.findIndex((s) => s.id === symbol.id);
  if (idx !== -1) {
    symbols.value[idx] = { ...symbols.value[idx], user_verified: true };
  }
  if (selectedSymbol.value?.id === symbol.id) {
    selectedSymbol.value = { ...selectedSymbol.value, user_verified: true };
  }
  updateStatus();
}

async function onCorrect(symbol, template = null) {
  if (!template) {
    // Fetch library for picker
    if (libraryTemplates.value.length === 0) {
      const data = await get("/scanner/library/templates?limit=200");
      libraryTemplates.value = data.items || [];
    }
    showCorrectPicker.value = true;
    return;
  }
  await put(`/scanner/symbols/${symbol.id}/correct`, {
    symbol_template_id: template.id,
  });
  const idx = symbols.value.findIndex((s) => s.id === symbol.id);
  if (idx !== -1) {
    symbols.value[idx] = {
      ...symbols.value[idx],
      user_verified: true,
      corrected_symbol: template,
    };
  }
  if (selectedSymbol.value?.id === symbol.id) {
    selectedSymbol.value = {
      ...selectedSymbol.value,
      user_verified: true,
      corrected_symbol: template,
    };
  }
  showCorrectPicker.value = false;
  updateStatus();
}

async function onCorrectToAlternative(symbol, alt) {
  // Correct symbol to the alternative template
  await put(`/scanner/symbols/${symbol.id}/correct`, {
    symbol_template_id: alt.template_id,
  });
  const idx = symbols.value.findIndex((s) => s.id === symbol.id);
  const corrected = { id: alt.template_id, display_name: alt.display_name };
  if (idx !== -1) {
    symbols.value[idx] = {
      ...symbols.value[idx],
      user_verified: true,
      corrected_symbol: corrected,
    };
  }
  if (selectedSymbol.value?.id === symbol.id) {
    selectedSymbol.value = {
      ...selectedSymbol.value,
      user_verified: true,
      corrected_symbol: corrected,
    };
  }
  updateStatus();
}

function onApplySessionConfig(cfg) {
  sessionConfig.value = cfg;
}

async function fetchLibraryIfNeeded() {
  if (libraryTemplates.value.length === 0) {
    const data = await get("/scanner/library/templates?limit=200");
    libraryTemplates.value = data.items || [];
  }
}

const groupedTemplates = computed(() => {
  const groups = {};
  const categoryLabels = {
    note: "Noten",
    rest: "Pausen",
    accidental: "Vorzeichen",
    clef: "Schlüssel",
    time_sig: "Taktarten",
    time_signature: "Taktarten",
    barline: "Taktstriche",
    dynamic: "Dynamik",
    ornament: "Verzierungen",
    other: "Sonstige",
  };
  for (const tpl of libraryTemplates.value) {
    const label = categoryLabels[tpl.category] || tpl.category;
    if (!groups[label]) groups[label] = [];
    groups[label].push(tpl);
  }
  return groups;
});

onMounted(() => {
  fetchScanData();
  fetchLibraryIfNeeded();
});

onUnmounted(() => {
  // AnalysisLogModal handles its own EventSource cleanup
});
</script>

<template>
  <div class="editor-layout">
    <!-- Top toolbar -->
    <ImageAdjustBar @adjust="onAdjust" @analyze="startAnalysis" />

    <!-- Main area -->
    <div class="editor-main">
      <div v-if="loading" class="editor-loading">
        <LoadingSpinner />
      </div>

      <div v-else-if="error" class="editor-error">
        <p>Fehler: {{ error }}</p>
        <button class="btn" @click="fetchScanData">Erneut laden</button>
      </div>

      <template v-else>
        <!-- Canvas area -->
        <div class="canvas-area">
          <div class="toolbar-extras">
            <button
              class="btn btn-sm"
              :class="{ 'btn-active': showStaves }"
              :title="showStaves ? 'Notenlinien ausblenden' : 'Notenlinien einblenden'"
              @click="showStaves = !showStaves"
            >
              {{ showStaves ? "Linien ausblenden" : "Linien einblenden" }}
            </button>
            <button
              class="btn btn-sm"
              :class="{ 'btn-active': showSymbols }"
              :title="showSymbols ? 'Symbole ausblenden' : 'Symbole einblenden'"
              @click="showSymbols = !showSymbols"
            >
              {{ showSymbols ? "Symbole ausblenden" : "Symbole einblenden" }}
            </button>
            <span v-if="staves.length" class="stave-count"
              >{{ staves.length }} Systeme erkannt</span
            >
            <button
              class="btn btn-sm"
              :class="{ 'btn-active': captureMode }"
              @click="captureMode = !captureMode"
            >
              {{ captureMode ? "Erfassung beenden" : "Vorlage erfassen" }}
            </button>
            <button
              class="btn btn-sm"
              :class="{ 'btn-active': sessionConfig !== null }"
              :title="
                sessionConfig ? 'Konfiguration (Sitzungsparameter aktiv)' : 'Scanner-Konfiguration'
              "
              @click="showConfig = true"
            >
              {{ sessionConfig ? "Konfig. *" : "Konfig." }}
            </button>
          </div>
          <ScanCanvas
            :image-path="scan?.image_path ?? null"
            :staves="staves"
            :symbols="symbols"
            :adjustments="adjustments"
            :selected-symbol-id="selectedSymbol?.id ?? null"
            :show-staves="showStaves"
            :show-symbols="showSymbols"
            :capture-mode="captureMode"
            @select-symbol="onSelectSymbol"
            @capture-box="onCaptureBox"
          />
        </div>

        <!-- Right panel -->
        <div class="panel-area">
          <SymbolPanel
            :symbol="selectedSymbol"
            :templates="libraryTemplates"
            @verify="onVerify"
            @correct="onCorrect"
            @correct-to-alternative="onCorrectToAlternative"
          />
        </div>
      </template>
    </div>

    <!-- Status bar -->
    <div class="status-bar">
      <RouterLink
        :to="{ name: 'scanner-project-detail', params: { id: projectId } }"
        class="status-back"
      >
        ← Zurück
      </RouterLink>
      <span v-if="imageInfo" class="status-meta">
        {{ imageInfo.width }}×{{ imageInfo.height }} px · {{ imageInfo.type }}
      </span>
      <span v-if="imageInfo" class="status-divider">|</span>
      <span class="status-text">
        <span v-if="processing" class="processing-indicator">⟳ </span>
        {{ statusMessage }}
      </span>
      <div class="status-actions">
        <span
          v-if="sessionConfig"
          class="session-badge"
          title="Klicken zum Zurücksetzen"
          @click="sessionConfig = null"
        >
          Sitzungsparameter aktiv ✕
        </span>
        <button
          v-if="scan?.status === 'review' || scan?.status === 'completed'"
          class="btn btn-primary btn-sm"
          @click="() => alert('MusicXML-Export noch nicht implementiert')"
        >
          Exportieren
        </button>
      </div>
    </div>

    <!-- Correct picker modal -->
    <div v-if="showCorrectPicker" class="modal-backdrop" @click.self="showCorrectPicker = false">
      <div class="modal modal-large">
        <h2>Symbol korrigieren</h2>
        <div class="template-grid">
          <button
            v-for="tpl in libraryTemplates"
            :key="tpl.id"
            class="tpl-btn"
            @click="onCorrect(selectedSymbol, tpl)"
          >
            <span class="tpl-name">{{ tpl.display_name }}</span>
            <span class="tpl-cat">{{ tpl.category }}</span>
          </button>
        </div>
        <div style="margin-top: 1rem; text-align: right">
          <button class="btn" @click="showCorrectPicker = false">Abbrechen</button>
        </div>
      </div>
    </div>
    <!-- Scanner config modal -->
    <ScannerConfigModal
      :open="showConfig"
      @close="showConfig = false"
      @apply-session="onApplySessionConfig"
    />

    <!-- Analysis log modal -->
    <AnalysisLogModal
      ref="analysisLogRef"
      :open="showAnalysisLog"
      @close="onAnalysisLogClose"
      @done="onAnalysisDone"
    />

    <!-- Capture dialog -->
    <div v-if="showCaptureDialog" class="modal-backdrop" @click.self="showCaptureDialog = false">
      <div class="modal">
        <h2>Vorlage erfassen</h2>
        <p class="capture-info">Ausschnitt: {{ captureBox?.width }}×{{ captureBox?.height }} px</p>
        <label>
          Vorlage zuordnen
          <select v-model="captureForm.template_id" @change="onTemplateSelect">
            <option :value="null">-- Neue Vorlage erstellen --</option>
            <optgroup v-for="(tpls, group) in groupedTemplates" :key="group" :label="group">
              <option v-for="tpl in tpls" :key="tpl.id" :value="tpl.id">
                {{ tpl.display_name }}
              </option>
            </optgroup>
          </select>
        </label>
        <label v-if="captureForm.template_id === null">
          Name der neuen Vorlage
          <input v-model="captureForm.name" type="text" placeholder="z.B. Viertelnote" />
        </label>
        <label>
          Kategorie
          <select v-model="captureForm.category" :disabled="captureForm.template_id !== null">
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
        <label>
          Höhe in Notenlinien
          <div class="height-input-row">
            <input
              v-model.number="captureForm.height_in_lines"
              type="number"
              min="0.1"
              max="10"
              step="0.1"
              :readonly="!heightEditable"
              :class="{ 'input-readonly': !heightEditable }"
            />
            <button
              class="btn btn-sm"
              :class="{ 'btn-active': heightEditable }"
              type="button"
              :title="heightEditable ? 'Berechnet verwenden' : 'Manuell bearbeiten'"
              @click="heightEditable = !heightEditable"
            >
              {{ heightEditable ? "Auto" : "Bearbeiten" }}
            </button>
          </div>
        </label>
        <label>
          MusicXML (optional)
          <textarea
            v-model="captureForm.musicxml_element"
            rows="3"
            placeholder="<note>...</note>"
          />
        </label>
        <div class="modal-actions">
          <button class="btn" @click="showCaptureDialog = false">Abbrechen</button>
          <button
            class="btn btn-primary"
            :disabled="captureForm.template_id === null && !captureForm.name.trim()"
            @click="saveCapturedTemplate"
          >
            Speichern
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.editor-layout {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 60px);
  overflow: hidden;
  /* Break out of App.vue .container max-width and padding */
  width: 100vw;
  margin-left: calc(-50vw + 50%);
  padding: 0;
}

.editor-main {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.editor-loading,
.editor-error {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 1rem;
}

.canvas-area {
  flex: 3;
  overflow: hidden;
  position: relative;
  display: flex;
  flex-direction: column;
}

.panel-area {
  flex: 1;
  min-width: 220px;
  max-width: 300px;
  overflow-y: auto;
}

.status-bar {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 0.5rem 1rem;
  border-top: 1px solid var(--color-border);
  background: var(--color-bg-soft);
  font-size: 0.875rem;
}

.status-back {
  color: var(--color-primary);
  white-space: nowrap;
}

.status-back:hover {
  text-decoration: underline;
}

.status-meta {
  font-size: 0.8rem;
  color: var(--color-muted);
  font-family: var(--font-mono);
  white-space: nowrap;
}

.status-divider {
  color: var(--color-border);
}

.status-text {
  flex: 1;
  color: var(--color-muted);
}

.processing-indicator {
  display: inline-block;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.status-actions {
  display: flex;
  gap: 0.5rem;
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

.template-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.tpl-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 0.5rem 0.75rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  background: var(--color-bg-soft);
  cursor: pointer;
  transition: background var(--transition);
  min-width: 90px;
}

.tpl-btn:hover {
  background: var(--color-primary-light);
  border-color: var(--color-primary);
}

.tpl-name {
  font-size: 0.85rem;
  font-weight: 500;
}

.tpl-cat {
  font-size: 0.7rem;
  color: var(--color-muted);
  margin-top: 0.2rem;
}

.toolbar-extras {
  display: flex;
  gap: 0.5rem;
  padding: 0.4rem 0.75rem;
  background: var(--color-bg-soft);
  border-bottom: 1px solid var(--color-border);
}

.btn-active {
  background: var(--color-primary);
  color: #fff;
  border-color: var(--color-primary);
}

.stave-count {
  font-size: 0.85rem;
  color: var(--color-muted);
  white-space: nowrap;
}

.capture-info {
  color: var(--color-muted);
  font-size: 0.85rem;
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

.height-input-row {
  display: flex;
  gap: 0.5rem;
  align-items: center;
  margin-top: 0.25rem;
}

.height-input-row input {
  flex: 1;
  margin-top: 0;
}

.input-readonly {
  background: var(--color-bg-soft) !important;
  color: var(--color-muted) !important;
}

.modal-actions {
  display: flex;
  gap: 0.5rem;
  justify-content: flex-end;
  margin-top: 1rem;
}

.session-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.2rem 0.6rem;
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--color-primary);
  background: var(--color-primary-light);
  border: 1px solid var(--color-primary);
  border-radius: var(--radius);
  cursor: pointer;
  white-space: nowrap;
}

.session-badge:hover {
  background: var(--color-primary);
  color: #fff;
}
</style>
