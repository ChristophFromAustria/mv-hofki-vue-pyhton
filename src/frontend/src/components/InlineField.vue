<script setup>
import { computed, nextTick, ref, watch } from "vue";
import TagSelect from "./TagSelect.vue";
import { formatDate, formatMoney } from "../lib/format.js";

const props = defineProps({
  fieldKey: { type: String, required: true },
  label: { type: String, required: true },
  type: { type: String, default: "text" },
  value: { type: [String, Number, Boolean, Array, Object], default: null },
  options: { type: Array, default: () => [] },
  required: Boolean,
  min: { type: Number, default: null },
  max: { type: Number, default: null },
  placeholder: { type: String, default: "" },
  createOption: { type: Function, default: null },
  currencies: { type: Array, default: () => [] },
  editing: Boolean,
  saving: Boolean,
  saved: Boolean,
  error: { type: String, default: "" },
});
const emit = defineEmits(["start", "cancel", "save"]);

const inputId = `inline-${props.fieldKey}-${Math.random().toString(36).slice(2, 7)}`;
const draft = ref(null);
const localError = ref("");
const editor = ref(null);
const editButton = ref(null);

const optionLabel = (v) => props.options.find((o) => String(o.value) === String(v))?.label;

const display = computed(() => {
  const v = props.value;
  switch (props.type) {
    case "bool":
      return v ? "Ja" : "Nein";
    case "select":
      return v === null || v === undefined || v === "" ? "—" : (optionLabel(v) ?? String(v));
    case "multiselect":
      return v?.length ? v.map((x) => optionLabel(x) ?? x).join(", ") : "—";
    case "date":
      return formatDate(v);
    case "money": {
      const abbr = props.currencies.find((c) => c.id === v?.currency_id)?.abbreviation;
      return formatMoney(v?.amount, abbr);
    }
    default:
      return v === null || v === undefined || v === "" ? "—" : String(v);
  }
});

function initialDraft() {
  const v = props.value;
  if (props.type === "money") return { amount: v?.amount ?? "", currency_id: v?.currency_id ?? "" };
  if (props.type === "multiselect" || props.type === "tags") return [...(v || [])];
  if (props.type === "bool") return !!v;
  return v ?? "";
}

watch(
  () => props.editing,
  async (editing) => {
    localError.value = "";
    if (editing) {
      draft.value = initialDraft();
      await nextTick();
      editor.value?.querySelector("input, select, textarea")?.focus();
    } else {
      await nextTick();
      editButton.value?.focus?.();
    }
  },
  { immediate: true },
);

function parsed() {
  const d = draft.value;
  switch (props.type) {
    case "number": {
      if (d === "" || d === null)
        return props.required ? { error: "Pflichtfeld" } : { value: null };
      const n = Number(d);
      if (!Number.isInteger(n)) return { error: "Bitte eine ganze Zahl eingeben." };
      if (props.min !== null && n < props.min) return { error: `Mindestens ${props.min}` };
      if (props.max !== null && n > props.max) return { error: `Höchstens ${props.max}` };
      return { value: n };
    }
    case "select":
      if (d === "" || d === null)
        return props.required ? { error: "Pflichtfeld" } : { value: null };
      return { value: props.options.find((o) => String(o.value) === String(d))?.value ?? d };
    case "bool":
      return { value: !!d };
    case "multiselect":
    case "tags":
      return { value: [...d] };
    case "money": {
      const amount = d.amount === "" || d.amount === null ? null : Number(d.amount);
      const currency =
        d.currency_id === "" || d.currency_id === null ? null : Number(d.currency_id);
      if (amount !== null && Number.isNaN(amount)) return { error: "Bitte einen Betrag eingeben." };
      if (amount !== null && currency === null) return { error: "Bitte eine Währung wählen." };
      return { value: { amount, currency_id: currency } };
    }
    default: {
      const s = typeof d === "string" ? d.trim() : d;
      if (!s) return props.required ? { error: "Pflichtfeld" } : { value: null };
      return { value: props.type === "textarea" ? d : s };
    }
  }
}

function submit() {
  const result = parsed();
  if (result.error) {
    localError.value = result.error;
    return;
  }
  localError.value = "";
  emit("save", result.value);
}

function onKeydown(e) {
  if (e.key === "Escape") {
    e.preventDefault();
    emit("cancel");
  } else if (e.key === "Enter") {
    if (props.type === "textarea" && !(e.ctrlKey || e.metaKey)) return;
    if (props.type === "tags" || props.type === "multiselect") return;
    e.preventDefault();
    submit();
  }
}

function toggleMulti(value, checked) {
  draft.value = checked ? [...draft.value, value] : draft.value.filter((x) => x !== value);
}

const shownError = computed(() => localError.value || props.error);
</script>

<template>
  <dt>
    <label v-if="editing && !['multiselect', 'bool', 'tags'].includes(type)" :for="inputId">{{
      label
    }}</label>
    <template v-else>{{ label }}</template>
  </dt>
  <dd class="inline-field" :class="{ 'is-editing': editing }">
    <template v-if="!editing">
      <span class="inline-value">
        <slot name="display" :value="value">{{ display }}</slot>
      </span>
      <button
        ref="editButton"
        type="button"
        class="inline-edit-btn"
        :aria-label="`„${label}“ bearbeiten`"
        :disabled="saving"
        @click="emit('start')"
      >
        <span aria-hidden="true">✎</span>
      </button>
      <span v-if="saving" class="inline-status">Speichert …</span>
      <span v-else-if="saved" class="inline-status inline-saved" role="status">Gespeichert</span>
    </template>

    <div v-else ref="editor" class="inline-editor" @keydown="onKeydown">
      <textarea
        v-if="type === 'textarea'"
        :id="inputId"
        v-model="draft"
        rows="3"
        :placeholder="placeholder"
      />
      <input
        v-else-if="type === 'number'"
        :id="inputId"
        v-model="draft"
        type="number"
        inputmode="numeric"
        :min="min ?? undefined"
        :max="max ?? undefined"
        step="1"
        class="input-narrow"
      />
      <input
        v-else-if="type === 'date'"
        :id="inputId"
        v-model="draft"
        type="date"
        class="input-narrow"
      />
      <select v-else-if="type === 'select'" :id="inputId" v-model="draft">
        <option v-if="!required" value="">—</option>
        <option v-for="o in options" :key="String(o.value)" :value="o.value">{{ o.label }}</option>
      </select>
      <label v-else-if="type === 'bool'" class="inline-check">
        <input v-model="draft" type="checkbox" />
        {{ label }}
      </label>
      <fieldset v-else-if="type === 'multiselect'" class="inline-multi">
        <legend class="sr-only">{{ label }}</legend>
        <label v-for="o in options" :key="String(o.value)" class="inline-check">
          <input
            type="checkbox"
            :checked="draft.includes(o.value)"
            @change="toggleMulti(o.value, $event.target.checked)"
          />
          {{ o.label }}
        </label>
      </fieldset>
      <TagSelect
        v-else-if="type === 'tags'"
        v-model="draft"
        :options="options.map((o) => ({ id: o.value, label: o.label }))"
        :label="label"
        :create-option="createOption"
      />
      <div v-else-if="type === 'money'" class="inline-money">
        <input
          :id="inputId"
          v-model="draft.amount"
          type="number"
          step="0.01"
          min="0"
          class="input-narrow"
          :aria-label="`${label}: Betrag`"
        />
        <select v-model="draft.currency_id" :aria-label="`${label}: Währung`">
          <option value="">—</option>
          <option v-for="c in currencies" :key="c.id" :value="c.id">{{ c.abbreviation }}</option>
        </select>
      </div>
      <input v-else :id="inputId" v-model="draft" type="text" :placeholder="placeholder" />

      <div class="inline-actions">
        <button
          type="button"
          class="btn-sm btn-primary inline-save"
          :disabled="saving"
          @click="submit"
        >
          {{ saving ? "Speichert …" : "Speichern" }}
        </button>
        <button
          type="button"
          class="btn-sm inline-cancel"
          :disabled="saving"
          @click="emit('cancel')"
        >
          Abbrechen
        </button>
      </div>
      <p v-if="shownError" class="form-error" role="alert">{{ shownError }}</p>
    </div>
  </dd>
</template>

<style scoped>
.inline-field {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2);
  min-height: 44px;
}

.inline-value {
  flex: 1 1 auto;
  min-width: 0;
}

.inline-edit-btn {
  display: inline-grid;
  place-items: center;
  width: 44px;
  height: 44px;
  padding: 0;
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-muted);
  cursor: pointer;
}

.inline-edit-btn:hover,
.inline-edit-btn:focus-visible {
  border-color: var(--color-border);
  color: var(--color-primary);
}

.inline-status {
  font-size: 0.8125rem;
  color: var(--color-muted);
}

.inline-saved {
  color: var(--color-success);
}

.inline-editor {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  width: 100%;
}

.inline-actions {
  display: flex;
  gap: var(--space-2);
}

.inline-actions .btn-sm {
  min-height: 44px;
}

.inline-check {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-height: 44px;
}

.inline-check input {
  width: auto;
}

.inline-multi {
  margin: 0;
  padding: 0;
  border: none;
}

.inline-money {
  display: flex;
  gap: var(--space-2);
}

.inline-money select {
  width: auto;
}
</style>
