<script setup>
import { ref, watch, nextTick } from "vue";

const props = defineProps({
  open: { type: Boolean, default: false },
});

const emit = defineEmits(["close", "done"]);

const BASE = (import.meta.env.VITE_BASE_PATH || "").replace(/\/$/, "");
const API_PREFIX = `${BASE}/api/v1`;

const logs = ref([]);
const status = ref("idle"); // idle | running | done | error
const errorMsg = ref(null);
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

function startStream(scanId) {
  logs.value = [];
  status.value = "running";
  errorMsg.value = null;

  const url = `${API_PREFIX}/scanner/scans/${scanId}/process-stream`;
  eventSource = new EventSource(url);

  eventSource.addEventListener("log", (e) => {
    const ts = new Date().toLocaleTimeString("de-DE", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
    logs.value.push({ time: ts, text: e.data, type: "log" });
    scrollToBottom();
  });

  eventSource.addEventListener("done", () => {
    const ts = new Date().toLocaleTimeString("de-DE", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
    logs.value.push({ time: ts, text: "Analyse abgeschlossen", type: "done" });
    status.value = "done";
    eventSource.close();
    eventSource = null;
    emit("done");
    scrollToBottom();
  });

  eventSource.addEventListener("error", (e) => {
    if (e.data) {
      errorMsg.value = e.data;
      const ts = new Date().toLocaleTimeString("de-DE", {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      });
      logs.value.push({ time: ts, text: `Fehler: ${e.data}`, type: "error" });
    }
    status.value = "error";
    if (eventSource) {
      eventSource.close();
      eventSource = null;
    }
    scrollToBottom();
  });

  // Handle connection errors (e.g. server crash)
  eventSource.onerror = () => {
    if (status.value === "running") {
      status.value = "error";
      errorMsg.value = "Verbindung zum Server verloren";
      const ts = new Date().toLocaleTimeString("de-DE", {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      });
      logs.value.push({ time: ts, text: "Verbindung verloren", type: "error" });
      if (eventSource) {
        eventSource.close();
        eventSource = null;
      }
      scrollToBottom();
    }
  };
}

function scrollToBottom() {
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

defineExpose({ startStream });
</script>

<template>
  <div v-if="open" class="modal-backdrop" @click.self="handleClose">
    <div class="modal log-modal">
      <div class="log-header">
        <h2>Analyse-Protokoll</h2>
        <div class="log-status">
          <span v-if="status === 'running'" class="status-indicator running">Läuft...</span>
          <span v-else-if="status === 'done'" class="status-indicator done">Fertig</span>
          <span v-else-if="status === 'error'" class="status-indicator error-status">Fehler</span>
        </div>
      </div>

      <div ref="logContainer" class="log-body">
        <div v-if="logs.length === 0 && status === 'running'" class="log-waiting">
          Warte auf Serverantwort...
        </div>
        <div
          v-for="(entry, i) in logs"
          :key="i"
          class="log-entry"
          :class="{ 'log-error': entry.type === 'error', 'log-done': entry.type === 'done' }"
        >
          <span class="log-time">{{ entry.time }}</span>
          <span class="log-text">{{ entry.text }}</span>
        </div>
      </div>

      <div class="log-footer">
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

.log-modal {
  background: var(--color-bg);
  border-radius: var(--radius);
  width: 100%;
  max-width: 560px;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
}

.log-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.25rem;
  border-bottom: 1px solid var(--color-border);
}

.log-header h2 {
  margin: 0;
  font-size: 1rem;
}

.status-indicator {
  font-size: 0.8rem;
  font-weight: 600;
  padding: 0.2rem 0.6rem;
  border-radius: var(--radius);
}

.status-indicator.running {
  color: var(--color-primary);
  background: var(--color-primary-light);
}

.status-indicator.done {
  color: #16a34a;
  background: rgba(22, 163, 74, 0.1);
}

.status-indicator.error-status {
  color: var(--color-danger);
  background: rgba(220, 38, 38, 0.1);
}

.log-body {
  flex: 1;
  overflow-y: auto;
  padding: 0.75rem 1.25rem;
  font-family: var(--font-mono);
  font-size: 0.8rem;
  background: var(--color-bg-soft);
  min-height: 200px;
  max-height: 400px;
}

.log-waiting {
  color: var(--color-muted);
  font-style: italic;
}

.log-entry {
  display: flex;
  gap: 0.75rem;
  padding: 0.2rem 0;
  line-height: 1.5;
}

.log-time {
  color: var(--color-muted);
  flex-shrink: 0;
}

.log-text {
  color: var(--color-text);
}

.log-error .log-text {
  color: var(--color-danger);
  font-weight: 600;
}

.log-done .log-text {
  color: #16a34a;
  font-weight: 600;
}

.log-footer {
  display: flex;
  justify-content: flex-end;
  padding: 0.75rem 1.25rem;
  border-top: 1px solid var(--color-border);
}
</style>
