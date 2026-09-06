<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount } from "vue";
import { RouterLink } from "vue-router";
import { get, put, post, postForm, API_PREFIX, BASE } from "../lib/api.js";
import { sessionStatus, pageStatus } from "../lib/importStatus.js";
import LoadingSpinner from "../components/LoadingSpinner.vue";
import ConfirmDialog from "../components/ConfirmDialog.vue";
import ImportPageViewer from "../components/ImportPageViewer.vue";

const props = defineProps({
  id: { type: String, required: true },
});

const session = ref(null);
const loading = ref(true);
const error = ref(null);

// reference data for the editor
const instrumentTypes = ref([]);
const musicians = ref([]);

// upload
const uploading = ref(false);
const uploadError = ref(null);
const dragOver = ref(false);
const fileInput = ref(null);

// analysis
const analyzing = ref(false);
const analysisLog = ref([]);
let eventSource = null;

// review
const selectedPageId = ref(null);
const selectedRowKey = ref(null);
const saveState = ref("idle"); // idle | pending | saving | saved | error
const saveError = ref(null);
let saveTimer = null;

// import
const confirmImportOpen = ref(false);
const importing = ref(false);
const importError = ref(null);

// ---------------------------------------------------------------------------
// loading
// ---------------------------------------------------------------------------

async function load() {
  loading.value = true;
  error.value = null;
  try {
    session.value = await get(`/import/sessions/${props.id}`);
    if (!selectedPageId.value && session.value.pages.length) {
      selectedPageId.value = session.value.pages[0].id;
    }
  } catch (e) {
    error.value = e.message;
  } finally {
    loading.value = false;
  }
}

async function loadReferenceData() {
  try {
    const [types, musicianData] = await Promise.all([
      get("/instrument-types"),
      get("/musicians?limit=200"),
    ]);
    instrumentTypes.value = types;
    musicians.value = musicianData.items || musicianData;
  } catch {
    // The editor still works with the model's text; selects are just empty.
  }
}

onMounted(() => {
  load();
  loadReferenceData();
});

onBeforeUnmount(() => {
  if (eventSource) eventSource.close();
  if (saveTimer) clearTimeout(saveTimer);
});

// ---------------------------------------------------------------------------
// derived state
// ---------------------------------------------------------------------------

const status = computed(() => sessionStatus(session.value?.status));
const isImported = computed(() => session.value?.status === "imported");
const isBusy = computed(
  () => ["analyzing", "importing"].includes(session.value?.status) || analyzing.value,
);
const readOnly = computed(() => isImported.value || isBusy.value);

const pendingPages = computed(
  () => session.value?.pages.filter((p) => p.status !== "done").length ?? 0,
);
const canAnalyze = computed(
  () => !!session.value && session.value.pages.length > 0 && !readOnly.value,
);

const draft = computed(() => session.value?.draft ?? null);
const validation = computed(() => session.value?.validation ?? null);
const summary = computed(() => validation.value?.summary ?? null);
const validationByKey = computed(() => {
  const map = {};
  for (const r of validation.value?.rows ?? []) map[r.key] = r;
  return map;
});

const selectedPage = computed(
  () => session.value?.pages.find((p) => p.id === selectedPageId.value) ?? null,
);

const pageBoxes = computed(() => {
  if (!draft.value || !selectedPage.value) return [];
  const boxes = [];
  for (const row of draft.value.instruments) {
    if (row.page_id === selectedPage.value.id && row.bbox_2d) {
      boxes.push({ key: row.key, bbox_2d: row.bbox_2d, kind: "row", label: rowLabel(row) });
    }
  }
  for (const photo of draft.value.photos) {
    if (photo.page_id === selectedPage.value.id && photo.bbox_2d) {
      boxes.push({ key: photo.key, bbox_2d: photo.bbox_2d, kind: "photo", label: "Foto" });
    }
  }
  return boxes;
});

const selectedRow = computed(
  () => draft.value?.instruments.find((r) => r.key === selectedRowKey.value) ?? null,
);

const canImport = computed(
  () => !!summary.value && !summary.value.blocking && session.value?.status === "review",
);

const importResult = computed(() => session.value?.import_result ?? null);

// ---------------------------------------------------------------------------
// helpers
// ---------------------------------------------------------------------------

function rowLabel(row) {
  const nr = row.inventory_nr ? `${row.inventory_nr}` : "";
  const type = row.instrument_type || row.label || "";
  return [nr, type].filter(Boolean).join(" ");
}

function rowIssues(key) {
  return validationByKey.value[key]?.issues ?? [];
}

function issueCount(key, level) {
  return rowIssues(key).filter((i) => i.level === level).length;
}

function rowClass(row) {
  if (row.skip) return "row-skipped";
  if (issueCount(row.key, "error")) return "row-error";
  if (issueCount(row.key, "warning")) return "row-warning";
  return "";
}

function fieldIssue(key, field) {
  return rowIssues(key).find((i) => i.field === field) ?? null;
}

function pageOfRow(row) {
  return session.value?.pages.find((p) => p.id === row.page_id) ?? null;
}

function selectRow(key) {
  selectedRowKey.value = key;
  const row = draft.value?.instruments.find((r) => r.key === key);
  if (row && row.page_id !== selectedPageId.value) selectedPageId.value = row.page_id;
}

function onViewerSelect(key) {
  if (draft.value?.instruments.some((r) => r.key === key)) selectRow(key);
  else selectedRowKey.value = key;
}

function cropUrl(photo) {
  const page = session.value?.pages.find((p) => p.id === photo.page_id);
  if (!page || !photo.bbox_2d) return "";
  const [x1, y1, x2, y2] = photo.bbox_2d;
  return `${API_PREFIX}/import/sessions/${props.id}/pages/${page.id}/crop?x1=${x1}&y1=${y1}&x2=${x2}&y2=${y2}`;
}

// resolved values for selects: explicit draft override wins over the resolver
function typeValue(row) {
  if (row.instrument_type_id != null) return row.instrument_type_id;
  return validationByKey.value[row.key]?.fields?.instrument_type_id ?? "";
}

function setType(row, value) {
  row.instrument_type_id = value === "" ? null : Number(value);
  scheduleSave();
}

function ensureLoan(row) {
  if (!row.loan) row.loan = { musician_name: "", start_date: null, end_date: null };
  return row.loan;
}

function musicianValue(row) {
  if (row.loan?.musician_id != null) return row.loan.musician_id;
  const m = validationByKey.value[row.key]?.musician;
  return m?.action === "existing" ? m.musician_id : "";
}

function setMusician(row, value) {
  const loan = ensureLoan(row);
  loan.musician_id = value === "" ? null : Number(value);
  scheduleSave();
}

function musicianNames(row) {
  const m = validationByKey.value[row.key]?.musician ?? {};
  return {
    first: row.loan?.first_name ?? m.first_name ?? "",
    last: row.loan?.last_name ?? m.last_name ?? "",
  };
}

function setMusicianName(row, which, value) {
  const loan = ensureLoan(row);
  const names = musicianNames(row);
  loan.first_name = which === "first" ? value : names.first;
  loan.last_name = which === "last" ? value : names.last;
  scheduleSave();
}

function applySuggestion(row, issue) {
  const s = issue.suggestion;
  if (issue.field === "instrument_type_id" && s?.id) row.instrument_type_id = s.id;
  else if (issue.field === "loan.musician_id" && s?.id) ensureLoan(row).musician_id = s.id;
  else if (issue.field === "inventory_nr" && s?.next_free) row.inventory_nr = String(s.next_free);
  else if (issue.field === "loan.start_date" && typeof s === "string")
    ensureLoan(row).start_date = s;
  else return;
  scheduleSave();
}

function hasApplicableSuggestion(issue) {
  const s = issue.suggestion;
  if (s == null || issue.level === "info") return false;
  if (issue.field === "instrument_type_id" || issue.field === "loan.musician_id") return !!s.id;
  if (issue.field === "inventory_nr") return !!s.next_free;
  if (issue.field === "loan.start_date") return typeof s === "string";
  return false;
}

function removeLoan(row) {
  row.loan = null;
  scheduleSave();
}

function addLoan(row) {
  ensureLoan(row);
  scheduleSave();
}

// ---------------------------------------------------------------------------
// saving the draft
// ---------------------------------------------------------------------------

function scheduleSave() {
  if (readOnly.value) return;
  saveState.value = "pending";
  if (saveTimer) clearTimeout(saveTimer);
  saveTimer = setTimeout(saveDraft, 600);
}

async function saveDraft() {
  if (!draft.value || readOnly.value) return;
  saveState.value = "saving";
  saveError.value = null;
  try {
    const updated = await put(`/import/sessions/${props.id}/draft`, { draft: draft.value });
    // keep the user's object identity (they may still be typing); only take validation
    session.value.validation = updated.validation;
    session.value.updated_at = updated.updated_at;
    saveState.value = "saved";
  } catch (e) {
    saveState.value = "error";
    saveError.value = e.message;
  }
}

// ---------------------------------------------------------------------------
// upload
// ---------------------------------------------------------------------------

async function uploadFiles(fileList) {
  const files = Array.from(fileList || []);
  if (!files.length) return;
  uploading.value = true;
  uploadError.value = null;
  try {
    const form = new FormData();
    for (const f of files) form.append("files", f);
    session.value = await postForm(`/import/sessions/${props.id}/files`, form);
    if (!selectedPageId.value && session.value.pages.length) {
      selectedPageId.value = session.value.pages[0].id;
    }
  } catch (e) {
    uploadError.value = e.message;
  } finally {
    uploading.value = false;
  }
}

function onFileInput(event) {
  uploadFiles(event.target.files);
  event.target.value = "";
}

function onDrop(event) {
  dragOver.value = false;
  uploadFiles(event.dataTransfer.files);
}

// ---------------------------------------------------------------------------
// analysis (SSE)
// ---------------------------------------------------------------------------

function startAnalysis(force = false) {
  if (!canAnalyze.value) return;
  analyzing.value = true;
  analysisLog.value = [];
  error.value = null;
  for (const p of session.value.pages) if (force || p.status !== "done") p.status = "analyzing";
  session.value.status = "analyzing";

  const url = `${API_PREFIX}/import/sessions/${props.id}/analyze-stream${force ? "?force=true" : ""}`;
  eventSource = new EventSource(url);

  eventSource.addEventListener("page", (e) => {
    const data = JSON.parse(e.data);
    const page = session.value.pages.find((p) => p.page_index === data.page_index);
    if (page) page.status = data.status;
    if (data.status === "done") {
      analysisLog.value.push(
        `Seite ${data.page_index + 1}: ${data.instruments} Instrument(e), ${data.photos} Foto(s), ${data.duration_seconds} s`,
      );
    } else {
      analysisLog.value.push(`Seite ${data.page_index + 1}: Fehler – ${data.error}`);
    }
  });

  eventSource.addEventListener("done", async () => {
    finishAnalysis();
    await load();
  });

  eventSource.addEventListener("error", async (e) => {
    if (e.data) analysisLog.value.push(`Fehler: ${e.data}`);
    else analysisLog.value.push("Verbindung zum Server abgebrochen.");
    finishAnalysis();
    await load();
  });
}

function finishAnalysis() {
  if (eventSource) {
    eventSource.close();
    eventSource = null;
  }
  analyzing.value = false;
}

// ---------------------------------------------------------------------------
// import
// ---------------------------------------------------------------------------

async function runImport() {
  confirmImportOpen.value = false;
  importing.value = true;
  importError.value = null;
  try {
    session.value = await post(`/import/sessions/${props.id}/import`, {});
  } catch (e) {
    importError.value = e.message;
    await load();
  } finally {
    importing.value = false;
  }
}

const importMessage = computed(() => {
  const s = summary.value;
  if (!s) return "";
  return `${s.instruments_new} Instrument(e), ${s.musicians_new} neue(r) Musiker, ${s.loans_new} Leihe(n) und ${s.photos_attached} Foto(s) werden angelegt.`;
});

watch(
  () => props.id,
  () => {
    selectedPageId.value = null;
    selectedRowKey.value = null;
    load();
  },
);
</script>

<template>
  <div>
    <div v-if="loading" class="loading-wrap"><LoadingSpinner /></div>

    <div v-else-if="error && !session" class="alert alert-danger" role="alert">
      {{ error }}
      <button class="btn btn-sm" style="margin-left: var(--space-3)" @click="load">
        Erneut versuchen
      </button>
    </div>

    <template v-else-if="session">
      <!-- Header -->
      <div class="page-header">
        <div class="header-left">
          <RouterLink to="/import" class="back-link">← Alle Importe</RouterLink>
          <div class="title-row">
            <h1>{{ session.title || `Import #${session.id}` }}</h1>
            <span :class="['badge', status.badge]">{{ status.label }}</span>
          </div>
        </div>
        <div class="header-actions">
          <button
            v-if="session.pages.length && !isImported"
            class="btn"
            :class="pendingPages ? 'btn-primary' : 'btn-secondary'"
            :disabled="!canAnalyze"
            @click="startAnalysis(pendingPages === 0)"
          >
            {{ pendingPages ? "Analyse starten" : "Analyse wiederholen" }}
          </button>
          <button
            v-if="draft && !isImported"
            class="btn btn-primary"
            :disabled="!canImport || importing"
            :title="summary?.blocking ? 'Fehler im Entwurf müssen zuerst behoben werden' : ''"
            @click="confirmImportOpen = true"
          >
            Importieren
          </button>
        </div>
      </div>

      <div v-if="error" class="alert alert-danger" role="alert">{{ error }}</div>
      <div
        v-if="session.error && session.status === 'error'"
        class="alert alert-danger"
        role="alert"
      >
        {{ session.error }}
      </div>

      <!-- Import result -->
      <section v-if="importResult" class="page-section">
        <div class="alert alert-success" role="status">
          Import abgeschlossen: {{ importResult.counts.items }} Instrument(e),
          {{ importResult.counts.musicians }} neue(r) Musiker,
          {{ importResult.counts.loans }} Leihe(n), {{ importResult.counts.images }} Foto(s).
        </div>
        <div class="table-scroll">
          <table class="ledger-table result-table">
            <thead>
              <tr>
                <th>Nr.</th>
                <th>Bezeichnung</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in importResult.items" :key="item.item_id">
                <td class="nowrap">{{ item.display_nr }}</td>
                <td>
                  <RouterLink :to="`/instrumente/${item.item_id}`">{{ item.label }}</RouterLink>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <p v-if="importResult.musicians.length" class="text-muted result-musicians">
          Neu angelegte Musiker:
          <template v-for="(m, i) in importResult.musicians" :key="m.musician_id">
            <RouterLink :to="`/musiker/${m.musician_id}`">{{ m.name }}</RouterLink
            ><span v-if="i < importResult.musicians.length - 1">, </span>
          </template>
        </p>
      </section>

      <!-- Documents -->
      <section class="page-section">
        <div class="section-header">
          <h2>Dokumente</h2>
          <span class="text-muted">{{ session.pages.length }} Seite(n)</span>
        </div>

        <div
          v-if="!isImported"
          class="dropzone"
          :class="{ 'drag-over': dragOver, disabled: isBusy }"
          @dragover.prevent="dragOver = true"
          @dragleave="dragOver = false"
          @drop.prevent="onDrop"
        >
          <p>
            PDF oder Bilder (JPG, PNG, TIFF) hierher ziehen oder
            <button
              class="btn btn-secondary btn-sm"
              :disabled="isBusy || uploading"
              @click="fileInput.click()"
            >
              Dateien auswählen
            </button>
          </p>
          <input
            ref="fileInput"
            type="file"
            multiple
            accept=".pdf,image/*"
            class="sr-only"
            aria-label="Dateien für den Import auswählen"
            @change="onFileInput"
          />
          <p v-if="uploading" class="text-muted">Dateien werden hochgeladen und gerendert…</p>
          <p v-if="uploadError" class="text-danger">{{ uploadError }}</p>
        </div>

        <div v-if="session.pages.length" class="thumbs" role="list">
          <button
            v-for="p in session.pages"
            :key="p.id"
            type="button"
            class="thumb"
            :class="{ active: p.id === selectedPageId }"
            role="listitem"
            :title="`${p.source_name}, Seite ${p.source_page + 1}`"
            @click="selectedPageId = p.id"
          >
            <img :src="`${BASE}${p.image_url}`" :alt="`Seite ${p.page_index + 1}`" loading="lazy" />
            <span class="thumb-label">
              {{ p.page_index + 1 }}
              <span :class="['badge', pageStatus(p.status).badge]">{{
                pageStatus(p.status).label
              }}</span>
            </span>
          </button>
        </div>

        <div v-if="analyzing || analysisLog.length" class="analysis-log" aria-live="polite">
          <p v-if="analyzing" class="analysis-running">
            <LoadingSpinner size="1rem" /> Analyse läuft, etwa 15 bis 30 Sekunden pro Seite …
          </p>
          <ul>
            <li v-for="(line, i) in analysisLog" :key="i">{{ line }}</li>
          </ul>
        </div>
      </section>

      <!-- Review -->
      <section v-if="draft" class="page-section">
        <div class="section-header">
          <h2>Prüfen und korrigieren</h2>
          <span class="save-state" :class="saveState">
            <template v-if="saveState === 'saving' || saveState === 'pending'"
              >Speichern …</template
            >
            <template v-else-if="saveState === 'saved'">Gespeichert</template>
            <template v-else-if="saveState === 'error'"
              >Speichern fehlgeschlagen: {{ saveError }}</template
            >
          </span>
        </div>

        <dl v-if="summary" class="key-figures summary">
          <div class="key-figure">
            <dt>Instrumente</dt>
            <dd>{{ summary.instruments_new }}</dd>
          </div>
          <div class="key-figure">
            <dt>Musiker neu / vorhanden</dt>
            <dd>{{ summary.musicians_new }} / {{ summary.musicians_existing }}</dd>
          </div>
          <div class="key-figure">
            <dt>Leihen</dt>
            <dd>{{ summary.loans_new }}</dd>
          </div>
          <div class="key-figure">
            <dt>Fotos</dt>
            <dd>{{ summary.photos_attached }}</dd>
          </div>
          <div class="key-figure">
            <dt>Fehler / Hinweise</dt>
            <dd
              :class="{
                'text-danger': summary.errors,
                'text-warning': !summary.errors && summary.warnings,
              }"
            >
              {{ summary.errors }} / {{ summary.warnings }}
            </dd>
          </div>
        </dl>
        <p v-if="summary?.blocking && summary.errors" class="alert alert-warning">
          {{ summary.errors }} Fehler blockieren den Import. Zeilen mit rotem Rand aufklappen und
          die markierten Felder ergänzen oder korrigieren.
        </p>

        <div class="review-grid">
          <div class="viewer-column">
            <ImportPageViewer
              v-if="selectedPage"
              :page="selectedPage"
              :boxes="pageBoxes"
              :selected-key="selectedRowKey"
              @select="onViewerSelect"
            />
          </div>

          <div class="rows-column">
            <div class="table-scroll">
              <table class="ledger-table rows-table">
                <thead>
                  <tr>
                    <th><span class="sr-only">Importieren</span></th>
                    <th>Nr.</th>
                    <th>Typ</th>
                    <th>Bezeichnung</th>
                    <th>Ausgegeben an</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  <template v-for="row in draft.instruments" :key="row.key">
                    <tr
                      :class="[rowClass(row), { selected: row.key === selectedRowKey }]"
                      @click="selectRow(row.key)"
                    >
                      <td class="cell-check">
                        <input
                          v-model="row.skip"
                          type="checkbox"
                          :true-value="false"
                          :false-value="true"
                          :disabled="readOnly"
                          :aria-label="`Zeile ${rowLabel(row)} importieren`"
                          @change="scheduleSave"
                        />
                      </td>
                      <td class="cell-nr">
                        <input
                          v-model="row.inventory_nr"
                          class="input-narrow"
                          :class="{
                            invalid: fieldIssue(row.key, 'inventory_nr')?.level === 'error',
                          }"
                          :disabled="readOnly || row.skip"
                          aria-label="Inventarnummer"
                          @input="scheduleSave"
                        />
                      </td>
                      <td class="cell-type">
                        <select
                          :value="typeValue(row)"
                          :class="{
                            invalid: fieldIssue(row.key, 'instrument_type_id')?.level === 'error',
                          }"
                          :disabled="readOnly || row.skip"
                          aria-label="Instrumententyp"
                          @change="setType(row, $event.target.value)"
                        >
                          <option value="">– wählen –</option>
                          <option v-for="t in instrumentTypes" :key="t.id" :value="t.id">
                            {{ t.label }}
                          </option>
                        </select>
                        <span
                          v-if="row.instrument_type"
                          class="source-hint"
                          :title="`Im Dokument: ${row.instrument_type}`"
                        >
                          „{{ row.instrument_type }}“
                        </span>
                      </td>
                      <td>
                        <input
                          v-model="row.label"
                          :disabled="readOnly || row.skip"
                          :placeholder="row.instrument_type || ''"
                          aria-label="Bezeichnung"
                          @input="scheduleSave"
                        />
                      </td>
                      <td class="cell-loan">
                        <template v-if="row.loan">
                          <span class="loan-summary">
                            {{ musicianNames(row).last }} {{ musicianNames(row).first }}
                            <span v-if="row.loan.start_date" class="text-muted"
                              >seit {{ row.loan.start_date }}</span
                            >
                          </span>
                        </template>
                        <span v-else class="text-muted">–</span>
                      </td>
                      <td class="cell-status">
                        <span v-if="row.skip" class="badge badge-gray">Übersprungen</span>
                        <template v-else>
                          <span v-if="issueCount(row.key, 'error')" class="badge badge-danger">
                            {{ issueCount(row.key, "error") }} Fehler
                          </span>
                          <span v-if="issueCount(row.key, 'warning')" class="badge badge-warning">
                            {{ issueCount(row.key, "warning") }} prüfen
                          </span>
                          <span
                            v-if="!issueCount(row.key, 'error') && !issueCount(row.key, 'warning')"
                            class="badge badge-success"
                          >
                            OK
                          </span>
                        </template>
                        <button
                          type="button"
                          class="btn btn-xs btn-muted expand-btn"
                          :aria-pressed="selectedRowKey === row.key"
                          @click.stop="selectRow(row.key)"
                        >
                          Details
                        </button>
                      </td>
                    </tr>
                  </template>
                  <tr v-if="!draft.instruments.length">
                    <td colspan="6" class="empty-note">
                      Das Modell hat auf den Seiten keine Instrumente erkannt.
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

            <section v-if="selectedRow" class="row-detail" aria-live="polite">
              <div class="row-detail-head">
                <h3>{{ rowLabel(selectedRow) || "Zeile" }}</h3>
                <button type="button" class="btn btn-xs btn-muted" @click="selectedRowKey = null">
                  Schließen
                </button>
              </div>
              <div class="detail-grid-wrap">
                <ul v-if="rowIssues(selectedRow.key).length" class="issues">
                  <li
                    v-for="(issue, i) in rowIssues(selectedRow.key)"
                    :key="i"
                    :class="['issue', issue.level]"
                  >
                    <span class="issue-level">
                      {{
                        issue.level === "error"
                          ? "Fehler"
                          : issue.level === "warning"
                            ? "Prüfen"
                            : "Hinweis"
                      }}
                    </span>
                    {{ issue.message }}
                    <button
                      v-if="hasApplicableSuggestion(issue) && !readOnly"
                      type="button"
                      class="btn btn-xs"
                      @click="applySuggestion(selectedRow, issue)"
                    >
                      Vorschlag übernehmen
                    </button>
                  </li>
                </ul>

                <div class="detail-fields">
                  <label>
                    Hersteller
                    <input
                      v-model="selectedRow.manufacturer"
                      :disabled="readOnly"
                      @input="scheduleSave"
                    />
                  </label>
                  <label>
                    Seriennummer
                    <input
                      v-model="selectedRow.serial_nr"
                      :disabled="readOnly"
                      @input="scheduleSave"
                    />
                  </label>
                  <label>
                    Baujahr
                    <input
                      v-model="selectedRow.construction_year"
                      :disabled="readOnly"
                      inputmode="numeric"
                      @input="scheduleSave"
                    />
                  </label>
                  <label>
                    Modell
                    <input v-model="selectedRow.model" :disabled="readOnly" @input="scheduleSave" />
                  </label>
                  <label>
                    Händler
                    <input
                      v-model="selectedRow.distributor"
                      :disabled="readOnly"
                      @input="scheduleSave"
                    />
                  </label>
                  <label>
                    Koffer / Etui
                    <input
                      v-model="selectedRow.container"
                      :disabled="readOnly"
                      @input="scheduleSave"
                    />
                  </label>
                  <label>
                    Anschaffung (Datum)
                    <input
                      v-model="selectedRow.acquisition_date"
                      :disabled="readOnly"
                      placeholder="TT.MM.JJJJ"
                      @input="scheduleSave"
                    />
                  </label>
                  <label>
                    Anschaffung (Preis)
                    <input
                      v-model="selectedRow.acquisition_cost"
                      :disabled="readOnly"
                      placeholder="z.B. 1.200 € oder 12.000 ATS"
                      @input="scheduleSave"
                    />
                  </label>
                  <label>
                    Eigentümer
                    <input
                      v-model="selectedRow.owner"
                      :disabled="readOnly"
                      placeholder="MV Hofkirchen"
                      @input="scheduleSave"
                    />
                  </label>
                  <label class="span-2">
                    Besonderheiten
                    <input
                      v-model="selectedRow.particularities"
                      :disabled="readOnly"
                      @input="scheduleSave"
                    />
                  </label>
                </div>

                <div class="loan-block">
                  <div class="loan-head">
                    <strong>Leihe</strong>
                    <button
                      v-if="selectedRow.loan && !readOnly"
                      type="button"
                      class="btn btn-xs btn-muted"
                      @click="removeLoan(selectedRow)"
                    >
                      Keine Leihe
                    </button>
                    <button
                      v-else-if="!selectedRow.loan && !readOnly"
                      type="button"
                      class="btn btn-xs"
                      @click="addLoan(selectedRow)"
                    >
                      Leihe erfassen
                    </button>
                  </div>
                  <div v-if="selectedRow.loan" class="detail-fields">
                    <label class="span-2">
                      Musiker
                      <select
                        :value="musicianValue(selectedRow)"
                        :disabled="readOnly"
                        @change="setMusician(selectedRow, $event.target.value)"
                      >
                        <option value="">– neu anlegen –</option>
                        <option v-for="m in musicians" :key="m.id" :value="m.id">
                          {{ m.last_name }} {{ m.first_name }}
                        </option>
                      </select>
                      <span v-if="selectedRow.loan.musician_name" class="source-hint"
                        >Im Dokument: „{{ selectedRow.loan.musician_name }}“</span
                      >
                    </label>
                    <template v-if="musicianValue(selectedRow) === ''">
                      <label>
                        Nachname
                        <input
                          :value="musicianNames(selectedRow).last"
                          :class="{ invalid: fieldIssue(selectedRow.key, 'loan.last_name') }"
                          :disabled="readOnly"
                          @input="setMusicianName(selectedRow, 'last', $event.target.value)"
                        />
                      </label>
                      <label>
                        Vorname
                        <input
                          :value="musicianNames(selectedRow).first"
                          :class="{ invalid: fieldIssue(selectedRow.key, 'loan.first_name') }"
                          :disabled="readOnly"
                          @input="setMusicianName(selectedRow, 'first', $event.target.value)"
                        />
                      </label>
                    </template>
                    <label>
                      Ausgegeben am
                      <input
                        v-model="selectedRow.loan.start_date"
                        :class="{
                          invalid:
                            fieldIssue(selectedRow.key, 'loan.start_date')?.level === 'error',
                        }"
                        :disabled="readOnly"
                        placeholder="TT.MM.JJJJ"
                        @input="scheduleSave"
                      />
                    </label>
                    <label>
                      Zurück am (leer = aktiv)
                      <input
                        v-model="selectedRow.loan.end_date"
                        :disabled="readOnly"
                        placeholder="TT.MM.JJJJ"
                        @input="scheduleSave"
                      />
                    </label>
                  </div>
                </div>

                <p v-if="selectedRow.source_text" class="source-text">
                  <span class="text-muted">Gelesen:</span> „{{ selectedRow.source_text }}“
                  <span
                    v-if="selectedRow.confidence"
                    :class="[
                      'badge',
                      selectedRow.confidence === 'low' ? 'badge-warning' : 'badge-gray',
                    ]"
                  >
                    {{
                      selectedRow.confidence === "high"
                        ? "sicher"
                        : selectedRow.confidence === "medium"
                          ? "mittel"
                          : "unsicher"
                    }}
                  </span>
                  <span v-if="pageOfRow(selectedRow)" class="text-muted"
                    >· Seite {{ pageOfRow(selectedRow).page_index + 1 }}</span
                  >
                </p>
              </div>
            </section>

            <!-- Photos -->
            <div v-if="draft.photos.length" class="photos">
              <h3>Fotos</h3>
              <p class="text-muted">
                Jedes Foto einer Zeile zuordnen. Es wird als Bild des Instruments gespeichert, das
                erste als Profilbild.
              </p>
              <ul class="photo-list">
                <li
                  v-for="photo in draft.photos"
                  :key="photo.key"
                  class="photo"
                  :class="{ selected: photo.key === selectedRowKey }"
                  @click="
                    selectedRowKey = photo.key;
                    selectedPageId = photo.page_id;
                  "
                >
                  <img :src="cropUrl(photo)" :alt="photo.caption || 'Foto'" loading="lazy" />
                  <div class="photo-meta">
                    <span v-if="photo.caption" class="source-hint">„{{ photo.caption }}“</span>
                    <select
                      v-model="photo.row_key"
                      :disabled="readOnly"
                      aria-label="Zeile für dieses Foto"
                      @change="scheduleSave"
                    >
                      <option :value="null">– nicht übernehmen –</option>
                      <option
                        v-for="row in draft.instruments"
                        :key="row.key"
                        :value="row.key"
                        :disabled="row.skip"
                      >
                        {{ rowLabel(row) || row.key }}
                      </option>
                    </select>
                  </div>
                </li>
              </ul>
            </div>
          </div>
        </div>
      </section>

      <div v-if="importError" class="alert alert-danger" role="alert">{{ importError }}</div>

      <ConfirmDialog
        :open="confirmImportOpen"
        title="In den Bestand übernehmen"
        :message="importMessage + ' Der Vorgang kann nicht rückgängig gemacht werden.'"
        confirm-label="Importieren"
        @confirm="runImport"
        @cancel="confirmImportOpen = false"
      />
    </template>
  </div>
</template>

<style scoped>
.loading-wrap {
  display: flex;
  justify-content: center;
  padding: 3rem;
}

.page-header {
  align-items: flex-start;
}

.header-left {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  min-width: 0;
}

.back-link {
  color: var(--color-primary);
  font-size: 0.9rem;
}

.title-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.header-actions {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.nowrap {
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}

.result-table {
  margin-top: var(--space-3);
}

.result-musicians {
  margin-top: var(--space-3);
}

/* Dropzone */
.dropzone {
  border: 1px dashed var(--color-border);
  border-radius: var(--radius);
  padding: 1rem 1.25rem;
  text-align: center;
  transition:
    border-color var(--transition),
    background var(--transition);
}

.dropzone p {
  margin: 0.25rem 0;
}

.dropzone.drag-over {
  border-color: var(--color-primary);
  background: var(--color-bg-soft);
}

.dropzone.disabled {
  opacity: 0.6;
}

/* Thumbnails */
.thumbs {
  display: flex;
  gap: 0.75rem;
  overflow-x: auto;
  padding: 1rem 0 0.5rem;
}

.thumb {
  flex: 0 0 auto;
  width: 7.5rem;
  padding: 0;
  border: 2px solid var(--color-border);
  border-radius: var(--radius);
  background: var(--color-bg);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  min-height: 44px;
}

.thumb img {
  display: block;
  width: 100%;
  aspect-ratio: 1 / 1.3;
  object-fit: cover;
  object-position: top;
}

.thumb.active {
  border-color: var(--color-primary);
}

.thumb-label {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.25rem;
  padding: 0.3rem 0.4rem;
  font-size: 0.75rem;
  font-variant-numeric: tabular-nums;
}

/* Analysis log */
.analysis-log {
  margin-top: 1rem;
  padding: 0.75rem 1rem;
  border-left: 3px solid var(--color-primary);
  background: var(--color-bg-soft);
  font-size: 0.875rem;
}

.analysis-running {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin: 0 0 0.5rem;
}

.analysis-running :deep(.spinner-container) {
  padding: 0;
}

.analysis-log ul {
  margin: 0;
  padding-left: 1.25rem;
  color: var(--color-muted);
}

/* Review */
.save-state {
  font-size: 0.8rem;
  color: var(--color-muted);
  min-height: 1.2em;
}

.save-state.error {
  color: var(--color-danger);
}

.summary {
  margin-bottom: var(--space-4);
}

.summary .key-figure dd {
  font-size: 1.5rem;
}

.review-grid {
  display: grid;
  grid-template-columns: minmax(0, 4fr) minmax(0, 8fr);
  gap: var(--space-5);
  align-items: start;
}

.viewer-column {
  position: sticky;
  top: var(--space-4);
}

.rows-table {
  max-width: none;
  width: 100%;
}

.rows-table input,
.rows-table select {
  padding: 0.35rem 0.5rem;
  font-size: 0.875rem;
  min-height: 36px;
  width: 100%;
  min-width: 5rem;
}

.rows-table td {
  vertical-align: top;
}

.rows-table tbody tr {
  cursor: pointer;
}

.rows-table tr.selected > td {
  background: var(--color-bg-soft);
}

.rows-table tr.row-error > td:first-child {
  box-shadow: inset 3px 0 0 var(--color-danger);
}

.rows-table tr.row-warning > td:first-child {
  box-shadow: inset 3px 0 0 var(--color-warning);
}

.rows-table tr.row-skipped > td {
  opacity: 0.55;
}

.cell-check {
  width: 2rem;
}

.cell-check input {
  width: 1.1rem;
  height: 1.1rem;
  min-height: 0;
}

.cell-nr {
  width: 5rem;
}

.cell-nr input {
  width: 4rem;
  min-width: 0;
  font-variant-numeric: tabular-nums;
}

.cell-type {
  min-width: 8rem;
}

.cell-type select {
  width: 100%;
}

.source-hint {
  display: block;
  margin-top: 0.15rem;
  font-size: 0.75rem;
  color: var(--color-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
}

.cell-loan {
  min-width: 8rem;
  font-size: 0.875rem;
}

.loan-summary {
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
  padding-top: 0.45rem;
}

.cell-status {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.35rem;
  min-width: 5.5rem;
}

.expand-btn {
  min-width: 36px;
  min-height: 36px;
}

.invalid {
  border-color: var(--color-danger) !important;
}

.row-detail {
  margin-top: var(--space-4);
  padding: 1rem 1.25rem;
  border: 1px solid var(--color-border);
  border-left: 3px solid var(--color-primary);
  border-radius: var(--radius);
}

.row-detail-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  margin-bottom: 0.75rem;
}

.row-detail-head h3 {
  margin: 0;
  font-size: 1rem;
}

.detail-grid-wrap {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.issues {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  font-size: 0.875rem;
}

.issue {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.issue-level {
  font-size: 0.7rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  padding: 0.1rem 0.4rem;
  border-radius: var(--radius);
  background: var(--color-info-bg);
  color: var(--color-info);
}

.issue.error .issue-level {
  background: var(--color-danger-bg);
  color: var(--color-danger);
}

.issue.warning .issue-level {
  background: var(--color-warning-bg);
  color: var(--color-warning);
}

.detail-fields {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(11rem, 1fr));
  gap: 0.5rem 0.75rem;
}

.detail-fields label {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--color-muted);
}

.detail-fields input,
.detail-fields select {
  font-weight: 400;
  letter-spacing: normal;
  text-transform: none;
  color: var(--color-text);
}

.detail-fields .span-2 {
  grid-column: span 2;
}

.loan-block {
  border-top: 1px solid var(--color-border);
  padding-top: 0.75rem;
}

.loan-head {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 0.5rem;
}

.source-text {
  margin: 0;
  font-size: 0.85rem;
  display: flex;
  gap: 0.4rem;
  align-items: center;
  flex-wrap: wrap;
}

/* Photos */
.photos {
  margin-top: var(--space-5);
}

.photos h3 {
  font-size: 1rem;
  margin: 0 0 0.25rem;
}

.photo-list {
  list-style: none;
  margin: 0.75rem 0 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(10rem, 1fr));
  gap: 0.75rem;
}

.photo {
  border: 2px solid var(--color-border);
  border-radius: var(--radius);
  overflow: hidden;
  background: var(--color-bg);
  cursor: pointer;
}

.photo.selected {
  border-color: var(--color-success);
}

.photo img {
  display: block;
  width: 100%;
  aspect-ratio: 1;
  object-fit: contain;
  background: var(--color-bg-soft);
}

.photo-meta {
  padding: 0.5rem;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.photo-meta select {
  font-size: 0.8rem;
  padding: 0.35rem 0.5rem;
  min-height: 36px;
}

@media (max-width: 960px) {
  .review-grid {
    grid-template-columns: 1fr;
  }

  .viewer-column {
    position: static;
  }
}
</style>
