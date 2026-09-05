<script setup>
defineProps({
  open: Boolean,
  title: { type: String, default: "Bestätigung" },
  message: { type: String, default: "" },
  confirmLabel: { type: String, default: "Löschen" },
});
defineEmits(["confirm", "cancel"]);
</script>

<template>
  <Transition name="fade">
    <div v-if="open" class="overlay" @click.self="$emit('cancel')">
      <div class="dialog">
        <h3>{{ title }}</h3>
        <p style="margin-top: 0.5rem">{{ message }}</p>
        <div class="dialog-actions">
          <button @click="$emit('cancel')">Abbrechen</button>
          <button class="btn-danger" @click="$emit('confirm')">{{ confirmLabel }}</button>
        </div>
      </div>
    </div>
  </Transition>
</template>
