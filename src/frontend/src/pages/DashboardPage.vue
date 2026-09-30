<script setup>
import { ref, onMounted } from "vue";
import { useRouter } from "vue-router";
import { get } from "../lib/api.js";
import { CATEGORIES } from "../lib/categories.js";
import LoadingSpinner from "../components/LoadingSpinner.vue";
import EventList from "../components/EventList.vue";

const router = useRouter();
const stats = ref(null);
const email = ref(null);
const loading = ref(true);
const error = ref(null);
const latest = ref([]);
const latestError = ref("");

function categoryRoute(category) {
  return CATEGORIES[category]?.routeBase || "/";
}

function goToCategory(category) {
  router.push(categoryRoute(category));
}

async function loadLatest() {
  latestError.value = "";
  try {
    latest.value = (await get("/events?limit=10")).items;
  } catch (e) {
    latestError.value = e.message;
  }
}

async function load() {
  loading.value = true;
  error.value = null;
  loadLatest();
  try {
    const [dashboardData, meData] = await Promise.all([get("/dashboard"), get("/me")]);
    stats.value = dashboardData;
    email.value = meData.email;
  } catch (e) {
    error.value = e.message;
  } finally {
    loading.value = false;
  }
}

onMounted(load);
</script>

<template>
  <div>
    <div class="page-header">
      <div>
        <h1>Dashboard</h1>
        <p v-if="email" class="page-subtitle">Angemeldet als {{ email }}</p>
      </div>
      <router-link to="/notenscanner" class="btn btn-primary">Noten digitalisieren</router-link>
    </div>

    <LoadingSpinner v-if="loading" />

    <div v-else-if="error" class="alert alert-danger" role="alert">
      Übersicht konnte nicht geladen werden: {{ error }}
      <button class="btn btn-sm" style="margin-left: var(--space-3)" @click="load">
        Erneut versuchen
      </button>
    </div>

    <template v-else-if="stats">
      <section class="page-section">
        <dl class="key-figures">
          <div class="key-figure">
            <dt>Gegenstände</dt>
            <dd>{{ stats.total_items }}</dd>
          </div>
          <router-link to="/musiker" class="key-figure">
            <dt>Musiker</dt>
            <dd>{{ stats.total_musicians }}</dd>
          </router-link>
          <router-link to="/leihen" class="key-figure">
            <dt>Aktive Leihen</dt>
            <dd>{{ stats.active_loans }}</dd>
          </router-link>
        </dl>
      </section>

      <section
        v-if="stats.items_by_category && stats.items_by_category.length"
        class="page-section"
      >
        <div class="section-header">
          <h2>Bestand nach Kategorie</h2>
        </div>
        <div class="table-scroll">
          <table class="ledger-table">
            <thead>
              <tr>
                <th>Kategorie</th>
                <th class="num">Anzahl</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="c in stats.items_by_category"
                :key="c.category"
                class="row-link"
                @click="goToCategory(c.category)"
              >
                <td>
                  <router-link :to="categoryRoute(c.category)">{{ c.label }}</router-link>
                </td>
                <td class="num">{{ c.count }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="page-section">
        <div class="section-header">
          <h2>Letzte Änderungen</h2>
          <router-link to="/protokoll" class="btn-sm">Ganzes Protokoll →</router-link>
        </div>
        <p v-if="latestError" class="form-error" role="alert">
          Protokoll konnte nicht geladen werden: {{ latestError }}
        </p>
        <p v-else-if="!latest.length" class="empty-note">Noch keine Änderungen protokolliert.</p>
        <EventList v-else :events="latest" />
      </section>
    </template>
  </div>
</template>

<style scoped>
.row-link {
  cursor: pointer;
  transition: background var(--transition);
}

.row-link:hover {
  background: var(--color-bg-soft);
}
</style>
