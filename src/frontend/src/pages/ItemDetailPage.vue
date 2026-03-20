<script setup>
import { ref, computed, onMounted, watch } from "vue";
import { useRouter } from "vue-router";
import { get, post, put, del } from "../lib/api.js";
import { CATEGORIES } from "../lib/categories.js";
import ConfirmDialog from "../components/ConfirmDialog.vue";
import ImageGallery from "../components/ImageGallery.vue";
import InvoiceModal from "../components/InvoiceModal.vue";
import ItemFormModal from "../components/ItemFormModal.vue";

const props = defineProps({
  category: { type: String, required: true },
  id: { type: [String, Number], required: true },
});

const router = useRouter();
const cat = computed(() => CATEGORIES[props.category]);
const item = ref(null);
const loans = ref([]);
const musicians = ref([]);
const images = ref([]);
const currencies = ref([]);
const invoices = ref([]);
const showDelete = ref(false);
const showEditModal = ref(false);

// Loan form state
const loanForm = ref({ musician_id: null, start_date: "" });
const loanSaving = ref(false);
const loanErrors = ref({});

// Return state
const showReturnDatePicker = ref(false);
const returnDate = ref("");

// Invoice modal state
const showInvoiceModal = ref(false);
const selectedInvoice = ref(null);

const activeLoan = computed(() => loans.value.find((l) => !l.end_date));
const defaultCurrencyId = computed(() => {
  if (item.value?.currency_id) return item.value.currency_id;
  const euro = currencies.value.find((c) => c.abbreviation === "€");
  return euro?.id || currencies.value[0]?.id || null;
});

async function reload() {
  item.value = await get(`/items/${props.id}`);
  images.value = await get(`/items/${props.id}/images`);
  if (cat.value.hasLoans) {
    loans.value = await get(`/loans?item_id=${props.id}`);
  }
  if (cat.value.hasInvoices) {
    invoices.value = await get(`/items/${props.id}/invoices`);
  }
}

async function uploadImage(file) {
  const formData = new FormData();
  formData.append("file", file);
  await fetch(`/api/v1/items/${props.id}/images`, {
    method: "POST",
    body: formData,
  });
  await reload();
}

async function setProfile(imageId) {
  await put(`/items/${props.id}/images/${imageId}/profile`);
  await reload();
}

async function deleteImage(imageId) {
  await del(`/items/${props.id}/images/${imageId}`);
  await reload();
}

onMounted(async () => {
  const promises = [get("/currencies")];
  if (cat.value.hasLoans) {
    promises.push(get("/musicians?limit=200"));
  }
  const results = await Promise.all(promises);
  currencies.value = results[0];
  if (cat.value.hasLoans && results[1]) {
    musicians.value = results[1].items;
  }
  await reload();
});

// Reload when navigating between items of the same category
watch(
  () => props.id,
  () => reload(),
);

async function remove() {
  await del(`/items/${props.id}`);
  router.push(cat.value.routeBase);
}

function validateLoan() {
  loanErrors.value = {};
  if (!loanForm.value.musician_id) loanErrors.value.musician_id = "Pflichtfeld";
  if (!loanForm.value.start_date) loanErrors.value.start_date = "Pflichtfeld";
  return Object.keys(loanErrors.value).length === 0;
}

async function createLoan() {
  if (!validateLoan()) return;
  loanSaving.value = true;
  try {
    await post("/loans", {
      item_id: parseInt(props.id),
      ...loanForm.value,
    });
    loanForm.value = { musician_id: null, start_date: "" };
    loanErrors.value = {};
    await reload();
  } catch (e) {
    alert("Fehler: " + e.message);
  } finally {
    loanSaving.value = false;
  }
}

async function returnToday() {
  await put(`/loans/${activeLoan.value.id}/return`);
  showReturnDatePicker.value = false;
  await reload();
}

async function returnWithDate() {
  if (!returnDate.value) return;
  await put(`/loans/${activeLoan.value.id}/return`, { end_date: returnDate.value });
  showReturnDatePicker.value = false;
  returnDate.value = "";
  await reload();
}

// Invoice functions
function openInvoice(inv) {
  selectedInvoice.value = inv;
  showInvoiceModal.value = true;
}

function newInvoice() {
  selectedInvoice.value = null;
  showInvoiceModal.value = true;
}

async function handleInvoiceSave(evt) {
  const base = `/items/${props.id}/invoices`;
  try {
    if (evt.isFileUpload) {
      await fetch(`/api/v1${base}/${evt.id}/file`, {
        method: "POST",
        body: evt.file,
      });
      await reload();
      selectedInvoice.value = invoices.value.find((i) => i.id === evt.id) || null;
      return;
    }

    let created;
    if (evt.isNew) {
      created = await post(base, evt.data);
      if (evt.pendingFile) {
        const formData = new FormData();
        formData.append("file", evt.pendingFile);
        await fetch(`/api/v1${base}/${created.id}/file`, {
          method: "POST",
          body: formData,
        });
      }
    } else {
      await put(`${base}/${evt.id}`, evt.data);
      if (evt.pendingFile) {
        const formData = new FormData();
        formData.append("file", evt.pendingFile);
        await fetch(`/api/v1${base}/${evt.id}/file`, {
          method: "POST",
          body: formData,
        });
      }
    }
    await reload();
    showInvoiceModal.value = false;
  } catch (e) {
    alert("Fehler: " + e.message);
  }
}

async function handleInvoiceDelete(invoiceId) {
  if (!confirm("Rechnung wirklich löschen?")) return;
  await del(`/items/${props.id}/invoices/${invoiceId}`);
  showInvoiceModal.value = false;
  await reload();
}

async function onEditSave() {
  await reload();
}
</script>

<template>
  <div v-if="item">
    <div class="page-header">
      <h1>{{ item.display_nr }} — {{ item.label }}</h1>
      <div style="display: flex; gap: 0.5rem">
        <button class="btn" @click="showEditModal = true">Bearbeiten</button>
        <button class="btn-danger" @click="showDelete = true">Löschen</button>
      </div>
    </div>

    <div class="card" style="margin-bottom: 1.5rem">
      <ImageGallery
        :images="images"
        :can-upload="true"
        :can-manage="true"
        @upload="uploadImage"
        @set-profile="setProfile"
        @delete="deleteImage"
      />
    </div>

    <div class="card" style="margin-bottom: 1.5rem">
      <dl class="detail-grid">
        <dt>Inventarnummer</dt>
        <dd>{{ item.display_nr }}</dd>
        <dt>Bezeichnung</dt>
        <dd>{{ item.label }}</dd>

        <!-- Instrument-specific -->
        <template v-if="category === 'instrument'">
          <dt>Seriennummer</dt>
          <dd>{{ item.serial_nr || "—" }}</dd>
          <dt>Hersteller</dt>
          <dd>{{ item.manufacturer || "—" }}</dd>
          <dt>Baujahr</dt>
          <dd>{{ item.construction_year || "—" }}</dd>
          <dt>Händler</dt>
          <dd>{{ item.distributor || "—" }}</dd>
          <dt>Behältnis</dt>
          <dd>{{ item.container || "—" }}</dd>
          <dt>Besonderheiten</dt>
          <dd>{{ item.particularities || "—" }}</dd>
        </template>

        <!-- Clothing-specific -->
        <template v-if="category === 'clothing'">
          <dt>Typ</dt>
          <dd>{{ item.clothing_type?.label || "—" }}</dd>
          <dt>Größe</dt>
          <dd>{{ item.size || "—" }}</dd>
          <dt>Geschlecht</dt>
          <dd>{{ item.gender || "—" }}</dd>
        </template>

        <!-- Sheet music-specific -->
        <template v-if="category === 'sheet_music'">
          <dt>Komponist</dt>
          <dd>{{ item.composer || "—" }}</dd>
          <dt>Arrangeur</dt>
          <dd>{{ item.arranger || "—" }}</dd>
          <dt>Schwierigkeitsgrad</dt>
          <dd>{{ item.difficulty || "—" }}</dd>
          <dt>Gattung</dt>
          <dd>{{ item.genre?.label || "—" }}</dd>
          <dt>Lagerort</dt>
          <dd>{{ item.storage_location || "—" }}</dd>
        </template>

        <!-- General item-specific -->
        <template v-if="category === 'general_item'">
          <dt>Lagerort</dt>
          <dd>{{ item.storage_location || "—" }}</dd>
        </template>

        <!-- Common fields -->
        <dt>Hersteller</dt>
        <dd>{{ item.manufacturer || "—" }}</dd>
        <dt>Eigentümer</dt>
        <dd>{{ item.owner }}</dd>
        <dt>Anschaffungsdatum</dt>
        <dd>{{ item.acquisition_date || "—" }}</dd>
        <dt>Anschaffungskosten</dt>
        <dd>
          {{
            item.acquisition_cost != null
              ? `${item.acquisition_cost} ${item.currency?.abbreviation || ""}`
              : "—"
          }}
        </dd>
        <dt>Notizen</dt>
        <dd>{{ item.notes || "—" }}</dd>
      </dl>
    </div>

    <!-- Loan management section -->
    <div v-if="cat.hasLoans" class="card" style="margin-bottom: 1.5rem">
      <h2 style="font-size: 1.1rem; margin-bottom: 1rem">Ausleihe</h2>

      <!-- Currently loaned out -->
      <div v-if="activeLoan">
        <p style="margin-bottom: 0.75rem">
          Ausgeliehen an
          <router-link :to="`/musiker/${activeLoan.musician.id}`">
            <strong
              >{{ activeLoan.musician.first_name }} {{ activeLoan.musician.last_name }}</strong
            >
          </router-link>
          seit {{ activeLoan.start_date }}
        </p>
        <div v-if="!showReturnDatePicker" style="display: flex; gap: 0.5rem">
          <button class="btn-primary" @click="returnToday">Heute zurückgeben</button>
          <button class="btn" @click="showReturnDatePicker = true">Datum wählen</button>
        </div>
        <div v-else style="display: flex; gap: 0.5rem; align-items: end; flex-wrap: wrap">
          <div class="form-group" style="margin: 0">
            <label>Rückgabedatum</label>
            <input v-model="returnDate" type="date" style="max-width: 180px" />
          </div>
          <button class="btn-primary" :disabled="!returnDate" @click="returnWithDate">
            Zurückgeben
          </button>
          <button class="btn" @click="showReturnDatePicker = false">Abbrechen</button>
        </div>
      </div>

      <!-- Available — loan form -->
      <div v-else>
        <p style="margin-bottom: 0.75rem; color: var(--color-muted)">
          <span class="badge badge-green">Verfügbar</span>
        </p>
        <form
          style="display: flex; gap: 0.75rem; align-items: end; flex-wrap: wrap"
          @submit.prevent="createLoan"
        >
          <div
            class="form-group"
            style="margin: 0; flex: 1"
            :class="{ error: loanErrors.musician_id }"
          >
            <label>Musiker</label>
            <select v-model.number="loanForm.musician_id">
              <option :value="null" disabled>Auswählen...</option>
              <option v-for="m in musicians" :key="m.id" :value="m.id">
                {{ m.last_name }} {{ m.first_name }}
              </option>
            </select>
            <span v-if="loanErrors.musician_id" class="form-error">{{
              loanErrors.musician_id
            }}</span>
          </div>
          <div class="form-group" style="margin: 0" :class="{ error: loanErrors.start_date }">
            <label>Datum</label>
            <input v-model="loanForm.start_date" type="date" style="max-width: 160px" />
            <span v-if="loanErrors.start_date" class="form-error">{{ loanErrors.start_date }}</span>
          </div>
          <button type="submit" class="btn-primary" :disabled="loanSaving">Ausleihen</button>
        </form>
      </div>
    </div>

    <!-- Invoices section -->
    <div v-if="cat.hasInvoices" class="card" style="margin-bottom: 1.5rem">
      <div
        style="
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 1rem;
        "
      >
        <h2 style="font-size: 1.1rem; margin: 0">Rechnungen</h2>
        <button class="btn-sm" @click="newInvoice">Neue Rechnung</button>
      </div>

      <div v-if="!invoices.length" style="color: var(--color-muted)">
        Keine Rechnungen vorhanden.
      </div>

      <div v-else style="overflow-x: auto; -webkit-overflow-scrolling: touch">
        <table>
          <thead>
            <tr>
              <th>Nr.</th>
              <th>Bezeichnung</th>
              <th>Datum</th>
              <th>Betrag</th>
              <th>Datei</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="inv in invoices"
              :key="inv.id"
              style="cursor: pointer"
              @click="openInvoice(inv)"
            >
              <td>{{ inv.invoice_nr }}</td>
              <td>{{ inv.title }}</td>
              <td>{{ inv.date_issued }}</td>
              <td>{{ inv.amount }} {{ inv.currency?.abbreviation || "" }}</td>
              <td>
                <span v-if="inv.file_url" class="badge badge-green">Ja</span>
                <span v-else class="badge badge-gray">Nein</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Loan history -->
    <div v-if="cat.hasLoans && loans.length" class="card">
      <h2 style="font-size: 1.1rem; margin-bottom: 1rem">Leihhistorie</h2>
      <div style="overflow-x: auto; -webkit-overflow-scrolling: touch">
        <table>
          <thead>
            <tr>
              <th>Musiker</th>
              <th>Von</th>
              <th>Bis</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="l in loans" :key="l.id">
              <td>
                <router-link :to="`/musiker/${l.musician.id}`">
                  {{ l.musician.first_name }} {{ l.musician.last_name }}
                </router-link>
              </td>
              <td>{{ l.start_date }}</td>
              <td>{{ l.end_date || "—" }}</td>
              <td>
                <span :class="l.end_date ? 'badge badge-gray' : 'badge badge-green'">
                  {{ l.end_date ? "Zurückgegeben" : "Ausgeliehen" }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <ConfirmDialog
      :open="showDelete"
      :title="cat.labelSingular + ' löschen'"
      :message="
        'Soll ' +
        (category === 'clothing'
          ? 'diese ' + cat.labelSingular
          : category === 'sheet_music'
            ? 'dieses ' + cat.labelSingular
            : 'dieser ' + cat.labelSingular) +
        ' wirklich gelöscht werden?'
      "
      @confirm="remove"
      @cancel="showDelete = false"
    />

    <InvoiceModal
      v-if="cat.hasInvoices"
      :open="showInvoiceModal"
      :invoice="selectedInvoice"
      :currencies="currencies"
      :item-id="item.id"
      :default-currency-id="defaultCurrencyId"
      @save="handleInvoiceSave"
      @delete="handleInvoiceDelete"
      @close="showInvoiceModal = false"
    />

    <ItemFormModal
      :open="showEditModal"
      :category="category"
      :item-id="item.id"
      :currencies="currencies"
      @save="onEditSave"
      @close="showEditModal = false"
    />
  </div>
</template>
