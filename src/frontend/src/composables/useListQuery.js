/**
 * State of a filterable, sortable list that loads more rows while scrolling.
 *
 * The filter state lives in the URL (same names as the API parameters), so the
 * back button and shared links restore it. Defaults are left out of the URL; a
 * cleared non-empty default is written as "alle" so it survives a reload.
 */
import { computed, onScopeDispose, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { get } from "../lib/api.js";

const ALL = "alle";

// Filters that describe *how* the list is displayed, not what it is
// narrowed to; they never count towards "filters are active".
const NOT_FILTERS = ["search", "group_by"];

function emptyOf(type) {
  if (type === "list") return [];
  if (type === "bool" || type === "number") return null;
  return "";
}

function isEmpty(value) {
  return value === null || value === "" || (Array.isArray(value) && value.length === 0);
}

function same(a, b) {
  return JSON.stringify(a) === JSON.stringify(b);
}

function clone(value) {
  return Array.isArray(value) ? [...value] : value;
}

function coerce(type, raw) {
  if (type === "list") {
    if (Array.isArray(raw)) return raw.map(String);
    return raw == null || raw === "" ? [] : String(raw).split(",").filter(Boolean);
  }
  if (type === "bool") {
    if (raw === true || raw === "true") return true;
    if (raw === false || raw === "false") return false;
    return null;
  }
  if (type === "number") {
    if (raw === null || raw === undefined || raw === "") return null;
    const n = Number(raw);
    return Number.isFinite(n) ? n : null;
  }
  return raw == null ? "" : String(raw);
}

function parseFromQuery(def, raw) {
  if (raw === ALL) return emptyOf(def.type);
  const value = coerce(def.type, raw);
  // An unparsable bool/number in the URL falls back to the default.
  if ((def.type === "bool" || def.type === "number") && value === null) return clone(def.default);
  return value;
}

function serialize(value) {
  return Array.isArray(value) ? value.join(",") : String(value);
}

/** Filter state from a route query. */
export function readState(filters, query) {
  const state = {};
  for (const [key, def] of Object.entries(filters)) {
    const raw = query[key];
    state[key] = raw === undefined ? clone(def.default) : parseFromQuery(def, raw);
  }
  return state;
}

/** Route query for a filter state and sort (defaults omitted). */
export function writeQuery(filters, state, sort, defaultSort) {
  const query = {};
  for (const [key, def] of Object.entries(filters)) {
    const value = state[key];
    if (same(value, def.default)) continue;
    query[key] = isEmpty(value) ? ALL : serialize(value);
  }
  if (sort && sort !== defaultSort) query.order_by = sort;
  return query;
}

/** URLSearchParams for the API request. */
export function buildParams(filters, state, { sort, base = {}, offset = 0, limit = 50 }) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(base)) {
    if (!isEmpty(value)) params.set(key, serialize(value));
  }
  for (const key of Object.keys(filters)) {
    let value = state[key];
    if (typeof value === "string") value = value.trim();
    if (!isEmpty(value)) params.set(key, serialize(value));
  }
  if (sort) params.set("order_by", sort);
  params.set("limit", String(limit));
  params.set("offset", String(offset));
  return params;
}

function queryKey(query) {
  return JSON.stringify(
    Object.keys(query)
      .sort()
      .map((k) => [k, String(query[k])]),
  );
}

export function useListQuery({
  endpoint,
  filters,
  defaultSort = "",
  pageSize = 50,
  baseParams = () => ({}),
  mapItem = (x) => x,
  debounceMs = 300,
}) {
  const route = useRoute();
  const router = useRouter();
  // App.vue's page Transition is out-in with a fade; the leaving page stays
  // mounted (and its watchers active) for ~150ms while the next route is
  // already current. Ignore route changes once we are no longer that route.
  const ownPath = route.path;

  const defaults = Object.fromEntries(
    Object.entries(filters).map(([k, def]) => [k, clone(def.default)]),
  );
  const debouncedKeys = Object.keys(filters).filter((k) => filters[k].debounce);
  const immediateKeys = Object.keys(filters).filter((k) => !filters[k].debounce);

  const state = reactive(readState(filters, route.query));
  const sort = ref(typeof route.query.order_by === "string" ? route.query.order_by : defaultSort);
  const items = ref([]);
  const total = ref(0);
  const lastResponse = ref(null);
  const loading = ref(false);
  const loadingMore = ref(false);
  const error = ref("");
  const hasMore = computed(() => items.value.length < total.value);
  const groups = computed(() => lastResponse.value?.groups ?? null);
  const itemTotal = computed(() => lastResponse.value?.item_total ?? total.value);
  const activeFilterCount = computed(
    () =>
      Object.keys(filters).filter((k) => !NOT_FILTERS.includes(k) && !same(state[k], defaults[k]))
        .length,
  );

  let seq = 0;
  // Queries this list wrote itself; their arrival in the route is not an
  // external change (a quick second change may already be pending). Compared
  // against lastWrittenKey, not the (possibly stale, since router.replace()
  // is async) live route.query, so a revert-before-navigation-lands still
  // writes the URL, and a stale ownQueries entry never blocks a genuine later
  // external navigation to the same query.
  const ownQueries = new Set();
  let lastWrittenKey = queryKey(route.query);

  async function fetchPage(append) {
    const my = ++seq;
    if (append) loadingMore.value = true;
    else loading.value = true;
    error.value = "";
    try {
      const params = buildParams(filters, state, {
        sort: sort.value,
        base: baseParams(),
        offset: append ? items.value.length : 0,
        limit: pageSize,
      });
      const data = await get(`${endpoint}?${params}`);
      if (my !== seq) return;
      const mapped = data.items.map(mapItem).map((row) => ({
        ...row,
        _key: row.group_key != null ? `${row.group_key}:${row.id}` : row.id,
      }));
      items.value = append ? [...items.value, ...mapped] : mapped;
      total.value = data.total;
      lastResponse.value = data;
    } catch (e) {
      if (my !== seq) return;
      error.value = e?.message || "Laden fehlgeschlagen.";
      if (!append) {
        items.value = [];
        total.value = 0;
      }
    } finally {
      if (my === seq) {
        loading.value = false;
        loadingMore.value = false;
      }
    }
  }

  function reload() {
    return fetchPage(false);
  }

  function loadMore() {
    if (loading.value || loadingMore.value || !hasMore.value) return Promise.resolve();
    return fetchPage(true);
  }

  function pushUrl() {
    const foreign = Object.fromEntries(
      Object.entries(route.query).filter(([k]) => !(k in filters) && k !== "order_by"),
    );
    const next = { ...foreign, ...writeQuery(filters, state, sort.value, defaultSort) };
    const key = queryKey(next);
    if (key === lastWrittenKey) return;
    lastWrittenKey = key;
    ownQueries.add(key);
    router.replace({ query: next });
  }

  function onChange() {
    // A reload from an immediate change already reflects the current
    // (possibly still-debounced) search, so a pending debounce timer would
    // only repeat the same fetch.
    clearTimeout(timer);
    pushUrl();
    reload();
  }

  const snapshot = (keys) => JSON.stringify(keys.map((k) => state[k]));

  let timer = null;
  watch(
    () => snapshot(debouncedKeys),
    () => {
      clearTimeout(timer);
      timer = setTimeout(onChange, debounceMs);
    },
  );
  watch(() => snapshot(immediateKeys) + "|" + sort.value, onChange);
  watch(() => JSON.stringify(baseParams()), reload);

  // Back/forward or a link: adopt the URL. Our own replace() is skipped,
  // unless it is the most recent one we wrote (lastWrittenKey) — once that
  // one arrives, ownQueries is cleared so a later external navigation to the
  // same query (e.g. the back button returning to it) is not swallowed.
  watch(
    () => route.query,
    (query) => {
      if (route.path !== ownPath) return;
      const key = queryKey(query);
      if (ownQueries.has(key)) {
        if (key === lastWrittenKey) ownQueries.clear();
        return;
      }
      lastWrittenKey = key;
      ownQueries.clear();
      Object.assign(state, readState(filters, query));
      sort.value = typeof query.order_by === "string" ? query.order_by : defaultSort;
    },
  );

  onScopeDispose(() => clearTimeout(timer));

  function setFilter(key, raw) {
    state[key] = coerce(filters[key].type, raw);
  }

  function setSort(value) {
    sort.value = value || defaultSort;
  }

  function resetFilters() {
    Object.assign(state, readState(filters, {}));
    sort.value = defaultSort;
  }

  reload();

  return {
    state,
    sort,
    setSort,
    setFilter,
    defaults,
    activeFilterCount,
    items,
    total,
    groups,
    itemTotal,
    lastResponse,
    loading,
    loadingMore,
    error,
    hasMore,
    loadMore,
    reload,
    resetFilters,
  };
}
