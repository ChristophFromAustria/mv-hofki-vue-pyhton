<script setup>
import { ref } from "vue";
import { RouterLink } from "vue-router";

const settingsOpen = ref(false);
</script>

<template>
  <nav class="navbar">
    <div class="navbar-inner">
      <RouterLink to="/" class="brand">MV Hofkirchen</RouterLink>
      <div class="links">
        <RouterLink to="/">Dashboard</RouterLink>
        <RouterLink to="/instrumente">Instrumente</RouterLink>
        <RouterLink to="/musiker">Musiker</RouterLink>
        <RouterLink to="/leihen">Leihregister</RouterLink>
        <div class="dropdown" @mouseenter="settingsOpen = true" @mouseleave="settingsOpen = false">
          <span class="dropdown-trigger">Einstellungen</span>
          <div v-show="settingsOpen" class="dropdown-menu">
            <RouterLink to="/einstellungen/instrumententypen">Instrumententypen</RouterLink>
            <RouterLink to="/einstellungen/waehrungen">Währungen</RouterLink>
          </div>
        </div>
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
  align-items: center;
}

.links a.router-link-active {
  color: var(--color-primary);
  font-weight: 600;
}

.dropdown {
  position: relative;
}

.dropdown-trigger {
  cursor: pointer;
  color: var(--color-primary);
}

.dropdown-menu {
  position: absolute;
  right: 0;
  top: 100%;
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: 6px;
  padding: 0.5rem 0;
  min-width: 180px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  z-index: 50;
}

.dropdown-menu a {
  display: block;
  padding: 0.5rem 1rem;
  color: var(--color-text);
}

.dropdown-menu a:hover {
  background: #f9fafb;
}
</style>
