<script setup>
import { ref, onMounted } from "vue";
import { RouterLink } from "vue-router";

const settingsOpen = ref(false);
const isDark = ref(false);

const menuOpen = ref(false);

function closeMenu() {
  menuOpen.value = false;
  settingsOpen.value = false;
}

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
      <button class="hamburger" :class="{ open: menuOpen }" @click="menuOpen = !menuOpen">
        <span></span><span></span><span></span>
      </button>

      <RouterLink to="/" class="brand" @click="closeMenu">
        <img src="/logo-64.png" alt="MVH" class="brand-logo" />
        MV Hofkirchen
      </RouterLink>

      <button
        class="theme-toggle"
        :title="isDark ? 'Light Mode' : 'Dark Mode'"
        @click="toggleTheme"
      >
        {{ isDark ? "\u2600" : "\u263E" }}
      </button>

      <div class="links" :class="{ open: menuOpen }">
        <RouterLink to="/" @click="closeMenu">Dashboard</RouterLink>
        <RouterLink to="/instrumente" @click="closeMenu">Instrumente</RouterLink>
        <RouterLink to="/kleidung" @click="closeMenu">Kleidung</RouterLink>
        <RouterLink to="/noten" @click="closeMenu">Noten</RouterLink>
        <RouterLink to="/allgemein" @click="closeMenu">Allgemein</RouterLink>
        <RouterLink to="/musiker" @click="closeMenu">Musiker</RouterLink>
        <RouterLink to="/leihen" @click="closeMenu">Leihregister</RouterLink>
        <RouterLink to="/rechnungen" @click="closeMenu">Rechnungen</RouterLink>
        <div class="dropdown" @mouseenter="settingsOpen = true" @mouseleave="settingsOpen = false">
          <span class="dropdown-trigger" @click="settingsOpen = !settingsOpen">Einstellungen</span>
          <div v-show="settingsOpen" class="dropdown-menu">
            <RouterLink to="/einstellungen/instrumententypen" @click="closeMenu">
              Instrumententypen
            </RouterLink>
            <RouterLink to="/einstellungen/kleidungstypen" @click="closeMenu">
              Kleidungstypen
            </RouterLink>
            <RouterLink to="/einstellungen/notengenres" @click="closeMenu">Notengenres</RouterLink>
            <RouterLink to="/einstellungen/waehrungen" @click="closeMenu">Währungen</RouterLink>
            <a href="//localhost:7681" target="_blank" class="terminal-link">Terminal</a>
          </div>
        </div>
      </div>

      <div v-if="menuOpen" class="menu-backdrop" @click="closeMenu"></div>
    </div>
  </nav>
</template>

<style scoped>
.navbar {
  border-bottom: 1px solid var(--color-border);
  background: var(--color-bg);
  position: sticky;
  top: 0;
  z-index: 200;
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
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.brand-logo {
  width: 28px;
  height: 28px;
  object-fit: contain;
}

.links {
  position: fixed;
  top: 0;
  left: 0;
  bottom: 0;
  width: 260px;
  max-width: 80vw;
  flex-direction: column;
  align-items: stretch;
  gap: 0;
  background: var(--color-bg);
  border-right: 1px solid var(--color-border);
  padding: 1rem 0;
  transform: translateX(-100%);
  transition: transform 0.25s ease;
  z-index: 300;
  overflow-y: auto;
  display: flex;
}

.links.open {
  transform: translateX(0);
}

.links > a,
.links > .dropdown {
  padding: 0.75rem 1.25rem;
  font-size: 1rem;
}

.links > a:hover,
.dropdown-trigger:hover {
  background: var(--color-bg-soft);
}

.links a.router-link-active {
  color: var(--color-primary);
  font-weight: 600;
}

.hamburger {
  display: flex;
  flex-direction: column;
  gap: 5px;
  background: none;
  border: none;
  padding: 0.5rem;
  cursor: pointer;
  min-height: 44px;
  min-width: 44px;
  align-items: center;
  justify-content: center;
}

.hamburger span {
  display: block;
  width: 22px;
  height: 2px;
  background: var(--color-text);
  border-radius: 2px;
  transition:
    transform 0.2s,
    opacity 0.2s;
}

.hamburger.open span:nth-child(1) {
  transform: translateY(7px) rotate(45deg);
}
.hamburger.open span:nth-child(2) {
  opacity: 0;
}
.hamburger.open span:nth-child(3) {
  transform: translateY(-7px) rotate(-45deg);
}

.menu-backdrop {
  display: block;
  position: fixed;
  inset: 0;
  background: var(--color-overlay);
  z-index: 250;
}

.dropdown {
  position: relative;
}

.dropdown-trigger {
  cursor: pointer;
  color: var(--color-primary);
  display: block;
  padding: 0;
}

.dropdown-menu {
  position: static;
  background: var(--color-bg);
  border: none;
  border-radius: 0;
  padding: 0;
  min-width: 0;
}

.dropdown-menu a {
  display: block;
  padding: 0.625rem 1.25rem 0.625rem 2.5rem;
  font-size: 0.9rem;
  color: var(--color-text);
}

.dropdown-menu a:hover {
  background: var(--color-bg-soft);
}

.terminal-link {
  border-top: none;
  margin-top: 0;
}

.theme-toggle {
  background: none;
  border: none;
  font-size: 1.2rem;
  cursor: pointer;
  padding: 0.5rem;
  min-height: 44px;
  min-width: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
  color: var(--color-muted);
}

.theme-toggle:hover {
  color: var(--color-text);
  background: none;
}
</style>
