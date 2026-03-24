<script setup>
import { ref, onMounted, onUnmounted } from "vue";
import { RouterLink } from "vue-router";
import { get, post, put } from "../lib/api.js";
import LoadingSpinner from "../components/LoadingSpinner.vue";
import ImageAdjustBar from "../components/ImageAdjustBar.vue";
import ScanCanvas from "../components/ScanCanvas.vue";
import SymbolPanel from "../components/SymbolPanel.vue";

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

const adjustments = ref({ brightness: 0, contrast: 1.0, rotation: 0 });
const selectedSymbol = ref(null);
const showCorrectPicker = ref(false);
const libraryTemplates = ref([]);

let pollTimer = null;

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
    await post(`/scanner/scans/${props.scanId}/process`, {});
    // Poll for completion
    pollTimer = setInterval(async () => {
      try {
        const status = await get(`/scanner/scans/${props.scanId}/status`);
        if (status.status !== "processing") {
          clearInterval(pollTimer);
          pollTimer = null;
          processing.value = false;
          await fetchScanData();
        } else {
          statusMessage.value = "Verarbeitung läuft...";
        }
      } catch {
        clearInterval(pollTimer);
        pollTimer = null;
        processing.value = false;
      }
    }, 2000);
  } catch (e) {
    processing.value = false;
    statusMessage.value = `Fehler: ${e.message}`;
  }
}

function onAdjust(adj) {
  adjustments.value = adj;
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
      const data = await get("/scanner/library/templates?limit=50");
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

async function fetchLibraryIfNeeded() {
  if (libraryTemplates.value.length === 0) {
    const data = await get("/scanner/library/templates?limit=50");
    libraryTemplates.value = data.items || [];
  }
}

onMounted(() => {
  fetchScanData();
  fetchLibraryIfNeeded();
});

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer);
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
          <ScanCanvas
            :image-path="scan?.image_path ?? null"
            :staves="staves"
            :symbols="symbols"
            :adjustments="adjustments"
            :selected-symbol-id="selectedSymbol?.id ?? null"
            @select-symbol="onSelectSymbol"
          />
        </div>

        <!-- Right panel -->
        <div class="panel-area">
          <SymbolPanel
            :symbol="selectedSymbol"
            :templates="libraryTemplates"
            @verify="onVerify"
            @correct="onCorrect"
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
  </div>
</template>

<style scoped>
.editor-layout {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 60px);
  overflow: hidden;
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
</style>
