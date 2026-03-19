<script setup>
import { ref, watch, computed } from "vue";

const props = defineProps({
  open: Boolean,
  invoice: { type: Object, default: null },
  currencies: { type: Array, default: () => [] },
  instrumentId: { type: Number, required: true },
  defaultCurrencyId: { type: Number, default: null },
});

const emit = defineEmits(["save", "delete", "close"]);

const mode = ref("view"); // view | edit | create
const saving = ref(false);
const errors = ref({});
const fileInput = ref(null);
const pendingFile = ref(null);
const showCurrencyPicker = ref(false);

function todayStr() {
  return new Date().toISOString().slice(0, 10);
}

const form = ref({
  title: "",
  amount: null,
  currency_id: null,
  date_issued: "",
  description: "",
  invoice_issuer: "",
  issuer_address: "",
});

const isNew = computed(() => !props.invoice);

const selectedCurrency = computed(
  () => props.currencies.find((c) => c.id === form.value.currency_id) || null,
);

const currencyAbbr = computed(() => selectedCurrency.value?.abbreviation || "?");

watch(
  () => props.open,
  (val) => {
    if (!val) return;
    pendingFile.value = null;
    showCurrencyPicker.value = false;
    if (props.invoice) {
      mode.value = "view";
      fillForm(props.invoice);
    } else {
      mode.value = "create";
      resetForm();
    }
  },
);

function fillForm(inv) {
  form.value = {
    title: inv.title || "",
    amount: inv.amount,
    currency_id: inv.currency_id,
    date_issued: inv.date_issued || "",
    description: inv.description || "",
    invoice_issuer: inv.invoice_issuer || "",
    issuer_address: inv.issuer_address || "",
  };
}

function resetForm() {
  form.value = {
    title: "",
    amount: null,
    currency_id: props.defaultCurrencyId,
    date_issued: todayStr(),
    description: "",
    invoice_issuer: "",
    issuer_address: "",
  };
  errors.value = {};
  pendingFile.value = null;
}

function validate() {
  errors.value = {};
  if (!form.value.title?.trim()) errors.value.title = "Pflichtfeld";
  if (form.value.amount == null || form.value.amount === "") errors.value.amount = "Pflichtfeld";
  if (!form.value.currency_id) errors.value.currency_id = "Pflichtfeld";
  if (!form.value.date_issued) errors.value.date_issued = "Pflichtfeld";
  return Object.keys(errors.value).length === 0;
}

function cleanPayload() {
  const data = { ...form.value };
  for (const key of Object.keys(data)) {
    if (data[key] === "") data[key] = null;
  }
  return data;
}

async function save() {
  if (!validate()) return;
  saving.value = true;
  try {
    const file = pendingFile.value;
    emit("save", {
      id: props.invoice?.id,
      data: cleanPayload(),
      isNew: isNew.value || mode.value === "create",
      pendingFile: file,
    });
  } finally {
    saving.value = false;
  }
}

function pickCurrency(id) {
  form.value.currency_id = id;
  showCurrencyPicker.value = false;
}

function triggerFileUpload() {
  fileInput.value?.click();
}

function onFileSelectedForCreate(e) {
  const file = e.target.files?.[0];
  if (file) pendingFile.value = file;
  e.target.value = "";
}

function onFileSelectedForExisting(e) {
  const file = e.target.files?.[0];
  if (!file) return;
  const formData = new FormData();
  formData.append("file", file);
  emit("save", {
    id: props.invoice.id,
    file: formData,
    isFileUpload: true,
  });
  e.target.value = "";
}
</script>

<template>
  <div v-if="open" class="overlay" @click.self="$emit('close')">
    <div class="dialog" style="max-width: 600px; width: 90vw">
      <div style="display: flex; justify-content: space-between; align-items: center">
        <h3>
          {{ isNew || mode === "create" ? "Neue Rechnung" : `Rechnung #${invoice.invoice_nr}` }}
        </h3>
        <div v-if="mode === 'view'" style="display: flex; gap: 0.5rem">
          <button class="btn-sm" @click="mode = 'edit'">Bearbeiten</button>
          <button class="btn-sm btn-danger" @click="$emit('delete', invoice.id)">Löschen</button>
        </div>
      </div>

      <!-- View mode -->
      <template v-if="mode === 'view' && invoice">
        <dl class="detail-grid" style="margin-top: 1rem">
          <dt>Nr.</dt>
          <dd>{{ invoice.invoice_nr }}</dd>
          <dt>Bezeichnung</dt>
          <dd>{{ invoice.title }}</dd>
          <dt>Datum</dt>
          <dd>{{ invoice.date_issued }}</dd>
          <dt>Betrag</dt>
          <dd>{{ invoice.amount }} {{ invoice.currency?.abbreviation || "" }}</dd>
          <dt>Aussteller</dt>
          <dd>{{ invoice.invoice_issuer || "—" }}</dd>
          <dt>Adresse</dt>
          <dd style="white-space: pre-line">{{ invoice.issuer_address || "—" }}</dd>
          <dt>Beschreibung</dt>
          <dd>{{ invoice.description || "—" }}</dd>
        </dl>

        <div style="margin-top: 1rem; border-top: 1px solid var(--color-border); padding-top: 1rem">
          <input
            ref="fileInput"
            type="file"
            accept="image/*,.pdf"
            style="display: none"
            @change="onFileSelectedForExisting"
          />
          <strong style="font-size: 0.85rem">Datei</strong>
          <div style="margin-top: 0.5rem">
            <template v-if="invoice.file_url">
              <a :href="invoice.file_url" target="_blank" class="btn-sm"> Anzeigen / Download </a>
              <button class="btn-sm" style="margin-left: 0.5rem" @click="triggerFileUpload">
                Ersetzen
              </button>
            </template>
            <button v-else class="btn-sm" @click="triggerFileUpload">Datei hochladen</button>
          </div>
        </div>

        <div class="dialog-actions">
          <button @click="$emit('close')">Schließen</button>
        </div>
      </template>

      <!-- Edit / Create mode -->
      <template v-if="mode === 'edit' || mode === 'create'">
        <form style="margin-top: 1rem" @submit.prevent="save">
          <div class="form-group" :class="{ error: errors.title }">
            <label>Bezeichnung *</label>
            <input v-model="form.title" placeholder="z.B. Reparatur Ventile" />
            <span v-if="errors.title" class="form-error">{{ errors.title }}</span>
          </div>
          <div class="form-group" :class="{ error: errors.date_issued }">
            <label>Datum *</label>
            <input v-model="form.date_issued" type="date" />
            <span v-if="errors.date_issued" class="form-error">{{ errors.date_issued }}</span>
          </div>
          <div class="form-group" :class="{ error: errors.amount || errors.currency_id }">
            <label>
              Betrag ({{ currencyAbbr }}) *
              <button
                type="button"
                class="currency-edit-btn"
                title="Währung ändern"
                @click="showCurrencyPicker = !showCurrencyPicker"
              >
                <svg
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                >
                  <path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z" />
                  <path d="m15 5 4 4" />
                </svg>
              </button>
            </label>
            <div v-if="showCurrencyPicker" class="currency-picker">
              <button
                v-for="c in currencies"
                :key="c.id"
                type="button"
                :class="{ active: c.id === form.currency_id }"
                @click="pickCurrency(c.id)"
              >
                {{ c.abbreviation }} — {{ c.label }}
              </button>
            </div>
            <input v-model.number="form.amount" type="number" step="0.01" />
            <span v-if="errors.amount" class="form-error">{{ errors.amount }}</span>
            <span v-if="errors.currency_id" class="form-error">{{ errors.currency_id }}</span>
          </div>
          <div class="form-group">
            <label>Aussteller</label>
            <input v-model="form.invoice_issuer" />
          </div>
          <div class="form-group">
            <label>Adresse</label>
            <textarea v-model="form.issuer_address" rows="2" placeholder="Straße, PLZ Ort" />
          </div>
          <div class="form-group">
            <label>Beschreibung</label>
            <textarea v-model="form.description" rows="2" />
          </div>
          <div class="form-group">
            <label>Datei</label>
            <div v-if="pendingFile" style="display: flex; align-items: center; gap: 0.5rem">
              <span style="font-size: 0.85rem">{{ pendingFile.name }}</span>
              <button type="button" class="btn-sm" @click="pendingFile = null">Entfernen</button>
            </div>
            <input v-else type="file" accept="image/*,.pdf" @change="onFileSelectedForCreate" />
          </div>
          <div class="dialog-actions">
            <button type="button" @click="mode === 'create' ? $emit('close') : (mode = 'view')">
              Abbrechen
            </button>
            <button type="submit" class="btn-primary" :disabled="saving">Speichern</button>
          </div>
        </form>
      </template>
    </div>
  </div>
</template>

<style scoped>
.currency-edit-btn {
  background: none;
  border: none;
  cursor: pointer;
  color: var(--color-muted);
  padding: 0 0.25rem;
  vertical-align: middle;
  display: inline-flex;
  align-items: center;
}

.currency-edit-btn:hover {
  color: var(--color-primary);
  background: none;
}

.currency-picker {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
  flex-wrap: wrap;
}

.currency-picker button {
  padding: 0.3rem 0.75rem;
  border: 1px solid var(--color-border);
  border-radius: 4px;
  background: var(--color-bg-soft);
  cursor: pointer;
  font-size: 0.85rem;
}

.currency-picker button:hover {
  border-color: var(--color-primary);
}

.currency-picker button.active {
  background: var(--color-primary);
  color: white;
  border-color: var(--color-primary);
}
</style>
