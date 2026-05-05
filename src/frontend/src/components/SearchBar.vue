<script setup>
const model = defineModel({ type: String, default: "" });
defineProps({ placeholder: { type: String, default: "Suchen..." } });
</script>

<template>
  <div class="search-wrapper">
    <svg class="search-icon" viewBox="0 0 20 20" fill="currentColor" width="16" height="16">
      <path
        fill-rule="evenodd"
        d="M9 3.5a5.5 5.5 0 1 0 0 11 5.5 5.5 0 0 0 0-11ZM2 9a7 7 0 1 1 12.45 4.39l3.58 3.58a.75.75 0 1 1-1.06 1.06l-3.58-3.58A7 7 0 0 1 2 9Z"
        clip-rule="evenodd"
      />
    </svg>
    <input
      type="search"
      :placeholder="placeholder"
      :value="model"
      class="search-input"
      @input="model = $event.target.value"
    />
  </div>
</template>

<style scoped>
.search-wrapper {
  position: relative;
  max-width: 100%;
}

.search-icon {
  position: absolute;
  left: 0.75rem;
  top: 50%;
  transform: translateY(-50%);
  color: var(--color-muted);
  pointer-events: none;
}

.search-input {
  padding-left: 2.25rem;
  max-width: 100%;
}
</style>
