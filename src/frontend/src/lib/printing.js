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

function listQuery(params, listParams) {
  if (!listParams) return;
  for (const [key, value] of listParams) {
    if (key !== "limit" && key !== "offset" && key !== "group_by") params.set(key, value);
  }
}

/**
 * URL of a data sheet PDF: one item (itemId) or all items of a list —
 * listParams are the list's applied query (URLSearchParams), without paging.
 */
export function datasheetUrl({ category, itemId = null, listParams = null, sections = [] }) {
  const params = new URLSearchParams();
  listQuery(params, listParams);
  params.set("category", category);
  if (itemId != null) params.set("item_id", String(itemId));
  params.set("sections", sections.join(","));
  return `${API_PREFIX}/print/datasheets?${params}`;
}

// --- labels ---------------------------------------------------------------

const LABEL_KEY = "print-label-settings";

// "Eigene Maße": sizes in mm; 0 columns = roll (one label per page).
export const CUSTOM_FIELDS = [
  { key: "width", label: "Breite (mm)", min: 15, max: 210, step: 0.1 },
  { key: "height", label: "Höhe (mm)", min: 10, max: 297, step: 0.1 },
  { key: "cols", label: "Spalten (0 = Rolle)", min: 0, max: 20, step: 1 },
  { key: "rows", label: "Zeilen", min: 0, max: 40, step: 1 },
  { key: "margin_left", label: "Rand links (mm)", min: 0, max: 100, step: 0.1 },
  { key: "margin_top", label: "Rand oben (mm)", min: 0, max: 100, step: 0.1 },
  { key: "gap_x", label: "Abstand waagrecht (mm)", min: 0, max: 50, step: 0.1 },
  { key: "gap_y", label: "Abstand senkrecht (mm)", min: 0, max: 50, step: 0.1 },
];

export const DEFAULT_LABEL_SETTINGS = {
  template: "roll-62x29",
  start: 1,
  logo: true,
  frame: false,
  custom: {
    width: 62,
    height: 29,
    cols: 0,
    rows: 0,
    margin_left: 0,
    margin_top: 0,
    gap_x: 0,
    gap_y: 0,
  },
};

export function loadLabelSettings() {
  try {
    const saved = JSON.parse(localStorage.getItem(LABEL_KEY) || "null");
    if (saved && typeof saved === "object") {
      return {
        ...DEFAULT_LABEL_SETTINGS,
        ...saved,
        custom: { ...DEFAULT_LABEL_SETTINGS.custom, ...(saved.custom || {}) },
        start: 1, // a sheet is used up differently each time
      };
    }
  } catch {
    // storage blocked or broken: defaults
  }
  return structuredClone(DEFAULT_LABEL_SETTINGS);
}

export function saveLabelSettings(settings) {
  try {
    localStorage.setItem(LABEL_KEY, JSON.stringify(settings));
  } catch {
    // not remembered, no harm
  }
}

/** URL of a label PDF (same item choice as datasheetUrl). */
export function labelUrl({ category, itemId = null, listParams = null, settings }) {
  const params = new URLSearchParams();
  listQuery(params, listParams);
  params.set("category", category);
  if (itemId != null) params.set("item_id", String(itemId));
  params.set("template", settings.template);
  params.set("logo", settings.logo ? "true" : "false");
  params.set("frame", settings.frame ? "true" : "false");
  if (settings.start > 1) params.set("start", String(settings.start));
  if (settings.template === "custom") {
    for (const { key } of CUSTOM_FIELDS) params.set(key, String(settings.custom[key]));
  }
  return `${API_PREFIX}/print/labels?${params}`;
}
