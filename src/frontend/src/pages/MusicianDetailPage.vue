<script setup>
import { ref, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import { get, del } from "../lib/api.js";
import { CATEGORIES } from "../lib/categories.js";
import { registerLabels } from "../lib/musicians.js";
import ConfirmDialog from "../components/ConfirmDialog.vue";

const route = useRoute();
const router = useRouter();
const musician = ref(null);
const loans = ref([]);
const showDelete = ref(false);
const loadError = ref("");
const deleteError = ref("");

onMounted(async () => {
  try {
    const [m, l] = await Promise.all([
      get(`/musicians/${route.params.id}`),
      get(`/loans?musician_id=${route.params.id}`),
    ]);
    musician.value = m;
    loans.value = l;
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

    <section class="page-section">
      <div class="section-header">
        <h2>Mitgliedschaft</h2>
      </div>
      <dl class="detail-grid">
        <dt>Status</dt>
        <dd>
          <span :class="musician.is_active === false ? 'badge badge-gray' : 'badge badge-green'">
            {{ musician.is_active === false ? "Inaktiv" : "Aktiv" }}
          </span>
        </dd>
        <dt>Register</dt>
        <dd>{{ registerLabels(musician) }}</dd>
        <dt>Extern</dt>
        <dd>{{ musician.is_extern ? "Ja" : "Nein" }}</dd>
        <dt>Notizen</dt>
        <dd class="text-pre-line">{{ musician.notes || "—" }}</dd>
      </dl>
    </section>

    <section class="page-section">
      <div class="section-header">
        <h2>Kontakt</h2>
      </div>
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
      </dl>
    </section>

    <section v-if="loans.length" class="page-section">
      <div class="section-header">
        <h2>Leihhistorie</h2>
      </div>
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
    </section>

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
