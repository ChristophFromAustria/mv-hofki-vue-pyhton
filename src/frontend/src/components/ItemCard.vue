<script setup>
import { RouterLink } from "vue-router";
import CategoryChips from "./CategoryChips.vue";

const props = defineProps({
  item: { type: Object, required: true },
  hasLoans: Boolean,
  to: { type: String, required: true },
  selecting: Boolean,
  selected: Boolean,
});
defineEmits(["toggle-select"]);
</script>

<template>
  <component
    :is="selecting ? 'label' : RouterLink"
    v-bind="selecting ? {} : { to }"
    class="item-card"
    :class="{ 'is-selected': selecting && selected }"
  >
    <input
      v-if="selecting"
      type="checkbox"
      class="item-card-check"
      :checked="selected"
      :aria-label="`„${props.item.label}“ auswählen`"
      @change="$emit('toggle-select')"
    />
    <span class="item-card-thumb">
      <img v-if="item.profile_image_url" :src="item.profile_image_url" alt="" />
      <span v-else>{{ item.display_nr }}</span>
    </span>
    <span class="item-card-body">
      <span class="item-card-title">
        {{ item.label }}
        <span v-if="item.quantity_label" class="item-card-quantity">{{ item.quantity_label }}</span>
      </span>
      <span class="item-card-meta">
        {{ item.display_nr }}{{ item.manufacturer ? " · " + item.manufacturer : "" }}
      </span>
      <span v-if="hasLoans && item.active_loan" class="item-card-borrower">
        <span class="sr-only">Ausgeliehen an </span>{{ item.active_loan.musician_name }}
      </span>
      <CategoryChips v-if="item.categories?.length" :categories="item.categories" />
    </span>
    <span v-if="hasLoans" class="item-card-status">
      <span :class="item.active_loan ? 'badge badge-green' : 'badge badge-gray'">
        {{ item.active_loan ? "Ausgeliehen" : "Verfügbar" }}
      </span>
    </span>
  </component>
</template>

<style scoped>
.item-card {
  position: relative;
  display: flex;
  flex-direction: column;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  overflow: hidden;
  background: var(--color-bg);
  color: inherit;
  text-decoration: none;
  cursor: pointer;
}

.item-card:hover {
  box-shadow: var(--shadow-float);
}

.item-card:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}

.item-card.is-selected {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 2px var(--color-primary-light);
}

.item-card-check {
  position: absolute;
  top: var(--space-2);
  right: var(--space-2);
  width: 22px;
  height: 22px;
  margin: 0;
  z-index: 1;
}

.item-card-thumb {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 120px;
  background: var(--color-bg-soft);
  color: var(--color-muted);
  font-size: 1.1rem;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.item-card-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.item-card-body {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  padding: var(--space-3);
}

.item-card-title {
  font-size: 0.9rem;
  font-weight: 600;
}

.item-card-quantity {
  margin-left: var(--space-1);
  font-weight: 500;
  color: var(--color-muted);
  font-variant-numeric: tabular-nums;
}

.item-card-meta {
  font-size: 0.8rem;
  color: var(--color-muted);
}

.item-card-borrower {
  font-size: 0.8rem;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.item-card-status {
  padding: 0 var(--space-3) var(--space-3);
}

/* Phone: one compact row per item, small picture on the left. */
@media (max-width: 640px) {
  .item-card {
    display: grid;
    grid-template-columns: 56px 1fr auto;
    align-items: center;
    gap: var(--space-3);
    min-height: 72px;
    padding: var(--space-2);
  }

  .item-card-thumb {
    grid-column: 1;
    grid-row: 1;
    width: 56px;
    height: 56px;
    border-radius: var(--radius-sm);
    overflow: hidden;
    font-size: 0.7rem;
    text-align: center;
  }

  .item-card-body {
    grid-column: 2;
    grid-row: 1;
    padding: 0;
    min-width: 0;
  }

  .item-card-title {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .item-card-status {
    grid-column: 3;
    grid-row: 1;
    padding: 0;
  }

  .item-card-check {
    position: absolute;
    top: var(--space-1);
    left: var(--space-1);
    z-index: 1;
  }
}
</style>
