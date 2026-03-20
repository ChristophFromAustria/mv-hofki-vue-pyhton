<script setup>
import { ref, onMounted, onUnmounted } from "vue";

const props = defineProps({
  columns: { type: Array, default: () => [] },
  rows: { type: Array, default: () => [] },
  loading: Boolean,
  cardBreakpoint: { type: Number, default: 0 },
});
defineEmits(["row-click"]);

const useCards = ref(false);

function checkWidth() {
  useCards.value = props.cardBreakpoint > 0 && window.innerWidth <= props.cardBreakpoint;
}

onMounted(() => {
  checkWidth();
  window.addEventListener("resize", checkWidth);
});

onUnmounted(() => {
  window.removeEventListener("resize", checkWidth);
});
</script>

<template>
  <!-- Card layout for mobile when cardBreakpoint is set -->
  <div v-if="useCards" class="dt-cards">
    <div v-if="loading" class="dt-empty">Laden...</div>
    <div v-else-if="!rows?.length" class="dt-empty">Keine Einträge</div>
    <div v-for="row in rows" :key="row.id" class="dt-card" @click="$emit('row-click', row)">
      <div v-for="col in columns" :key="col.key" class="dt-card-row">
        <span class="dt-card-label">{{ col.label }}</span>
        <span class="dt-card-value">
          <slot :name="col.key" :row="row" :value="row[col.key]">
            {{ row[col.key] }}
          </slot>
        </span>
      </div>
    </div>
  </div>

  <!-- Standard table with horizontal scroll -->
  <div v-else class="table-scroll">
    <table>
      <thead>
        <tr>
          <th v-for="col in columns" :key="col.key" :class="col.class">{{ col.label }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="loading">
          <td :colspan="columns.length" style="text-align: center; padding: 2rem">Laden...</td>
        </tr>
        <tr v-else-if="!rows?.length">
          <td
            :colspan="columns.length"
            style="text-align: center; padding: 2rem; color: var(--color-muted)"
          >
            Keine Einträge
          </td>
        </tr>
        <tr
          v-for="row in rows"
          :key="row.id"
          style="cursor: pointer"
          @click="$emit('row-click', row)"
        >
          <td v-for="col in columns" :key="col.key" :class="col.class">
            <slot :name="col.key" :row="row" :value="row[col.key]">
              {{ row[col.key] }}
            </slot>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.table-scroll {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}

.dt-empty {
  text-align: center;
  padding: 2rem;
  color: var(--color-muted);
}

.dt-cards {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.dt-card {
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 0.75rem 1rem;
  background: var(--color-bg);
  cursor: pointer;
}

.dt-card:hover {
  box-shadow: 0 2px 8px var(--color-shadow);
}

.dt-card-row {
  display: flex;
  justify-content: space-between;
  padding: 0.25rem 0;
  font-size: 0.875rem;
}

.dt-card-row + .dt-card-row {
  border-top: 1px solid var(--color-border);
}

.dt-card-label {
  color: var(--color-muted);
  font-weight: 500;
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.025em;
}

.dt-card-value {
  text-align: right;
}
</style>
