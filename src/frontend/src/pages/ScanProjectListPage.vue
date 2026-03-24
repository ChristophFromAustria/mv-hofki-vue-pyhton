<script setup>
import { ref, onMounted } from "vue";
import { RouterLink, useRouter } from "vue-router";
import { get, post, del } from "../lib/api.js";
import LoadingSpinner from "../components/LoadingSpinner.vue";
import ConfirmDialog from "../components/ConfirmDialog.vue";

const router = useRouter();
const projects = ref([]);
const loading = ref(true);
const showCreate = ref(false);
const newName = ref("");
const newComposer = ref("");
const confirmOpen = ref(false);
const deleteTarget = ref(null);

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

onMounted(fetchProjects);
</script>

<template>
  <div>
    <div class="page-header">
      <h1>Scan-Projekte</h1>
      <button class="btn btn-primary" @click="showCreate = true">+ Neues Projekt</button>
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
</style>
