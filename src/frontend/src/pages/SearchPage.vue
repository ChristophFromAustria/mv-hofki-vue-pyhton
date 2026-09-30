<script setup>
import { computed, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { get } from "../lib/api.js";
import { searchSections, searchTotal } from "../lib/searchResults.js";
import SearchBar from "../components/SearchBar.vue";
import SearchEntry from "../components/SearchEntry.vue";
import LoadingSpinner from "../components/LoadingSpinner.vue";

// All hits of the global search (/suche?q=…); at most PAGE_LIMIT per area,
// the rest via the area's own list filtered by the same text.
const PAGE_LIMIT = 50;

const route = useRoute();
const router = useRouter();
const text = ref(typeof route.query.q === "string" ? route.query.q : "");
const result = ref(null);
const loading = ref(false);
const error = ref("");
let seq = 0;
let timer = null;

const term = computed(() => result.value?.query || "");
const sections = computed(() => searchSections(result.value));
const total = computed(() => searchTotal(result.value));

async function run(value) {
  const my = ++seq;
  const q = value.trim();
  if (!q) {
    result.value = null;
    loading.value = false;
    return;
  }
  loading.value = true;
  error.value = "";
  try {
    const data = await get(`/search?q=${encodeURIComponent(q)}&limit=${PAGE_LIMIT}`);
    if (my === seq) result.value = data;
  } catch (e) {
    if (my === seq) error.value = e?.message || "Suche fehlgeschlagen.";
  } finally {
    if (my === seq) loading.value = false;
  }
}

// The header search navigates here with ?q=; typing here updates the URL.
watch(
  () => route.query.q,
  (q) => {
    const value = typeof q === "string" ? q : "";
    if (value !== text.value) text.value = value;
    run(value);
  },
  { immediate: true },
);

watch(text, (value) => {
  clearTimeout(timer);
  timer = setTimeout(() => {
    if (value.trim() !== (route.query.q || "")) {
      router.replace({ query: value.trim() ? { q: value.trim() } : {} });
    }
  }, 300);
});
</script>

<template>
  <div>
    <div class="page-header">
      <h1>Suche</h1>
    </div>

    <div class="toolbar">
      <SearchBar
        v-model="text"
        placeholder="Inventar, Musiker und Rechnungen durchsuchen …"
        class="grow"
      />
    </div>

    <p v-if="result && !loading" class="list-count" aria-live="polite">
      {{ total }} Treffer für „{{ term }}“
    </p>

    <LoadingSpinner v-if="loading && !result" />
    <div v-else-if="error" class="alert alert-danger" role="alert">
      Suche fehlgeschlagen: {{ error }}
      <button type="button" class="btn-sm" @click="run(text)">Erneut versuchen</button>
    </div>
    <p v-else-if="!text.trim()" class="empty-note">
      Suchbegriff eingeben – z. B. eine Inventarnummer („TR 6“), einen Namen („Müller“) oder mehrere
      Wörter („Trompete Yamaha“).
    </p>
    <p v-else-if="result && !total" class="empty-note">
      {{
        term.length < 2 ? "Bitte mindestens 2 Zeichen eingeben." : `Keine Treffer für „${term}“.`
      }}
    </p>

    <section v-for="section in sections" :key="section.key" class="search-section">
      <h2 class="search-section-title">
        {{ section.label }}
        <span class="search-section-count">{{ section.total }}</span>
      </h2>
      <ul class="search-list">
        <li v-for="entry in section.entries" :key="entry.key">
          <RouterLink :to="entry.to" class="search-row">
            <SearchEntry :entry="entry" :term="term" />
          </RouterLink>
        </li>
      </ul>
      <p v-if="section.total > section.entries.length && section.listTo" class="search-more">
        <RouterLink :to="section.listTo">
          Alle {{ section.total }} in „{{ section.label }}“ anzeigen →
        </RouterLink>
      </p>
    </section>
  </div>
</template>

<style scoped>
.list-count {
  font-variant-numeric: tabular-nums;
  color: var(--color-muted);
  margin: 0 0 var(--space-3);
}

.search-section {
  margin-bottom: var(--space-section);
}

.search-section-title {
  display: flex;
  align-items: baseline;
  gap: var(--space-2);
  margin: 0 0 var(--space-2);
  font-size: 0.8rem;
  font-weight: 600;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: var(--color-muted);
}

.search-section-count {
  font-variant-numeric: tabular-nums;
  font-weight: 500;
}

.search-list {
  margin: 0;
  padding: 0;
  list-style: none;
  border-top: 1px solid var(--color-border);
}

.search-list li {
  border-bottom: 1px solid var(--color-border);
}

.search-row {
  display: block;
  min-height: 44px;
  padding: var(--space-2) var(--space-3);
  color: var(--color-text);
}

.search-row:hover {
  background: var(--color-primary-light);
  color: var(--color-text);
}

.search-row:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: -2px;
}

.search-more {
  margin: var(--space-2) 0 0;
}
</style>
