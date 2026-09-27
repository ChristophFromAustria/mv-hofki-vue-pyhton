/** Collapsed group keys of one list and grouping, remembered per browser. */
import { ref, watch } from "vue";

const PREFIX = "groups-collapsed:";

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
    // storage unavailable: collapsing still works for this visit
  }
}

export function useGroupCollapse(storageKey) {
  const collapsed = ref(read(storageKey.value));
  watch(storageKey, (key) => (collapsed.value = read(key)));

  function toggle(groupKey) {
    const next = new Set(collapsed.value);
    if (next.has(groupKey)) next.delete(groupKey);
    else next.add(groupKey);
    collapsed.value = next;
    write(storageKey.value, next);
  }

  return { collapsed, toggle };
}
