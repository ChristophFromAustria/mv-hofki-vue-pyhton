/**
 * Symbol-template categories for the Notenscanner.
 *
 * Categories are stored as free strings in the backend. This module only
 * provides German labels and a display order for the known ones; unknown
 * categories fall back to their raw key so new ones are never hidden.
 */

export const SYMBOL_CATEGORY_LABELS = {
  note: "Noten",
  rest: "Pausen",
  accidental: "Vorzeichen",
  key_sig: "Tonarten",
  clef: "Schlüssel",
  time_sig: "Taktarten",
  barline: "Taktstriche",
  dynamic: "Dynamik",
  ornament: "Verzierungen",
  other: "Sonstige",
};

export const SYMBOL_CATEGORY_LABELS_SINGULAR = {
  note: "Note",
  rest: "Pause",
  accidental: "Vorzeichen",
  key_sig: "Tonart",
  clef: "Schlüssel",
  time_sig: "Taktart",
  barline: "Taktstrich",
  dynamic: "Dynamik",
  ornament: "Verzierung",
  other: "Sonstiges",
};

/** Preferred display order for known categories; unknown ones sort after. */
export const SYMBOL_CATEGORY_ORDER = Object.keys(SYMBOL_CATEGORY_LABELS);

export function symbolCategoryLabel(key) {
  return SYMBOL_CATEGORY_LABELS[key] || key;
}

export function symbolCategoryLabelSingular(key) {
  return SYMBOL_CATEGORY_LABELS_SINGULAR[key] || key;
}

export function compareSymbolCategories(a, b) {
  const ia = SYMBOL_CATEGORY_ORDER.indexOf(a);
  const ib = SYMBOL_CATEGORY_ORDER.indexOf(b);
  const ra = ia === -1 ? SYMBOL_CATEGORY_ORDER.length : ia;
  const rb = ib === -1 ? SYMBOL_CATEGORY_ORDER.length : ib;
  if (ra !== rb) return ra - rb;
  return a.localeCompare(b, "de");
}

/**
 * Merge the known categories with those actually present in the backend.
 * Returns [{ key, label, count }] sorted by display order.
 */
export function mergeSymbolCategories(serverCategories = []) {
  const counts = new Map(serverCategories.map((c) => [c.category, c.count]));
  const keys = new Set([...SYMBOL_CATEGORY_ORDER, ...counts.keys()]);
  return [...keys].sort(compareSymbolCategories).map((key) => ({
    key,
    label: symbolCategoryLabel(key),
    count: counts.get(key) ?? 0,
  }));
}
