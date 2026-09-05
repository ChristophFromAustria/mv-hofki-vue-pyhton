<script setup>
import { computed } from "vue";

const props = defineProps({
  textRegion: { type: Object, default: null },
});

const confidencePercent = computed(() => {
  if (!props.textRegion?.confidence) return null;
  return Math.round(props.textRegion.confidence);
});

const confidenceColor = computed(() => {
  const c = props.textRegion?.confidence;
  if (c == null) return "var(--color-muted)";
  if (c >= 80) return "var(--color-success)";
  if (c >= 50) return "var(--color-warning)";
  return "var(--color-danger)";
});
</script>

<template>
  <div class="text-region-panel">
    <div v-if="!textRegion" class="panel-empty">
      <p>Keine Textregion ausgewählt.</p>
      <p class="hint">Klicken Sie auf eine Textregion im Bild, um sie hier anzuzeigen.</p>
    </div>

    <div v-else class="panel-content">
      <h3 class="panel-title">Textregion</h3>

      <div class="detail-grid">
        <span class="detail-label">Erkannter Text</span>
        <span class="detail-value text-value">{{ textRegion.text || "—" }}</span>

        <span class="detail-label">Konfidenz</span>
        <span class="detail-value" :style="{ color: confidenceColor }">
          {{ confidencePercent != null ? confidencePercent + " %" : "—" }}
        </span>

        <span class="detail-label">System</span>
        <span class="detail-value">{{ textRegion.staff_index }}</span>

        <span class="detail-label">Position</span>
        <span class="detail-value"> x={{ textRegion.x }}, y={{ textRegion.y }} </span>

        <span class="detail-label">Größe</span>
        <span class="detail-value"> {{ textRegion.width }} × {{ textRegion.height }} px </span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.text-region-panel {
  padding: 1rem;
}

.panel-empty {
  color: var(--color-muted);
  text-align: center;
  padding: 2rem 1rem;
}

.panel-empty .hint {
  font-size: 0.8rem;
  margin-top: 0.5rem;
}

.panel-title {
  font-size: 0.95rem;
  font-weight: 600;
  margin-bottom: 1rem;
  color: var(--color-text);
}

.detail-grid {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 0.4rem 0.75rem;
  font-size: 0.85rem;
}

.detail-label {
  color: var(--color-muted);
  white-space: nowrap;
}

.detail-value {
  color: var(--color-text);
}

.text-value {
  font-weight: 600;
  font-size: 1rem;
}

.panel-content {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
</style>
