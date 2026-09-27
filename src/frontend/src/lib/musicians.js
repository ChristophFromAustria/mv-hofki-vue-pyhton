/**
 * Helpers for the musician list and form: filter/query building and
 * register display. Kept free of Vue so they can be unit-tested.
 */

/** Allowed values of the "Status" filter; "" means all musicians. */
export const ACTIVE_FILTERS = [
  { value: "true", label: "Aktiv" },
  { value: "false", label: "Inaktiv" },
  { value: "", label: "Alle" },
];

export const DEFAULT_ACTIVE_FILTER = "true";

/** Route-query spelling of the "all" status filter (an empty value would vanish). */
const ALL_QUERY_VALUE = "alle";

/** Normalise a route-query value for the status filter. */
export function parseActiveFilter(value) {
  if (value === undefined || value === null) return DEFAULT_ACTIVE_FILTER;
  const v = String(value);
  if (v === ALL_QUERY_VALUE) return "";
  return v === "true" || v === "false" ? v : DEFAULT_ACTIVE_FILTER;
}

/** Route-query value for the status filter; undefined for the default. */
export function activeFilterQueryValue(active) {
  if (active === DEFAULT_ACTIVE_FILTER) return undefined;
  return active === "" ? ALL_QUERY_VALUE : active;
}

/** Normalise a route-query value for the register filter ("" = all). */
export function parseRegisterFilter(value) {
  const n = Number.parseInt(value, 10);
  return Number.isInteger(n) && n > 0 ? String(n) : "";
}

/**
 * Build the query string for GET /musicians.
 * `active` is "true" | "false" | "" (all), `registerId` is "" or an id.
 */
export function buildMusicianQuery({ active = "", registerId = "", search = "", limit, offset }) {
  const params = new URLSearchParams();
  if (limit != null) params.set("limit", limit);
  if (offset != null) params.set("offset", offset);
  if (active === "true" || active === "false") params.set("active", active);
  if (registerId !== "" && registerId != null) params.set("register_id", registerId);
  const q = search?.trim();
  if (q) params.set("search", q);
  return params.toString();
}

/** Comma-separated register labels of a musician, "—" when none. */
export function registerLabels(musician) {
  const regs = musician?.registers || [];
  return regs.length ? regs.map((r) => r.label).join(", ") : "—";
}
