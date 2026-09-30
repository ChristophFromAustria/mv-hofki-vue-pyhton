<script setup>
import { nextTick, ref, watch } from "vue";
import { post } from "../lib/api.js";
import { RETIRE_REASONS } from "../lib/retire.js";
import { todayIso } from "../lib/loans.js";

// "Ausscheiden": the item leaves the stock (sold, lost, …) but keeps its
// history and number. Can be undone with "Wieder in Bestand".
const props = defineProps({
  open: Boolean,
  item: { type: Object, required: true },
});
const emit = defineEmits(["retired", "cancel"]);

const dialog = ref(null);
const reasonSelect = ref(null);
const form = ref({ reason: "", retired_at: todayIso(), notes: "" });
const errors = ref({});
const error = ref("");
const saving = ref(false);
const titleId = `retire-${Math.random().toString(36).slice(2, 7)}`;

watch(
  () => props.open,
  (open) => {
    if (open) {
      form.value = { reason: "", retired_at: todayIso(), notes: "" };
      errors.value = {};
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
      reasonSelect.value?.focus();
    } else if (dialog.value.open) {
      dialog.value.close();
    }
  },
  { immediate: true },
);

async function save() {
  errors.value = {};
  error.value = "";
  if (!form.value.reason) errors.value.reason = "Bitte einen Grund wählen";
  if (!form.value.retired_at) errors.value.retired_at = "Pflichtfeld";
  if (Object.keys(errors.value).length) return;
  saving.value = true;
  try {
    const item = await post(`/items/${props.item.id}/retire`, {
      reason: form.value.reason,
      retired_at: form.value.retired_at,
      notes: form.value.notes || null,
    });
    emit("retired", item);
  } catch (e) {
    error.value = "Ausscheiden nicht möglich: " + e.message;
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <Teleport to="body">
    <dialog
      ref="dialog"
      class="dialog dialog-md retire-dialog"
      :aria-labelledby="titleId"
      @cancel.prevent="emit('cancel')"
    >
      <form novalidate @submit.prevent="save">
        <h2 :id="titleId">{{ item.display_nr }} ausscheiden</h2>
        <p class="retire-lead">
          Der Gegenstand verlässt den Bestand, bleibt aber mit Nummer und Historie erhalten. „Wieder
          in Bestand“ macht das rückgängig.
        </p>
        <div class="form-group" :class="{ error: errors.reason }">
          <label for="retire-reason">Grund *</label>
          <select id="retire-reason" ref="reasonSelect" v-model="form.reason">
            <option value="" disabled>Bitte wählen …</option>
            <option v-for="r in RETIRE_REASONS" :key="r.value" :value="r.value">
              {{ r.label }}
            </option>
          </select>
          <span v-if="errors.reason" class="form-error">{{ errors.reason }}</span>
        </div>
        <div class="form-group" :class="{ error: errors.retired_at }">
          <label for="retire-date">Datum *</label>
          <input id="retire-date" v-model="form.retired_at" type="date" class="input-narrow" />
          <span v-if="errors.retired_at" class="form-error">{{ errors.retired_at }}</span>
        </div>
        <div class="form-group">
          <label for="retire-notes">Notiz</label>
          <textarea
            id="retire-notes"
            v-model="form.notes"
            rows="3"
            maxlength="1000"
            placeholder="z. B. an wen verkauft, Preis, Schadensmeldung …"
          />
        </div>
        <p v-if="error" class="form-error" role="alert">{{ error }}</p>
        <div class="dialog-actions">
          <button type="button" :disabled="saving" @click="emit('cancel')">Abbrechen</button>
          <button type="submit" class="btn-primary" :disabled="saving">
            {{ saving ? "Speichert …" : "Ausscheiden" }}
          </button>
        </div>
      </form>
    </dialog>
  </Teleport>
</template>

<style scoped>
.retire-dialog {
  border: none;
}

.retire-dialog::backdrop {
  background: var(--color-overlay);
}

.retire-dialog h2 {
  margin: 0 0 var(--space-2);
  font-size: 1.1rem;
}

.retire-lead {
  margin: 0 0 var(--space-3);
  color: var(--color-muted);
  font-size: 0.875rem;
}

.retire-dialog textarea {
  width: 100%;
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
