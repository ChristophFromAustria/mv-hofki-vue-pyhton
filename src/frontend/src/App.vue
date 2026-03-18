<script setup>
import NavBar from "./components/NavBar.vue";
</script>

<template>
  <NavBar />
  <main class="container">
    <RouterView />
  </main>
</template>

<style scoped>
.container {
  max-width: var(--max-width);
  margin: 0 auto;
  padding: 2rem 1rem;
}
</style>
