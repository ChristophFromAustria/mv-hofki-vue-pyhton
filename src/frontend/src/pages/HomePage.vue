<script setup>
import { ref, onMounted } from "vue";
import { get } from "../lib/api.js";

const health = ref(null);

onMounted(async () => {
  try {
    health.value = await get("/health");
  } catch {
    health.value = { status: "error" };
  }
});
</script>

<template>
  <div class="home">
    <h1>mv_hofki</h1>
    <p>Full-stack project template — FastAPI + Vue 3</p>
    <div v-if="health" class="status">
      API status: <code>{{ health.status }}</code>
    </div>
  </div>
</template>

<style scoped>
.home {
  text-align: center;
  padding-top: 4rem;
}

h1 {
  font-size: 2.5rem;
  margin-bottom: 0.5rem;
}

.status {
  margin-top: 2rem;
  color: var(--color-muted);
}

code {
  font-family: var(--font-mono);
  background: var(--color-border);
  padding: 0.1em 0.4em;
  border-radius: 4px;
}
</style>
