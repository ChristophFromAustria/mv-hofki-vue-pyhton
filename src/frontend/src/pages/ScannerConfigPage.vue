<script setup>
import { ref, computed, onMounted } from "vue";
import { get, put, post } from "../lib/api.js";
import FieldToggle from "../components/config/FieldToggle.vue";
import FieldSelect from "../components/config/FieldSelect.vue";
import FieldNumber from "../components/config/FieldNumber.vue";

const entries = ref([]);
const loading = ref(true);
const saving = ref(false);
const error = ref(null);
const successMsg = ref(null);
const collapsedGroups = ref(new Set());

const groupTree = computed(() => buildGroupTree(entries.value));

onMounted(async () => {
  await loadConfig();
  // Collapse all groups by default after first load
  const tree = groupTree.value;
  for (const node of tree.roots) {
    collapsedGroups.value.add(node.path);
    for (const child of node.children) {
      collapsedGroups.value.add(child.path);
    }
  }
});

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

    <div v-if="error" class="msg msg-error">{{ error }}</div>
    <div v-if="successMsg" class="msg msg-success">{{ successMsg }}</div>

    <div v-if="loading" style="text-align: center; padding: 2rem; color: var(--color-muted)">
      Laden...
    </div>

    <div v-else class="config-grid">
      <!-- Root-level entries -->
      <div v-if="groupTree.rootEntries.length" class="card config-card">
        <div class="card-fields">
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
      </div>

      <!-- Grouped entries -->
      <template v-for="node in groupTree.roots" :key="node.path">
        <div class="card config-card">
          <h2 class="card-title" @click="toggleGroup(node.path)">
            <span class="group-chevron">{{
              collapsedGroups.has(node.path) ? "\u25B8" : "\u25BE"
            }}</span>
            {{ node.label }}
          </h2>
          <div v-show="!collapsedGroups.has(node.path)">
            <div class="card-fields">
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
              <h3 class="subgroup-title" @click="toggleGroup(child.path)">
                <span class="group-chevron">{{
                  collapsedGroups.has(child.path) ? "\u25B8" : "\u25BE"
                }}</span>
                {{ child.label }}
              </h3>
              <div v-show="!collapsedGroups.has(child.path)" class="card-fields">
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
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1.5rem;
}

.msg {
  padding: 0.5rem 0.75rem;
  border-radius: var(--radius);
  font-size: 0.85rem;
  margin-bottom: 1rem;
}
.msg-error {
  color: var(--color-danger);
  background: rgba(220, 38, 38, 0.08);
}
.msg-success {
  color: #16a34a;
  background: rgba(22, 163, 74, 0.08);
}

.config-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 1rem;
}

.config-card {
  padding: 1.25rem;
}

.card-title {
  font-size: 0.95rem;
  font-weight: 600;
  margin-bottom: 1rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid var(--color-border);
  cursor: pointer;
  user-select: none;
  display: flex;
  align-items: center;
  gap: 0.3rem;
}
.card-title:hover {
  color: var(--color-primary);
}

.group-chevron {
  font-size: 0.7rem;
  width: 0.8rem;
  text-align: center;
}

.subgroup {
  margin-top: 0.75rem;
  margin-left: 0.75rem;
  padding-left: 0.75rem;
  border-left: 2px solid var(--color-border);
}

.subgroup-title {
  font-size: 0.8rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--color-muted);
  margin-bottom: 0.5rem;
  cursor: pointer;
  user-select: none;
  display: flex;
  align-items: center;
  gap: 0.3rem;
}
.subgroup-title:hover {
  color: var(--color-text);
}

.card-fields {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}
.field-row {
  padding: 0.1rem 0;
}

.is-modified {
  border-left: 2px solid var(--color-primary);
  padding-left: 0.5rem;
}
</style>
