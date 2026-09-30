<script setup>
import { nextTick, ref, watch } from "vue";
import { post } from "../lib/api.js";
import { guessName } from "../lib/names.js";

// Quick "new musician" from a person picker: just the name (and extern);
// everything else can be filled in on the musician page later.
const props = defineProps({
  open: Boolean,
  // What was typed into the picker, used as a first guess for the name.
  initialText: { type: String, default: "" },
});
const emit = defineEmits(["created", "cancel"]);

const dialog = ref(null);
const firstInput = ref(null);
const form = ref({ first_name: "", last_name: "", is_extern: false });
const errors = ref({});
const error = ref("");
const saving = ref(false);
const titleId = `musician-create-${Math.random().toString(36).slice(2, 7)}`;

watch(
  () => props.open,
  (open) => {
    if (open) {
      form.value = { ...guessName(props.initialText), is_extern: false };
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
      firstInput.value?.focus();
    } else if (dialog.value.open) {
      dialog.value.close();
    }
  },
  { immediate: true },
);

function swap() {
  const { first_name, last_name } = form.value;
  form.value = { ...form.value, first_name: last_name, last_name: first_name };
}

async function save() {
  errors.value = {};
  error.value = "";
  const first = form.value.first_name.trim();
  const last = form.value.last_name.trim();
  if (!first) errors.value.first_name = "Pflichtfeld";
  if (!last) errors.value.last_name = "Pflichtfeld";
  if (Object.keys(errors.value).length) return;
  saving.value = true;
  try {
    const musician = await post("/musicians", {
      first_name: first,
      last_name: last,
      is_extern: form.value.is_extern,
    });
    emit("created", musician);
  } catch (e) {
    error.value = "Anlegen fehlgeschlagen: " + e.message;
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <Teleport to="body">
    <dialog
      ref="dialog"
      class="dialog musician-create-dialog"
      :aria-labelledby="titleId"
      @cancel.prevent="emit('cancel')"
    >
      <form novalidate @submit.prevent="save">
        <h2 :id="titleId">Neuer Musiker</h2>
        <div class="form-group" :class="{ error: errors.first_name }">
          <label for="mc-first">Vorname *</label>
          <input
            id="mc-first"
            ref="firstInput"
            v-model="form.first_name"
            autocomplete="off"
            :aria-invalid="errors.first_name ? 'true' : undefined"
          />
          <span v-if="errors.first_name" class="form-error">{{ errors.first_name }}</span>
        </div>
        <div class="form-group" :class="{ error: errors.last_name }">
          <label for="mc-last">Nachname *</label>
          <input
            id="mc-last"
            v-model="form.last_name"
            autocomplete="off"
            :aria-invalid="errors.last_name ? 'true' : undefined"
          />
          <span v-if="errors.last_name" class="form-error">{{ errors.last_name }}</span>
        </div>
        <button type="button" class="btn-sm musician-create-swap" @click="swap">
          Vor- und Nachname tauschen
        </button>
        <label class="checkbox-option musician-create-extern">
          <input v-model="form.is_extern" type="checkbox" />
          Extern
        </label>
        <p v-if="error" class="form-error" role="alert">{{ error }}</p>
        <div class="dialog-actions">
          <button type="button" :disabled="saving" @click="emit('cancel')">Abbrechen</button>
          <button type="submit" class="btn-primary" :disabled="saving">
            {{ saving ? "Legt an …" : "Anlegen" }}
          </button>
        </div>
      </form>
    </dialog>
  </Teleport>
</template>

<style scoped>
.musician-create-dialog {
  border: none;
}

.musician-create-dialog::backdrop {
  background: var(--color-overlay);
}

.musician-create-dialog h2 {
  margin: 0 0 var(--space-3);
  font-size: 1.1rem;
}

.musician-create-swap {
  margin-bottom: var(--space-3);
}

.musician-create-extern {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-height: 44px;
}

.musician-create-extern input {
  width: auto;
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
