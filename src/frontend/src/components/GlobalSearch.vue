<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { get } from "../lib/api.js";
import { searchSections, searchTotal } from "../lib/searchResults.js";
import SearchEntry from "./SearchEntry.vue";

// The search field in the header (docs/konzept-allgemeine-suche.md): results
// pop up while typing, Enter on an inventory number jumps to the item,
// "Alle Treffer anzeigen" opens /suche. On phones a magnifier button opens the
// same panel full screen. Ctrl/Cmd+K or "/" focus it from anywhere.
const props = defineProps({
  debounceMs: { type: Number, default: 200 },
});

const router = useRouter();
const baseId = `global-search-${Math.random().toString(36).slice(2, 7)}`;
const input = ref(null);
const query = ref("");
const result = ref(null);
const loading = ref(false);
const error = ref("");
const open = ref(false);
const activeIndex = ref(-1);
const phoneOpen = ref(false);
const isPhone = ref(false);
let timer = null;
let seq = 0;
let media = null;

const term = computed(() => query.value.trim());
const sections = computed(() => searchSections(result.value, result.value?.query));
const total = computed(() => searchTotal(result.value));
const showAll = computed(() => total.value > 0);
// Keyboard/listbox order: all entries, then "Alle Treffer anzeigen".
const options = computed(() => {
  const list = sections.value.flatMap((s) => s.entries);
  if (showAll.value) list.push({ key: "all", kind: "all", to: allTo.value });
  return list;
});
const allTo = computed(() => ({ path: "/suche", query: { q: term.value } }));
const expanded = computed(() => open.value && term.value !== "");

function indexOf(entry) {
  return options.value.findIndex((o) => o.key === entry.key);
}

async function run(text) {
  const my = ++seq;
  if (!text) {
    result.value = null;
    loading.value = false;
    return;
  }
  loading.value = true;
  error.value = "";
  try {
    const data = await get(`/search?q=${encodeURIComponent(text)}&limit=3`);
    if (my !== seq) return;
    result.value = data;
    activeIndex.value = -1;
  } catch (e) {
    if (my !== seq) return;
    result.value = null;
    error.value = e?.message || "Suche fehlgeschlagen.";
  } finally {
    if (my === seq) loading.value = false;
  }
}

watch(query, (value) => {
  clearTimeout(timer);
  open.value = true;
  timer = setTimeout(() => run(value.trim()), props.debounceMs);
});

function reset() {
  clearTimeout(timer);
  seq++;
  query.value = "";
  result.value = null;
  loading.value = false;
  error.value = "";
  activeIndex.value = -1;
  open.value = false;
}

function close() {
  open.value = false;
  activeIndex.value = -1;
  if (phoneOpen.value) setPhoneOpen(false);
}

function go(to) {
  reset();
  if (phoneOpen.value) setPhoneOpen(false);
  input.value?.blur();
  router.push(to);
}

// Enter without a chosen entry: the exact inventory number, else all hits.
async function submit() {
  const text = term.value;
  if (!text) return;
  clearTimeout(timer);
  if (result.value?.query !== text) await run(text);
  const exact = result.value?.query === text ? result.value.exact : null;
  if (exact) {
    go(searchSections(result.value)[0].entries[0].to);
  } else {
    go(allTo.value);
  }
}

function onKeydown(e) {
  const count = options.value.length;
  if (e.key === "ArrowDown") {
    e.preventDefault();
    open.value = true;
    if (count) activeIndex.value = Math.min(count - 1, activeIndex.value + 1);
  } else if (e.key === "ArrowUp") {
    e.preventDefault();
    if (count) activeIndex.value = Math.max(-1, activeIndex.value - 1);
  } else if (e.key === "Enter") {
    e.preventDefault();
    const chosen = expanded.value ? options.value[activeIndex.value] : null;
    if (chosen) go(chosen.to);
    else submit();
  } else if (e.key === "Escape") {
    e.preventDefault();
    if (expanded.value && !phoneOpen.value) close();
    else if (phoneOpen.value) setPhoneOpen(false);
    else reset();
  }
}

function onFocusOut(e) {
  if (phoneOpen.value) return;
  if (e.currentTarget.contains(e.relatedTarget)) return;
  open.value = false;
  activeIndex.value = -1;
}

async function setPhoneOpen(value) {
  phoneOpen.value = value;
  document.body.classList.toggle("global-search-open", value);
  if (value) {
    open.value = true;
    await nextTick();
    input.value?.focus();
  }
}

async function focusSearch() {
  if (isPhone.value) {
    setPhoneOpen(true);
    return;
  }
  open.value = true;
  await nextTick();
  input.value?.focus();
  input.value?.select();
}

function isEditable(el) {
  return (
    el instanceof HTMLElement &&
    (el.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName))
  );
}

function onGlobalKeydown(e) {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
    e.preventDefault();
    focusSearch();
  } else if (e.key === "/" && !e.ctrlKey && !e.metaKey && !isEditable(e.target)) {
    if (document.querySelector("dialog[open]")) return;
    e.preventDefault();
    focusSearch();
  }
}

function onMedia() {
  isPhone.value = !!media?.matches;
  if (!isPhone.value && phoneOpen.value) setPhoneOpen(false);
}

onMounted(() => {
  window.addEventListener("keydown", onGlobalKeydown);
  media = window.matchMedia?.("(max-width: 640px)") ?? null;
  media?.addEventListener?.("change", onMedia);
  onMedia();
});

onBeforeUnmount(() => {
  clearTimeout(timer);
  window.removeEventListener("keydown", onGlobalKeydown);
  media?.removeEventListener?.("change", onMedia);
  document.body.classList.remove("global-search-open");
});
</script>

<template>
  <div class="global-search-wrap">
    <button
      type="button"
      class="global-search-trigger"
      aria-label="Suchen"
      :aria-expanded="phoneOpen ? 'true' : 'false'"
      @click="setPhoneOpen(true)"
    >
      <svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
        <path
          fill-rule="evenodd"
          d="M9 3.5a5.5 5.5 0 1 0 0 11 5.5 5.5 0 0 0 0-11ZM2 9a7 7 0 1 1 12.45 4.39l3.58 3.58a.75.75 0 1 1-1.06 1.06l-3.58-3.58A7 7 0 0 1 2 9Z"
          clip-rule="evenodd"
        />
      </svg>
    </button>

    <div
      class="global-search"
      :class="{ 'is-phone-open': phoneOpen }"
      :role="phoneOpen ? 'dialog' : undefined"
      :aria-modal="phoneOpen ? 'true' : undefined"
      :aria-label="phoneOpen ? 'Suche' : undefined"
      @focusout="onFocusOut"
    >
      <div class="global-search-bar">
        <svg
          class="global-search-icon"
          width="16"
          height="16"
          viewBox="0 0 20 20"
          fill="currentColor"
          aria-hidden="true"
        >
          <path
            fill-rule="evenodd"
            d="M9 3.5a5.5 5.5 0 1 0 0 11 5.5 5.5 0 0 0 0-11ZM2 9a7 7 0 1 1 12.45 4.39l3.58 3.58a.75.75 0 1 1-1.06 1.06l-3.58-3.58A7 7 0 0 1 2 9Z"
            clip-rule="evenodd"
          />
        </svg>
        <input
          :id="`${baseId}-input`"
          ref="input"
          v-model="query"
          type="search"
          role="combobox"
          autocomplete="off"
          enterkeyhint="search"
          aria-label="Suche in Inventar, Musikern und Rechnungen"
          aria-autocomplete="list"
          :aria-expanded="expanded ? 'true' : 'false'"
          :aria-controls="`${baseId}-list`"
          :aria-activedescendant="activeIndex >= 0 ? `${baseId}-opt-${activeIndex}` : undefined"
          :aria-busy="loading ? 'true' : undefined"
          placeholder="Suchen …"
          @focus="open = true"
          @keydown="onKeydown"
        />
        <kbd v-if="!query" class="global-search-kbd" aria-hidden="true">Strg K</kbd>
        <button
          v-if="phoneOpen"
          type="button"
          class="global-search-close"
          @click="setPhoneOpen(false)"
        >
          Schließen
        </button>
      </div>

      <div v-show="expanded || phoneOpen" class="global-search-popup">
        <ul :id="`${baseId}-list`" role="listbox" aria-label="Suchergebnisse">
          <li
            v-for="section in sections"
            :key="section.key"
            role="group"
            :aria-labelledby="`${baseId}-sec-${section.key}`"
            class="global-search-section"
          >
            <div
              :id="`${baseId}-sec-${section.key}`"
              class="global-search-section-label"
              role="presentation"
            >
              {{ section.label }}
              <span v-if="section.total > section.entries.length" class="global-search-count">
                {{ section.entries.length }} von {{ section.total }}
              </span>
            </div>
            <ul role="presentation">
              <li
                v-for="entry in section.entries"
                :id="`${baseId}-opt-${indexOf(entry)}`"
                :key="entry.key"
                role="option"
                class="global-search-option"
                :class="{ active: indexOf(entry) === activeIndex }"
                :aria-selected="indexOf(entry) === activeIndex ? 'true' : 'false'"
                @mousedown.prevent
                @click="go(entry.to)"
              >
                <SearchEntry :entry="entry" :term="result?.query || ''" />
              </li>
            </ul>
          </li>
          <li
            v-if="showAll"
            :id="`${baseId}-opt-${options.length - 1}`"
            role="option"
            class="global-search-option global-search-all"
            :class="{ active: activeIndex === options.length - 1 }"
            :aria-selected="activeIndex === options.length - 1 ? 'true' : 'false'"
            @mousedown.prevent
            @click="go(allTo)"
          >
            Alle {{ total }} Treffer anzeigen →
          </li>
        </ul>
        <p v-if="loading && !result" class="global-search-status">Suche …</p>
        <p v-else-if="error" class="global-search-status form-error" role="alert">{{ error }}</p>
        <p v-else-if="term && result?.query === term && !total" class="global-search-status">
          {{
            term.length < 2
              ? "Bitte mindestens 2 Zeichen eingeben."
              : `Keine Treffer für „${term}“.`
          }}
        </p>
        <p v-else-if="!term && phoneOpen" class="global-search-status">
          Inventar, Musiker und Rechnungen durchsuchen – z. B. „TR 6“, „Müller“, „Trompete Yamaha“.
        </p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.global-search-wrap {
  flex: 1 1 auto;
  display: flex;
  justify-content: center;
  min-width: 0;
  margin: 0 var(--space-4);
}

.global-search-trigger {
  display: none;
}

.global-search {
  position: relative;
  width: 100%;
  max-width: 28rem;
}

.global-search-bar {
  position: relative;
  display: flex;
  align-items: center;
}

.global-search-icon {
  position: absolute;
  left: 0.75rem;
  color: var(--color-muted);
  pointer-events: none;
}

.global-search-bar input {
  width: 100%;
  min-height: 40px;
  padding-left: 2.25rem;
  padding-right: 4.5rem;
  background: var(--color-bg-soft);
}

.global-search-kbd {
  position: absolute;
  right: 0.5rem;
  padding: 1px 6px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  font-family: var(--font-sans);
  font-size: 0.7rem;
  color: var(--color-muted);
  pointer-events: none;
}

.global-search-popup {
  position: absolute;
  z-index: var(--z-dropdown);
  top: calc(100% + var(--space-1));
  left: 0;
  right: 0;
  max-height: min(70vh, 34rem);
  overflow-y: auto;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  background: var(--color-bg);
  box-shadow: var(--shadow-float);
}

.global-search-popup ul {
  margin: 0;
  padding: 0;
  list-style: none;
}

.global-search-section + .global-search-section {
  border-top: 1px solid var(--color-border);
}

.global-search-section-label {
  display: flex;
  justify-content: space-between;
  padding: var(--space-2) var(--space-3) var(--space-1);
  font-size: 0.7rem;
  font-weight: 600;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: var(--color-muted);
}

.global-search-count {
  font-weight: 500;
  letter-spacing: 0;
  text-transform: none;
  font-variant-numeric: tabular-nums;
}

.global-search-option {
  min-height: 44px;
  padding: var(--space-2) var(--space-3);
  cursor: pointer;
}

.global-search-option.active,
.global-search-option:hover {
  background: var(--color-primary-light);
}

.global-search-all {
  display: flex;
  align-items: center;
  border-top: 1px solid var(--color-border);
  color: var(--color-primary);
  font-weight: 500;
}

.global-search-status {
  margin: 0;
  padding: var(--space-3);
  color: var(--color-muted);
}

@media (max-width: 640px) {
  /* The magnifier sits next to the theme switch, easy to reach one-handed. */
  .global-search-wrap {
    flex: 0 0 auto;
    margin: 0 0 0 auto;
  }

  .global-search-trigger {
    display: inline-grid;
    place-items: center;
    width: 44px;
    height: 44px;
    padding: 0;
    border: none;
    background: none;
    color: var(--color-text);
    cursor: pointer;
  }

  .global-search:not(.is-phone-open) {
    display: none;
  }

  .global-search.is-phone-open {
    position: fixed;
    inset: 0;
    z-index: var(--z-overlay);
    max-width: none;
    display: flex;
    flex-direction: column;
    background: var(--color-bg);
  }

  .is-phone-open .global-search-bar {
    gap: var(--space-2);
    padding: var(--space-2) var(--space-3);
    border-bottom: 1px solid var(--color-border);
  }

  .is-phone-open .global-search-icon {
    left: calc(var(--space-3) + 0.75rem);
  }

  .is-phone-open .global-search-bar input {
    min-height: 44px;
    padding-right: 0.75rem;
    font-size: 1rem;
  }

  .global-search-kbd {
    display: none;
  }

  .global-search-close {
    min-height: 44px;
    flex-shrink: 0;
  }

  .is-phone-open .global-search-popup {
    position: static;
    flex: 1;
    max-height: none;
    border: none;
    border-radius: 0;
    box-shadow: none;
  }
}
</style>
