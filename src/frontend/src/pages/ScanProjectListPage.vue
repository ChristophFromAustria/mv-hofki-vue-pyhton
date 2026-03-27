<script setup>
import { ref, onMounted } from "vue";
import { RouterLink, useRouter } from "vue-router";
import { get, post, del } from "../lib/api.js";
import LoadingSpinner from "../components/LoadingSpinner.vue";
import ConfirmDialog from "../components/ConfirmDialog.vue";
import BatchAnalysisModal from "../components/BatchAnalysisModal.vue";

const router = useRouter();
const projects = ref([]);
const loading = ref(true);
const showCreate = ref(false);
const newName = ref("");
const newComposer = ref("");
const confirmOpen = ref(false);
const deleteTarget = ref(null);
const showBatch = ref(false);
const batchRef = ref(null);
const batchFilter = ref({ projectId: null, statusFilter: "" });

async function fetchProjects() {
  loading.value = true;
  try {
    const data = await get("/scanner/projects");
    projects.value = data.items;
  } finally {
    loading.value = false;
  }
}

async function createProject() {
  if (!newName.value.trim()) return;
  const project = await post("/scanner/projects", {
    name: newName.value.trim(),
    composer: newComposer.value.trim() || null,
  });
  showCreate.value = false;
  newName.value = "";
  newComposer.value = "";
  router.push({ name: "scanner-project-detail", params: { id: project.id } });
}

function confirmDelete(project) {
  deleteTarget.value = project;
  confirmOpen.value = true;
}

async function deleteProject() {
  if (!deleteTarget.value) return;
  await del(`/scanner/projects/${deleteTarget.value.id}`);
  deleteTarget.value = null;
  confirmOpen.value = false;
  await fetchProjects();
}

async function startBatchAnalysis() {
  showBatch.value = true;
  await new Promise((r) => setTimeout(r, 50));
  if (batchRef.value) {
    batchRef.value.startBatch(
      batchFilter.value.projectId || null,
      batchFilter.value.statusFilter || null,
    );
  }
}

onMounted(fetchProjects);
</script>

<template>
  <div>
    <div class="page-header">
      <h1>Scan-Projekte</h1>
      <div class="header-actions">
        <RouterLink to="/notenscanner/konfiguration" class="btn btn-secondary">
          Konfiguration
        </RouterLink>
        <RouterLink to="/notenscanner/bibliothek" class="btn btn-secondary">
          Vorlagen verwalten
        </RouterLink>
        <button class="btn btn-primary" @click="showCreate = true">+ Neues Projekt</button>
      </div>
    </div>

    <!-- Batch analysis controls -->
    <div v-if="!loading && projects.length > 0" class="batch-section">
      <h2>Massenanalyse</h2>
      <div class="batch-controls">
        <label class="batch-filter">
          Projekt
          <select v-model="batchFilter.projectId">
            <option :value="null">Alle Projekte</option>
            <option v-for="p in projects" :key="p.id" :value="p.id">
              {{ p.name }}
            </option>
          </select>
        </label>
        <label class="batch-filter">
          Status
          <select v-model="batchFilter.statusFilter">
            <option value="">Alle</option>
            <option value="uploaded">Nur hochgeladen</option>
            <option value="review">Nur Review</option>
          </select>
        </label>
        <button class="btn btn-primary" @click="startBatchAnalysis">Analyse starten</button>
      </div>
    </div>

    <LoadingSpinner v-if="loading" />

    <div v-else-if="projects.length === 0" class="empty-state">
      <p>Noch keine Scan-Projekte vorhanden.</p>
      <button class="btn btn-primary" @click="showCreate = true">Erstes Projekt erstellen</button>
    </div>

    <div v-else class="project-list">
      <RouterLink
        v-for="p in projects"
        :key="p.id"
        :to="{ name: 'scanner-project-detail', params: { id: p.id } }"
        class="project-card"
      >
        <div class="project-info">
          <strong>{{ p.name }}</strong>
          <span v-if="p.composer" class="composer">{{ p.composer }}</span>
        </div>
        <button class="btn btn-danger btn-sm" @click.prevent="confirmDelete(p)">Löschen</button>
      </RouterLink>
    </div>

    <!-- Create dialog -->
    <div v-if="showCreate" class="modal-backdrop" @click.self="showCreate = false">
      <div class="modal">
        <h2>Neues Scan-Projekt</h2>
        <label>
          Name des Stücks
          <input v-model="newName" type="text" placeholder="z.B. Böhmischer Traum" />
        </label>
        <label>
          Komponist (optional)
          <input v-model="newComposer" type="text" placeholder="z.B. J. Brunner" />
        </label>
        <div class="modal-actions">
          <button class="btn" @click="showCreate = false">Abbrechen</button>
          <button class="btn btn-primary" :disabled="!newName.trim()" @click="createProject">
            Erstellen
          </button>
        </div>
      </div>
    </div>

    <BatchAnalysisModal ref="batchRef" :open="showBatch" @close="showBatch = false" />

    <ConfirmDialog
      :open="confirmOpen"
      title="Projekt löschen"
      :message="`'${deleteTarget?.name}' und alle zugehörigen Scans wirklich löschen?`"
      @confirm="deleteProject"
      @cancel="confirmOpen = false"
    />
  </div>
</template>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
}

.project-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.project-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 1.25rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  transition: background var(--transition);
}

.project-card:hover {
  background: var(--color-bg-soft);
}

.project-info {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.composer {
  color: var(--color-muted);
  font-size: 0.9rem;
}

.empty-state {
  text-align: center;
  padding: 3rem 1rem;
  color: var(--color-muted);
}

.empty-state .btn {
  margin-top: 1rem;
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

.modal h2 {
  margin-bottom: 1rem;
}

.modal label {
  display: block;
  margin-bottom: 1rem;
  font-size: 0.9rem;
  color: var(--color-muted);
}

.modal input {
  display: block;
  width: 100%;
  margin-top: 0.25rem;
  padding: 0.5rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  background: var(--color-bg);
  color: var(--color-text);
}

.modal-actions {
  display: flex;
  gap: 0.5rem;
  justify-content: flex-end;
}

.header-actions {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

.batch-section {
  margin-bottom: 1.5rem;
  padding-bottom: 1.25rem;
  border-bottom: 1px solid var(--color-border);
}

.batch-section h2 {
  font-size: 1rem;
  margin-bottom: 0.75rem;
}

.batch-controls {
  display: flex;
  gap: 1rem;
  align-items: flex-end;
  flex-wrap: wrap;
}

.batch-filter {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  font-size: 0.85rem;
  color: var(--color-muted);
}

.batch-filter select {
  padding: 0.4rem 0.5rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  background: var(--color-bg);
  color: var(--color-text);
  font-family: inherit;
  font-size: 0.85rem;
}
</style>
