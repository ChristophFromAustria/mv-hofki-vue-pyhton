<script setup>
import { ref, watch } from "vue";

const emit = defineEmits(["adjust", "analyze"]);

const brightness = ref(0);
const contrast = ref(1.0);
const rotation = ref(0);
const threshold = ref(128);

function emitAdjust() {
  emit("adjust", {
    brightness: brightness.value,
    contrast: contrast.value,
    rotation: rotation.value,
    threshold: threshold.value,
  });
}

function rotate(deg) {
  rotation.value = (((rotation.value + deg) % 360) + 360) % 360;
  emitAdjust();
}

watch([brightness, contrast, threshold], emitAdjust);
</script>

<template>
  <div class="adjust-bar">
    <div class="adjust-group">
      <label class="adjust-label">
        Helligkeit
        <span class="adjust-value">{{ brightness > 0 ? "+" : "" }}{{ brightness }}</span>
      </label>
      <input
        v-model.number="brightness"
        type="range"
        min="-50"
        max="50"
        step="1"
        class="adjust-slider"
      />
    </div>

    <div class="adjust-group">
      <label class="adjust-label">
        Kontrast
        <span class="adjust-value">{{ contrast.toFixed(1) }}</span>
      </label>
      <input
        v-model.number="contrast"
        type="range"
        min="0.5"
        max="2.0"
        step="0.1"
        class="adjust-slider"
      />
    </div>

    <div class="adjust-group">
      <label class="adjust-label">
        Schwellwert
        <span class="adjust-value">{{ threshold }}</span>
      </label>
      <input
        v-model.number="threshold"
        type="range"
        min="0"
        max="255"
        step="1"
        class="adjust-slider"
      />
    </div>

    <div class="adjust-group adjust-rotate">
      <label class="adjust-label">Rotation</label>
      <div class="rotate-btns">
        <button class="btn btn-sm btn-secondary" title="90° links" @click="rotate(-90)">
          ↺ -90°
        </button>
        <span class="adjust-value">{{ rotation }}°</span>
        <button class="btn btn-sm btn-secondary" title="90° rechts" @click="rotate(90)">
          ↻ +90°
        </button>
      </div>
    </div>

    <div class="adjust-spacer"></div>

    <button class="btn btn-primary" @click="emit('analyze')">Analyse starten</button>
  </div>
</template>

<style scoped>
.adjust-bar {
  display: flex;
  align-items: center;
  gap: 1.5rem;
  padding: 0.75rem 1rem;
  border-bottom: 1px solid var(--color-border);
  background: var(--color-bg-soft);
  flex-wrap: wrap;
}

.adjust-group {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  min-width: 140px;
}

.adjust-label {
  display: flex;
  justify-content: space-between;
  font-size: 0.8rem;
  color: var(--color-muted);
}

.adjust-value {
  font-weight: 600;
  color: var(--color-text);
}

.adjust-slider {
  width: 100%;
  accent-color: var(--color-primary);
}

.adjust-rotate {
  min-width: auto;
}

.rotate-btns {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.adjust-spacer {
  flex: 1;
}
</style>
