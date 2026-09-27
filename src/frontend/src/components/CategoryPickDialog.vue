<script setup>
import { computed, ref, watch, nextTick } from "vue";

const props = defineProps({
  open: Boolean,
  mode: { type: String, default: "add" },
  categories: { type: Array, default: () => [] },
});
const emit = defineEmits(["confirm", "cancel"]);

const dialog = ref(null);
const chosen = ref([]);
const title = computed(() =>
  props.mode === "add" ? "Kategorien hinzufügen" : "Kategorien entfernen",
);
const confirmLabel = computed(() => (props.mode === "add" ? "Hinzufügen" : "Entfernen"));

// Reset the choice synchronously so it can never race with a user's click that
// happens before the dialog element itself has mounted (see the second watcher).
watch(
  () => props.open,
  (open) => {
    if (open) chosen.value = [];
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
    } else if (dialog.value.open) {
      dialog.value.close();
    }
  },
  { immediate: true },
);

function toggle(id, checked) {
  chosen.value = checked ? [...chosen.value, id] : chosen.value.filter((x) => x !== id);
}
</script>

<template>
  <dialog ref="dialog" class="dialog pick-dialog" @cancel.prevent="emit('cancel')">
    <h2>{{ title }}</h2>
    <fieldset>
      <legend class="sr-only">Kategorien</legend>
      <label v-for="c in categories" :key="c.id" class="pick-option">
        <input
          type="checkbox"
          :checked="chosen.includes(c.id)"
          @change="toggle(c.id, $event.target.checked)"
        />
        {{ c.label }}
      </label>
      <p v-if="!categories.length" class="text-muted">Noch keine Kategorien angelegt.</p>
    </fieldset>
    <div class="dialog-actions">
      <button type="button" class="dialog-cancel" @click="emit('cancel')">Abbrechen</button>
      <button
        type="button"
        class="btn-primary dialog-confirm"
        :disabled="!chosen.length"
        @click="emit('confirm', [...chosen])"
      >
        {{ confirmLabel }}
      </button>
    </div>
  </dialog>
</template>

<style scoped>
.pick-dialog {
  border: none;
}

.pick-dialog::backdrop {
  background: var(--color-overlay);
}

.pick-dialog h2 {
  margin: 0 0 var(--space-3);
  font-size: 1.1rem;
}

.pick-dialog fieldset {
  max-height: 50vh;
  overflow-y: auto;
  margin: 0;
  padding: 0;
  border: none;
}

.pick-option {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-height: 44px;
}

.pick-option input {
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
