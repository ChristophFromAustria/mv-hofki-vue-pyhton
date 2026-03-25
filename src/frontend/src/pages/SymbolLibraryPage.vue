<script setup>
import { ref, computed, watch, onMounted } from "vue";
import { get, put, del } from "../lib/api.js";
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

const editingTemplate = ref(null);
const editForm = ref({ display_name: "", musicxml_element: "", lilypond_token: "" });
const variants = ref([]);
const loadingVariants = ref(false);
const confirmDeleteOpen = ref(false);
const confirmVariantDeleteOpen = ref(false);
const deleteVariantTarget = ref(null);

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

async function openEdit(tpl) {
  editingTemplate.value = tpl;
  editForm.value = {
    display_name: tpl.display_name,
    musicxml_element: tpl.musicxml_element || "",
    lilypond_token: tpl.lilypond_token || "",
  };
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

function variantImageUrl(variant) {
  return `${BASE}/${variant.image_path}`;
}

watch([activeCategory, currentPage], fetchTemplates);
onMounted(fetchTemplates);
</script>

<template>
  <div>
    <div class="page-header">
      <h1>Symbol-Bibliothek</h1>
      <span class="total-count">{{ total }} Vorlagen</span>
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

        <!-- Variants -->
        <div class="variants-section">
          <h3>Varianten ({{ variants.length }})</h3>
          <LoadingSpinner v-if="loadingVariants" />
          <div v-else-if="variants.length === 0" class="empty-variants">
            Keine Varianten vorhanden.
          </div>
          <div v-else class="variants-grid">
            <div v-for="v in variants" :key="v.id" class="variant-item">
              <img :src="variantImageUrl(v)" alt="Variante" class="variant-img" />
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
  </div>
</template>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
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
}

.variant-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.2rem 0.4rem;
  font-size: 0.7rem;
}

.variant-source {
  color: var(--color-muted);
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
</style>
