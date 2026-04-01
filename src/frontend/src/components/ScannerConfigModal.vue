<script setup>
import { ref, watch } from "vue";
import { get, put } from "../lib/api.js";
import { groupedFields, SCANNER_CONFIG_FIELDS } from "../lib/scanner-config.js";

const props = defineProps({
  open: { type: Boolean, default: false },
  scanId: { type: [Number, String], default: null },
  projectId: { type: [Number, String], default: null },
  adjustments: { type: Object, default: () => ({}) },
});

const emit = defineEmits(["close", "update-adjustments"]);

const config = ref({});
const loading = ref(false);
const saving = ref(false);
const error = ref(null);
const successMsg = ref(null);
const scanSpecific = ref(false);

const groups = groupedFields();
const analysisKeys = SCANNER_CONFIG_FIELDS.map((f) => f.key);

watch(
  () => props.open,
  async (isOpen) => {
    if (!isOpen) return;
    successMsg.value = null;
    error.value = null;

    const analysis = props.adjustments?.analysis;
    scanSpecific.value = analysis?.enabled === true;

    await loadGlobalConfig();

    // If scan has specific values, overlay them onto the loaded global config
    if (analysis && analysis.enabled) {
      for (const key of analysisKeys) {
        if (key in analysis) {
          config.value[key] = analysis[key];
        }
      }
    }
  },
);

watch(scanSpecific, (isScanSpecific) => {
  if (!isScanSpecific) {
    // Switching back to global: reload global values
    loadGlobalConfig();
  }
});

async function loadGlobalConfig() {
  loading.value = true;
  error.value = null;
  try {
    config.value = await get("/scanner/config");
  } catch (e) {
    error.value = e.message;
  } finally {
    loading.value = false;
  }
}

async function saveGlobal() {
  saving.value = true;
  error.value = null;
  successMsg.value = null;
  try {
    config.value = await put("/scanner/config", config.value);
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
    // Build analysis object from current config values
    const analysis = { enabled: true };
    for (const key of analysisKeys) {
      if (key in config.value) {
        analysis[key] = config.value[key];
      }
    }
    const updated = { ...props.adjustments, analysis };
    // Save to backend
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
</script>

<template>
  <div v-if="open" class="modal-backdrop" @click.self="emit('close')">
    <div class="modal modal-config">
      <div class="modal-header">
        <h2>Scanner-Konfiguration</h2>
        <button class="close-btn" title="Schließen" @click="emit('close')">✕</button>
      </div>

      <div v-if="loading" class="modal-loading">Laden...</div>

      <div v-else class="modal-body">
        <div v-if="error" class="config-error">{{ error }}</div>
        <div v-if="successMsg" class="config-success">{{ successMsg }}</div>

        <!-- Scan-specific toggle -->
        <div v-if="scanId" class="scan-toggle">
          <label class="toggle-label">
            <input v-model="scanSpecific" type="checkbox" class="toggle-input" />
            <span class="toggle-text">Scan-spezifische Parameter verwenden</span>
          </label>
        </div>

        <div v-for="group in groups" :key="group.label" class="config-group">
          <h3 class="group-title">{{ group.label }}</h3>
          <div class="group-fields">
            <div v-for="field in group.fields" :key="field.key" class="config-field">
              <!-- Toggle -->
              <template v-if="field.type === 'toggle'">
                <label class="toggle-label">
                  <input v-model="config[field.key]" type="checkbox" class="toggle-input" />
                  <span class="toggle-text">{{ field.label }}</span>
                </label>
              </template>

              <!-- Select -->
              <template v-else-if="field.type === 'select'">
                <label class="field-label">
                  {{ field.label }}
                  <select v-model="config[field.key]" class="field-select">
                    <option v-for="opt in field.options" :key="opt.value" :value="opt.value">
                      {{ opt.label }}
                    </option>
                  </select>
                </label>
              </template>

              <!-- Number -->
              <template v-else-if="field.type === 'number'">
                <label class="field-label">
                  <span class="field-label-row">
                    {{ field.label }}
                    <span class="field-value">{{ config[field.key] }}</span>
                  </span>
                  <input
                    v-model.number="config[field.key]"
                    type="range"
                    :min="field.min"
                    :max="field.max"
                    :step="field.step"
                    class="field-slider"
                  />
                </label>
              </template>
            </div>
          </div>
        </div>
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
}

.group-fields {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.config-field {
  padding: 0.25rem 0;
}

/* Toggle */
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

/* Select */
.field-label {
  display: block;
  font-size: 0.85rem;
  color: var(--color-muted);
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

/* Number slider */
.field-label-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
}

.field-value {
  font-weight: 600;
  color: var(--color-text);
  font-size: 0.85rem;
}

.field-slider {
  width: 100%;
  margin-top: 0.2rem;
  accent-color: var(--color-primary);
}

/* Footer */
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
