<script setup>
import { ref, computed, onMounted, nextTick, watch } from "vue";
import { useRouter } from "vue-router";
import { get, getAll, post, put, del } from "../lib/api.js";
import { CATEGORIES, itemPath } from "../lib/categories.js";
import ConfirmDialog from "../components/ConfirmDialog.vue";
import CategoryChips from "../components/CategoryChips.vue";
import ImageGallery from "../components/ImageGallery.vue";
import ScanDocuments from "../components/ScanDocuments.vue";
import CollapsibleSection from "../components/CollapsibleSection.vue";
import InlineField from "../components/InlineField.vue";
import NotesBlock from "../components/NotesBlock.vue";
import { useInlineEdit } from "../composables/useInlineEdit.js";
import { itemFieldDefs, renumberPrefix } from "../lib/itemFields.js";
import { formatDate, formatMoney } from "../lib/format.js";
import { splitImages } from "../lib/images.js";
import { quantityDetail } from "../lib/quantity.js";
import InvoiceModal from "../components/InvoiceModal.vue";
import ItemFormModal from "../components/ItemFormModal.vue";
import MusicianPicker from "../components/MusicianPicker.vue";
import RecordHistory from "../components/RecordHistory.vue";
import RetireDialog from "../components/RetireDialog.vue";
import CopyItemDialog from "../components/CopyItemDialog.vue";
import { retireReasonLabel } from "../lib/retire.js";
import { isOverdue, loanStatus } from "../lib/loans.js";
import { TRASH_CONFIRM, TRASH_NOTE } from "../lib/trash.js";

const props = defineProps({
  category: { type: String, required: true },
  // Inventory number from the URL (TR-0006), or an id from an old link.
  nr: { type: String, required: true },
});

// The item's id, resolved from the URL's number (API calls use the id).
const itemId = ref(null);
const loadError = ref("");

const router = useRouter();
const cat = computed(() => CATEGORIES[props.category]);
const item = ref(null);
const loans = ref([]);
const images = ref([]);
const currencies = ref([]);
const invoices = ref([]);
const types = ref([]);
const genres = ref([]);
const categories = ref([]);
const showDelete = ref(false);
const deleteError = ref("");
const showRetire = ref(false);
const showCopy = ref(false);
const reinstating = ref(false);
const reinstateError = ref("");
const showEditModal = ref(false);

// Loan form state
const loanForm = ref({ musician_id: null, start_date: "", due_date: "", notes: "" });
const loanSaving = ref(false);
const loanErrors = ref({});
const loanError = ref("");

// Return state
const showReturnDatePicker = ref(false);
const returnDate = ref("");

// Invoice modal state
const showInvoiceModal = ref(false);
const selectedInvoice = ref(null);

const imageGroups = computed(() => splitImages(images.value));
const imageError = ref("");

const activeLoan = computed(() => loans.value.find((l) => !l.end_date));
const defaultCurrencyId = computed(() => {
  if (item.value?.currency_id) return item.value.currency_id;
  const euro = currencies.value.find((c) => c.abbreviation === "€");
  return euro?.id || currencies.value[0]?.id || null;
});

// Master-data fields, per category, for the collapsible "Stammdaten" section.
const fields = computed(() =>
  itemFieldDefs(props.category, {
    types: types.value,
    genres: genres.value,
    categories: categories.value,
    currencies: currencies.value,
  }),
);
// Long free-text fields (notes, particularities) render as a full-width
// NotesBlock with a dialog editor, below the <dl>, instead of inline.
const inlineFields = computed(() => fields.value.filter((f) => !f.block));
const blockFields = computed(() => fields.value.filter((f) => f.block));

// Fields of the current loan (e.g. its note), saved to the loan itself.
const loanInline = useInlineEdit(async (patch) => {
  await put(`/loans/${activeLoan.value.id}`, patch);
  await reload();
});

// Bumped after every save/reload so the "Verlauf" shows the new events.
const historyKey = ref(0);

const inline = useInlineEdit(async (patch) => {
  item.value = await put(`/items/${itemId.value}`, patch);
  historyKey.value++;
});
const pendingRenumber = ref(null); // { key, patch, from, to }

function saveField(field, value) {
  const patch = field.toPatch(value, item.value);
  if (field.key === "type") {
    const next = renumberPrefix(item.value, value, types.value);
    if (next) {
      pendingRenumber.value = {
        key: field.key,
        patch,
        from: item.value.display_nr,
        to: `${next}-…`,
      };
      return;
    }
  }
  inline.commit(field.key, patch);
}

function confirmRenumber() {
  const p = pendingRenumber.value;
  pendingRenumber.value = null;
  inline.commit(p.key, p.patch);
}

// Cancelling the renumber dialog leaves the type field's editor open behind
// it (see saveField/pendingRenumber above) — move focus back into its select
// rather than dropping it back to the document body.
async function cancelRenumber() {
  pendingRenumber.value = null;
  await nextTick();
  document.querySelector(".inline-editor select")?.focus();
}

async function createCategory(label) {
  const created = await post("/general-item-categories", { label });
  categories.value = [...categories.value, created];
  return created;
}

// Short info shown next to each section title while it is collapsed.
const photoSummary = computed(() => {
  const n = imageGroups.value.photos.length;
  return n ? `${n} ${n === 1 ? "Foto" : "Fotos"}` : "Keine Fotos";
});
const scanSummary = computed(() => {
  const n = imageGroups.value.scans.length;
  return `${n} ${n === 1 ? "Seite" : "Seiten"}`;
});
const masterSummary = computed(() =>
  [item.value?.display_nr, item.value?.manufacturer].filter(Boolean).join(" · "),
);
const loanSummary = computed(() =>
  activeLoan.value
    ? `an ${activeLoan.value.musician.first_name} ${activeLoan.value.musician.last_name} seit ${formatDate(activeLoan.value.start_date)}${isOverdue(activeLoan.value) ? " · überfällig" : ""}`
    : "verfügbar",
);
const invoiceSummary = computed(() => {
  if (!invoices.value.length) return "keine";
  const sums = {};
  for (const inv of invoices.value) {
    const abbr = inv.currency?.abbreviation || "";
    sums[abbr] = (sums[abbr] || 0) + Number(inv.amount || 0);
  }
  const totals = Object.entries(sums)
    .map(([abbr, sum]) => formatMoney(sum, abbr))
    .join(" · ");
  return `${invoices.value.length} · ${totals}`;
});
const historySummary = computed(
  () => `${loans.value.length} ${loans.value.length === 1 ? "Eintrag" : "Einträge"}`,
);

async function resolveId() {
  if (/^\d+$/.test(props.nr)) return Number(props.nr);
  const found = await get(
    `/items/by-number/${encodeURIComponent(props.nr)}?category=${props.category}`,
  );
  return found.id;
}

// Keep the URL on the item's current number (old id links, renumbering).
function syncUrl() {
  if (item.value && props.nr !== item.value.display_nr) {
    router.replace(itemPath(item.value));
  }
}

async function reload() {
  historyKey.value++;
  loadError.value = "";
  try {
    if (itemId.value == null) itemId.value = await resolveId();
    item.value = await get(`/items/${itemId.value}`);
  } catch (e) {
    item.value = null;
    loadError.value = e.message;
    return;
  }
  syncUrl();
  images.value = await get(`/items/${itemId.value}/images`);
  if (cat.value.hasLoans) {
    loans.value = await getAll(`/loans?item_id=${itemId.value}`);
  }
  if (cat.value.hasInvoices) {
    invoices.value = await get(`/items/${itemId.value}/invoices`);
  }
}

async function uploadImage(file) {
  const formData = new FormData();
  formData.append("file", file);
  await fetch(`/api/v1/items/${itemId.value}/images`, {
    method: "POST",
    body: formData,
  });
  await reload();
}

async function setProfile(imageId) {
  imageError.value = "";
  try {
    await put(`/items/${itemId.value}/images/${imageId}/profile`);
    await reload();
  } catch (e) {
    imageError.value = "Profilbild konnte nicht gesetzt werden: " + e.message;
  }
}

async function deleteImage(imageId) {
  imageError.value = "";
  try {
    await del(`/items/${itemId.value}/images/${imageId}`);
    await reload();
  } catch (e) {
    imageError.value = "Bild konnte nicht gelöscht werden: " + e.message;
  }
}

onMounted(async () => {
  currencies.value = await get("/currencies");
  if (props.category === "instrument") {
    types.value = await get("/instrument-types").catch(() => []);
  } else if (props.category === "clothing") {
    types.value = await get("/clothing-types").catch(() => []);
  } else if (props.category === "sheet_music") {
    genres.value = await get("/sheet-music-genres").catch(() => []);
  } else if (props.category === "general_item") {
    categories.value = await get("/general-item-categories").catch(() => []);
  }
  await reload();
});

// Reload when navigating between items of the same category. Drop any
// in-progress inline edit / pending renumber first — they belong to the item
// we're leaving, and would otherwise show or act on the wrong item's data.
watch(
  () => props.nr,
  (nr) => {
    // Our own URL fix (syncUrl) needs no reload.
    if (item.value && (nr === item.value.display_nr || nr === String(item.value.id))) return;
    inline.cancel();
    pendingRenumber.value = null;
    itemId.value = null;
    reload();
  },
);
watch(() => item.value?.display_nr, syncUrl);

// One copy: open it. Several: the list, newest numbers first.
function onCopied(created) {
  showCopy.value = false;
  if (created.length === 1) router.push(itemPath(created[0]));
  else router.push(`${cat.value.routeBase}?order_by=-number`);
}

async function onRetired() {
  showRetire.value = false;
  await reload();
}

async function reinstate() {
  reinstating.value = true;
  reinstateError.value = "";
  try {
    await post(`/items/${itemId.value}/reinstate`, {});
    await reload();
  } catch (e) {
    reinstateError.value = "Wieder in Bestand nicht möglich: " + e.message;
  } finally {
    reinstating.value = false;
  }
}

async function remove() {
  deleteError.value = "";
  try {
    await del(`/items/${itemId.value}`);
    router.push(cat.value.routeBase);
  } catch (e) {
    showDelete.value = false;
    deleteError.value = "Löschen nicht möglich: " + e.message;
  }
}

function validateLoan() {
  loanErrors.value = {};
  if (!loanForm.value.musician_id) loanErrors.value.musician_id = "Pflichtfeld";
  if (!loanForm.value.start_date) loanErrors.value.start_date = "Pflichtfeld";
  const { start_date: start, due_date: due } = loanForm.value;
  if (due && start && due < start) loanErrors.value.due_date = "Liegt vor dem Ausleihdatum";
  return Object.keys(loanErrors.value).length === 0;
}

async function createLoan() {
  loanError.value = "";
  if (!validateLoan()) return;
  loanSaving.value = true;
  try {
    await post("/loans", {
      item_id: itemId.value,
      ...loanForm.value,
      due_date: loanForm.value.due_date || null,
    });
    loanForm.value = { musician_id: null, start_date: "", due_date: "", notes: "" };
    loanErrors.value = {};
    await reload();
  } catch (e) {
    loanError.value = "Ausleihen fehlgeschlagen: " + e.message;
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
  const base = `/items/${itemId.value}/invoices`;
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
  if (!confirm(`Rechnung in den Papierkorb verschieben? ${TRASH_NOTE}`)) return;
  await del(`/items/${itemId.value}/invoices/${invoiceId}`);
  showInvoiceModal.value = false;
  await reload();
}

async function onEditSave() {
  await reload();
}
</script>

<template>
  <div v-if="loadError" class="alert alert-danger" role="alert">
    {{ cat.labelSingular }} konnte nicht geladen werden: {{ loadError }}
    <RouterLink :to="cat.routeBase">Zur Liste</RouterLink>
  </div>
  <div v-else-if="item">
    <div class="page-header">
      <h1>{{ item.display_nr }} — {{ item.label }}</h1>
      <div class="cluster">
        <button class="btn" @click="showEditModal = true">Bearbeiten</button>
        <button class="btn" @click="showCopy = true">Kopieren …</button>
        <button v-if="!item.retired_at" class="btn" @click="showRetire = true">
          Ausscheiden …
        </button>
        <button class="btn-danger" @click="showDelete = true">Löschen</button>
      </div>
    </div>

    <div v-if="deleteError" class="alert alert-danger" role="alert">{{ deleteError }}</div>

    <section v-if="item.retired_at" class="retired-banner" aria-label="Ausgeschieden">
      <div>
        <p class="retired-title">
          <strong>Ausgeschieden</strong>
          am {{ formatDate(item.retired_at) }} · {{ retireReasonLabel(item.retired_reason) }}
        </p>
        <p v-if="item.retired_notes" class="retired-notes">{{ item.retired_notes }}</p>
        <p class="retired-hint">Nicht mehr im Bestand – Nummer und Historie bleiben erhalten.</p>
        <p v-if="reinstateError" class="form-error" role="alert">{{ reinstateError }}</p>
      </div>
      <button type="button" class="btn" :disabled="reinstating" @click="reinstate">
        Wieder in Bestand
      </button>
    </section>

    <CollapsibleSection :scope="category" section="photos" title="Fotos" :summary="photoSummary">
      <div v-if="imageError" class="alert alert-danger image-alert" role="alert">
        {{ imageError }}
      </div>
      <ImageGallery
        :images="imageGroups.photos"
        :can-upload="true"
        :can-manage="true"
        @upload="uploadImage"
        @set-profile="setProfile"
        @delete="deleteImage"
      />
    </CollapsibleSection>

    <CollapsibleSection
      v-if="imageGroups.scans.length"
      :scope="category"
      section="scans"
      title="Unterlagen (Scans)"
      :summary="scanSummary"
    >
      <ScanDocuments :scans="imageGroups.scans" :can-manage="true" @delete="deleteImage" />
    </CollapsibleSection>

    <CollapsibleSection
      :scope="category"
      section="master"
      title="Stammdaten"
      :summary="masterSummary"
    >
      <dl class="detail-grid">
        <dt>Inventarnummer</dt>
        <dd>{{ item.display_nr }}</dd>
        <InlineField
          v-for="f in inlineFields"
          :key="f.key"
          :field-key="f.key"
          :label="f.label"
          :type="f.type"
          :value="f.value(item)"
          :options="f.options || []"
          :required="!!f.required"
          :min="f.min ?? null"
          :max="f.max ?? null"
          :currencies="currencies"
          :default-currency-id="f.type === 'money' ? defaultCurrencyId : null"
          :create-option="f.type === 'tags' ? createCategory : null"
          :editing="inline.editingKey.value === f.key"
          :saving="inline.savingKey.value === f.key"
          :saved="inline.savedKey.value === f.key"
          :error="inline.editingKey.value === f.key ? inline.error.value : ''"
          @start="inline.start(f.key)"
          @cancel="inline.cancel()"
          @save="(v) => saveField(f, v)"
        >
          <template v-if="f.key === 'quantity'" #display>{{ quantityDetail(item) }}</template>
          <template v-else-if="f.key === 'categories'" #display>
            <CategoryChips :categories="item.categories || []" />
          </template>
        </InlineField>
      </dl>

      <NotesBlock
        v-for="f in blockFields"
        :key="f.key"
        :label="f.label"
        :value="f.value(item)"
        :max-length="f.maxLength"
        :saving="inline.savingKey.value === f.key"
        :saved="inline.savedKey.value === f.key"
        :error="inline.editingKey.value === f.key ? inline.error.value : ''"
        :editing="inline.editingKey.value === f.key"
        @start="inline.start(f.key)"
        @cancel="inline.cancel()"
        @save="(v) => saveField(f, v)"
      />
    </CollapsibleSection>

    <!-- Loan management section -->
    <CollapsibleSection
      v-if="cat.hasLoans"
      :scope="category"
      section="loan"
      title="Ausleihe"
      :summary="loanSummary"
    >
      <!-- Currently loaned out -->
      <div v-if="activeLoan">
        <p class="section-lead">
          Ausgeliehen an
          <router-link :to="`/musiker/${activeLoan.musician.id}`">
            <strong
              >{{ activeLoan.musician.first_name }} {{ activeLoan.musician.last_name }}</strong
            >
          </router-link>
          seit {{ formatDate(activeLoan.start_date) }}
          <span v-if="isOverdue(activeLoan)" class="badge badge-warning">Überfällig</span>
        </p>
        <dl class="detail-grid loan-details">
          <InlineField
            field-key="loan-due"
            label="Rückgabe geplant"
            type="date"
            :value="activeLoan.due_date"
            :editing="loanInline.editingKey.value === 'due_date'"
            :saving="loanInline.savingKey.value === 'due_date'"
            :saved="loanInline.savedKey.value === 'due_date'"
            :error="loanInline.editingKey.value === 'due_date' ? loanInline.error.value : ''"
            @start="loanInline.start('due_date')"
            @cancel="loanInline.cancel()"
            @save="(v) => loanInline.commit('due_date', { due_date: v || null })"
          />
          <InlineField
            field-key="loan-notes"
            label="Notiz"
            type="textarea"
            :value="activeLoan.notes"
            placeholder="z. B. mit Koffer, Mundstück fehlt …"
            :editing="loanInline.editingKey.value === 'notes'"
            :saving="loanInline.savingKey.value === 'notes'"
            :saved="loanInline.savedKey.value === 'notes'"
            :error="loanInline.editingKey.value === 'notes' ? loanInline.error.value : ''"
            @start="loanInline.start('notes')"
            @cancel="loanInline.cancel()"
            @save="(v) => loanInline.commit('notes', { notes: v })"
          />
        </dl>
        <div v-if="!showReturnDatePicker" class="cluster">
          <button class="btn-primary" @click="returnToday">Heute zurückgeben</button>
          <button class="btn" @click="showReturnDatePicker = true">Datum wählen</button>
        </div>
        <div v-else class="cluster cluster-end">
          <div class="form-group">
            <label>Rückgabedatum</label>
            <input v-model="returnDate" type="date" class="input-narrow" />
          </div>
          <button class="btn-primary" :disabled="!returnDate" @click="returnWithDate">
            Zurückgeben
          </button>
          <button class="btn" @click="showReturnDatePicker = false">Abbrechen</button>
        </div>
      </div>

      <p v-else-if="item.retired_at" class="section-lead">
        Ausgeschiedene Gegenstände können nicht ausgeliehen werden.
      </p>

      <!-- Available — loan form -->
      <div v-else>
        <p class="section-lead">
          <span class="badge badge-green">Verfügbar</span>
        </p>
        <form class="cluster cluster-end" @submit.prevent="createLoan">
          <div class="form-group grow" :class="{ error: loanErrors.musician_id }">
            <MusicianPicker
              v-model="loanForm.musician_id"
              label="Musiker"
              placeholder="Name eingeben …"
              creatable
            />
            <span v-if="loanErrors.musician_id" class="form-error">{{
              loanErrors.musician_id
            }}</span>
          </div>
          <div class="form-group" :class="{ error: loanErrors.start_date }">
            <label>Datum</label>
            <input v-model="loanForm.start_date" type="date" class="input-narrow" />
            <span v-if="loanErrors.start_date" class="form-error">{{ loanErrors.start_date }}</span>
          </div>
          <div class="form-group" :class="{ error: loanErrors.due_date }">
            <label for="loan-due">Rückgabe geplant</label>
            <input
              id="loan-due"
              v-model="loanForm.due_date"
              type="date"
              class="input-narrow"
              :min="loanForm.start_date || undefined"
            />
            <span v-if="loanErrors.due_date" class="form-error">{{ loanErrors.due_date }}</span>
          </div>
          <div class="form-group loan-notes-field">
            <label for="loan-notes">Notiz</label>
            <textarea
              id="loan-notes"
              v-model="loanForm.notes"
              rows="2"
              maxlength="1000"
              placeholder="optional, z. B. mit Koffer"
            />
          </div>
          <button type="submit" class="btn-primary" :disabled="loanSaving">Ausleihen</button>
        </form>
        <p v-if="loanError" class="form-error" role="alert">{{ loanError }}</p>
      </div>
    </CollapsibleSection>

    <!-- Invoices section -->
    <CollapsibleSection
      v-if="cat.hasInvoices"
      :scope="category"
      section="invoices"
      title="Rechnungen"
      :summary="invoiceSummary"
    >
      <template #actions>
        <button class="btn-sm" @click="newInvoice">Neue Rechnung</button>
      </template>

      <p v-if="!invoices.length" class="empty-note">Keine Rechnungen vorhanden.</p>

      <div v-else class="table-scroll">
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
    </CollapsibleSection>

    <!-- Loan history -->
    <CollapsibleSection
      v-if="cat.hasLoans && loans.length"
      :scope="category"
      section="history"
      title="Leihhistorie"
      :summary="historySummary"
    >
      <div class="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Musiker</th>
              <th>Von</th>
              <th>Bis</th>
              <th>Status</th>
              <th>Notiz</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="l in loans" :key="l.id">
              <td>
                <template v-if="l.musician.deleted_at">
                  {{ l.musician.first_name }} {{ l.musician.last_name }}
                  <span class="badge badge-gray">im Papierkorb</span>
                </template>
                <router-link v-else :to="`/musiker/${l.musician.id}`">
                  {{ l.musician.first_name }} {{ l.musician.last_name }}
                </router-link>
              </td>
              <td>{{ formatDate(l.start_date) }}</td>
              <td>{{ l.end_date ? formatDate(l.end_date) : "—" }}</td>
              <td>
                <span :class="loanStatus(l).badge">{{ loanStatus(l).label }}</span>
              </td>
              <td>
                <span class="loan-note">{{ l.notes || "" }}</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </CollapsibleSection>

    <RecordHistory :scope="category" :item-id="item.id" :refresh-key="historyKey" />

    <CopyItemDialog
      :open="showCopy"
      :item="item"
      :category="category"
      @copied="onCopied"
      @cancel="showCopy = false"
    />
    <RetireDialog
      :open="showRetire"
      :item="item"
      @retired="onRetired"
      @cancel="showRetire = false"
    />

    <ConfirmDialog
      :open="showDelete"
      :title="cat.labelSingular + ' löschen'"
      :message="`„${item.display_nr} ${item.label}“ in den Papierkorb verschieben? ${TRASH_NOTE}`"
      :confirm-label="TRASH_CONFIRM"
      @confirm="remove"
      @cancel="showDelete = false"
    />

    <ConfirmDialog
      :open="!!pendingRenumber"
      title="Neue Inventarnummer"
      :message="
        pendingRenumber
          ? `Die Inventarnummer wird neu vergeben: ${pendingRenumber.from} → ${pendingRenumber.to}`
          : ''
      "
      confirm-label="Typ ändern"
      @confirm="confirmRenumber"
      @cancel="cancelRenumber"
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

<style scoped>
.retired-banner {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
  flex-wrap: wrap;
  margin-bottom: var(--space-section);
  padding: var(--space-3) var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  background: var(--color-bg-soft);
}

.retired-banner p {
  margin: 0;
}

.retired-title {
  font-weight: 500;
}

.retired-banner .retired-notes {
  margin-top: var(--space-1);
  white-space: pre-line;
}

.retired-banner .retired-hint {
  margin-top: var(--space-1);
  font-size: 0.8125rem;
  color: var(--color-muted);
}

.retired-banner button {
  min-height: 44px;
}

.loan-details {
  margin: 0 0 var(--space-3);
}

.loan-notes-field {
  flex-basis: 100%;
}

.loan-notes-field textarea {
  width: 100%;
}

.image-alert {
  margin-bottom: var(--space-3);
}
</style>
