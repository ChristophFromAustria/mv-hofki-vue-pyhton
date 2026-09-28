/** One-field-at-a-time inline editing with save state for a detail page. */
import { ref } from "vue";

export function useInlineEdit(save) {
  const editingKey = ref(null);
  const savingKey = ref(null);
  const savedKey = ref(null);
  const error = ref("");
  let savedTimer = null;

  function start(key) {
    editingKey.value = key;
    error.value = "";
  }

  function cancel() {
    editingKey.value = null;
    error.value = "";
  }

  async function commit(key, patch) {
    savingKey.value = key;
    error.value = "";
    try {
      await save(patch);
      editingKey.value = null;
      savedKey.value = key;
      clearTimeout(savedTimer);
      savedTimer = setTimeout(() => {
        if (savedKey.value === key) savedKey.value = null;
      }, 2000);
    } catch (e) {
      error.value = e?.message || "Speichern fehlgeschlagen.";
    } finally {
      savingKey.value = null;
    }
  }

  return { editingKey, savingKey, savedKey, error, start, cancel, commit };
}
