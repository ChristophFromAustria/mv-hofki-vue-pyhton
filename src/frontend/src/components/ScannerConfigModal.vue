<script setup>
import { ref, watch } from "vue";
import { get } from "../lib/api.js";
import FieldToggle from "./config/FieldToggle.vue";
import FieldSelect from "./config/FieldSelect.vue";
import FieldNumber from "./config/FieldNumber.vue";

const props = defineProps({
  open: { type: Boolean, default: false },
  scanId: { type: [Number, String], default: null },
  projectId: { type: [Number, String], default: null },
  adjustments: { type: Object, default: () => ({}) },
});

const emit = defineEmits(["close", "update-adjustments"]);

const entries = ref([]);
const globalValues = ref({});
const loading = ref(false);
const error = ref(null);
const collapsedGroups = ref(new Set());

watch(
  () => props.open,
  async (isOpen) => {
    if (!isOpen) return;
    error.value = null;
    await loadConfigWithOverrides();
  },
);

async function loadConfigWithOverrides() {
  loading.value = true;
  error.value = null;
  try {
    const configData = await get("/scanner/config");
    const globalEntries = configData.entries;

    globalValues.value = {};
    for (const e of globalEntries) {
      globalValues.value[e.key] = e.value;
    }

    // Use props.adjustments as primary source (includes unsaved local changes).
    // props.adjustments is always current because:
    // - On page load: fetchScanData parses adjustments_json from DB
    // - On modal close: emit("update-adjustments") updates the parent ref
    const analysis = props.adjustments?.analysis;
    entries.value = globalEntries.map((e) => {
      if (analysis && analysis.enabled && e.key in analysis) {
        const overrideVal = analysis[e.key];
        return {
          ...e,
          value: overrideVal,
          is_modified: String(overrideVal) !== String(e.value),
        };
      }
      return { ...e, is_modified: false };
    });

    collapsedGroups.value = new Set();
    for (const e of entries.value) {
      if (e.group_path) {
        collapsedGroups.value.add(e.group_path);
        const parts = e.group_path.split("\\");
        for (let i = 1; i < parts.length; i++) {
          collapsedGroups.value.add(parts.slice(0, i).join("\\"));
        }
      }
    }
  } catch (e) {
    error.value = e.message;
  } finally {
    loading.value = false;
  }
}

function buildAnalysis() {
  const hasOverrides = entries.value.some((e) => e.is_modified);
  if (!hasOverrides) return { enabled: false };
  const analysis = { enabled: true };
  for (const entry of entries.value) {
    analysis[entry.key] = entry.value;
  }
  return analysis;
}

function close() {
  // Update parent adjustments with current analysis state on close
  const analysis = buildAnalysis();
  emit("update-adjustments", { ...props.adjustments, analysis });
  emit("close");
}

function getGroupTree() {
  const byGroup = new Map();
  for (const entry of entries.value) {
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

function resetAll() {
  entries.value = entries.value.map((e) => ({
    ...e,
    value: globalValues.value[e.key] ?? e.value,
    is_modified: false,
  }));
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
  if (entry) {
    entry.value = val;
    entry.is_modified = String(val) !== String(globalValues.value[key]);
  }
}

function resetSingle(key) {
  const entry = entries.value.find((e) => e.key === key);
  if (entry && key in globalValues.value) {
    entry.value = globalValues.value[key];
    entry.is_modified = false;
  }
}
</script>

<template>
  <div v-if="open" class="overlay" @click.self="close">
    <div class="dialog dialog-md dialog-flush">
      <div class="dialog-header">
        <h2>Scanner-Konfiguration</h2>
        <button class="dialog-close" title="Schließen" @click="close">&#10005;</button>
      </div>

      <div v-if="loading" class="modal-loading">Laden...</div>

      <div v-else class="dialog-body">
        <div v-if="error" class="config-error">{{ error }}</div>

        <p class="config-hint">
          Änderungen werden beim nächsten Vorschau oder Analyse automatisch gespeichert.
        </p>

        <template v-for="node in getGroupTree().roots" :key="node.path">
          <div class="config-group">
            <h3 class="group-title" @click="toggleGroup(node.path)">
              <span class="group-chevron">{{
                collapsedGroups.has(node.path) ? "\u25B8" : "\u25BE"
              }}</span>
              {{ node.label }}
            </h3>
            <div v-show="!collapsedGroups.has(node.path)" class="group-fields">
              <div
                v-for="entry in node.entries"
                :key="entry.key"
                class="config-field"
                :class="{ 'field-modified': entry.is_modified }"
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
              <div v-for="child in node.children" :key="child.path" class="subgroup">
                <h4 class="subgroup-title" @click="toggleGroup(child.path)">
                  <span class="group-chevron">{{
                    collapsedGroups.has(child.path) ? "\u25B8" : "\u25BE"
                  }}</span>
                  {{ child.label }}
                </h4>
                <div v-show="!collapsedGroups.has(child.path)" class="group-fields">
                  <div
                    v-for="entry in child.entries"
                    :key="entry.key"
                    class="config-field"
                    :class="{ 'field-modified': entry.is_modified }"
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

      <div class="dialog-footer">
        <button class="btn" :disabled="loading" @click="resetAll">Auf Global zurücksetzen</button>
        <div class="footer-spacer"></div>
        <button class="btn btn-primary" @click="close">Schließen</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.modal-loading {
  padding: 2rem;
  text-align: center;
  color: var(--color-muted);
}
.config-error {
  color: var(--color-danger);
  font-size: 0.85rem;
  margin-bottom: 0.75rem;
  padding: 0.5rem;
  background: var(--color-danger-bg);
  border-radius: var(--radius);
}
.config-hint {
  font-size: 0.8rem;
  color: var(--color-muted);
  margin-bottom: 1rem;
  padding: 0.5rem 0.6rem;
  background: var(--color-bg-soft);
  border-radius: var(--radius);
  border: 1px solid var(--color-border);
}
.config-group {
  margin-bottom: 1.25rem;
}
.group-title {
  font-size: 0.8rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--color-muted);
  margin-bottom: 0.5rem;
  padding-bottom: 0.25rem;
  border-bottom: 1px solid var(--color-border);
  cursor: pointer;
  user-select: none;
  display: flex;
  align-items: center;
  gap: 0.3rem;
}
.group-title:hover {
  color: var(--color-text);
}
.group-chevron {
  font-size: 0.7rem;
  width: 0.8rem;
  text-align: center;
}
.subgroup {
  margin-top: 0.5rem;
  margin-left: 0.75rem;
  padding-left: 0.75rem;
  border-left: 2px solid var(--color-border);
}
.subgroup-title {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--color-muted);
  margin-bottom: 0.4rem;
  cursor: pointer;
  user-select: none;
  display: flex;
  align-items: center;
  gap: 0.3rem;
}
.subgroup-title:hover {
  color: var(--color-text);
}
.group-fields {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.config-field {
  padding: 0.25rem 0;
}
.field-modified {
  border-left: 2px solid var(--color-primary);
  padding-left: 0.5rem;
}
.footer-spacer {
  flex: 1;
}
</style>
