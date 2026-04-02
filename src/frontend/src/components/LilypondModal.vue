<script setup>
defineProps({
  open: { type: Boolean, default: false },
  lilypondCode: { type: String, default: "" },
  pdfPath: { type: String, default: null },
});

const emit = defineEmits(["close"]);

const BASE = (import.meta.env.VITE_BASE_PATH || "").replace(/\/$/, "");

function pdfUrl(path) {
  if (!path) return null;
  const relative = path.replace(/^data\/scans\//, "");
  return `${BASE}/scans/${relative}`;
}
</script>

<template>
  <div v-if="open" class="modal-backdrop" @click.self="emit('close')">
    <div class="modal modal-lilypond">
      <div class="modal-header">
        <h2>LilyPond-Code</h2>
        <button class="close-btn" title="Schließen" @click="emit('close')">✕</button>
      </div>

      <div class="modal-body">
        <pre class="ly-code">{{ lilypondCode }}</pre>
      </div>

      <div class="modal-footer">
        <a v-if="pdfPath" :href="pdfUrl(pdfPath)" target="_blank" class="btn btn-primary">
          PDF öffnen
        </a>
        <button class="btn" @click="emit('close')">Schließen</button>
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

.modal-lilypond {
  background: var(--color-bg);
  border-radius: var(--radius);
  width: 100%;
  max-width: 700px;
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

.modal-body {
  padding: 1rem 1.5rem;
  overflow-y: auto;
  flex: 1;
}

.ly-code {
  background: #1a1a2e;
  color: #e0e0e0;
  padding: 1rem;
  border-radius: var(--radius);
  font-family: "Fira Code", "Cascadia Code", monospace;
  font-size: 0.8rem;
  line-height: 1.5;
  overflow-x: auto;
  white-space: pre;
  margin: 0;
}

.modal-footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 0.5rem;
  padding: 0.75rem 1.5rem;
  border-top: 1px solid var(--color-border);
}
</style>
