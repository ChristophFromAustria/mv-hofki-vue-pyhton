<script setup>
import { ref, computed, onMounted } from "vue";
import { RouterLink, useRouter } from "vue-router";
import { get, post, del } from "../lib/api.js";
import LoadingSpinner from "../components/LoadingSpinner.vue";
import ConfirmDialog from "../components/ConfirmDialog.vue";
import BatchAnalysisModal from "../components/BatchAnalysisModal.vue";

const router = useRouter();
const projects = ref([]);
const loading = ref(true);
const search = ref("");
const sortBy = ref("name");
const showCreate = ref(false);
const newName = ref("");
const newComposer = ref("");
const newCategory = ref("Marschbuch");
const newCatalogNumber = ref(null);
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
    category: newCategory.value.trim() || null,
    catalog_number: newCatalogNumber.value || null,
  });
  showCreate.value = false;
  newName.value = "";
  newComposer.value = "";
  newCategory.value = "Marschbuch";
  newCatalogNumber.value = null;
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

const filteredProjects = computed(() => {
  let list = projects.value;
  if (search.value.trim()) {
    const q = search.value.trim().toLowerCase();
    list = list.filter(
      (p) =>
        p.name.toLowerCase().includes(q) ||
        (p.composer && p.composer.toLowerCase().includes(q)) ||
        (p.category && p.category.toLowerCase().includes(q)) ||
        (p.catalog_number != null && String(p.catalog_number).includes(q)),
    );
  }
  return [...list].sort((a, b) => {
    if (sortBy.value === "catalog_number") {
      const na = a.catalog_number ?? Infinity;
      const nb = b.catalog_number ?? Infinity;
      return na - nb || a.name.localeCompare(b.name, "de");
    }
    return a.name.localeCompare(b.name, "de");
  });
});

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
            <option value="error">Nur Fehler</option>
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

    <template v-else>
      <div class="list-toolbar">
        <input
          v-model="search"
          type="text"
          placeholder="Projekte durchsuchen..."
          class="search-input"
        />
        <select v-model="sortBy" class="sort-select">
          <option value="name">A-Z</option>
          <option value="catalog_number">Nr.</option>
        </select>
      </div>

      <div class="project-list">
        <RouterLink
          v-for="p in filteredProjects"
          :key="p.id"
          :to="{ name: 'scanner-project-detail', params: { id: p.id } }"
          class="project-card"
        >
          <div class="project-info">
            <strong>
              <span v-if="p.catalog_number != null" class="catalog-nr"
                >{{ p.catalog_number }}.</span
              >
              {{ p.name }}
            </strong>
            <span class="project-meta">
              <span v-if="p.composer">{{ p.composer }}</span>
              <span v-if="p.composer && p.category" class="meta-sep">&middot;</span>
              <span v-if="p.category" class="category-tag">{{ p.category }}</span>
            </span>
          </div>
          <div class="project-stats">
            <span class="stat" title="Stimmen">{{ p.part_count }} Stimmen</span>
            <span class="stat" title="Notenblätter">{{ p.scan_count }} Scans</span>
            <span v-if="p.status_review" class="badge badge-green" title="Bereit zur Überprüfung">
              {{ p.status_review }} Review
            </span>
            <span v-if="p.status_uploaded" class="badge badge-gray" title="Noch nicht analysiert">
              {{ p.status_uploaded }} Offen
            </span>
            <span v-if="p.status_processing" class="badge badge-blue" title="Wird verarbeitet">
              {{ p.status_processing }} Läuft
            </span>
            <span v-if="p.status_error" class="badge badge-red" title="Fehler bei Analyse">
              {{ p.status_error }} Fehler
            </span>
            <span
              v-if="p.scan_count && !p.status_uploaded && !p.status_processing && !p.status_error"
              class="badge badge-done"
              title="Alle analysiert"
            >
              Fertig
            </span>
          </div>
          <div class="project-actions">
            <button class="btn btn-danger btn-sm" @click.prevent="confirmDelete(p)">Löschen</button>
          </div>
        </RouterLink>
        <p v-if="filteredProjects.length === 0" class="no-results">Keine Projekte gefunden.</p>
      </div>
    </template>

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
        <label>
          Kategorie
          <input v-model="newCategory" type="text" placeholder="z.B. Marschbuch" />
        </label>
        <label>
          Nr. im Inhaltsverzeichnis (optional)
          <input v-model.number="newCatalogNumber" type="number" min="1" placeholder="z.B. 14" />
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

.list-toolbar {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 1rem;
}

.search-input {
  flex: 1;
  padding: 0.5rem 0.75rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  background: var(--color-bg);
  color: var(--color-text);
  font-family: inherit;
  font-size: 0.9rem;
}

.search-input::placeholder {
  color: var(--color-muted);
}

.sort-select {
  padding: 0.5rem 0.75rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  background: var(--color-bg);
  color: var(--color-text);
  font-family: inherit;
  font-size: 0.85rem;
  min-width: 70px;
}

.project-card {
  display: grid;
  grid-template-columns: 1fr auto auto;
  align-items: center;
  gap: 1rem;
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
  min-width: 0;
}

.catalog-nr {
  color: var(--color-muted);
  font-weight: 400;
  margin-right: 0.15rem;
}

.project-meta {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  color: var(--color-muted);
  font-size: 0.85rem;
}

.meta-sep {
  color: var(--color-border);
}

.category-tag {
  font-size: 0.75rem;
  padding: 0.1rem 0.4rem;
  border-radius: var(--radius);
  background: var(--color-bg-soft);
  color: var(--color-muted);
}

.project-stats {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.project-actions {
  display: flex;
  justify-content: flex-end;
}

.no-results {
  text-align: center;
  color: var(--color-muted);
  padding: 1.5rem;
}

.stat {
  font-size: 0.8rem;
  color: var(--color-muted);
  white-space: nowrap;
}

.badge {
  display: inline-block;
  font-size: 0.7rem;
  font-weight: 600;
  padding: 0.15rem 0.5rem;
  border-radius: var(--radius);
  white-space: nowrap;
}

.badge-green {
  color: #16a34a;
  background: rgba(22, 163, 74, 0.1);
}

.badge-gray {
  color: var(--color-muted);
  background: var(--color-bg-soft);
}

.badge-blue {
  color: var(--color-primary);
  background: var(--color-primary-light);
}

.badge-red {
  color: var(--color-danger);
  background: rgba(220, 38, 38, 0.1);
}

.badge-done {
  color: #16a34a;
  background: rgba(22, 163, 74, 0.1);
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
