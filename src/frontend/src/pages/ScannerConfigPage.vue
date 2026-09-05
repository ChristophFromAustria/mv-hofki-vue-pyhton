<script setup>
import { ref, computed, onMounted } from "vue";
import { get, put, post } from "../lib/api.js";
import FieldToggle from "../components/config/FieldToggle.vue";
import FieldSelect from "../components/config/FieldSelect.vue";
import FieldNumber from "../components/config/FieldNumber.vue";
import LoadingSpinner from "../components/LoadingSpinner.vue";

const entries = ref([]);
const loading = ref(true);
const saving = ref(false);
const error = ref(null);
const successMsg = ref(null);
const collapsedGroups = ref(new Set());

const groupTree = computed(() => buildGroupTree(entries.value));

onMounted(loadConfig);

function groupId(path) {
  return "cfg-" + path.toLowerCase().replace(/[^a-z0-9]+/g, "-");
}

function countEntries(node) {
  return node.entries.length + node.children.reduce((n, c) => n + countEntries(c), 0);
}

function jumpTo(id) {
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  document
    .getElementById(id)
    ?.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
}

function buildGroupTree(items) {
  const byGroup = new Map();
  for (const entry of items) {
    const path = entry.group_path || "";
    if (!byGroup.has(path)) byGroup.set(path, []);
    byGroup.get(path).push(entry);
  }
  for (const list of byGroup.values()) {
    list.sort((a, b) => a.sort_order - b.sort_order);
  }

  const allPaths = new Set();
  for (const path of byGroup.keys()) {
    if (!path) continue;
    const parts = path.split("\\");
    for (let i = 1; i <= parts.length; i++) {
      allPaths.add(parts.slice(0, i).join("\\"));
    }
  }

  const sortedPaths = [...allPaths].sort((a, b) => a.localeCompare(b, "de"));
  const nodeMap = new Map();
  const roots = [];

  for (const path of sortedPaths) {
    const parts = path.split("\\");
    const label = parts[parts.length - 1];
    nodeMap.set(path, { path, label, children: [], entries: byGroup.get(path) || [] });
  }

  for (const path of sortedPaths) {
    const parts = path.split("\\");
    const node = nodeMap.get(path);
    if (parts.length === 1) {
      roots.push(node);
    } else {
      const parentPath = parts.slice(0, -1).join("\\");
      const parent = nodeMap.get(parentPath);
      if (parent) parent.children.push(node);
    }
  }

  for (const node of nodeMap.values()) {
    node.children.sort((a, b) => a.label.localeCompare(b.label, "de"));
  }

  return { roots, rootEntries: byGroup.get("") || [] };
}

async function loadConfig() {
  loading.value = true;
  error.value = null;
  try {
    const data = await get("/scanner/config");
    entries.value = data.entries;
  } catch (e) {
    error.value = e.message;
  } finally {
    loading.value = false;
  }
}

async function saveConfig() {
  saving.value = true;
  error.value = null;
  successMsg.value = null;
  try {
    const values = {};
    for (const entry of entries.value) {
      values[entry.key] = entry.value;
    }
    const data = await put("/scanner/config", { values });
    entries.value = data.entries;
    successMsg.value = "Konfiguration gespeichert";
    setTimeout(() => {
      successMsg.value = null;
    }, 3000);
  } catch (e) {
    error.value = e.message;
  } finally {
    saving.value = false;
  }
}

async function resetSingle(key) {
  error.value = null;
  try {
    const data = await post("/scanner/config/reset", { keys: [key] });
    entries.value = data.entries;
  } catch (e) {
    error.value = e.message;
  }
}

function toggleGroup(path) {
  if (collapsedGroups.value.has(path)) {
    collapsedGroups.value.delete(path);
  } else {
    collapsedGroups.value.add(path);
  }
}

function updateValue(key, val) {
  const entry = entries.value.find((e) => e.key === key);
  if (entry) entry.value = val;
}
</script>

<template>
  <div>
    <div class="page-header">
      <h1>Scanner-Konfiguration</h1>
      <button class="btn btn-primary" :disabled="saving || loading" @click="saveConfig">
        {{ saving ? "Speichert..." : "Speichern" }}
      </button>
    </div>

    <div v-if="error" class="alert alert-danger" role="alert">{{ error }}</div>
    <div v-if="successMsg" class="alert alert-success" role="status">{{ successMsg }}</div>

    <LoadingSpinner v-if="loading" />

    <div v-else class="config-layout">
      <nav class="config-nav" aria-label="Konfigurationsgruppen">
        <ul>
          <li v-if="groupTree.rootEntries.length">
            <a href="#cfg-allgemein" @click.prevent="jumpTo('cfg-allgemein')">Allgemein</a>
          </li>
          <li v-for="node in groupTree.roots" :key="node.path">
            <a :href="'#' + groupId(node.path)" @click.prevent="jumpTo(groupId(node.path))">
              {{ node.label }}
            </a>
          </li>
        </ul>
      </nav>

      <div class="config-sections">
        <section v-if="groupTree.rootEntries.length" id="cfg-allgemein" class="page-section">
          <div class="section-header">
            <h2>Allgemein</h2>
          </div>
          <div class="field-list">
            <div
              v-for="entry in groupTree.rootEntries"
              :key="entry.key"
              class="field-row"
              :class="{ 'is-modified': entry.is_modified }"
            >
              <FieldToggle
                v-if="entry.type === 'toggle'"
                :entry="entry"
                @update="updateValue"
                @reset="resetSingle"
              />
              <FieldSelect
                v-else-if="entry.type === 'select'"
                :entry="entry"
                @update="updateValue"
                @reset="resetSingle"
              />
              <FieldNumber
                v-else-if="entry.type === 'number'"
                :entry="entry"
                @update="updateValue"
                @reset="resetSingle"
              />
            </div>
          </div>
        </section>

        <section
          v-for="node in groupTree.roots"
          :id="groupId(node.path)"
          :key="node.path"
          class="page-section"
        >
          <div class="section-header">
            <h2>
              <button
                type="button"
                class="group-toggle"
                :aria-expanded="!collapsedGroups.has(node.path)"
                :aria-controls="groupId(node.path) + '-body'"
                @click="toggleGroup(node.path)"
              >
                <span class="group-chevron" aria-hidden="true">{{
                  collapsedGroups.has(node.path) ? "\u25B8" : "\u25BE"
                }}</span>
                {{ node.label }}
              </button>
            </h2>
            <span class="section-count">{{ countEntries(node) }} Felder</span>
          </div>

          <div v-show="!collapsedGroups.has(node.path)" :id="groupId(node.path) + '-body'">
            <div v-if="node.entries.length" class="field-list">
              <div
                v-for="entry in node.entries"
                :key="entry.key"
                class="field-row"
                :class="{ 'is-modified': entry.is_modified }"
              >
                <FieldToggle
                  v-if="entry.type === 'toggle'"
                  :entry="entry"
                  @update="updateValue"
                  @reset="resetSingle"
                />
                <FieldSelect
                  v-else-if="entry.type === 'select'"
                  :entry="entry"
                  @update="updateValue"
                  @reset="resetSingle"
                />
                <FieldNumber
                  v-else-if="entry.type === 'number'"
                  :entry="entry"
                  @update="updateValue"
                  @reset="resetSingle"
                />
              </div>
            </div>

            <div v-for="child in node.children" :key="child.path" class="subgroup">
              <h3 class="subgroup-title">
                <button
                  type="button"
                  class="group-toggle"
                  :aria-expanded="!collapsedGroups.has(child.path)"
                  :aria-controls="groupId(child.path) + '-body'"
                  @click="toggleGroup(child.path)"
                >
                  <span class="group-chevron" aria-hidden="true">{{
                    collapsedGroups.has(child.path) ? "\u25B8" : "\u25BE"
                  }}</span>
                  {{ child.label }}
                </button>
              </h3>
              <div
                v-show="!collapsedGroups.has(child.path)"
                :id="groupId(child.path) + '-body'"
                class="field-list"
              >
                <div
                  v-for="entry in child.entries"
                  :key="entry.key"
                  class="field-row"
                  :class="{ 'is-modified': entry.is_modified }"
                >
                  <FieldToggle
                    v-if="entry.type === 'toggle'"
                    :entry="entry"
                    @update="updateValue"
                    @reset="resetSingle"
                  />
                  <FieldSelect
                    v-else-if="entry.type === 'select'"
                    :entry="entry"
                    @update="updateValue"
                    @reset="resetSingle"
                  />
                  <FieldNumber
                    v-else-if="entry.type === 'number'"
                    :entry="entry"
                    @update="updateValue"
                    @reset="resetSingle"
                  />
                </div>
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  </div>
</template>

<style scoped>
.config-layout {
  display: grid;
  grid-template-columns: 12rem minmax(0, 1fr);
  gap: var(--space-7);
  align-items: start;
}

.config-nav {
  position: sticky;
  top: 5rem;
}

.config-nav ul {
  list-style: none;
  margin: 0;
  padding: 0;
  border-left: 2px solid var(--color-border);
}

.config-nav a {
  display: block;
  padding: var(--space-1) var(--space-3);
  margin-left: -2px;
  border-left: 2px solid transparent;
  font-size: 0.875rem;
  color: var(--color-muted);
}

.config-nav a:hover {
  color: var(--color-text);
  border-left-color: var(--color-primary);
}

.config-sections {
  max-width: 42rem;
  min-width: 0;
}

.group-toggle {
  background: none;
  border: 0;
  padding: 0;
  font: inherit;
  color: inherit;
  gap: var(--space-2);
  cursor: pointer;
  text-align: left;
}

.group-toggle:hover {
  color: var(--color-primary);
  background: none;
}

.group-chevron {
  font-size: 0.7rem;
  width: 0.8rem;
  text-align: center;
  color: var(--color-muted);
}

.section-count {
  font-size: 0.8rem;
  color: var(--color-muted);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.field-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.field-row {
  padding: 0.1rem 0;
}

.is-modified {
  border-left: 2px solid var(--color-primary);
  padding-left: var(--space-2);
}

.subgroup {
  margin-top: var(--space-5);
  padding-left: var(--space-4);
  border-left: 1px solid var(--color-border);
}

.subgroup-title {
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--color-muted);
  margin-bottom: var(--space-3);
}

@media (max-width: 768px) {
  .config-layout {
    grid-template-columns: 1fr;
    gap: var(--space-4);
  }

  .config-nav {
    position: static;
  }

  .config-nav ul {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-1) var(--space-4);
    border-left: 0;
  }

  .config-nav a {
    padding: var(--space-1) 0;
    margin-left: 0;
    border-left: 0;
  }
}
</style>
