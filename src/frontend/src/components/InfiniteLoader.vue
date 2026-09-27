<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from "vue";

const props = defineProps({
  hasMore: Boolean,
  loading: Boolean,
  error: { type: String, default: "" },
  count: { type: Number, default: 0 },
  total: { type: Number, default: 0 },
});
const emit = defineEmits(["load-more"]);

const el = ref(null);
let observer = null;
let visible = false;

function maybeLoad() {
  if (visible && props.hasMore && !props.loading && !props.error) emit("load-more");
}

onMounted(() => {
  if (typeof IntersectionObserver === "undefined") return;
  observer = new IntersectionObserver(
    (entries) => {
      visible = entries.some((e) => e.isIntersecting);
      maybeLoad();
    },
    { rootMargin: "400px 0px" },
  );
  observer.observe(el.value);
});

onBeforeUnmount(() => observer?.disconnect());

// After a page arrives the sentinel may still be on screen (tall window).
watch(() => [props.loading, props.hasMore], maybeLoad, { flush: "post" });
</script>

<template>
  <div ref="el" class="infinite-loader" aria-live="polite">
    <p v-if="error" class="form-error" role="alert">
      {{ error }}
      <button type="button" class="btn-sm" @click="$emit('load-more')">Erneut versuchen</button>
    </p>
    <p v-else-if="loading" class="text-muted">Wird geladen …</p>
    <template v-else-if="total > 0">
      <p class="text-muted infinite-count">{{ count }} von {{ total }}</p>
      <button v-if="hasMore" type="button" class="btn-sm" @click="$emit('load-more')">
        Weitere laden
      </button>
    </template>
  </div>
</template>

<style scoped>
.infinite-loader {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2);
  min-height: 1px;
  padding: var(--space-4) 0;
}

.infinite-loader p {
  margin: 0;
}

.infinite-count {
  font-variant-numeric: tabular-nums;
}

.infinite-loader .btn-sm {
  min-height: 44px;
}
</style>
