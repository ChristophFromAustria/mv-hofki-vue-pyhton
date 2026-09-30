<script setup>
defineProps({
  parts: { type: Array, required: true },
});
</script>

<template>
  <template v-for="(part, i) in parts" :key="i">
    <mark v-if="part.match">{{ part.text }}</mark>
    <template v-else>{{ part.text }}</template>
  </template>
</template>
