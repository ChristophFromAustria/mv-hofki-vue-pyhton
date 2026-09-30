<script setup>
import {
  actorLabel,
  eventChanges,
  eventHeadline,
  eventLink,
  formatEventTime,
  shorten,
} from "../lib/events.js";

// Event log entries as a quiet ledger: when, who, what (with old → new).
defineProps({
  events: { type: Array, required: true },
  // In a record's own history the record label repeats; hide it for items
  // themselves but keep it for their loans/invoices.
  hideLabelFor: { type: String, default: "" },
});
</script>

<template>
  <ol class="event-list">
    <li v-for="e in events" :key="e.id" class="event">
      <div class="event-meta">
        <time :datetime="e.at">{{ formatEventTime(e.at) }}</time>
        <span class="event-actor">{{ actorLabel(e) }}</span>
      </div>
      <div class="event-body">
        <p class="event-headline">
          <span class="event-what">{{ eventHeadline(e) }}</span>
          <template v-if="e.entity_type !== hideLabelFor">
            <RouterLink v-if="eventLink(e)" :to="eventLink(e)" class="event-label">
              {{ e.entity_label }}
            </RouterLink>
            <span v-else class="event-label">{{ e.entity_label }}</span>
          </template>
        </p>
        <p v-if="e.summary" class="event-summary">{{ e.summary }}</p>
        <ul v-if="e.changes?.length" class="event-changes">
          <li v-for="(c, i) in eventChanges(e)" :key="i">
            <span class="event-field">{{ c.label }}:</span>
            <template v-if="c.long">
              <span class="event-old" :class="{ empty: c.oldEmpty }" :title="c.old">{{
                shorten(c.old)
              }}</span>
              <span aria-hidden="true"> → </span><span class="sr-only"> geändert in </span>
              <span class="event-new" :title="c.new">{{ shorten(c.new) }}</span>
            </template>
            <template v-else>
              <span class="event-old" :class="{ empty: c.oldEmpty }">{{ c.old }}</span>
              <span aria-hidden="true"> → </span><span class="sr-only"> geändert in </span>
              <span class="event-new">{{ c.new }}</span>
            </template>
          </li>
        </ul>
      </div>
    </li>
  </ol>
</template>

<style scoped>
.event-list {
  margin: 0;
  padding: 0;
  list-style: none;
}

.event {
  display: grid;
  grid-template-columns: 11rem 1fr;
  gap: var(--space-1) var(--space-4);
  padding: var(--space-2) 0;
  border-bottom: 1px solid var(--color-border);
}

.event-meta {
  display: flex;
  flex-direction: column;
  font-size: 0.8125rem;
  color: var(--color-muted);
  font-variant-numeric: tabular-nums;
  min-width: 0;
}

.event-actor {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.event-body {
  min-width: 0;
}

.event-headline,
.event-summary {
  margin: 0;
}

.event-what {
  font-weight: 500;
  margin-right: var(--space-2);
}

.event-summary {
  font-size: 0.875rem;
  color: var(--color-muted);
}

.event-changes {
  margin: var(--space-1) 0 0;
  padding: 0;
  list-style: none;
  font-size: 0.8125rem;
}

.event-field {
  color: var(--color-muted);
  margin-right: var(--space-1);
}

.event-old {
  color: var(--color-muted);
  text-decoration: line-through;
  text-decoration-color: var(--color-border);
}

.event-old.empty {
  text-decoration: none;
}

.event-changes li {
  overflow-wrap: anywhere;
}

@media (max-width: 640px) {
  .event {
    grid-template-columns: 1fr;
  }

  .event-meta {
    flex-direction: row;
    gap: var(--space-2);
  }
}
</style>
