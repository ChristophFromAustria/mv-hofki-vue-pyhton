/** Open/closed state of one detail-page section, shared by all pages of a kind. */
import { ref } from "vue";

const key = (scope, section) => `detail-collapsed:${scope}:${section}`;

export function useSectionCollapse(scope, section) {
  let collapsed = false;
  try {
    collapsed = localStorage.getItem(key(scope, section)) === "1";
  } catch {
    collapsed = false;
  }
  const open = ref(!collapsed);

  function toggle() {
    open.value = !open.value;
    try {
      if (open.value) localStorage.removeItem(key(scope, section));
      else localStorage.setItem(key(scope, section), "1");
    } catch {
      // storage unavailable: state lasts for this visit only
    }
  }

  return { open, toggle };
}
