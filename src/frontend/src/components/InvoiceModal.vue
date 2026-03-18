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

const form = ref({
  amount: null,
  currency_id: null,
  date_issued: "",
  description: "",
  invoice_nr: "",
  invoice_issuer: "",
  issuer_address: "",
});

const isNew = computed(() => !props.invoice);

watch(
  () => props.open,
  (val) => {
    if (!val) return;
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
    amount: inv.amount,
    currency_id: inv.currency_id,
    date_issued: inv.date_issued || "",
    description: inv.description || "",
    invoice_nr: inv.invoice_nr || "",
    invoice_issuer: inv.invoice_issuer || "",
    issuer_address: inv.issuer_address || "",
  };
}

function resetForm() {
  form.value = {
    amount: null,
    currency_id: props.defaultCurrencyId,
    date_issued: "",
    description: "",
    invoice_nr: "",
    invoice_issuer: "",
    issuer_address: "",
  };
  errors.value = {};
}

function validate() {
  errors.value = {};
  if (!form.value.currency_id) errors.value.currency_id = "Pflichtfeld";
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
    emit("save", {
      id: props.invoice?.id,
      data: cleanPayload(),
      isNew: isNew.value || mode.value === "create",
    });
  } finally {
    saving.value = false;
  }
}

function triggerFileUpload() {
  fileInput.value?.click();
}

function onFileSelected(e) {
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
      <input
        ref="fileInput"
        type="file"
        accept="image/*,.pdf"
        style="display: none"
        @change="onFileSelected"
      />

      <div style="display: flex; justify-content: space-between; align-items: center">
        <h3>{{ isNew || mode === "create" ? "Neue Rechnung" : "Rechnung" }}</h3>
        <div v-if="mode === 'view'" style="display: flex; gap: 0.5rem">
          <button class="btn-sm" @click="mode = 'edit'">Bearbeiten</button>
          <button class="btn-sm btn-danger" @click="$emit('delete', invoice.id)">Löschen</button>
        </div>
      </div>

      <!-- View mode -->
      <template v-if="mode === 'view' && invoice">
        <dl class="detail-grid" style="margin-top: 1rem">
          <dt>Rechnungsnr.</dt>
          <dd>{{ invoice.invoice_nr || "—" }}</dd>
          <dt>Aussteller</dt>
          <dd>{{ invoice.invoice_issuer || "—" }}</dd>
          <dt>Adresse</dt>
          <dd>{{ invoice.issuer_address || "—" }}</dd>
          <dt>Datum</dt>
          <dd>{{ invoice.date_issued || "—" }}</dd>
          <dt>Betrag</dt>
          <dd>
            {{
              invoice.amount != null
                ? `${invoice.amount} ${invoice.currency?.abbreviation || ""}`
                : "—"
            }}
          </dd>
          <dt>Beschreibung</dt>
          <dd>{{ invoice.description || "—" }}</dd>
        </dl>

        <div style="margin-top: 1rem; border-top: 1px solid var(--color-border); padding-top: 1rem">
          <strong style="font-size: 0.85rem">Datei</strong>
          <div style="margin-top: 0.5rem">
            <template v-if="invoice.file_url">
              <a :href="invoice.file_url" target="_blank" class="btn-sm">Anzeigen / Download</a>
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
          <div class="grid grid-2">
            <div class="form-group">
              <label>Rechnungsnr.</label>
              <input v-model="form.invoice_nr" />
            </div>
            <div class="form-group">
              <label>Datum</label>
              <input v-model="form.date_issued" type="date" />
            </div>
            <div class="form-group">
              <label>Aussteller</label>
              <input v-model="form.invoice_issuer" />
            </div>
            <div class="form-group">
              <label>Adresse</label>
              <input v-model="form.issuer_address" />
            </div>
            <div class="form-group">
              <label>Betrag</label>
              <input v-model.number="form.amount" type="number" step="0.01" />
            </div>
            <div class="form-group" :class="{ error: errors.currency_id }">
              <label>Währung *</label>
              <select v-model.number="form.currency_id">
                <option :value="null" disabled>Auswählen...</option>
                <option v-for="c in currencies" :key="c.id" :value="c.id">
                  {{ c.label }} ({{ c.abbreviation }})
                </option>
              </select>
              <span v-if="errors.currency_id" class="form-error">{{ errors.currency_id }}</span>
            </div>
          </div>
          <div class="form-group">
            <label>Beschreibung</label>
            <textarea v-model="form.description" rows="2" />
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
