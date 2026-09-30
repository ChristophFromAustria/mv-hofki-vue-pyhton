// Marks the search term in list values, mirroring the backend search
// (filters/inventory_item.py): the whole term, case-insensitive, as a
// substring; an inventory number may also be typed as "tu 2" or "TU2".

const DISPLAY_NR_RE = /^\s*(\p{L}+)\s*-?\s*0*(\d+)\s*$/u;

function escapeRegExp(text) {
  return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/** Split `text` into [{ text, match }] parts around every hit of `term`. */
export function highlightParts(text, term) {
  const value = text == null ? "" : String(text);
  const needle = (term || "").trim();
  if (!value || !needle) return value ? [{ text: value, match: false }] : [];
  const re = new RegExp(escapeRegExp(needle), "giu");
  const parts = [];
  let last = 0;
  for (const m of value.matchAll(re)) {
    if (m.index > last) parts.push({ text: value.slice(last, m.index), match: false });
    parts.push({ text: m[0], match: true });
    last = m.index + m[0].length;
  }
  if (last < value.length) parts.push({ text: value.slice(last), match: false });
  return parts;
}

export function hasMatch(text, term) {
  return highlightParts(text, term).some((p) => p.match);
}

/** "TU-002" is found by "TU-002", "tu 2" and "TU2" (as in the backend). */
export function displayNrMatches(displayNr, term) {
  const m = DISPLAY_NR_RE.exec(term || "");
  const nr = DISPLAY_NR_RE.exec(displayNr || "");
  if (!m || !nr) return false;
  return m[1].toUpperCase() === nr[1].toUpperCase() && Number(m[2]) === Number(nr[2]);
}

/** Parts for an inventory number: fully marked when typed as a number. */
export function displayNrParts(displayNr, term) {
  if (displayNrMatches(displayNr, term)) return [{ text: displayNr, match: true }];
  return highlightParts(displayNr, term);
}

/**
 * A short excerpt of `text` around the first hit of `term`, on one line,
 * with "…" where it was cut. Returns parts like highlightParts, or null.
 */
export function snippetParts(text, term, radius = 24) {
  const flat = (text || "").replace(/\s+/g, " ").trim();
  const parts = highlightParts(flat, term);
  const first = parts.findIndex((p) => p.match);
  if (first === -1) return null;
  const start = parts.slice(0, first).reduce((n, p) => n + p.text.length, 0);
  const end = start + parts[first].text.length;
  let from = Math.max(0, start - radius);
  let to = Math.min(flat.length, end + radius);
  // Cut at word boundaries where possible.
  if (from > 0) {
    const space = flat.indexOf(" ", from);
    if (space !== -1 && space < start) from = space + 1;
  }
  if (to < flat.length) {
    const space = flat.lastIndexOf(" ", to);
    if (space > end) to = space;
  }
  const excerpt = highlightParts(flat.slice(from, to), term);
  if (from > 0) excerpt.unshift({ text: "…", match: false });
  if (to < flat.length) excerpt.push({ text: "…", match: false });
  return excerpt;
}

// Fields GET /items searches, in the order a hint prefers them.
const SEARCHED_FIELDS = [
  { key: "label", label: "Bezeichnung" },
  { key: "manufacturer", label: "Hersteller" },
  { key: "borrower", label: "Ausgeliehen an" },
  { key: "notes", label: "Notizen" },
];

/**
 * Where a row was found, when no field on screen shows it: the first
 * matching field of SEARCHED_FIELDS that is not in `visibleKeys`, as
 * { label, parts } with a short excerpt. null when a visible field (or the
 * inventory number) already shows the hit.
 */
export function searchHint(row, term, visibleKeys) {
  if (!(term || "").trim()) return null;
  const visible = new Set(visibleKeys);
  if (visible.has("display_nr") && hasMatch(row.display_nr, term)) return null;
  if (displayNrMatches(row.display_nr, term)) return null;
  for (const f of SEARCHED_FIELDS) {
    if (visible.has(f.key) && hasMatch(row[f.key], term)) return null;
  }
  for (const f of SEARCHED_FIELDS) {
    if (visible.has(f.key)) continue;
    const parts = snippetParts(row[f.key], term);
    if (parts) return { label: f.label, parts };
  }
  return null;
}
