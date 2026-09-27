<script setup>
defineProps({
  categories: { type: Array, default: () => [] },
});
</script>

<template>
  <ul v-if="categories.length" class="category-chips">
    <li v-for="c in categories" :key="c.id" class="category-chip">{{ c.label }}</li>
  </ul>
  <span v-else class="text-muted">—</span>
</template>
