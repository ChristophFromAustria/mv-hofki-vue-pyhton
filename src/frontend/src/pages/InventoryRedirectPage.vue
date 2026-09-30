<script setup>
import { onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { get } from "../lib/api.js";
import { CATEGORIES } from "../lib/categories.js";

// /inventar/:id → the item's page in its category (links from the event log,
// later QR labels, only know the item id).
const route = useRoute();
const router = useRouter();
const error = ref("");

onMounted(async () => {
  try {
    const item = await get(`/items/${route.params.id}`);
    const base = CATEGORIES[item.category]?.routeBase || "/instrumente";
    router.replace(`${base}/${item.id}`);
  } catch (e) {
    error.value = e?.message || "Gegenstand nicht gefunden.";
  }
});
</script>

<template>
  <div>
    <p v-if="error" class="alert alert-danger" role="alert">
      Gegenstand konnte nicht geöffnet werden: {{ error }}
    </p>
    <p v-else class="empty-note">Wird geöffnet …</p>
  </div>
</template>
