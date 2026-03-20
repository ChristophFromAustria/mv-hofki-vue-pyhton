<script setup>
import { ref, watch, computed } from "vue";
import { get, post, put } from "../lib/api.js";
import { CATEGORIES } from "../lib/categories.js";

const props = defineProps({
  open: Boolean,
  category: { type: String, required: true },
  itemId: { type: Number, default: null },
  currencies: { type: Array, default: () => [] },
});

const emit = defineEmits(["save", "close"]);

const cat = computed(() => CATEGORIES[props.category]);
const saving = ref(false);
const errors = ref({});
const typeOptions = ref([]);
const genreOptions = ref([]);
const showCurrencyPicker = ref(false);

const currentYear = new Date().getFullYear();
const yearOptions = [];
for (let y = currentYear; y >= 1950; y--) {
  yearOptions.push(y);
}

const form = ref({});

function defaultForm() {
  const euroCurrency = props.currencies.find((c) => c.abbreviation === "€");
  return {
    label: "",
    instrument_type_id: null,
    clothing_type_id: null,
    serial_nr: "",
    manufacturer: "",
    construction_year: currentYear,
    distributor: "",
    container: "",
    particularities: "",
    size: "",
    gender: "",
    composer: "",
    arranger: "",
    difficulty: "",
    genre_id: null,
    storage_location: "",
    owner: "MV Hofkirchen",
    acquisition_date: "",
    acquisition_cost: null,
    currency_id: euroCurrency?.id || null,
    notes: "",
  };
}

const selectedCurrency = computed(
  () => props.currencies.find((c) => c.id === form.value.currency_id) || null,
);
const currencyAbbr = computed(() => selectedCurrency.value?.abbreviation || "?");

const isEdit = computed(() => props.itemId != null);

async function loadTypeOptions() {
  const c = cat.value;
  if (c.labelField === "dropdown" && c.typeEndpoint) {
    typeOptions.value = await get(c.typeEndpoint);
  }
  if (props.category === "sheet_music") {
    genreOptions.value = await get("/sheet-music-genres");
  }
}

watch(
  () => props.open,
  async (val) => {
    if (!val) return;
    errors.value = {};
    showCurrencyPicker.value = false;
    await loadTypeOptions();

    if (isEdit.value) {
      const item = await get(`/items/${props.itemId}`);
      form.value = {
        label: item.label || "",
        instrument_type_id: item.instrument_type_id || null,
        clothing_type_id: item.clothing_type_id || null,
        serial_nr: item.serial_nr || "",
        manufacturer: item.manufacturer || "",
        construction_year: item.construction_year || currentYear,
        distributor: item.distributor || "",
        container: item.container || "",
        particularities: item.particularities || "",
        size: item.size || "",
        gender: item.gender || "",
        composer: item.composer || "",
        arranger: item.arranger || "",
        difficulty: item.difficulty || "",
        genre_id: item.genre_id || null,
        storage_location: item.storage_location || "",
        owner: item.owner || "MV Hofkirchen",
        acquisition_date: item.acquisition_date || "",
        acquisition_cost: item.acquisition_cost,
        currency_id: item.currency_id || defaultForm().currency_id,
        notes: item.notes || "",
      };
    } else {
      form.value = defaultForm();
    }
  },
);

function onTypeChange(e) {
  const id = parseInt(e.target.value);
  const c = cat.value;
  form.value[c.typeIdField] = id || null;
  const selected = typeOptions.value.find((t) => t.id === id);
  form.value.label = selected ? selected.label : "";
}

function pickCurrency(id) {
  form.value.currency_id = id;
  showCurrencyPicker.value = false;
}

function validate() {
  errors.value = {};
  const c = cat.value;
  if (c.labelField === "dropdown") {
    if (!form.value[c.typeIdField]) errors.value.type = "Pflichtfeld";
  } else {
    if (!form.value.label?.trim()) errors.value.label = "Pflichtfeld";
  }
  if (!form.value.owner?.trim()) errors.value.owner = "Pflichtfeld";
  return Object.keys(errors.value).length === 0;
}

function buildPayload() {
  const c = cat.value;
  const data = { category: props.category };

  // Label
  data.label = form.value.label;

  // Type ID for dropdown categories
  if (c.labelField === "dropdown" && c.typeIdField) {
    data[c.typeIdField] = form.value[c.typeIdField];
  }

  // Common fields
  data.owner = form.value.owner || null;
  data.acquisition_date = form.value.acquisition_date || null;
  data.acquisition_cost = form.value.acquisition_cost;
  data.currency_id = form.value.currency_id || null;
  data.notes = form.value.notes || null;

  // Category-specific fields
  if (props.category === "instrument") {
    data.serial_nr = form.value.serial_nr || null;
    data.manufacturer = form.value.manufacturer || null;
    data.construction_year = form.value.construction_year || null;
    data.distributor = form.value.distributor || null;
    data.container = form.value.container || null;
    data.particularities = form.value.particularities || null;
  } else if (props.category === "clothing") {
    data.size = form.value.size || null;
    data.gender = form.value.gender || null;
  } else if (props.category === "sheet_music") {
    data.composer = form.value.composer || null;
    data.arranger = form.value.arranger || null;
    data.difficulty = form.value.difficulty || null;
    data.genre_id = form.value.genre_id || null;
    data.storage_location = form.value.storage_location || null;
  } else if (props.category === "general_item") {
    data.manufacturer = form.value.manufacturer || null;
    data.storage_location = form.value.storage_location || null;
  }

  return data;
}

async function save() {
  if (!validate()) return;
  saving.value = true;
  try {
    if (isEdit.value) {
      await put(`/items/${props.itemId}`, buildPayload());
    } else {
      await post("/items", buildPayload());
    }
    emit("save");
    emit("close");
  } catch (e) {
    alert("Fehler: " + e.message);
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <div v-if="open" class="overlay" @click.self="$emit('close')">
    <div
      class="dialog"
      style="max-width: 700px; width: 90vw; max-height: 90vh; display: flex; flex-direction: column"
    >
      <div style="display: flex; justify-content: space-between; align-items: center">
        <h3>
          {{ isEdit ? cat.labelSingular + " bearbeiten" : cat.labelSingular + " anlegen" }}
        </h3>
      </div>

      <form
        style="margin-top: 1rem; display: flex; flex-direction: column; overflow: hidden; flex: 1"
        @submit.prevent="save"
      >
        <div style="overflow-y: auto; flex: 1; padding-bottom: 0.5rem">
          <!-- Label field: dropdown or text -->
          <div
            v-if="cat.labelField === 'dropdown'"
            class="form-group"
            :class="{ error: errors.type }"
          >
            <label>{{ cat.labelFieldName }} *</label>
            <select :value="form[cat.typeIdField]" @change="onTypeChange">
              <option :value="null" disabled>Auswählen...</option>
              <option v-for="t in typeOptions" :key="t.id" :value="t.id">
                {{ t.label }}
              </option>
            </select>
            <span v-if="errors.type" class="form-error">{{ errors.type }}</span>
          </div>

          <div v-if="cat.labelField === 'text'" class="form-group" :class="{ error: errors.label }">
            <label>{{ cat.labelFieldName }} *</label>
            <input v-model="form.label" />
            <span v-if="errors.label" class="form-error">{{ errors.label }}</span>
          </div>

          <!-- Instrument-specific fields -->
          <template v-if="category === 'instrument'">
            <div class="form-group">
              <label>Seriennummer</label>
              <input v-model="form.serial_nr" />
            </div>
            <div class="form-group">
              <label>Hersteller</label>
              <input v-model="form.manufacturer" />
            </div>
            <div class="form-group">
              <label>Baujahr</label>
              <select v-model.number="form.construction_year">
                <option v-for="y in yearOptions" :key="y" :value="y">{{ y }}</option>
              </select>
            </div>
            <div class="form-group">
              <label>Händler</label>
              <input v-model="form.distributor" />
            </div>
            <div class="form-group">
              <label>Behältnis</label>
              <input v-model="form.container" />
            </div>
            <div class="form-group">
              <label>Besonderheiten</label>
              <input v-model="form.particularities" />
            </div>
          </template>

          <!-- Clothing-specific fields -->
          <template v-if="category === 'clothing'">
            <div class="form-group">
              <label>Größe</label>
              <input v-model="form.size" />
            </div>
            <div class="form-group">
              <label>Geschlecht</label>
              <select v-model="form.gender">
                <option value="">—</option>
                <option value="Herren">Herren</option>
                <option value="Damen">Damen</option>
              </select>
            </div>
          </template>

          <!-- Sheet music-specific fields -->
          <template v-if="category === 'sheet_music'">
            <div class="form-group">
              <label>Komponist</label>
              <input v-model="form.composer" />
            </div>
            <div class="form-group">
              <label>Arrangeur</label>
              <input v-model="form.arranger" />
            </div>
            <div class="form-group">
              <label>Schwierigkeitsgrad</label>
              <input v-model="form.difficulty" />
            </div>
            <div class="form-group">
              <label>Gattung</label>
              <select v-model.number="form.genre_id">
                <option :value="null">—</option>
                <option v-for="g in genreOptions" :key="g.id" :value="g.id">
                  {{ g.label }}
                </option>
              </select>
            </div>
            <div class="form-group">
              <label>Lagerort</label>
              <input v-model="form.storage_location" />
            </div>
          </template>

          <!-- General item-specific fields -->
          <template v-if="category === 'general_item'">
            <div class="form-group">
              <label>Hersteller</label>
              <input v-model="form.manufacturer" />
            </div>
            <div class="form-group">
              <label>Lagerort</label>
              <input v-model="form.storage_location" />
            </div>
          </template>

          <!-- Common fields -->
          <div class="form-group" :class="{ error: errors.owner }">
            <label>Eigentümer *</label>
            <input v-model="form.owner" />
            <span v-if="errors.owner" class="form-error">{{ errors.owner }}</span>
          </div>
          <div class="form-group">
            <label>Anschaffungsdatum</label>
            <input v-model="form.acquisition_date" type="date" />
          </div>
          <div class="form-group">
            <label>
              Anschaffungskosten ({{ currencyAbbr }})
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
            <input v-model.number="form.acquisition_cost" type="number" step="0.01" />
          </div>
          <div class="form-group">
            <label>Notizen</label>
            <textarea v-model="form.notes" rows="3" />
          </div>
        </div>

        <div
          class="dialog-actions"
          style="
            border-top: 1px solid var(--color-border);
            padding-top: 0.75rem;
            margin-top: 0.5rem;
            flex-shrink: 0;
          "
        >
          <button type="button" @click="$emit('close')">Abbrechen</button>
          <button type="submit" class="btn-primary" :disabled="saving">Speichern</button>
        </div>
      </form>
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
