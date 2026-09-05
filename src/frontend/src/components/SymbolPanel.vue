<script setup>
import { computed } from "vue";
import { RouterLink } from "vue-router";

const props = defineProps({
  symbol: { type: Object, default: null },
  templates: { type: Array, default: () => [] },
});

const emit = defineEmits(["verify", "correct", "correct-to-alternative"]);

const BASE = (import.meta.env.VITE_BASE_PATH || "").replace(/\/$/, "");

const snippetUrl = computed(() => {
  if (!props.symbol?.snippet_path) return null;
  return `${BASE}/${props.symbol.snippet_path}`;
});

// The library variant that produced this match (only for uncorrected hits)
const matchedVariant = computed(() => {
  if (!props.symbol || props.symbol.corrected_symbol) return null;
  return props.symbol.matched_variant ?? null;
});

const matchedVariantUrl = computed(() => {
  const v = matchedVariant.value;
  if (!v?.image_path) return null;
  const relative = v.image_path.replace(/^data\/symbol_library\//, "");
  return `${BASE}/symbol-library/${relative}`;
});

const variantEditorRoute = computed(() => {
  const v = matchedVariant.value;
  if (!v) return null;
  return {
    name: "symbol-library",
    query: { template: String(v.template_id), variant: String(v.id) },
  };
});

/**
 * Height of the anchor point above the bottom staff line, in line spacings.
 * Same rule as the backend (note_geometry.head_center_lines): notes take
 * the head half a line inside the stem-free end of the box, everything
 * else the box centre; the variant's manual anchor correction is applied.
 */
const anchorLines = computed(() => {
  const s = props.symbol;
  if (!s || s.staff_y_top == null || s.staff_y_bottom == null) return null;
  const template = s.corrected_symbol ?? s.matched_symbol;
  const stem = template?.category === "note" ? template?.stem_direction : null;
  let center;
  if (stem === "up") center = s.staff_y_bottom + 0.5;
  else if (stem === "down") center = s.staff_y_top - 0.5;
  else center = (s.staff_y_top + s.staff_y_bottom) / 2;
  const v = matchedVariant.value;
  if (v?.anchor_dy && v.source_line_spacing > 0) center -= v.anchor_dy / v.source_line_spacing;
  return center;
});

/** Human-readable staff position for a height in line spacings (0 = bottom line). */
const anchorPositionLabel = computed(() => {
  if (anchorLines.value == null) return null;
  const step = Math.round(anchorLines.value * 2);
  if (step < 0 || step > 8) return "außerhalb des Systems";
  if (step % 2 === 0) return `${step / 2 + 1}. Linie`;
  return `${(step + 1) / 2}. Zwischenraum`;
});

const matchedName = computed(() => {
  if (!props.symbol) return null;
  const corrected = props.symbol.corrected_symbol;
  const matched = props.symbol.matched_symbol;
  return corrected?.display_name ?? matched?.display_name ?? null;
});

const confidence = computed(() => {
  return props.symbol?.confidence ?? null;
});

function confidenceClass(conf) {
  if (conf == null) return "conf-none";
  if (conf >= 0.85) return "conf-high";
  if (conf >= 0.4) return "conf-medium";
  return "conf-low";
}

function confidenceLabel(conf) {
  if (conf == null) return "–";
  return `${Math.round(conf * 100)} %`;
}
</script>

<template>
  <div class="symbol-panel">
    <div v-if="!symbol" class="panel-empty">
      <p>Kein Symbol ausgewählt.</p>
      <p class="hint">Klicken Sie auf ein Symbol im Bild, um es hier anzuzeigen.</p>
    </div>

    <div v-else class="panel-content">
      <h3 class="panel-title">Symbol</h3>

      <!-- Snippet preview and the variant that matched it -->
      <div class="snippet-row">
        <figure class="snippet-wrap">
          <img v-if="snippetUrl" :src="snippetUrl" alt="Symbol-Ausschnitt" class="snippet-img" />
          <div v-else class="snippet-placeholder">Kein Ausschnitt</div>
          <figcaption class="snippet-caption">Scan</figcaption>
        </figure>
        <figure v-if="matchedVariantUrl" class="snippet-wrap">
          <img :src="matchedVariantUrl" alt="Getroffene Variante" class="snippet-img" />
          <figcaption class="snippet-caption">
            Variante #{{ matchedVariant.id }}
            <span v-if="matchedVariant.anchor_dx || matchedVariant.anchor_dy" class="snippet-note">
              · Anker korrigiert
            </span>
          </figcaption>
        </figure>
      </div>
      <RouterLink
        v-if="variantEditorRoute"
        :to="variantEditorRoute"
        class="btn btn-sm variant-link"
      >
        Variante bearbeiten
      </RouterLink>

      <!-- Match info -->
      <div class="match-info">
        <div class="info-row">
          <span class="info-label">Erkannt als</span>
          <span class="info-value">{{ matchedName ?? "Unbekannt" }}</span>
        </div>
        <div class="info-row">
          <span class="info-label">Konfidenz</span>
          <span :class="['conf-badge', confidenceClass(confidence)]">
            {{ confidenceLabel(confidence) }}
          </span>
        </div>
        <div class="info-row">
          <span class="info-label">Verifiziert</span>
          <span class="info-value">{{ symbol.user_verified ? "Ja" : "Nein" }}</span>
        </div>
        <div v-if="symbol.staff_x_start != null" class="info-row">
          <span class="info-label">X</span>
          <span class="info-value">{{ symbol.staff_x_start }} – {{ symbol.staff_x_end }} px</span>
        </div>
        <div v-if="symbol.staff_y_top != null" class="info-row">
          <span class="info-label">Y (Staff)</span>
          <span class="info-value">
            {{ symbol.staff_y_top.toFixed(1) }} – {{ symbol.staff_y_bottom.toFixed(1) }} Linien
          </span>
        </div>
        <div v-if="anchorLines != null" class="info-row">
          <span class="info-label">Mittelpunkt (Y)</span>
          <span class="info-value">
            {{ anchorLines.toFixed(2) }} Linien
            <span class="info-muted">· {{ anchorPositionLabel }}</span>
          </span>
        </div>
        <div v-if="symbol.corrected_symbol" class="info-row">
          <span class="info-label">Korrigiert zu</span>
          <span class="info-value">{{ symbol.corrected_symbol.display_name }}</span>
        </div>
      </div>

      <!-- Actions -->
      <div class="panel-actions">
        <button
          class="btn btn-primary"
          :disabled="symbol.user_verified"
          @click="emit('verify', symbol)"
        >
          {{ symbol.user_verified ? "Bereits bestätigt" : "Bestätigen" }}
        </button>
        <button class="btn btn-secondary" @click="emit('correct', symbol)">Korrigieren</button>
      </div>

      <!-- Alternative detections (from NMS) -->
      <div v-if="symbol.alternatives && symbol.alternatives.length > 0" class="alternatives">
        <h4>Weitere Treffer</h4>
        <div class="alt-list">
          <button
            v-for="alt in symbol.alternatives"
            :key="alt.template_id"
            class="alt-btn"
            @click="emit('correct-to-alternative', symbol, alt)"
          >
            <span class="alt-name">{{ alt.display_name ?? `#${alt.template_id}` }}</span>
            <span :class="['alt-conf', confidenceClass(alt.confidence)]">
              {{ confidenceLabel(alt.confidence) }}
            </span>
          </button>
        </div>
      </div>

      <!-- Library templates -->
      <div v-if="templates.length > 0" class="alternatives">
        <h4>Bibliothek (Auswahl)</h4>
        <div class="alt-list">
          <button
            v-for="tpl in templates.slice(0, 8)"
            :key="tpl.id"
            class="alt-btn"
            @click="emit('correct', symbol, tpl)"
          >
            {{ tpl.display_name }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.symbol-panel {
  height: 100%;
  overflow-y: auto;
  padding: 1rem;
  border-left: 1px solid var(--color-border);
  background: var(--color-bg);
}

.panel-empty {
  text-align: center;
  padding: 2rem 0.5rem;
  color: var(--color-muted);
}

.hint {
  font-size: 0.85rem;
  margin-top: 0.5rem;
}

.panel-title {
  margin-bottom: 1rem;
  font-size: 1rem;
}

.snippet-row {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
}

.snippet-wrap {
  flex: 1 1 0;
  min-width: 0;
  margin: 0;
  background: var(--color-canvas-bg);
  border-radius: var(--radius);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.25rem;
  min-height: 80px;
  padding: 0.5rem;
}

.snippet-caption {
  font-size: 0.7rem;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--color-muted);
}

.snippet-note {
  text-transform: none;
  letter-spacing: 0;
}

.variant-link {
  display: inline-block;
  margin-bottom: 1rem;
}

.snippet-img {
  max-width: 100%;
  max-height: 120px;
  object-fit: contain;
  image-rendering: pixelated;
}

.snippet-placeholder {
  color: var(--color-canvas-fg);
  font-size: 0.85rem;
}

.match-info {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  margin-bottom: 1rem;
}

.info-row {
  display: flex;
  justify-content: space-between;
  font-size: 0.875rem;
}

.info-muted {
  color: var(--color-muted);
}

.info-label {
  color: var(--color-muted);
}

.info-value {
  font-weight: 500;
}

.conf-badge {
  font-weight: 600;
  font-size: 0.875rem;
}

.conf-high {
  color: var(--color-success);
}

.conf-medium {
  color: var(--color-warning);
}

.conf-low {
  color: var(--color-danger);
}

.conf-none {
  color: var(--color-muted);
}

.panel-actions {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  margin-bottom: 1rem;
}

.alternatives h4 {
  font-size: 0.85rem;
  color: var(--color-muted);
  margin-bottom: 0.5rem;
}

.alt-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}

.alt-btn {
  padding: 0.25rem 0.5rem;
  font-size: 0.8rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  background: var(--color-bg-soft);
  color: var(--color-text);
  cursor: pointer;
  transition: background var(--transition);
}

.alt-btn:hover {
  background: var(--color-primary-light);
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.alt-name {
  font-size: 0.8rem;
  font-weight: 500;
}

.alt-conf {
  font-size: 0.7rem;
  font-weight: 600;
}
</style>
