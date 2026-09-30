<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { get } from "../lib/api.js";
import CollapsibleSection from "./CollapsibleSection.vue";
import EventList from "./EventList.vue";

// "Verlauf" on an item or musician page: its recorded changes, newest first.
const props = defineProps({
  scope: { type: String, required: true },
  itemId: { type: Number, default: null },
  musicianId: { type: Number, default: null },
  // Bump to reload after the page saved something.
  refreshKey: { type: Number, default: 0 },
});

const LIMIT = 20;
const events = ref([]);
const total = ref(0);
const error = ref("");

const param = computed(() =>
  props.itemId != null ? `item_id=${props.itemId}` : `musician_id=${props.musicianId}`,
);
const summary = computed(() =>
  total.value ? `${total.value} ${total.value === 1 ? "Eintrag" : "Einträge"}` : "Keine Einträge",
);

async function load() {
  error.value = "";
  try {
    const page = await get(`/events?${param.value}&limit=${LIMIT}`);
    events.value = page.items;
    total.value = page.total;
  } catch (e) {
    error.value = e?.message || "Verlauf konnte nicht geladen werden.";
  }
}

onMounted(load);
watch(() => [param.value, props.refreshKey], load);
</script>

<template>
  <CollapsibleSection :scope="scope" section="history-log" title="Verlauf" :summary="summary">
    <p v-if="error" class="form-error" role="alert">{{ error }}</p>
    <p v-else-if="!events.length" class="empty-note">Noch keine Änderungen protokolliert.</p>
    <template v-else>
      <EventList :events="events" :hide-label-for="itemId != null ? 'item' : 'musician'" />
      <p v-if="total > events.length" class="history-more">
        <RouterLink :to="`/protokoll?${param}`">
          Alle {{ total }} Einträge im Protokoll →
        </RouterLink>
      </p>
    </template>
  </CollapsibleSection>
</template>

<style scoped>
.history-more {
  margin: var(--space-2) 0 0;
}
</style>
