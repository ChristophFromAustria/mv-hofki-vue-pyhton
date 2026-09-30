<script setup>
import { ref, computed, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import { get, getAll, put, del } from "../lib/api.js";
import { CATEGORIES } from "../lib/categories.js";
import { registerLabels } from "../lib/musicians.js";
import { sortRegisters } from "../lib/registers.js";
import { musicianFieldDefs } from "../lib/musicianFields.js";
import ConfirmDialog from "../components/ConfirmDialog.vue";
import CollapsibleSection from "../components/CollapsibleSection.vue";
import InlineField from "../components/InlineField.vue";
import NotesBlock from "../components/NotesBlock.vue";
import { useInlineEdit } from "../composables/useInlineEdit.js";

const route = useRoute();
const router = useRouter();
const musician = ref(null);
const loans = ref([]);
const registers = ref([]);
const showDelete = ref(false);
const loadError = ref("");
const deleteError = ref("");

const defs = computed(() => musicianFieldDefs(registers.value));
// Notes render as a full-width NotesBlock with a dialog editor, below the
// <dl>, instead of inline.
const membershipInlineFields = computed(() => defs.value.membership.filter((f) => !f.block));
const membershipBlockFields = computed(() => defs.value.membership.filter((f) => f.block));

const inline = useInlineEdit(async (patch) => {
  musician.value = await put(`/musicians/${route.params.id}`, patch);
});

const membershipSummary = computed(() => {
  const status = musician.value?.is_active === false ? "Inaktiv" : "Aktiv";
  const regs = registerLabels(musician.value);
  return regs !== "—" ? `${status} · ${regs}` : status;
});
const contactSummary = computed(() => musician.value?.phone || musician.value?.email || "—");
const historySummary = computed(
  () => `${loans.value.length} ${loans.value.length === 1 ? "Eintrag" : "Einträge"}`,
);

onMounted(async () => {
  try {
    const [m, l, r] = await Promise.all([
      get(`/musicians/${route.params.id}`),
      getAll(`/loans?musician_id=${route.params.id}`),
      get("/registers").catch(() => []),
    ]);
    musician.value = m;
    loans.value = l;
    registers.value = sortRegisters(r);
  } catch (e) {
    loadError.value = e.message;
  }
});

async function remove() {
  deleteError.value = "";
  try {
    await del(`/musicians/${route.params.id}`);
    router.push("/musiker");
  } catch (e) {
    deleteError.value = "Löschen fehlgeschlagen: " + e.message;
    showDelete.value = false;
  }
}
</script>

<template>
  <div v-if="loadError" class="alert alert-danger" role="alert">
    Musiker konnte nicht geladen werden: {{ loadError }}
  </div>
  <div v-else-if="musician">
    <div class="page-header">
      <h1>
        {{ musician.first_name }} {{ musician.last_name }}
        <span v-if="musician.is_active === false" class="badge badge-gray title-badge">
          inaktiv
        </span>
      </h1>
      <div class="cluster">
        <router-link :to="`/musiker/${musician.id}/bearbeiten`" class="btn">
          Bearbeiten
        </router-link>
        <button class="btn-danger" @click="showDelete = true">Löschen</button>
      </div>
    </div>

    <div v-if="deleteError" class="alert alert-danger page-alert" role="alert">
      {{ deleteError }}
    </div>

    <CollapsibleSection
      scope="musician"
      section="membership"
      title="Mitgliedschaft"
      :summary="membershipSummary"
    >
      <dl class="detail-grid">
        <InlineField
          v-for="f in membershipInlineFields"
          :key="f.key"
          :field-key="f.key"
          :label="f.label"
          :type="f.type"
          :value="f.value(musician)"
          :options="f.options || []"
          :required="!!f.required"
          :min="f.min ?? null"
          :max="f.max ?? null"
          :editing="inline.editingKey.value === f.key"
          :saving="inline.savingKey.value === f.key"
          :saved="inline.savedKey.value === f.key"
          :error="
            inline.editingKey.value === f.key || inline.failedKey.value === f.key
              ? inline.error.value
              : ''
          "
          :on-text="f.onText"
          :off-text="f.offText"
          @start="inline.start(f.key)"
          @cancel="inline.cancel()"
          @save="(v) => inline.commit(f.key, f.toPatch(v))"
        >
          <template v-if="f.key === 'registers'" #display>
            {{ registerLabels(musician) }}
          </template>
        </InlineField>
      </dl>

      <NotesBlock
        v-for="f in membershipBlockFields"
        :key="f.key"
        :label="f.label"
        :value="f.value(musician)"
        :max-length="f.maxLength"
        :saving="inline.savingKey.value === f.key"
        :saved="inline.savedKey.value === f.key"
        :error="inline.editingKey.value === f.key ? inline.error.value : ''"
        :editing="inline.editingKey.value === f.key"
        @start="inline.start(f.key)"
        @cancel="inline.cancel()"
        @save="(v) => inline.commit(f.key, f.toPatch(v))"
      />
    </CollapsibleSection>

    <CollapsibleSection
      scope="musician"
      section="contact"
      title="Kontakt"
      :summary="contactSummary"
    >
      <dl class="detail-grid">
        <InlineField
          v-for="f in defs.contact"
          :key="f.key"
          :field-key="f.key"
          :label="f.label"
          :type="f.type"
          :value="f.value(musician)"
          :options="f.options || []"
          :required="!!f.required"
          :min="f.min ?? null"
          :max="f.max ?? null"
          :editing="inline.editingKey.value === f.key"
          :saving="inline.savingKey.value === f.key"
          :saved="inline.savedKey.value === f.key"
          :error="inline.editingKey.value === f.key ? inline.error.value : ''"
          @start="inline.start(f.key)"
          @cancel="inline.cancel()"
          @save="(v) => inline.commit(f.key, f.toPatch(v))"
        />
      </dl>
    </CollapsibleSection>

    <CollapsibleSection
      v-if="loans.length"
      scope="musician"
      section="history"
      title="Leihhistorie"
      :summary="historySummary"
    >
      <div class="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Gegenstand</th>
              <th>Inv.-Nr.</th>
              <th>Von</th>
              <th>Bis</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="l in loans" :key="l.id">
              <td>
                <router-link
                  :to="(CATEGORIES[l.item.category]?.routeBase || '/instrumente') + '/' + l.item.id"
                >
                  {{ l.item.label }}
                </router-link>
              </td>
              <td>{{ l.item.display_nr }}</td>
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
    </CollapsibleSection>

    <ConfirmDialog
      :open="showDelete"
      title="Musiker löschen"
      message="Soll dieser Musiker wirklich gelöscht werden?"
      @confirm="remove"
      @cancel="showDelete = false"
    />
  </div>
</template>

<style scoped>
.title-badge {
  vertical-align: middle;
  margin-left: var(--space-2);
}

.page-alert {
  margin-bottom: var(--space-4);
}
</style>
