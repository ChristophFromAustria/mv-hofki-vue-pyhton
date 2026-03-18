<script setup>
import { ref, onMounted } from "vue";
import { RouterLink } from "vue-router";

const settingsOpen = ref(false);
const isDark = ref(false);

function applyTheme(dark) {
  document.documentElement.setAttribute("data-theme", dark ? "dark" : "light");
  localStorage.setItem("theme", dark ? "dark" : "light");
}

function toggleTheme() {
  isDark.value = !isDark.value;
  applyTheme(isDark.value);
}

onMounted(() => {
  const saved = localStorage.getItem("theme");
  if (saved) {
    isDark.value = saved === "dark";
  } else {
    isDark.value = window.matchMedia("(prefers-color-scheme: dark)").matches;
  }
  applyTheme(isDark.value);
});
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
        <button
          class="theme-toggle"
          :title="isDark ? 'Light Mode' : 'Dark Mode'"
          @click="toggleTheme"
        >
          {{ isDark ? "\u2600" : "\u263E" }}
        </button>
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
  background: var(--color-bg-soft);
}

.theme-toggle {
  background: none;
  border: none;
  font-size: 1.2rem;
  cursor: pointer;
  padding: 0.25rem;
  line-height: 1;
  color: var(--color-muted);
}

.theme-toggle:hover {
  color: var(--color-text);
  background: none;
}
</style>
