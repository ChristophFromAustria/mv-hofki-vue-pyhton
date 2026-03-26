<script setup>
import { ref, onMounted } from "vue";
import { get, put } from "../lib/api.js";
import { groupedFields } from "../lib/scanner-config.js";

const config = ref({});
const loading = ref(true);
const saving = ref(false);
const error = ref(null);
const successMsg = ref(null);

const groups = groupedFields();

onMounted(async () => {
  await loadConfig();
});

async function loadConfig() {
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

async function saveConfig() {
  saving.value = true;
  error.value = null;
  successMsg.value = null;
  try {
    config.value = await put("/scanner/config", config.value);
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
      <div v-for="group in groups" :key="group.label" class="card config-card">
        <h2 class="card-title">{{ group.label }}</h2>

        <div class="card-fields">
          <div v-for="field in group.fields" :key="field.key" class="field-row">
            <!-- Toggle -->
            <template v-if="field.type === 'toggle'">
              <label class="toggle-row">
                <input v-model="config[field.key]" type="checkbox" class="toggle-checkbox" />
                <span>{{ field.label }}</span>
              </label>
            </template>

            <!-- Select -->
            <template v-else-if="field.type === 'select'">
              <label class="select-row">
                <span class="field-name">{{ field.label }}</span>
                <select v-model="config[field.key]">
                  <option v-for="opt in field.options" :key="opt.value" :value="opt.value">
                    {{ opt.label }}
                  </option>
                </select>
              </label>
            </template>

            <!-- Number -->
            <template v-else-if="field.type === 'number'">
              <label class="number-row">
                <span class="field-name">
                  {{ field.label }}
                  <strong>{{ config[field.key] }}</strong>
                </span>
                <input
                  v-model.number="config[field.key]"
                  type="range"
                  :min="field.min"
                  :max="field.max"
                  :step="field.step"
                />
              </label>
            </template>
          </div>
        </div>
      </div>
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
}

.card-fields {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.field-row {
  padding: 0.1rem 0;
}

.toggle-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
  font-size: 0.9rem;
}

.toggle-checkbox {
  width: 1.1rem;
  height: 1.1rem;
  accent-color: var(--color-primary);
  cursor: pointer;
}

.select-row {
  display: block;
  font-size: 0.85rem;
  color: var(--color-muted);
}

.select-row select {
  display: block;
  width: 100%;
  margin-top: 0.25rem;
  padding: 0.4rem 0.5rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  background: var(--color-bg);
  color: var(--color-text);
  font-family: inherit;
  font-size: 0.85rem;
}

.number-row {
  display: block;
  font-size: 0.85rem;
  color: var(--color-muted);
}

.field-name {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
}

.field-name strong {
  color: var(--color-text);
}

.number-row input[type="range"] {
  width: 100%;
  margin-top: 0.2rem;
  accent-color: var(--color-primary);
}
</style>
