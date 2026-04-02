<script setup>
import { ref, computed, onMounted, onUnmounted } from "vue";
import { RouterLink } from "vue-router";
import { get, put, post } from "../lib/api.js";
import LoadingSpinner from "../components/LoadingSpinner.vue";
import ImageAdjustBar from "../components/ImageAdjustBar.vue";
import ScanCanvas from "../components/ScanCanvas.vue";
import SymbolPanel from "../components/SymbolPanel.vue";
import FilterDropdown from "../components/FilterDropdown.vue";
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

const adjustments = ref({
  preprocessing: {
    brightness: 0,
    contrast: 1.0,
    rotation: 0,
    threshold: 128,
    morphology_kernel_size: 2,
  },
});
const initialPreprocessing = computed(() => adjustments.value.preprocessing ?? null);
const measures = ref([]);
const showMeasures = ref(true);
const showStaves = ref(true);
const hideFiltered = ref(true);
const hiddenCategories = ref(new Set());
const selectedSymbol = ref(null);
const showCorrectPicker = ref(false);
const libraryTemplates = ref([]);

const showConfig = ref(false);
const imageInfo = ref(null); // { width, height, type }
const showAnalysisLog = ref(false);
const viewMode = ref("original");
const analysisLogRef = ref(null);

const captureMode = ref(false);
const scanCanvasRef = ref(null);
const panelCollapsed = ref(false);

const avgLineThickness = computed(() => {
  const thicknesses = staves.value.map((s) => s.line_thickness).filter((t) => t != null);
  if (!thicknesses.length) return null;
  return Math.round(thicknesses.reduce((a, b) => a + b, 0) / thicknesses.length);
});
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
    const [, stavesData, symbolsData, measuresData] = await Promise.all([
      get(`/scanner/scans/${props.scanId}/status`).catch(() => null),
      get(`/scanner/scans/${props.scanId}/staves`),
      get(`/scanner/scans/${props.scanId}/symbols`),
      get(`/scanner/scans/${props.scanId}/measures`).catch(() => []),
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
    measures.value = measuresData || [];

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

    // Default to binary view if analysis results exist
    if (foundScan?.processed_image_path) {
      viewMode.value = "binary";
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
    error: "Fehler bei der Analyse",
  };
  const label = statusLabels[scan.value.status] || scan.value.status;
  if (total > 0) {
    const visible = filteredSymbols.value.length;
    const visibleInfo = visible < total ? ` · ${visible} / ${total} sichtbar` : "";
    statusMessage.value = `${label} · ${verified} / ${total} verifiziert${visibleInfo}`;
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
  // Reload results without setting loading=true (which would unmount the canvas and reset zoom)
  try {
    const [, stavesData, symbolsData, measuresData] = await Promise.all([
      get(`/scanner/scans/${props.scanId}/status`).catch(() => null),
      get(`/scanner/scans/${props.scanId}/staves`),
      get(`/scanner/scans/${props.scanId}/symbols`),
      get(`/scanner/scans/${props.scanId}/measures`).catch(() => []),
    ]);
    const partsData = await get(`/scanner/projects/${props.projectId}/parts`);
    for (const part of partsData) {
      const scansData = await get(`/scanner/projects/${props.projectId}/parts/${part.id}/scans`);
      const foundScan = scansData.find((s) => String(s.id) === String(props.scanId));
      if (foundScan) {
        // Cache-bust the processed image so the browser loads the fresh version
        if (foundScan.processed_image_path) {
          foundScan.processed_image_path += "?t=" + Date.now();
        }
        scan.value = foundScan;
        break;
      }
    }
    staves.value = stavesData || [];
    symbols.value = symbolsData || [];
    measures.value = measuresData || [];
    updateStatus();
  } catch {
    // Fall back to full reload on error
    await fetchScanData();
  }
  if (scan.value?.processed_image_path) {
    viewMode.value = "binary";
  }
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

async function startPreview() {
  if (processing.value) return;
  try {
    const result = await post(`/scanner/scans/${props.scanId}/preview`, {
      adjustments_json: JSON.stringify(adjustments.value),
    });
    if (result.processed_image_path && scan.value) {
      // Append cache-buster so the browser fetches the freshly generated image
      scan.value.processed_image_path = result.processed_image_path + "?t=" + Date.now();
    }
    viewMode.value = "binary";
    showStaves.value = false;
  } catch (e) {
    statusMessage.value = `Vorschau-Fehler: ${e.message}`;
  }
}

const currentZoom = computed(() => scanCanvasRef.value?.zoom ?? 1.0);

function onZoomIn() {
  scanCanvasRef.value?.zoomIn();
}

function onZoomOut() {
  scanCanvasRef.value?.zoomOut();
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
  if (!captureBox.value || !scanCanvasRef.value) return;
  const isNew = captureForm.value.template_id === null;
  if (isNew && !captureForm.value.name.trim()) return;

  const box = captureBox.value;

  // Determine source_line_spacing from staves data
  const captureCenter = box.y + box.height / 2;
  let sourceLineSpacing = 0;
  for (const staff of staves.value) {
    if (staff.y_top <= captureCenter && captureCenter <= staff.y_bottom) {
      sourceLineSpacing = staff.line_spacing;
      break;
    }
  }
  if (sourceLineSpacing <= 0 && staves.value.length > 0) {
    sourceLineSpacing = staves.value[0].line_spacing;
  }
  if (sourceLineSpacing <= 5) {
    alert("Linienabstand konnte nicht ermittelt werden oder ist zu niedrig.");
    return;
  }

  // Crop from the already-rendered canvas (threshold already applied)
  let blob;
  try {
    blob = await scanCanvasRef.value.cropRegion(box);
  } catch (e) {
    alert(`Ausschnitt fehlgeschlagen: ${e.message}`);
    return;
  }

  // Build FormData and upload
  const BASE = (import.meta.env.VITE_BASE_PATH || "").replace(/\/$/, "");
  const formData = new FormData();
  formData.append("file", blob, "captured.png");
  formData.append("source_line_spacing", String(sourceLineSpacing));
  formData.append("source", "user_capture");
  formData.append("height_in_lines", String(captureForm.value.height_in_lines));

  let url;
  if (isNew) {
    url = `${BASE}/api/v1/scanner/library/templates/upload-new`;
    formData.append("name", captureForm.value.name.trim());
    formData.append("category", captureForm.value.category);
    if (captureForm.value.musicxml_element) {
      formData.append("musicxml_element", captureForm.value.musicxml_element);
    }
  } else {
    url = `${BASE}/api/v1/scanner/library/templates/${captureForm.value.template_id}/variants/upload`;
  }

  const resp = await fetch(url, { method: "POST", body: formData });
  if (!resp.ok) {
    const text = await resp.text();
    alert(`Fehler beim Speichern: ${text}`);
    return;
  }

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

function onUpdateAdjustments(updated) {
  adjustments.value = updated;
}

async function fetchLibraryIfNeeded() {
  if (libraryTemplates.value.length === 0) {
    const data = await get("/scanner/library/templates?limit=200");
    libraryTemplates.value = data.items || [];
  }
}

const filteredSymbols = computed(() => {
  return symbols.value.filter((sym) => {
    if (hideFiltered.value && sym.filtered) return false;
    const cat = sym.matched_symbol?.category ?? sym.corrected_symbol?.category;
    if (cat && hiddenCategories.value.has(cat)) return false;
    return true;
  });
});

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
    <ImageAdjustBar
      :zoom-level="currentZoom"
      :initial-values="initialPreprocessing"
      @adjust="onAdjust"
      @analyze="startAnalysis"
      @preview="startPreview"
      @zoom-in="onZoomIn"
      @zoom-out="onZoomOut"
    />

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
            <RouterLink
              :to="{ name: 'scanner-project-detail', params: { id: projectId } }"
              class="btn btn-sm"
            >
              ← Zurück
            </RouterLink>
            <RouterLink :to="{ name: 'symbol-library' }" class="btn btn-sm">
              Bibliothek
            </RouterLink>
            <span class="toolbar-separator"></span>
            <FilterDropdown
              :show-staves="showStaves"
              :show-measures="showMeasures"
              :hide-filtered="hideFiltered"
              :symbols="symbols"
              :hidden-categories="hiddenCategories"
              @update:show-staves="showStaves = $event"
              @update:show-measures="showMeasures = $event"
              @update:hide-filtered="hideFiltered = $event"
              @update:hidden-categories="hiddenCategories = $event"
            />
            <span v-if="staves.length" class="stave-count"
              >{{ staves.length }} Systeme erkannt</span
            >
            <div class="view-toggle">
              <button
                class="btn btn-sm"
                :class="{ 'btn-active': viewMode === 'original' }"
                @click="viewMode = 'original'"
              >
                Original
              </button>
              <button
                class="btn btn-sm"
                :class="{ 'btn-active': viewMode === 'binary' }"
                :disabled="!scan?.processed_image_path"
                @click="viewMode = 'binary'"
              >
                Binär
              </button>
            </div>
            <button
              class="btn btn-sm"
              :class="{ 'btn-active': captureMode }"
              @click="captureMode = !captureMode"
            >
              {{ captureMode ? "Erfassung beenden" : "Vorlage erfassen" }}
            </button>
            <button
              class="btn btn-sm"
              :class="{ 'btn-active': adjustments.analysis?.enabled }"
              :title="
                adjustments.analysis?.enabled
                  ? 'Konfiguration (Scan-spezifisch aktiv)'
                  : 'Scanner-Konfiguration'
              "
              @click="showConfig = true"
            >
              {{ adjustments.analysis?.enabled ? "Konfig. *" : "Konfig." }}
            </button>
          </div>
          <ScanCanvas
            ref="scanCanvasRef"
            :image-path="scan?.image_path ?? null"
            :processed-image-path="scan?.processed_image_path ?? null"
            :staves="staves"
            :symbols="filteredSymbols"
            :adjustments="adjustments"
            :selected-symbol-id="selectedSymbol?.id ?? null"
            :show-staves="showStaves"
            :show-symbols="true"
            :capture-mode="captureMode"
            :view-mode="viewMode"
            :measures="measures"
            :show-measures="showMeasures"
            @select-symbol="onSelectSymbol"
            @capture-box="onCaptureBox"
          />
        </div>

        <!-- Right panel -->
        <button
          class="panel-toggle"
          :title="panelCollapsed ? 'Panel einblenden' : 'Panel ausblenden'"
          @click="panelCollapsed = !panelCollapsed"
        >
          {{ panelCollapsed ? "◀" : "▶" }}
        </button>
        <div v-if="!panelCollapsed" class="panel-area">
          <div class="scan-info">
            <h3 class="scan-info-title">Scan-Informationen</h3>
            <div class="scan-info-grid">
              <span class="scan-info-label">Auflösung</span>
              <span class="scan-info-value">{{
                imageInfo ? `${imageInfo.width} × ${imageInfo.height}` : "–"
              }}</span>
              <span class="scan-info-label">Linienstärke</span>
              <span class="scan-info-value">{{
                avgLineThickness != null ? `${avgLineThickness} px` : "–"
              }}</span>
              <span class="scan-info-label">Systeme</span>
              <span class="scan-info-value">{{ staves.length }}</span>
              <span class="scan-info-label">Symbole</span>
              <span class="scan-info-value">{{ symbols.length }}</span>
            </div>
          </div>
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
        {{ imageInfo.width }}×{{ imageInfo.height }} px · {{ imageInfo.type
        }}<template v-if="avgLineThickness"> · Liniendicke {{ avgLineThickness }} px</template>
      </span>
      <span v-if="imageInfo" class="status-divider">|</span>
      <span class="status-text">
        <span v-if="processing" class="processing-indicator">⟳ </span>
        {{ statusMessage }}
      </span>
      <div class="status-actions">
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
      :scan-id="props.scanId"
      :project-id="props.projectId"
      :adjustments="adjustments"
      @close="showConfig = false"
      @update-adjustments="onUpdateAdjustments"
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
  align-items: center;
  gap: 0.5rem;
  padding: 0.4rem 0.75rem;
  background: var(--color-bg-soft);
  border-bottom: 1px solid var(--color-border);
}

.toolbar-separator {
  width: 1px;
  height: 1.2rem;
  background: var(--color-border);
}

.panel-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 1.25rem;
  padding: 0;
  border: none;
  border-left: 1px solid var(--color-border);
  background: var(--color-bg-soft);
  color: var(--color-muted);
  cursor: pointer;
  font-size: 0.7rem;
  flex-shrink: 0;
  align-self: stretch;
}

.panel-toggle:hover {
  background: var(--color-bg);
  color: var(--color-text);
}

.scan-info {
  padding: 1rem;
  border-bottom: 1px solid var(--color-border);
}

.scan-info-title {
  font-size: 0.9rem;
  margin-bottom: 0.5rem;
}

.scan-info-grid {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 0.25rem 0.75rem;
  font-size: 0.8rem;
}

.scan-info-label {
  color: var(--color-muted);
}

.scan-info-value {
  font-weight: 500;
  font-family: var(--font-mono);
}

.btn-active {
  background: var(--color-primary);
  color: #fff;
  border-color: var(--color-primary);
}

.view-toggle {
  display: inline-flex;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  overflow: hidden;
  margin-left: 0.5rem;
}

.view-toggle .btn {
  border: none;
  border-radius: 0;
  border-right: 1px solid var(--color-border);
}

.view-toggle .btn:last-child {
  border-right: none;
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
</style>
