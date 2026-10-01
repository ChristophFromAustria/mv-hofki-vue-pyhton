<script setup>
import { computed, nextTick, ref, watch } from "vue";
import { post } from "../lib/api.js";
import { copyChoices, copyPayload, defaultCopyKeys, MAX_COPIES } from "../lib/itemCopy.js";

// "Kopieren": new items from an existing one, with the values chosen here.
const props = defineProps({
  open: Boolean,
  item: { type: Object, required: true },
  category: { type: String, required: true },
});
const emit = defineEmits(["copied", "cancel"]);

const dialog = ref(null);
const labelInput = ref(null);
const label = ref("");
const count = ref(1);
const chosen = ref([]);
const error = ref("");
const saving = ref(false);
const titleId = `copy-${Math.random().toString(36).slice(2, 7)}`;

const choices = computed(() => copyChoices(props.item, props.category));

watch(
  () => props.open,
  (open) => {
    if (open) {
      label.value = props.item.label;
      count.value = 1;
      chosen.value = defaultCopyKeys(choices.value);
      error.value = "";
    }
  },
  { immediate: true },
);

watch(
  () => props.open,
  async (open) => {
    await nextTick();
    if (!dialog.value) return;
    if (open) {
      if (!dialog.value.open) dialog.value.showModal();
      labelInput.value?.focus();
      labelInput.value?.select();
    } else if (dialog.value.open) {
      dialog.value.close();
    }
  },
  { immediate: true },
);

function toggle(key, on) {
  chosen.value = on ? [...chosen.value, key] : chosen.value.filter((k) => k !== key);
}

async function copy() {
  error.value = "";
  const text = label.value.trim();
  const n = Number(count.value);
  if (!text) {
    error.value = "Bitte eine Bezeichnung angeben.";
    return;
  }
  if (!Number.isInteger(n) || n < 1 || n > MAX_COPIES) {
    error.value = `Anzahl: 1 bis ${MAX_COPIES}.`;
    return;
  }
  saving.value = true;
  const created = [];
  try {
    for (let i = 0; i < n; i++) {
      created.push(
        await post("/items", copyPayload(props.item, props.category, chosen.value, text)),
      );
    }
    emit("copied", created);
  } catch (e) {
    error.value = created.length
      ? `${created.length} von ${n} angelegt, dann fehlgeschlagen: ${e.message}`
      : `Kopieren fehlgeschlagen: ${e.message}`;
    // Stay open so the message is seen; the new items exist (in the list).
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <Teleport to="body">
    <dialog
      ref="dialog"
      class="dialog dialog-md copy-dialog"
      :aria-labelledby="titleId"
      @cancel.prevent="emit('cancel')"
    >
      <form novalidate @submit.prevent="copy">
        <h2 :id="titleId">{{ item.display_nr }} kopieren</h2>
        <p class="copy-lead">
          Jede Kopie bekommt eine neue Inventarnummer. Fotos, Rechnungen und Leihen werden nicht
          übernommen.
        </p>
        <div class="copy-row">
          <div class="form-group grow">
            <label for="copy-label">Bezeichnung *</label>
            <input id="copy-label" ref="labelInput" v-model="label" autocomplete="off" />
          </div>
          <div class="form-group">
            <label for="copy-count">Anzahl Kopien</label>
            <input
              id="copy-count"
              v-model="count"
              type="number"
              min="1"
              :max="MAX_COPIES"
              inputmode="numeric"
              class="input-narrow"
            />
          </div>
        </div>
        <fieldset class="copy-fields">
          <legend>Übernehmen</legend>
          <label v-for="c in choices" :key="c.key" class="copy-option">
            <input
              type="checkbox"
              :checked="c.locked || chosen.includes(c.key)"
              :disabled="c.locked"
              @change="toggle(c.key, $event.target.checked)"
            />
            {{ c.label }}
            <span v-if="c.locked" class="copy-hint">bestimmt den Nummernkreis</span>
          </label>
        </fieldset>
        <p v-if="error" class="form-error" role="alert">{{ error }}</p>
        <div class="dialog-actions">
          <button type="button" :disabled="saving" @click="emit('cancel')">Abbrechen</button>
          <button type="submit" class="btn-primary" :disabled="saving">
            {{
              saving ? "Kopiert …" : Number(count) > 1 ? `${count} Kopien anlegen` : "Kopie anlegen"
            }}
          </button>
        </div>
      </form>
    </dialog>
  </Teleport>
</template>

<style scoped>
.copy-dialog {
  border: none;
}

.copy-dialog::backdrop {
  background: var(--color-overlay);
}

.copy-dialog h2 {
  margin: 0 0 var(--space-2);
  font-size: 1.1rem;
}

.copy-lead {
  margin: 0 0 var(--space-3);
  color: var(--color-muted);
  font-size: 0.875rem;
}

.copy-row {
  display: flex;
  gap: var(--space-3);
  flex-wrap: wrap;
}

.copy-row .grow {
  flex: 1 1 14rem;
}

.copy-fields {
  margin: var(--space-2) 0 0;
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
}

.copy-fields legend {
  padding: 0 var(--space-1);
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--color-muted);
}

.copy-option {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-height: 44px;
}

.copy-option input {
  width: auto;
}

.copy-hint {
  font-size: 0.8125rem;
  color: var(--color-muted);
}

.dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
  margin-top: var(--space-4);
}

.dialog-actions button {
  min-height: 44px;
}
</style>
