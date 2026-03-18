<script setup>
import { ref, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import { get, del } from "../lib/api.js";
import ConfirmDialog from "../components/ConfirmDialog.vue";

const route = useRoute();
const router = useRouter();
const musician = ref(null);
const loans = ref([]);
const showDelete = ref(false);

onMounted(async () => {
  musician.value = await get(`/musicians/${route.params.id}`);
  loans.value = await get(`/loans?musician_id=${route.params.id}`);
});

async function remove() {
  try {
    await del(`/musicians/${route.params.id}`);
    router.push("/musiker");
  } catch (e) {
    alert("Fehler: " + e.message);
    showDelete.value = false;
  }
}
</script>

<template>
  <div v-if="musician">
    <div class="page-header">
      <h1>{{ musician.first_name }} {{ musician.last_name }}</h1>
      <div style="display: flex; gap: 0.5rem">
        <router-link :to="`/musiker/${musician.id}/bearbeiten`" class="btn">
          Bearbeiten
        </router-link>
        <button class="btn-danger" @click="showDelete = true">Löschen</button>
      </div>
    </div>

    <div class="card" style="margin-bottom: 1.5rem">
      <dl class="detail-grid">
        <dt>Vorname</dt>
        <dd>{{ musician.first_name }}</dd>
        <dt>Nachname</dt>
        <dd>{{ musician.last_name }}</dd>
        <dt>Telefon</dt>
        <dd>{{ musician.phone || "—" }}</dd>
        <dt>E-Mail</dt>
        <dd>{{ musician.email || "—" }}</dd>
        <dt>Adresse</dt>
        <dd>{{ musician.street_address || "—" }}</dd>
        <dt>PLZ / Ort</dt>
        <dd>
          {{ [musician.postal_code, musician.city].filter(Boolean).join(" ") || "—" }}
        </dd>
        <dt>Extern</dt>
        <dd>{{ musician.is_extern ? "Ja" : "Nein" }}</dd>
        <dt>Notizen</dt>
        <dd>{{ musician.notes || "—" }}</dd>
      </dl>
    </div>

    <div v-if="loans.length" class="card">
      <h2 style="font-size: 1.1rem; margin-bottom: 1rem">Ausgeliehene Instrumente</h2>
      <table>
        <thead>
          <tr>
            <th>Instrument</th>
            <th>Inv.-Nr.</th>
            <th>Von</th>
            <th>Bis</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="l in loans" :key="l.id">
            <td>
              <router-link :to="`/instrumente/${l.instrument.id}`">
                {{ l.instrument.instrument_type.label }}
              </router-link>
            </td>
            <td>{{ l.instrument.inventory_nr }}</td>
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
      title="Musiker löschen"
      message="Soll dieser Musiker wirklich gelöscht werden?"
      @confirm="remove"
      @cancel="showDelete = false"
    />
  </div>
</template>
