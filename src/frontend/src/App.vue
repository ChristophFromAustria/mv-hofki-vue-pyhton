<script setup>
import NavBar from "./components/NavBar.vue";

// eslint-disable-next-line no-undef
const version = __APP_VERSION__;
</script>

<template>
  <NavBar />
  <main class="container">
    <RouterView v-slot="{ Component, route }">
      <Transition name="fade" mode="out-in">
        <component :is="Component" :key="route.path" />
      </Transition>
    </RouterView>
  </main>
  <div class="app-version">v{{ version }}</div>
</template>

<style scoped>
.container {
  max-width: var(--max-width);
  margin: 0 auto;
  padding: 2rem 1rem;
}

@media (max-width: 768px) {
  .container {
    padding: 1rem 0.75rem;
  }
}

.app-version {
  position: fixed;
  bottom: 0.5rem;
  right: 0.75rem;
  font-size: 0.7rem;
  color: var(--color-muted);
  opacity: 0.5;
  pointer-events: none;
}
</style>
