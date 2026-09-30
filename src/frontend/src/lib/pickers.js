/** Option loaders for RemotePicker (search-as-you-type selects). */
import { get } from "./api.js";
import { CATEGORIES } from "./categories.js";

// Search scopes for musician pickers (RemotePicker `scopes`).
export const MUSICIAN_SCOPES = [
  { value: "active", label: "Nur aktive" },
  { value: "all", label: "Alle" },
];

// `scope` (from RemotePicker) wins over `activeOnly`.
export async function fetchMusicianOptions(text, { activeOnly = true, scope } = {}) {
  if (scope) activeOnly = scope !== "all";
  const params = new URLSearchParams();
  if (activeOnly) params.set("is_active", "true");
  params.set("limit", "20");
  if (text) params.set("search", text);
  const page = await get(`/musicians?${params}`);
  return page.items.map((m) => ({
    id: m.id,
    label: `${m.last_name} ${m.first_name}`,
    description: [m.is_extern && "extern", m.is_active === false && "inaktiv"]
      .filter(Boolean)
      .join(" · "),
  }));
}

const LOANABLE = ["instrument", "clothing", "general_item"];

export async function fetchLoanableItemOptions(text) {
  const pages = await Promise.all(
    LOANABLE.map((category) => {
      const params = new URLSearchParams({ category, status: "verfuegbar", limit: "7" });
      if (text) params.set("search", text);
      return get(`/items?${params}`);
    }),
  );
  return pages
    .flatMap((p) => p.items)
    .map((i) => ({
      id: i.id,
      label: `${i.display_nr} ${i.label}`,
      description: CATEGORIES[i.category]?.labelSingular || "",
    }));
}
