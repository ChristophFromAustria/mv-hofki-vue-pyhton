/** Retired items (sold, lost, …) — backend: schemas/inventory_item.py RETIRE_REASONS. */

export const RETIRE_REASONS = [
  { value: "sold", label: "Verkauft" },
  { value: "lost", label: "Verloren/gestohlen" },
  { value: "scrapped", label: "Verschrottet/defekt" },
  { value: "returned_to_owner", label: "An Eigentümer zurückgegeben" },
  { value: "other", label: "Sonstiges" },
];

export function retireReasonLabel(value) {
  return RETIRE_REASONS.find((r) => r.value === value)?.label || value || "";
}

// "Bestand" filter of the item lists; "aktiv" is the backend's default.
export const STOCK_OPTIONS = [
  { value: "aktiv", label: "Bestand" },
  { value: "ausgeschieden", label: "Ausgeschieden" },
  { value: "alle", label: "Alle" },
];
