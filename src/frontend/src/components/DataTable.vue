<script setup>
defineProps({
  columns: { type: Array, default: () => [] },
  rows: { type: Array, default: () => [] },
  loading: Boolean,
});
defineEmits(["row-click"]);
</script>

<template>
  <div class="table-wrap">
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
