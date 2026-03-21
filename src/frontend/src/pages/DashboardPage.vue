<script setup>
import { ref, onMounted } from "vue";
import { get } from "../lib/api.js";
import { CATEGORIES } from "../lib/categories.js";
import StatCard from "../components/StatCard.vue";

const stats = ref(null);
const email = ref(null);
const loading = ref(true);

function categoryRoute(category) {
  return CATEGORIES[category]?.routeBase || "/";
}

onMounted(async () => {
  try {
    const [dashboardData, meData] = await Promise.all([get("/dashboard"), get("/me")]);
    stats.value = dashboardData;
    email.value = meData.email;
  } catch (e) {
    console.error("Dashboard laden fehlgeschlagen:", e);
  } finally {
    loading.value = false;
  }
});
</script>

<template>
  <div>
    <h1 style="margin-bottom: 1.5rem; text-align: center">
      <template v-if="email">Willkommen {{ email }}!</template>
      <template v-else>Dashboard</template>
    </h1>

    <div v-if="loading" style="text-align: center; padding: 2rem">Laden...</div>

    <template v-else-if="stats">
      <div
        v-if="stats.items_by_category && stats.items_by_category.length"
        class="grid grid-4"
        style="margin-bottom: 2rem"
      >
        <StatCard
          v-for="c in stats.items_by_category"
          :key="c.category"
          :title="c.label"
          :value="c.count"
          :to="categoryRoute(c.category)"
        />
      </div>

      <div class="grid grid-3" style="margin-bottom: 2rem">
        <StatCard title="Gesamt" :value="stats.total_items" />
        <StatCard title="Musiker" :value="stats.total_musicians" to="/musiker" />
        <StatCard title="Aktive Leihen" :value="stats.active_loans" to="/leihen" />
      </div>
    </template>
  </div>
</template>
