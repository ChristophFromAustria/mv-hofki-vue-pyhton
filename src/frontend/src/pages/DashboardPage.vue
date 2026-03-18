<script setup>
import { ref, onMounted } from "vue";
import { get } from "../lib/api.js";
import StatCard from "../components/StatCard.vue";

const stats = ref(null);
const loading = ref(true);

onMounted(async () => {
  try {
    stats.value = await get("/dashboard");
  } catch (e) {
    console.error("Dashboard laden fehlgeschlagen:", e);
  } finally {
    loading.value = false;
  }
});
</script>

<template>
  <div>
    <h1 style="margin-bottom: 1.5rem">Dashboard</h1>

    <div v-if="loading" style="text-align: center; padding: 2rem">Laden...</div>

    <template v-else-if="stats">
      <div class="grid grid-3" style="margin-bottom: 2rem">
        <StatCard title="Instrumente" :value="stats.total_instruments" />
        <StatCard title="Musiker" :value="stats.total_musicians" />
        <StatCard title="Aktive Leihen" :value="stats.active_loans" />
      </div>

      <div v-if="stats.instruments_by_type.length" class="card">
        <h2 style="font-size: 1.1rem; margin-bottom: 1rem">Instrumente nach Typ</h2>
        <table>
          <thead>
            <tr>
              <th>Typ</th>
              <th>Kürzel</th>
              <th style="text-align: right">Anzahl</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="t in stats.instruments_by_type" :key="t.label">
              <td>{{ t.label }}</td>
              <td>{{ t.label_short }}</td>
              <td style="text-align: right">{{ t.count }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </div>
</template>
