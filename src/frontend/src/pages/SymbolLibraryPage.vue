<script setup>
import { ref, computed, watch, onMounted } from "vue";
import { get } from "../lib/api.js";
import LoadingSpinner from "../components/LoadingSpinner.vue";
import SymbolCard from "../components/SymbolCard.vue";

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
        <SymbolCard v-for="tpl in templates" :key="tpl.id" :template="tpl" />
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
</style>
