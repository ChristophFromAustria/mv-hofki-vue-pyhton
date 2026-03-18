<script setup>
import { ref, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import { get, del } from "../lib/api.js";
import ConfirmDialog from "../components/ConfirmDialog.vue";

const route = useRoute();
const router = useRouter();
const instrument = ref(null);
const loans = ref([]);
const showDelete = ref(false);

onMounted(async () => {
  instrument.value = await get(`/instruments/${route.params.id}`);
  loans.value = await get(`/loans?instrument_id=${route.params.id}`);
});

async function remove() {
  await del(`/instruments/${route.params.id}`);
  router.push("/instrumente");
}
</script>

<template>
  <div v-if="instrument">
    <div class="page-header">
      <h1>{{ instrument.instrument_type.label }} #{{ instrument.inventory_nr }}</h1>
      <div style="display: flex; gap: 0.5rem">
        <router-link :to="`/instrumente/${instrument.id}/bearbeiten`" class="btn">
          Bearbeiten
        </router-link>
        <button class="btn-danger" @click="showDelete = true">Löschen</button>
      </div>
    </div>

    <div class="card" style="margin-bottom: 1.5rem">
      <dl class="detail-grid">
        <dt>Inventarnummer</dt>
        <dd>{{ instrument.inventory_nr }}</dd>
        <dt>Typ</dt>
        <dd>
          {{ instrument.instrument_type.label }} ({{ instrument.instrument_type.label_short }})
        </dd>
        <dt>Bezeichnungszusatz</dt>
        <dd>{{ instrument.label_addition || "—" }}</dd>
        <dt>Hersteller</dt>
        <dd>{{ instrument.manufacturer || "—" }}</dd>
        <dt>Seriennummer</dt>
        <dd>{{ instrument.serial_nr || "—" }}</dd>
        <dt>Baujahr</dt>
        <dd>{{ instrument.construction_year || "—" }}</dd>
        <dt>Eigentümer</dt>
        <dd>{{ instrument.owner }}</dd>
        <dt>Händler</dt>
        <dd>{{ instrument.distributor || "—" }}</dd>
        <dt>Anschaffungsdatum</dt>
        <dd>{{ instrument.acquisition_date || "—" }}</dd>
        <dt>Anschaffungskosten</dt>
        <dd>
          {{
            instrument.acquisition_cost != null
              ? `${instrument.acquisition_cost} ${instrument.currency.abbreviation}`
              : "—"
          }}
        </dd>
        <dt>Behältnis</dt>
        <dd>{{ instrument.container || "—" }}</dd>
        <dt>Besonderheiten</dt>
        <dd>{{ instrument.particularities || "—" }}</dd>
        <dt>Notizen</dt>
        <dd>{{ instrument.notes || "—" }}</dd>
      </dl>
    </div>

    <div v-if="loans.length" class="card">
      <h2 style="font-size: 1.1rem; margin-bottom: 1rem">Leihhistorie</h2>
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

    <ConfirmDialog
      :open="showDelete"
      title="Instrument löschen"
      message="Soll dieses Instrument wirklich gelöscht werden?"
      @confirm="remove"
      @cancel="showDelete = false"
    />
  </div>
</template>
