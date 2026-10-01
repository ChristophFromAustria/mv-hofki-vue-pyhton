/** PDF output (backend: api/routes/printing.py). */
import { API_PREFIX } from "./api.js";

export const MAX_PRINT_ITEMS = 300;

export const DATASHEET_SECTIONS = [
  { value: "photo", label: "Profilfoto" },
  { value: "loan", label: "Aktuelle Ausleihe" },
  { value: "loan_history", label: "Leihhistorie" },
  { value: "invoices", label: "Rechnungen" },
  { value: "notes", label: "Notizen" },
];

const STORAGE_KEY = "print-datasheet-sections";
const DEFAULT_SECTIONS = ["photo", "loan", "loan_history"];

/** The sections chosen last time in this browser (or the defaults). */
export function loadSections() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
    if (Array.isArray(saved))
      return saved.filter((s) => DATASHEET_SECTIONS.some((d) => d.value === s));
  } catch {
    // storage blocked or broken: defaults
  }
  return [...DEFAULT_SECTIONS];
}

export function saveSections(sections) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(sections));
  } catch {
    // not remembered, no harm
  }
}

/**
 * URL of a data sheet PDF: one item (itemId) or all items of a list —
 * listParams are the list's applied query (URLSearchParams), without paging.
 */
export function datasheetUrl({ category, itemId = null, listParams = null, sections = [] }) {
  const params = new URLSearchParams();
  if (listParams) {
    for (const [key, value] of listParams) {
      if (key !== "limit" && key !== "offset" && key !== "group_by") params.set(key, value);
    }
  }
  params.set("category", category);
  if (itemId != null) params.set("item_id", String(itemId));
  params.set("sections", sections.join(","));
  return `${API_PREFIX}/print/datasheets?${params}`;
}
