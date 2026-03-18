<script setup>
import { RouterLink } from "vue-router";
</script>

<template>
  <nav class="navbar">
    <div class="navbar-inner">
      <RouterLink to="/" class="brand"> mv_hofki </RouterLink>
      <div class="links">
        <RouterLink to="/"> Home </RouterLink>
      </div>
    </div>
  </nav>
</template>

<style scoped>
.navbar {
  border-bottom: 1px solid var(--color-border);
  background: var(--color-bg);
}

.navbar-inner {
  max-width: var(--max-width);
  margin: 0 auto;
  padding: 0.75rem 1rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.brand {
  font-weight: 700;
  font-size: 1.1rem;
  color: var(--color-text);
}

.links {
  display: flex;
  gap: 1.5rem;
}

.links a.router-link-active {
  color: var(--color-primary);
  font-weight: 600;
}
</style>
