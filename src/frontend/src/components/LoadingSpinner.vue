<script setup>
defineProps({
  size: { type: String, default: "2rem" },
});
</script>

<template>
  <div class="spinner-container">
    <div class="spinner" :style="{ width: size, height: size }"></div>
  </div>
</template>

<style scoped>
.spinner-container {
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 2rem;
}

.spinner {
  border: 3px solid var(--color-border);
  border-top-color: var(--color-primary);
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
