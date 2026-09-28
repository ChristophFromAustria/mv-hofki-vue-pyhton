/** Expanded group keys of one list and grouping, remembered per browser.
 * Groups start collapsed by default; only keys explicitly expanded (and
 * still persisted) count as open. */
import { ref, computed, watch } from "vue";

const PREFIX = "groups-expanded:";

function read(key) {
  try {
    const raw = localStorage.getItem(PREFIX + key);
    const parsed = raw ? JSON.parse(raw) : [];
    return new Set(Array.isArray(parsed) ? parsed.map(String) : []);
  } catch {
    return new Set();
  }
}

function write(key, set) {
  try {
    localStorage.setItem(PREFIX + key, JSON.stringify([...set]));
  } catch {
    // storage unavailable: expanding still works for this visit
  }
}

export function useGroupCollapse(storageKey, groupsRef) {
  const expanded = ref(read(storageKey.value));
  watch(storageKey, (key) => (expanded.value = read(key)));

  const groupKeys = computed(() => (groupsRef?.value ?? []).map((g) => g.key));

  const collapsed = computed(() => {
    const set = new Set();
    for (const key of groupKeys.value) {
      if (!expanded.value.has(key)) set.add(key);
    }
    return set;
  });

  const allExpanded = computed(
    () => groupKeys.value.length > 0 && groupKeys.value.every((key) => expanded.value.has(key)),
  );

  function persist(next) {
    expanded.value = next;
    write(storageKey.value, next);
  }

  function toggle(groupKey) {
    const next = new Set(expanded.value);
    if (next.has(groupKey)) next.delete(groupKey);
    else next.add(groupKey);
    persist(next);
  }

  function expandAll() {
    persist(new Set(groupKeys.value));
  }

  function collapseAll() {
    persist(new Set());
  }

  return { collapsed, toggle, expandAll, collapseAll, allExpanded };
}
