<script setup>
import { ref, watch, nextTick } from "vue";

const props = defineProps({
  open: { type: Boolean, default: false },
});

const emit = defineEmits(["close"]);

const BASE = (import.meta.env.VITE_BASE_PATH || "").replace(/\/$/, "");
const API_PREFIX = `${BASE}/api/v1`;

const logs = ref([]);
const status = ref("idle"); // idle | running | done | error
const progress = ref({ index: 0, total: 0, ok: 0, failed: 0 });
const currentScan = ref(null);
const logContainer = ref(null);

let eventSource = null;

watch(
  () => props.open,
  (isOpen) => {
    if (!isOpen && eventSource) {
      eventSource.close();
      eventSource = null;
    }
  },
);

function startBatch(projectId, statusFilter) {
  logs.value = [];
  status.value = "running";
  progress.value = { index: 0, total: 0, ok: 0, failed: 0 };
  currentScan.value = null;

  const params = new URLSearchParams();
  if (projectId) params.set("project_id", projectId);
  if (statusFilter) params.set("status_filter", statusFilter);
  const qs = params.toString();
  const url = `${API_PREFIX}/scanner/batch-process-stream${qs ? "?" + qs : ""}`;

  eventSource = new EventSource(url);

  eventSource.addEventListener("scan", (e) => {
    const data = JSON.parse(e.data);
    currentScan.value = data;
    progress.value.index = data.index;
    progress.value.total = data.total;
    addLog(`── [${data.index}/${data.total}] ${data.project} / ${data.part} ──`, "scan");
  });

  eventSource.addEventListener("log", (e) => {
    addLog(e.data, "log");
  });

  eventSource.addEventListener("done", (e) => {
    const data = JSON.parse(e.data);
    progress.value.ok++;
    addLog(`Scan ${data.scan_id}: ${data.status}`, "done");
  });

  eventSource.addEventListener("error", (e) => {
    if (e.data) {
      try {
        const data = JSON.parse(e.data);
        progress.value.failed++;
        addLog(`Scan ${data.scan_id}: Fehler — ${data.error}`, "error");
      } catch {
        addLog(`Fehler: ${e.data}`, "error");
      }
    }
  });

  eventSource.addEventListener("batch_done", (e) => {
    const data = JSON.parse(e.data);
    progress.value = { ...progress.value, ...data };
    status.value = "done";
    addLog(
      `\nAbgeschlossen: ${data.ok} erfolgreich, ${data.failed} fehlgeschlagen von ${data.total}`,
      data.failed > 0 ? "error" : "done",
    );
    eventSource.close();
    eventSource = null;
  });

  eventSource.onerror = () => {
    if (status.value === "running") {
      status.value = "error";
      addLog("Verbindung zum Server verloren", "error");
      if (eventSource) {
        eventSource.close();
        eventSource = null;
      }
    }
  };
}

function addLog(text, type) {
  const ts = new Date().toLocaleTimeString("de-DE", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
  logs.value.push({ time: ts, text, type });
  nextTick(() => {
    if (logContainer.value) {
      logContainer.value.scrollTop = logContainer.value.scrollHeight;
    }
  });
}

function handleClose() {
  if (eventSource) {
    eventSource.close();
    eventSource = null;
  }
  emit("close");
}

defineExpose({ startBatch });
</script>

<template>
  <div v-if="open" class="modal-backdrop" @click.self="handleClose">
    <div class="modal batch-modal">
      <div class="batch-header">
        <h2>Massenanalyse</h2>
        <div class="batch-status">
          <span v-if="status === 'running'" class="indicator running">
            {{ progress.index }} / {{ progress.total }}
          </span>
          <span v-else-if="status === 'done'" class="indicator done"> Fertig </span>
          <span v-else-if="status === 'error'" class="indicator err"> Fehler </span>
        </div>
      </div>

      <div v-if="progress.total > 0" class="progress-bar-wrap">
        <div
          class="progress-bar-fill"
          :style="{ width: ((progress.ok + progress.failed) / progress.total) * 100 + '%' }"
          :class="{ 'has-errors': progress.failed > 0 }"
        ></div>
      </div>

      <div ref="logContainer" class="batch-log">
        <div v-if="logs.length === 0 && status === 'running'" class="log-waiting">
          Warte auf Serverantwort...
        </div>
        <div
          v-for="(entry, i) in logs"
          :key="i"
          class="log-line"
          :class="{
            'log-scan': entry.type === 'scan',
            'log-done': entry.type === 'done',
            'log-error': entry.type === 'error',
          }"
        >
          <span class="log-ts">{{ entry.time }}</span>
          <span class="log-msg">{{ entry.text }}</span>
        </div>
      </div>

      <div class="batch-footer">
        <div v-if="progress.total > 0" class="footer-stats">
          <span class="stat-ok">{{ progress.ok }} OK</span>
          <span v-if="progress.failed" class="stat-fail">{{ progress.failed }} Fehler</span>
        </div>
        <div class="footer-spacer"></div>
        <button class="btn" @click="handleClose">
          {{ status === "running" ? "Abbrechen" : "Schließen" }}
        </button>
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
  z-index: 600;
}

.batch-modal {
  background: var(--color-bg);
  border-radius: var(--radius);
  width: 100%;
  max-width: 640px;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
}

.batch-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.25rem;
  border-bottom: 1px solid var(--color-border);
}

.batch-header h2 {
  margin: 0;
  font-size: 1rem;
}

.indicator {
  font-size: 0.8rem;
  font-weight: 600;
  padding: 0.2rem 0.6rem;
  border-radius: var(--radius);
}

.indicator.running {
  color: var(--color-primary);
  background: var(--color-primary-light);
}

.indicator.done {
  color: #16a34a;
  background: rgba(22, 163, 74, 0.1);
}

.indicator.err {
  color: var(--color-danger);
  background: rgba(220, 38, 38, 0.1);
}

.progress-bar-wrap {
  height: 4px;
  background: var(--color-border);
}

.progress-bar-fill {
  height: 100%;
  background: var(--color-primary);
  transition: width 0.3s ease;
}

.progress-bar-fill.has-errors {
  background: linear-gradient(90deg, var(--color-primary), var(--color-danger));
}

.batch-log {
  flex: 1;
  overflow-y: auto;
  padding: 0.75rem 1.25rem;
  font-family: var(--font-mono);
  font-size: 0.78rem;
  background: var(--color-bg-soft);
  min-height: 250px;
  max-height: 450px;
}

.log-waiting {
  color: var(--color-muted);
  font-style: italic;
}

.log-line {
  display: flex;
  gap: 0.75rem;
  padding: 0.15rem 0;
  line-height: 1.4;
}

.log-ts {
  color: var(--color-muted);
  flex-shrink: 0;
}

.log-msg {
  color: var(--color-text);
  white-space: pre-wrap;
}

.log-scan .log-msg {
  font-weight: 600;
  color: var(--color-primary);
}

.log-done .log-msg {
  color: #16a34a;
}

.log-error .log-msg {
  color: var(--color-danger);
  font-weight: 600;
}

.batch-footer {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem 1.25rem;
  border-top: 1px solid var(--color-border);
}

.footer-stats {
  display: flex;
  gap: 0.75rem;
  font-size: 0.85rem;
  font-weight: 600;
}

.stat-ok {
  color: #16a34a;
}

.stat-fail {
  color: var(--color-danger);
}

.footer-spacer {
  flex: 1;
}
</style>
