<script setup>
import { ref, watch } from "vue";
import { get, put, post } from "../lib/api.js";

const props = defineProps({
  open: { type: Boolean, default: false },
  scanId: { type: [Number, String], default: null },
  projectId: { type: [Number, String], default: null },
  adjustments: { type: Object, default: () => ({}) },
});

const emit = defineEmits(["close", "update-adjustments"]);

const entries = ref([]);
const loading = ref(false);
const saving = ref(false);
const error = ref(null);
const successMsg = ref(null);
const scanSpecific = ref(false);
const collapsedGroups = ref(new Set());

watch(
  () => props.open,
  async (isOpen) => {
    if (!isOpen) return;
    successMsg.value = null;
    error.value = null;

    const analysis = props.adjustments?.analysis;
    scanSpecific.value = analysis?.enabled === true;

    await loadGlobalConfig();

    if (analysis && analysis.enabled) {
      for (const entry of entries.value) {
        if (entry.key in analysis) {
          entry.value = analysis[entry.key];
          entry.is_modified = true;
        }
      }
    }
  },
);

watch(scanSpecific, (isScanSpecific) => {
  if (!isScanSpecific) {
    loadGlobalConfig();
  }
});

async function loadGlobalConfig() {
  loading.value = true;
  error.value = null;
  try {
    const data = await get("/scanner/config");
    entries.value = data.entries;
    // Collapse all groups by default
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

async function saveGlobal() {
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
    successMsg.value = "Global gespeichert";
    setTimeout(() => {
      successMsg.value = null;
    }, 2000);
  } catch (e) {
    error.value = e.message;
  } finally {
    saving.value = false;
  }
}

async function saveScanSpecific() {
  saving.value = true;
  error.value = null;
  successMsg.value = null;
  try {
    const analysis = { enabled: true };
    for (const entry of entries.value) {
      analysis[entry.key] = entry.value;
    }
    const updated = { ...props.adjustments, analysis };
    const partsData = await get(`/scanner/projects/${props.projectId}/parts`);
    for (const part of partsData) {
      const scansData = await get(`/scanner/projects/${props.projectId}/parts/${part.id}/scans`);
      const found = scansData.find((s) => String(s.id) === String(props.scanId));
      if (found) {
        await put(`/scanner/projects/${props.projectId}/parts/${part.id}/scans/${props.scanId}`, {
          adjustments_json: JSON.stringify(updated),
        });
        break;
      }
    }
    emit("update-adjustments", updated);
    successMsg.value = "Für diesen Scan gespeichert";
    setTimeout(() => {
      successMsg.value = null;
    }, 2000);
  } catch (e) {
    error.value = e.message;
  } finally {
    saving.value = false;
  }
}

async function resetDefaults() {
  await loadGlobalConfig();
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

async function resetSingle(key) {
  error.value = null;
  try {
    const data = await post("/scanner/config/reset", { keys: [key] });
    entries.value = data.entries;
  } catch (e) {
    error.value = e.message;
  }
}
</script>

<template>
  <div v-if="open" class="modal-backdrop" @click.self="emit('close')">
    <div class="modal modal-config">
      <div class="modal-header">
        <h2>Scanner-Konfiguration</h2>
        <button class="close-btn" title="Schließen" @click="emit('close')">&#10005;</button>
      </div>

      <div v-if="loading" class="modal-loading">Laden...</div>

      <div v-else class="modal-body">
        <div v-if="error" class="config-error">{{ error }}</div>
        <div v-if="successMsg" class="config-success">{{ successMsg }}</div>

        <div v-if="scanId" class="scan-toggle">
          <label class="toggle-label">
            <input v-model="scanSpecific" type="checkbox" class="toggle-input" />
            <span class="toggle-text">Scan-spezifische Parameter verwenden</span>
          </label>
        </div>

        <template v-for="node in getGroupTree().roots" :key="node.path">
          <div class="config-group">
            <h3 class="group-title" @click="toggleGroup(node.path)">
              <span class="group-chevron">{{
                collapsedGroups.has(node.path) ? "\u25B8" : "\u25BE"
              }}</span>
              {{ node.label }}
            </h3>
            <div v-show="!collapsedGroups.has(node.path)" class="group-fields">
              <div v-for="entry in node.entries" :key="entry.key" class="config-field">
                <ModalField :entry="entry" @update="updateValue" @reset="resetSingle" />
              </div>
              <div v-for="child in node.children" :key="child.path" class="subgroup">
                <h4 class="subgroup-title" @click="toggleGroup(child.path)">
                  <span class="group-chevron">{{
                    collapsedGroups.has(child.path) ? "\u25B8" : "\u25BE"
                  }}</span>
                  {{ child.label }}
                </h4>
                <div v-show="!collapsedGroups.has(child.path)" class="group-fields">
                  <div v-for="entry in child.entries" :key="entry.key" class="config-field">
                    <ModalField :entry="entry" @update="updateValue" @reset="resetSingle" />
                  </div>
                </div>
              </div>
            </div>
          </div>
        </template>
      </div>

      <div class="modal-footer">
        <button class="btn" :disabled="loading" @click="resetDefaults">Zurücksetzen</button>
        <div class="footer-spacer"></div>
        <template v-if="scanSpecific && scanId">
          <button class="btn btn-primary" :disabled="loading || saving" @click="saveScanSpecific">
            {{ saving ? "Speichert..." : "Für diesen Scan speichern" }}
          </button>
        </template>
        <template v-else>
          <button class="btn btn-primary" :disabled="loading || saving" @click="saveGlobal">
            {{ saving ? "Speichert..." : "Global speichern" }}
          </button>
        </template>
      </div>
    </div>
  </div>
</template>

<script>
const ModalField = {
  props: {
    entry: { type: Object, required: true },
  },
  emits: ["update", "reset"],
  template: `
    <div :class="{ 'field-modified': entry.is_modified }">
      <template v-if="entry.type === 'toggle'">
        <label class="toggle-label">
          <input type="checkbox" class="toggle-input" :checked="entry.value" @change="$emit('update', entry.key, $event.target.checked)" />
          <span class="toggle-text">{{ entry.label }}</span>
          <span v-if="entry.is_modified" class="modified-dot"></span>
          <button v-if="entry.is_modified" class="reset-btn" title="Zur\u00fccksetzen" @click.prevent="$emit('reset', entry.key)">\u21BA</button>
        </label>
      </template>

      <template v-else-if="entry.type === 'select'">
        <label class="field-label">
          <span class="field-label-row">
            {{ entry.label }}
            <span v-if="entry.is_modified" class="modified-dot"></span>
            <button v-if="entry.is_modified" class="reset-btn" title="Zur\u00fccksetzen" @click.prevent="$emit('reset', entry.key)">\u21BA</button>
          </span>
          <select class="field-select" :value="entry.value" @change="$emit('update', entry.key, $event.target.value)">
            <option v-for="opt in entry.options" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
          </select>
          <span v-if="entry.is_modified" class="default-hint">Standard: {{ entry.options?.find(o => o.value === entry.default_value)?.label || entry.default_value }}</span>
        </label>
      </template>

      <template v-else-if="entry.type === 'number'">
        <label class="field-label">
          <span class="field-label-row">
            {{ entry.label }}
            <span class="field-value-group">
              <span class="field-value">{{ entry.value }}</span>
              <span v-if="entry.is_modified" class="default-hint">(Std: {{ entry.default_value }})</span>
              <span v-if="entry.is_modified" class="modified-dot"></span>
              <button v-if="entry.is_modified" class="reset-btn" title="Zur\u00fccksetzen" @click.prevent="$emit('reset', entry.key)">\u21BA</button>
            </span>
          </span>
          <input type="range" class="field-slider" :value="entry.value" :min="entry.min" :max="entry.max" :step="entry.step" @input="$emit('update', entry.key, Number($event.target.value))" />
        </label>
      </template>
    </div>
  `,
};

export default {
  components: { ModalField },
};
</script>

<style scoped>
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: var(--color-overlay);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 550;
}
.modal-config {
  background: var(--color-bg);
  border-radius: var(--radius);
  width: 100%;
  max-width: 520px;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
}
.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1.25rem 1.5rem 0.75rem;
  border-bottom: 1px solid var(--color-border);
}
.modal-header h2 {
  margin: 0;
  font-size: 1.1rem;
}
.close-btn {
  background: none;
  border: none;
  font-size: 1.2rem;
  cursor: pointer;
  color: var(--color-muted);
  padding: 0.25rem;
  line-height: 1;
}
.close-btn:hover {
  color: var(--color-text);
}
.modal-loading {
  padding: 2rem;
  text-align: center;
  color: var(--color-muted);
}
.modal-body {
  padding: 1rem 1.5rem;
  overflow-y: auto;
  flex: 1;
}
.config-error {
  color: var(--color-danger);
  font-size: 0.85rem;
  margin-bottom: 0.75rem;
  padding: 0.5rem;
  background: rgba(220, 38, 38, 0.08);
  border-radius: var(--radius);
}
.config-success {
  color: #16a34a;
  font-size: 0.85rem;
  margin-bottom: 0.75rem;
  padding: 0.5rem;
  background: rgba(22, 163, 74, 0.08);
  border-radius: var(--radius);
}
.scan-toggle {
  margin-bottom: 1rem;
  padding: 0.75rem;
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
.toggle-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
  font-size: 0.9rem;
}
.toggle-input {
  width: 1.1rem;
  height: 1.1rem;
  accent-color: var(--color-primary);
  cursor: pointer;
}
.toggle-text {
  color: var(--color-text);
}
.field-label {
  display: block;
  font-size: 0.85rem;
  color: var(--color-muted);
}
.field-label-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 0.25rem;
}
.field-value {
  font-weight: 600;
  color: var(--color-text);
  font-size: 0.85rem;
}
.field-value-group {
  display: flex;
  align-items: baseline;
  gap: 0.35rem;
}
.field-select {
  display: block;
  width: 100%;
  margin-top: 0.2rem;
  padding: 0.4rem 0.5rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  background: var(--color-bg);
  color: var(--color-text);
  font-family: inherit;
  font-size: 0.85rem;
}
.field-slider {
  width: 100%;
  margin-top: 0.2rem;
  accent-color: var(--color-primary);
}
.modified-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-primary);
  flex-shrink: 0;
}
.default-hint {
  font-size: 0.75rem;
  color: var(--color-muted);
  font-weight: normal;
}
.reset-btn {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 0.85rem;
  color: var(--color-muted);
  padding: 0 0.15rem;
  line-height: 1;
}
.reset-btn:hover {
  color: var(--color-primary);
}
.modal-footer {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 1.5rem;
  border-top: 1px solid var(--color-border);
}
.footer-spacer {
  flex: 1;
}
</style>
