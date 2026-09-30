<script setup>
import HighlightText from "./HighlightText.vue";
import { displayNrParts, highlightParts } from "../lib/highlight.js";

// One hit of the global search (popup and search page).
defineProps({
  entry: { type: Object, required: true },
  term: { type: String, default: "" },
});
</script>

<template>
  <span class="search-entry" :class="{ 'is-muted': entry.muted }">
    <span class="search-entry-main">
      <span class="search-entry-heading">
        <span v-if="entry.displayNr" class="search-entry-nr"
          ><HighlightText :parts="displayNrParts(entry.displayNr, term)" /></span
        >{{ " "
        }}<span class="search-entry-title"
          ><HighlightText :parts="highlightParts(entry.title, term)"
        /></span>
      </span>
      <span v-for="b in entry.badges || []" :key="b" class="badge badge-gray">{{ b }}</span>
      <span v-if="entry.status" :class="entry.status.badge" class="search-entry-status">{{
        entry.status.label
      }}</span>
    </span>
    <span v-if="entry.meta || entry.borrower || entry.context" class="search-entry-meta">
      <template v-if="entry.context">{{ entry.context }} · </template>
      <HighlightText v-if="entry.meta" :parts="highlightParts(entry.meta, term)" />
      <template v-if="entry.borrower">
        <template v-if="entry.meta"> · </template>
        <span class="sr-only">Ausgeliehen an </span
        ><HighlightText :parts="highlightParts(entry.borrower, term)" />
      </template>
    </span>
    <span v-if="entry.hint" class="search-hint"
      ><span class="search-hint-label">{{ `Treffer in ${entry.hint.label}: ` }}</span
      ><HighlightText :parts="entry.hint.parts"
    /></span>
  </span>
</template>

<style scoped>
.search-entry {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

/* Title wraps; badges stay on the right of its first line. */
.search-entry-main {
  display: flex;
  align-items: baseline;
  gap: var(--space-2);
}

.search-entry-heading {
  flex: 1 1 auto;
  min-width: 0;
  overflow-wrap: anywhere;
}

.search-entry-main .badge {
  flex-shrink: 0;
}

.search-entry-nr {
  margin-right: var(--space-1);
  font-variant-numeric: tabular-nums;
  color: var(--color-muted);
  font-size: 0.8125rem;
}

.search-entry-title {
  font-weight: 500;
}

.is-muted .search-entry-title {
  color: var(--color-muted);
}

.search-entry-status {
  margin-left: auto;
}

.search-entry-meta {
  font-size: 0.8125rem;
  color: var(--color-muted);
}

.search-entry .search-hint {
  margin-top: 0;
  max-width: none;
}
</style>
