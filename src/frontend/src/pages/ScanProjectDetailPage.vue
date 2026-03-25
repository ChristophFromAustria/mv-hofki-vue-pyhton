<script setup>
import { ref, onMounted } from "vue";
import { useRouter, RouterLink } from "vue-router";
import { get, post, del } from "../lib/api.js";
import LoadingSpinner from "../components/LoadingSpinner.vue";
import ConfirmDialog from "../components/ConfirmDialog.vue";

const props = defineProps({
  id: { type: String, required: true },
});

const router = useRouter();

const project = ref(null);
const parts = ref([]);
const loading = ref(true);
const error = ref(null);

// Add part form
const newPartName = ref("");
const newPartClef = ref("");
const addingPart = ref(false);

// Confirm dialogs
const confirmPartOpen = ref(false);
const confirmScanOpen = ref(false);
const deletePartTarget = ref(null);
const deleteScanTarget = ref(null);

// File upload refs keyed by partId
const fileInputs = ref({});

// Drag state per part
const dragOver = ref({});

const BASE = (import.meta.env.VITE_BASE_PATH || "").replace(/\/$/, "");

function scanImageUrl(imagePath) {
  const relative = imagePath.replace(/^data\/scans\//, "");
  return `${BASE}/scans/${relative}`;
}

async function fetchData() {
  loading.value = true;
  error.value = null;
  try {
    const [proj, partsData] = await Promise.all([
      get(`/scanner/projects/${props.id}`),
      get(`/scanner/projects/${props.id}/parts`),
    ]);
    project.value = proj;
    // Fetch scans for each part
    const partsWithScans = await Promise.all(
      partsData.map(async (part) => {
        const scans = await get(`/scanner/projects/${props.id}/parts/${part.id}/scans`);
        return { ...part, scans };
      }),
    );
    parts.value = partsWithScans;
  } catch (e) {
    error.value = e.message;
  } finally {
    loading.value = false;
  }
}

async function addPart() {
  if (!newPartName.value.trim()) return;
  addingPart.value = true;
  try {
    await post(`/scanner/projects/${props.id}/parts`, {
      part_name: newPartName.value.trim(),
      clef_hint: newPartClef.value || null,
    });
    newPartName.value = "";
    newPartClef.value = "";
    await fetchData();
  } finally {
    addingPart.value = false;
  }
}

function confirmDeletePart(part) {
  deletePartTarget.value = part;
  confirmPartOpen.value = true;
}

async function deletePart() {
  if (!deletePartTarget.value) return;
  await del(`/scanner/projects/${props.id}/parts/${deletePartTarget.value.id}`);
  deletePartTarget.value = null;
  confirmPartOpen.value = false;
  await fetchData();
}

function confirmDeleteScan(scan, part) {
  deleteScanTarget.value = { scan, part };
  confirmScanOpen.value = true;
}

async function deleteScan() {
  if (!deleteScanTarget.value) return;
  const { scan, part } = deleteScanTarget.value;
  await del(`/scanner/projects/${props.id}/parts/${part.id}/scans/${scan.id}`);
  deleteScanTarget.value = null;
  confirmScanOpen.value = false;
  await fetchData();
}

async function uploadFile(partId, file) {
  if (!file) return;
  const formData = new FormData();
  formData.append("file", file);
  const BASE_URL = (import.meta.env.VITE_BASE_PATH || "").replace(/\/$/, "");
  const url = `${BASE_URL}/api/v1/scanner/projects/${props.id}/parts/${partId}/scans`;
  const response = await fetch(url, { method: "POST", body: formData });
  if (!response.ok) {
    const text = await response.text();
    alert(`Upload fehlgeschlagen: ${text}`);
    return;
  }
  await fetchData();
}

async function uploadScan(partId, event) {
  const file = event.target.files[0];
  if (!file) return;
  await uploadFile(partId, file);
  event.target.value = "";
}

function onDrop(partId, event) {
  dragOver.value[partId] = false;
  const file = event.dataTransfer.files[0];
  if (file) uploadFile(partId, file);
}

function onDragOver(partId) {
  dragOver.value[partId] = true;
}

function onDragLeave(partId) {
  dragOver.value[partId] = false;
}

function triggerFileInput(partId) {
  fileInputs.value[partId]?.click();
}

function navigateToScan(scan) {
  router.push({
    name: "scan-editor",
    params: { id: props.id, scanId: scan.id },
  });
}

function exportMusicXml() {
  alert("MusicXML-Export ist noch nicht implementiert.");
}

function statusLabel(status) {
  const labels = {
    uploaded: "Hochgeladen",
    processing: "Verarbeitung",
    review: "Überprüfung",
    completed: "Fertig",
  };
  return labels[status] || status;
}

onMounted(fetchData);
</script>

<template>
  <div>
    <div v-if="loading" class="loading-wrap">
      <LoadingSpinner />
    </div>

    <div v-else-if="error" class="error-state">
      <p>Fehler beim Laden: {{ error }}</p>
      <button class="btn" @click="fetchData">Erneut versuchen</button>
    </div>

    <template v-else>
      <!-- Header -->
      <div class="page-header">
        <div class="header-left">
          <RouterLink to="/notenscanner" class="back-link">← Zurück</RouterLink>
          <div>
            <h1>{{ project.name }}</h1>
            <p v-if="project.composer" class="composer">{{ project.composer }}</p>
          </div>
        </div>
        <button class="btn btn-secondary" @click="exportMusicXml">MusicXML exportieren</button>
      </div>

      <!-- Parts list -->
      <div class="parts-list">
        <div v-for="part in parts" :key="part.id" class="part-section">
          <div class="part-header">
            <h2>{{ part.part_name }}</h2>
            <div class="part-actions">
              <button class="btn btn-sm btn-danger" @click="confirmDeletePart(part)">
                Teil löschen
              </button>
            </div>
          </div>

          <!-- Scan thumbnails -->
          <div v-if="part.scans.length > 0" class="scans-grid">
            <div
              v-for="scan in part.scans"
              :key="scan.id"
              class="scan-thumb"
              @click="navigateToScan(scan)"
            >
              <div class="thumb-img-wrap">
                <img
                  :src="scanImageUrl(scan.image_path)"
                  :alt="`Seite ${scan.page_number}`"
                  class="thumb-img"
                />
                <span :class="['status-badge', `status-${scan.status}`]">
                  {{ statusLabel(scan.status) }}
                </span>
              </div>
              <div class="thumb-footer">
                <span class="page-label">Seite {{ scan.page_number }}</span>
                <button class="btn btn-xs btn-danger" @click.stop="confirmDeleteScan(scan, part)">
                  ×
                </button>
              </div>
            </div>
          </div>

          <!-- Drop zone -->
          <div
            :class="['drop-zone', { 'drop-zone-active': dragOver[part.id] }]"
            @dragover.prevent="onDragOver(part.id)"
            @dragleave.prevent="onDragLeave(part.id)"
            @drop.prevent="onDrop(part.id, $event)"
            @click="triggerFileInput(part.id)"
          >
            <input
              :ref="
                (el) => {
                  if (el) fileInputs[part.id] = el;
                }
              "
              type="file"
              accept="image/png,image/jpeg,image/tiff"
              style="display: none"
              @change="uploadScan(part.id, $event)"
            />
            <span class="drop-zone-icon">+</span>
            <span class="drop-zone-text">Scan hierher ziehen oder klicken</span>
          </div>
        </div>
      </div>

      <!-- Add part form -->
      <div class="add-part-form">
        <h3>Neuen Teil hinzufügen</h3>
        <div class="add-part-row">
          <input
            v-model="newPartName"
            type="text"
            placeholder="Stimme / Partie (z.B. Trompete 1)"
            class="part-name-input"
          />
          <select v-model="newPartClef" class="clef-select">
            <option value="">Schlüssel (optional)</option>
            <option value="treble">Violinschlüssel</option>
            <option value="bass">Bassschlüssel</option>
            <option value="alto">Altschlüssel</option>
            <option value="tenor">Tenorschlüssel</option>
          </select>
          <button
            class="btn btn-primary"
            :disabled="!newPartName.trim() || addingPart"
            @click="addPart"
          >
            Hinzufügen
          </button>
        </div>
      </div>
    </template>

    <!-- Delete part dialog -->
    <ConfirmDialog
      :open="confirmPartOpen"
      title="Teil löschen"
      :message="`'${deletePartTarget?.part_name}' und alle Scans dieses Teils wirklich löschen?`"
      @confirm="deletePart"
      @cancel="confirmPartOpen = false"
    />

    <!-- Delete scan dialog -->
    <ConfirmDialog
      :open="confirmScanOpen"
      title="Scan löschen"
      :message="`Seite ${deleteScanTarget?.scan?.page_number} wirklich löschen?`"
      @confirm="deleteScan"
      @cancel="confirmScanOpen = false"
    />
  </div>
</template>

<style scoped>
.loading-wrap {
  padding: 2rem;
}

.error-state {
  text-align: center;
  padding: 3rem 1rem;
  color: var(--color-muted);
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 2rem;
  gap: 1rem;
}

.header-left {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.back-link {
  color: var(--color-primary);
  font-size: 0.9rem;
}

.back-link:hover {
  text-decoration: underline;
}

.composer {
  color: var(--color-muted);
  margin-top: 0.25rem;
}

.parts-list {
  display: flex;
  flex-direction: column;
  gap: 2rem;
}

.part-section {
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  padding: 1.25rem;
}

.part-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.part-header h2 {
  font-size: 1.1rem;
  margin: 0;
}

.part-actions {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

.drop-zone {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  margin-top: 0.75rem;
  padding: 1rem;
  border: 2px dashed var(--color-border);
  border-radius: var(--radius);
  color: var(--color-muted);
  cursor: pointer;
  transition:
    border-color var(--transition),
    background var(--transition);
}

.drop-zone:hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.drop-zone-active {
  border-color: var(--color-primary);
  background: color-mix(in srgb, var(--color-primary) 8%, transparent);
  color: var(--color-primary);
}

.drop-zone-icon {
  font-size: 1.25rem;
  font-weight: 600;
  line-height: 1;
}

.drop-zone-text {
  font-size: 0.85rem;
}

.scans-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
}

.scan-thumb {
  width: 120px;
  cursor: pointer;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  overflow: hidden;
  transition: box-shadow var(--transition);
}

.scan-thumb:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
}

.thumb-img-wrap {
  position: relative;
  height: 90px;
  background: var(--color-bg-soft);
}

.thumb-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.status-badge {
  position: absolute;
  bottom: 4px;
  left: 4px;
  font-size: 0.65rem;
  padding: 2px 5px;
  border-radius: 3px;
  font-weight: 600;
  text-transform: uppercase;
}

.status-uploaded {
  background: #9ca3af;
  color: #fff;
}

.status-processing {
  background: #3b82f6;
  color: #fff;
}

.status-review {
  background: #f97316;
  color: #fff;
}

.status-completed {
  background: #22c55e;
  color: #fff;
}

.thumb-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.25rem 0.4rem;
}

.page-label {
  font-size: 0.75rem;
  color: var(--color-muted);
}

.btn-xs {
  padding: 0.1rem 0.35rem;
  font-size: 0.75rem;
  line-height: 1.4;
}

.add-part-form {
  margin-top: 2rem;
  padding: 1.25rem;
  border: 1px dashed var(--color-border);
  border-radius: var(--radius);
}

.add-part-form h3 {
  margin-bottom: 0.75rem;
  font-size: 1rem;
}

.add-part-row {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.part-name-input {
  flex: 1;
  min-width: 200px;
  padding: 0.5rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  background: var(--color-bg);
  color: var(--color-text);
}

.clef-select {
  padding: 0.5rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  background: var(--color-bg);
  color: var(--color-text);
}
</style>
