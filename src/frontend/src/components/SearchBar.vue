<script setup>
const model = defineModel({ type: String, default: "" });
defineProps({ placeholder: { type: String, default: "Suchen..." } });
</script>

<template>
  <input
    type="search"
    :placeholder="placeholder"
    :value="model"
    class="search-input"
    @input="model = $event.target.value"
  />
</template>

<style scoped>
.search-input {
  max-width: 300px;
}
</style>
