// Marks search hits in list values, mirroring the backend search
// (filters/text_search.py): the search text is split into words, every word
// is marked where it occurs, and text is compared "folded" like the SQL
// function fold() in db/text_fold.py — case, accents and ue/ü spellings don't
// matter. An inventory number may also be typed as "tu 2" or "TU2".

const DISPLAY_NR_RE = /^\s*(\p{L}+)\s*-?\s*0*(\d+)\s*$/u;
const COMBINING_MARKS = /\p{M}/gu;

/**
 * Fold `text` like the backend's fold(): lower case (ß → ss), accents dropped,
 * ae/oe/ue → a/o/u. Returns the folded string and, for every folded
 * character, the [start, end) range of the original characters it came from.
 */
export function foldWithMap(text) {
  const value = text == null ? "" : String(text);
  const chars = [];
  const starts = [];
  const ends = [];
  for (let i = 0; i < value.length; ) {
    const ch = String.fromCodePoint(value.codePointAt(i));
    let folded = ch.toLowerCase();
    if (folded === "ß") folded = "ss";
    folded = folded.normalize("NFKD").replace(COMBINING_MARKS, "");
    for (const c of folded) {
      chars.push(c);
      starts.push(i);
      ends.push(i + ch.length);
    }
    i += ch.length;
  }
  const out = { folded: "", starts: [], ends: [] };
  for (let k = 0; k < chars.length; k++) {
    const digraph = "aou".includes(chars[k]) && chars[k + 1] === "e";
    out.folded += chars[k];
    out.starts.push(starts[k]);
    out.ends.push(digraph ? ends[k + 1] : ends[k]);
    if (digraph) k++;
  }
  return out;
}

export function fold(text) {
  return foldWithMap(text).folded;
}

/** The folded, distinct words of a search text (as the backend splits it). */
export function searchWords(term) {
  const words = [];
  for (const raw of (term || "").split(/\s+/)) {
    const word = fold(raw);
    if (word && !words.includes(word)) words.push(word);
  }
  return words;
}

/** Original [start, end) ranges of every hit of the (folded) `words`, merged. */
function hitRanges(value, words) {
  const { folded, starts, ends } = foldWithMap(value);
  const ranges = [];
  for (const word of words) {
    for (let at = folded.indexOf(word); at !== -1; at = folded.indexOf(word, at + 1)) {
      ranges.push([starts[at], ends[at + word.length - 1]]);
    }
  }
  ranges.sort((a, b) => a[0] - b[0]);
  const merged = [];
  for (const r of ranges) {
    const last = merged[merged.length - 1];
    if (last && r[0] <= last[1]) last[1] = Math.max(last[1], r[1]);
    else merged.push([...r]);
  }
  return merged;
}

function partsFromRanges(value, ranges) {
  const parts = [];
  let last = 0;
  for (const [start, end] of ranges) {
    if (start > last) parts.push({ text: value.slice(last, start), match: false });
    parts.push({ text: value.slice(start, end), match: true });
    last = end;
  }
  if (last < value.length) parts.push({ text: value.slice(last), match: false });
  return parts;
}

/** Split `text` into [{ text, match }] parts around every hit of a search word. */
export function highlightParts(text, term) {
  const value = text == null ? "" : String(text);
  if (!value) return [];
  const words = searchWords(term);
  if (!words.length) return [{ text: value, match: false }];
  return partsFromRanges(value, hitRanges(value, words));
}

/** Whether `text` contains the (folded) `word`. */
function containsWord(text, word) {
  return text != null && fold(text).includes(word);
}

export function hasMatch(text, term) {
  return searchWords(term).some((w) => containsWord(text, w));
}

/** "TU-0002" is found by "TU-0002", "TU-002", "tu 2" and "TU2" (as in the backend). */
export function displayNrMatches(displayNr, term) {
  const m = DISPLAY_NR_RE.exec(term || "");
  const nr = DISPLAY_NR_RE.exec(displayNr || "");
  if (!m || !nr) return false;
  return m[1].toUpperCase() === nr[1].toUpperCase() && Number(m[2]) === Number(nr[2]);
}

/**
 * Parts for an inventory number: marked as a whole when the search text is
 * that number, otherwise not at all (the backend matches numbers only whole).
 */
export function displayNrParts(displayNr, term) {
  if (!displayNr) return [];
  return [{ text: displayNr, match: displayNrMatches(displayNr, term) }];
}

/**
 * A short excerpt of `text` around the first hit of `focusWord` (folded; by
 * default the first search word found), on one line, with "…" where it was
 * cut. All search words are marked. Returns parts like highlightParts, or null.
 */
export function snippetParts(text, term, radius = 24, focusWord = null) {
  const flat = (text || "").replace(/\s+/g, " ").trim();
  const words = searchWords(term);
  const focus = focusWord ?? words.find((w) => containsWord(flat, w));
  if (!focus) return null;
  const [start, end] = hitRanges(flat, [focus])[0] ?? [];
  if (start === undefined) return null;
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
 * Where a row was found, when the fields on screen don't show it: for a
 * search word that no visible field contains, the first field of
 * SEARCHED_FIELDS not in `visibleKeys` that has it, as { label, parts } with a
 * short excerpt. null when the visible fields (or the inventory number)
 * already show every word.
 */
export function searchHint(row, term, visibleKeys) {
  const words = searchWords(term);
  if (!words.length) return null;
  const visible = new Set(visibleKeys);
  if (displayNrMatches(row.display_nr, term)) return null;
  const shown = (w) =>
    SEARCHED_FIELDS.some((f) => visible.has(f.key) && containsWord(row[f.key], w));
  const hidden = words.filter((w) => !shown(w));
  for (const f of SEARCHED_FIELDS) {
    if (visible.has(f.key)) continue;
    const word = hidden.find((w) => containsWord(row[f.key], w));
    if (word) return { label: f.label, parts: snippetParts(row[f.key], term, 24, word) };
  }
  return null;
}
