<script setup>
/**
 * Browser-side notation editor for the generated LilyPond code.
 *
 * Rendering: VexFlow (SVG). Model: lib/lilyparse.js token list.
 * Editing is purely client-side; the edited code is emitted through
 * `update:code` and nothing is persisted.
 */
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from "vue";
import {
  Renderer,
  Stave,
  StaveNote,
  Voice,
  Formatter,
  Accidental,
  Dot,
  Beam,
  Barline,
  Annotation,
  Articulation,
  Volta,
  Modifier,
  StaveHairpin,
  StaveTie,
  Curve,
} from "vexflow/bravura";
import {
  parseLilypond,
  serializeDocument,
  buildMeasures,
  transposeEvent,
  alterEvent,
  setEventDuration,
  toggleDot,
  toggleRest,
  deleteEvent,
  insertEvent,
  insertBarline,
  deleteBarline,
  setBarlineType,
  barlineTypeOf,
  deleteMeasure,
  insertEmptyMeasure,
  toggleArticulation,
  setDynamic,
  setHairpin,
  eventDecorations,
  ARTICULATIONS,
  DYNAMICS,
  BARLINE_TYPES,
  MAJOR_KEYS,
  setKeyForRange,
  setPercentCount,
  toggleTie,
  tieAllowed,
  nextSoundingIndex,
  placeSlur,
  removeSlur,
  findSlurs,
  removeHairpin,
  placeHairpin,
  normalizeDocument,
  keyFlats,
  keyAlteration,
  fracToString,
  durationLabel,
  pitchLabel,
} from "../lib/lilyparse.js";

const props = defineProps({
  code: { type: String, default: "" },
  originalCode: { type: String, default: "" },
  /** URL of the scan image; together with `staves` it provides the original line snippets. */
  staffImageUrl: { type: String, default: null },
  /** Detected staves of the scan (y_top, y_bottom, line_spacing in image pixels). */
  staves: { type: Array, default: () => [] },
});
const emit = defineEmits(["update:code"]);

// ── State ────────────────────────────────────────────────────────────────

const host = ref(null);
const container = ref(null);
const doc = ref(null);
const measures = ref([]);
const parseError = ref(null);
// Selection: exactly one of these is set
const selected = ref(null); // token index of a note/rest
const selectedMeasure = ref(null); // whole measure (index) selected via its number
const selectedCell = ref(null); // printed number of the clicked cell (percent repeats)
const selectedMeasureEnd = ref(null); // other end of a measure range (Shift+click / Shift+arrows)
const selectedBarline = ref(null); // index of the measure whose end barline is selected
const selectedNoteEnd = ref(null); // other end of a note range (Shift+click / Shift+arrows)
const selectedHairpin = ref(null); // { startUid, endUid, kind } of a selected hairpin
let hairpinDrag = null; // { side, moved } while dragging a hairpin end
let notePositions = []; // [{ ti, uid, x, row }] of drawn notes, for drag targets
let rowTopsCache = [];
// Context menu: { x, y } while open
const menu = ref(null);
const menuButton = ref(null);
const history = ref([]);
const future = ref([]);
const width = ref(900);
const fontsReady = ref(false);
const renderError = ref(null);

// Hover hints per measure (filled during render, read on pointermove)
let measureBoxes = [];
let svgLogicalWidth = 0;
const tooltip = ref(null); // { x, y, title, lines }

// Layout: "auto" wraps measures by available width; "lilypond" breaks only
// where the generated code has \break (mirrors the LilyPond line layout).
const layoutMode = ref("auto");
try {
  const stored = localStorage.getItem("lilypondEditorLayout");
  if (stored === "lilypond" || stored === "auto") layoutMode.value = stored;
} catch {
  // storage unavailable
}
// Original line snippets above each row (only meaningful in the LilyPond layout,
// where rows correspond to the scanned systems).
const showSnippets = ref(false);
try {
  showSnippets.value = localStorage.getItem("lilypondEditorSnippets") === "1";
} catch {
  // storage unavailable
}
const imageSize = ref(null); // { w, h } of the scan image once loaded
const canShowSnippets = computed(() => !!props.staffImageUrl && props.staves.length > 0);

function toggleSnippets() {
  showSnippets.value = !showSnippets.value;
  try {
    localStorage.setItem("lilypondEditorSnippets", showSnippets.value ? "1" : "0");
  } catch {
    // ignore
  }
  if (showSnippets.value && layoutMode.value !== "lilypond") setLayoutMode("lilypond");
  else scheduleRender();
}

function loadImageSize(url) {
  imageSize.value = null;
  if (!url) return;
  const img = new Image();
  img.onload = () => {
    imageSize.value = { w: img.naturalWidth, h: img.naturalHeight };
    scheduleRender();
  };
  img.src = url;
}
watch(() => props.staffImageUrl, loadImageSize, { immediate: true });

/** Crop rectangle (image pixels) of the scanned system for editor row `rowIdx`. */
function snippetCrop(rowIdx) {
  const st = props.staves[rowIdx];
  const img = imageSize.value;
  if (!st || !img) return null;
  const margin = 1.5 * (st.line_spacing || 20);
  const top = Math.max(0, Math.floor(st.y_top - margin));
  const bottom = Math.min(img.h, Math.ceil(st.y_bottom + margin));
  return bottom > top ? { top, height: bottom - top } : null;
}

function setLayoutMode(mode) {
  layoutMode.value = mode;
  try {
    localStorage.setItem("lilypondEditorLayout", mode);
  } catch {
    // ignore
  }
  scheduleRender();
}

const isDirty = computed(() => props.originalCode !== "" && props.code !== props.originalCode);

const selectedToken = computed(() => {
  if (selected.value === null || !doc.value) return null;
  const t = doc.value.tokens[selected.value];
  return t && t.type === "event" ? t : null;
});

const selectedInfo = computed(() => {
  const sl = selectedSlurIndices.value;
  if (sl) {
    const from = measureOfToken(sl.start);
    const to = sl.end !== null ? measureOfToken(sl.end) : null;
    return `Bindebogen · ${from ? measureLabel(from) : ""}${to && to !== from ? ` bis ${measureLabel(to)}` : ""}`;
  }
  const hp = selectedHairpinIndices.value;
  if (hp) {
    const label = hp.kind === "cresc" ? "Crescendo" : "Decrescendo";
    const from = measureOfToken(hp.start);
    const to = hp.end !== null ? measureOfToken(hp.end) : null;
    const span = `${from ? measureLabel(from) : ""}${to && to !== from ? ` bis ${measureLabel(to)}` : ""}`;
    return `${label} · ${span} · Enden ziehen zum Verlängern`;
  }
  if (isNoteRange.value) {
    return `${noteRangeIndices.value.length} Noten ausgewählt · Shift+Klick oder Shift+Pfeil erweitert`;
  }
  if (selectedBarlineMeasure.value) {
    const type = BARLINE_TYPES[selectedBarlineType.value]?.label || "Taktstrich";
    return `Taktstrich nach ${measureLabel(selectedBarlineMeasure.value)} · ${type}`;
  }
  const t = selectedToken.value;
  if (!t) return null;
  const parts = [];
  if (t.kind === "note") parts.push(t.pitches.map(pitchLabel).join(" "));
  else if (t.kind === "rest") parts.push("Pause");
  else if (t.kind === "mmrest") parts.push("Mehrtaktpause");
  else parts.push("Platzhalter");
  if (t.duration) parts.push(durationLabel(t.duration));
  return parts.join(" · ");
});

function measureLabel(m) {
  return m.span > 1 ? `Takte ${m.number}–${m.number + m.span - 1}` : `Takt ${m.number}`;
}

function measureHints(m) {
  const lines = [];
  if (m.mismatch) {
    lines.push(`Taktfüllung ${fracToString(m.actualLen)} statt ${m.time.beats}/${m.time.beatType}`);
  }
  if (m.percent !== null) lines.push(`Wird ${m.percent}× gespielt (Taktwiederholung)`);
  if (m.copy) lines.push("Aus Vorlage übernommen");
  if (m.volta) lines.push(`Volta ${m.volta.count}`);
  return lines;
}

const selectedMeasureInfo = computed(() => {
  const m = currentMeasure();
  if (!m) return null;
  if (isRange.value) return `${rangeLabel()} ausgewählt · Shift+Klick oder Shift+Pfeil erweitert`;
  if (selectedIsRepeatCell.value) {
    return `Takt ${selectedCell.value} · Wiederholung von Takt ${m.number}`;
  }
  const hints = measureHints(m);
  return `${measureLabel(m)}${hints.length ? " · " + hints.join(" · ") : ""}`;
});

const measureSummary = computed(() => {
  const total = measures.value.length;
  const bad = measures.value.filter((m) => m.mismatch).length;
  return { total, bad };
});

function clearSelection() {
  selected.value = null;
  selectedNoteEnd.value = null;
  selectedMeasure.value = null;
  selectedCell.value = null;
  selectedMeasureEnd.value = null;
  selectedBarline.value = null;
  selectedHairpin.value = null;
  if (typeof selectedSlur.value !== "undefined") selectedSlur.value = null;
}

function selectNote(tokenIndex) {
  clearSelection();
  selected.value = tokenIndex;
}

function extendNoteSelection(tokenIndex) {
  if (selected.value === null) {
    selectNote(tokenIndex);
    return;
  }
  selectedNoteEnd.value = tokenIndex === selected.value ? null : tokenIndex;
}

function selectHairpin(startUid, endUid, kind) {
  clearSelection();
  selectedHairpin.value = { startUid, endUid, kind };
}

const selectedSlur = ref(null); // { startUid, endUid }
function selectSlur(startUid, endUid) {
  clearSelection();
  selectedSlur.value = { startUid, endUid };
}
const selectedSlurIndices = computed(() => {
  const sl = selectedSlur.value;
  if (!sl) return null;
  const start = tokenIndexByUid(sl.startUid);
  const end = tokenIndexByUid(sl.endUid);
  return start >= 0 ? { start, end: end >= 0 ? end : null } : null;
});

/** Event token indices (score order, no spacers) covered by the note range. */
const noteRangeIndices = computed(() => {
  if (selected.value === null || !doc.value) return [];
  const a = selected.value;
  const b = selectedNoteEnd.value ?? a;
  const lo = Math.min(a, b);
  const hi = Math.max(a, b);
  const out = [];
  for (let i = lo; i <= hi; i += 1) {
    const t = doc.value.tokens[i];
    if (t && t.type === "event" && t.kind !== "spacer" && t.kind !== "skip") out.push(i);
  }
  return out;
});
const isNoteRange = computed(() => noteRangeIndices.value.length > 1);

function tokenIndexByUid(uid) {
  if (!doc.value || uid === null || uid === undefined) return -1;
  return doc.value.tokens.findIndex((t) => t.uid === uid);
}

const selectedHairpinIndices = computed(() => {
  const h = selectedHairpin.value;
  if (!h) return null;
  const start = tokenIndexByUid(h.startUid);
  const end = tokenIndexByUid(h.endUid);
  return start >= 0 ? { start, end: end >= 0 ? end : null, kind: h.kind } : null;
});

function selectMeasure(index, cellNumber = null) {
  clearSelection();
  selectedMeasure.value = index;
  selectedCell.value = cellNumber;
}

/** Extend the measure selection to `index` (range from the anchor measure). */
function extendMeasureSelection(index) {
  if (selectedMeasure.value === null) {
    selectMeasure(index);
    return;
  }
  selected.value = null;
  selectedBarline.value = null;
  selectedCell.value = null;
  selectedMeasureEnd.value = index === selectedMeasure.value ? null : index;
}

/** [lo, hi] measure indices of the current measure selection, or null. */
const selectedRange = computed(() => {
  if (selectedMeasure.value === null) return null;
  const a = selectedMeasure.value;
  const b = selectedMeasureEnd.value ?? a;
  return [Math.min(a, b), Math.max(a, b)];
});

const isRange = computed(
  () => !!selectedRange.value && selectedRange.value[0] !== selectedRange.value[1],
);

function rangeLabel() {
  const r = selectedRange.value;
  if (!r) return "";
  const first = measures.value[r[0]];
  const last = measures.value[r[1]];
  if (!first || !last) return "";
  return `Takte ${first.number}–${last.number + last.span - 1}`;
}

/** True when a repeated (percent) cell rather than the written measure is selected. */
const selectedIsRepeatCell = computed(() => {
  const m = selectedMeasure.value !== null ? measures.value[selectedMeasure.value] : null;
  return !!m && m.percent !== null && selectedCell.value !== null && selectedCell.value > m.number;
});

function selectBarline(index) {
  clearSelection();
  selectedBarline.value = index;
}

const selectedBarlineMeasure = computed(() =>
  selectedBarline.value === null ? null : measures.value[selectedBarline.value] || null,
);

const selectedBarlineType = computed(() =>
  doc.value && selectedBarlineMeasure.value
    ? barlineTypeOf(doc.value.tokens, selectedBarlineMeasure.value)
    : null,
);

const hasSelection = computed(
  () =>
    selected.value !== null ||
    selectedMeasure.value !== null ||
    selectedBarline.value !== null ||
    selectedHairpin.value !== null ||
    selectedSlur.value !== null,
);

// ── Parsing ──────────────────────────────────────────────────────────────

function loadCode(code) {
  const parsed = parseLilypond(code || "");
  if (!parsed.ok) {
    parseError.value = parsed.error;
    doc.value = null;
    measures.value = [];
    return;
  }
  parseError.value = null;
  doc.value = parsed;
  measures.value = buildMeasures(parsed.tokens);
}

watch(
  () => props.code,
  (code) => {
    // Only reload when the code differs from what we produced ourselves.
    if (doc.value && serializeDocument(doc.value) === code) return;
    loadCode(code);
    clearSelection();
    scheduleRender();
  },
);

// ── Editing ──────────────────────────────────────────────────────────────

function commit(nextDoc, nextSelected = selected.value) {
  if (!doc.value) return;
  history.value.push(serializeDocument(doc.value));
  if (history.value.length > 100) history.value.shift();
  future.value = [];
  const normalized = normalizeDocument(nextDoc);
  doc.value = normalized;
  measures.value = buildMeasures(normalized.tokens);
  // token indices may have shifted through normalization: re-locate by uid
  if (nextSelected !== null && nextDoc.tokens[nextSelected]) {
    const uid = nextDoc.tokens[nextSelected].uid;
    const idx = normalized.tokens.findIndex((t) => t.uid === uid);
    selected.value = idx >= 0 ? idx : null;
  } else {
    selected.value = null;
  }
  // measure/barline selections refer to measure indices that may have shifted
  if (selectedMeasure.value !== null && !measures.value[selectedMeasure.value]) {
    selectedMeasure.value = null;
  }
  if (selectedBarline.value !== null && !measures.value[selectedBarline.value]) {
    selectedBarline.value = null;
  }
  if (selectedMeasureEnd.value !== null && !measures.value[selectedMeasureEnd.value]) {
    selectedMeasureEnd.value = null;
  }
  if (selectedNoteEnd.value !== null && !normalized.tokens[selectedNoteEnd.value]) {
    selectedNoteEnd.value = null;
  }
  if (selectedHairpin.value && tokenIndexByUid(selectedHairpin.value.startUid) < 0) {
    selectedHairpin.value = null;
  }
  menu.value = null;
  emit("update:code", serializeDocument(normalized));
  scheduleRender();
}

function undo() {
  if (!history.value.length) return;
  future.value.push(serializeDocument(doc.value));
  const code = history.value.pop();
  loadCode(code);
  clearSelection();
  emit("update:code", code);
  scheduleRender();
}

function redo() {
  if (!future.value.length) return;
  history.value.push(serializeDocument(doc.value));
  const code = future.value.pop();
  loadCode(code);
  clearSelection();
  emit("update:code", code);
  scheduleRender();
}

function resetToOriginal() {
  if (!props.originalCode) return;
  history.value = [];
  future.value = [];
  loadCode(props.originalCode);
  clearSelection();
  emit("update:code", props.originalCode);
  scheduleRender();
}

function requireNote() {
  const t = selectedToken.value;
  return t && t.kind === "note" ? t : null;
}

function stepPitch(delta) {
  if (!requireNote()) return;
  commit(transposeEvent(doc.value, measures.value, selected.value, delta));
}

function stepAccidental(delta) {
  if (!requireNote()) return;
  commit(alterEvent(doc.value, selected.value, delta));
}

function setDuration(base) {
  if (!selectedToken.value || selectedToken.value.kind === "spacer") return;
  commit(setEventDuration(doc.value, selected.value, base));
}

function dot() {
  if (!selectedToken.value) return;
  commit(toggleDot(doc.value, selected.value));
}

function restToggle() {
  const t = selectedToken.value;
  if (!t || t.kind === "spacer" || t.kind === "mmrest") return;
  commit(toggleRest(doc.value, selected.value, defaultPitchForSelection()));
}

function deleteSelection() {
  const sl = selectedSlurIndices.value;
  if (sl) {
    const next = removeSlur(doc.value, sl.start, sl.end);
    selectedSlur.value = null;
    commit(next, null);
    return;
  }
  const hp = selectedHairpinIndices.value;
  if (hp) {
    const next = removeHairpin(doc.value, hp.start, hp.end);
    selectedHairpin.value = null;
    commit(next, null);
    return;
  }
  if (isNoteRange.value) {
    const idx = [...noteRangeIndices.value].sort((a, b) => b - a);
    let next = doc.value;
    for (const i of idx) next = deleteEvent(next, i);
    const m = measureOfToken(idx[idx.length - 1]);
    clearSelection();
    commit(next, null);
    if (m && measures.value[m.index]) selectMeasure(m.index);
    scheduleRender();
    return;
  }
  if (selectedBarlineMeasure.value) {
    const m = selectedBarlineMeasure.value;
    const next = deleteBarline(doc.value, m);
    if (next !== doc.value) {
      selectedBarline.value = null;
      commit(next, null);
      selectMeasure(Math.min(m.index, measures.value.length - 1));
      scheduleRender();
    }
    return;
  }
  if (isRange.value && selected.value === null) {
    const [lo, hi] = selectedRange.value;
    let next = doc.value;
    // delete from the back so earlier measure indices stay valid
    for (let i = hi; i >= lo; i -= 1) next = deleteMeasure(next, measures.value[i]);
    clearSelection();
    commit(next, null);
    if (measures.value.length) selectMeasure(Math.min(lo, measures.value.length - 1));
    scheduleRender();
    return;
  }
  if (selectedMeasure.value !== null && selected.value === null) {
    const m = measures.value[selectedMeasure.value];
    if (!m) return;
    if (selectedIsRepeatCell.value) {
      const idx = m.index;
      commit(setPercentCount(doc.value, m, m.percent - 1), null);
      selectMeasure(idx);
      scheduleRender();
      return;
    }
    const next = deleteMeasure(doc.value, m);
    selectedMeasure.value = null;
    commit(next, null);
    if (measures.value.length) selectMeasure(Math.min(m.index, measures.value.length - 1));
    scheduleRender();
    return;
  }
  remove();
}

function remove() {
  if (!selectedToken.value) return;
  const m = measureOfToken(selected.value);
  const cur = selected.value;
  // Keep working in the same measure: select the following note, else the previous one
  let neighbour = null;
  if (m) {
    const pos = m.events.indexOf(cur);
    neighbour = m.events[pos + 1] ?? m.events[pos - 1] ?? null;
  }
  const next = deleteEvent(doc.value, cur);
  selectedMeasure.value = neighbour === null && m ? m.index : null;
  const nextSelected = neighbour === null ? null : neighbour > cur ? neighbour - 1 : neighbour;
  commit(next, nextSelected);
}

function barlineInsert() {
  if (!selectedToken.value) return;
  const next = insertBarline(doc.value, measures.value, selected.value);
  if (next !== doc.value) commit(next);
}

function barlineRemove() {
  const m = selectedBarlineMeasure.value || currentMeasure();
  if (!m) return;
  const keep = selected.value;
  const next = deleteBarline(doc.value, m);
  if (next !== doc.value) {
    selectedBarline.value = null;
    commit(next, keep);
  }
}

function barlineSetType(type) {
  const m = selectedBarlineMeasure.value || currentMeasure();
  if (!m) return;
  const keepBar = selectedBarline.value;
  const keepMeasure = selectedMeasure.value;
  const next = setBarlineType(doc.value, m, type);
  if (next !== doc.value) {
    commit(next, selected.value);
    selectedBarline.value = keepBar;
    selectedMeasure.value = keepMeasure;
    scheduleRender();
  }
}

function measureDelete() {
  const m = currentMeasure();
  if (!m) return;
  selectMeasure(m.index);
  deleteSelection();
}

function measureInsert(where) {
  const m = currentMeasure();
  if (!m) return;
  const next = insertEmptyMeasure(doc.value, m, where);
  commit(next, null);
  const idx = where === "after" ? m.index + 1 : m.index;
  if (measures.value[idx]) selectMeasure(idx);
  scheduleRender();
}

function repeatCountChange(delta) {
  const m = currentMeasure();
  if (!m) return;
  const idx = m.index;
  const count = (m.percent ?? 1) + delta;
  const next = setPercentCount(doc.value, m, Math.max(1, count));
  if (next === doc.value) return;
  commit(next, null);
  selectMeasure(idx);
  scheduleRender();
}

function keySet(keyName) {
  const m = currentMeasure();
  if (!m) return;
  const range = selectedRange.value || [m.index, m.index];
  const keep = selected.value;
  const end = selectedMeasureEnd.value;
  const next = setKeyForRange(doc.value, measures.value, range[0], range[1], keyName);
  if (next === doc.value) return;
  commit(next, keep);
  if (keep === null) {
    selectMeasure(range[0]);
    selectedMeasureEnd.value = end;
  }
  scheduleRender();
}

function extendToEnd() {
  if (selectedMeasure.value === null || !measures.value.length) return;
  extendMeasureSelection(measures.value.length - 1);
  scheduleRender();
}

function hairpinOverRange(kind) {
  const idx = noteRangeIndices.value;
  if (idx.length < 2) return;
  const first = idx[0];
  const last = idx[idx.length - 1];
  const startUid = doc.value.tokens[first].uid;
  const endUid = doc.value.tokens[last].uid;
  commit(placeHairpin(doc.value, first, last, kind), null);
  selectHairpin(startUid, endUid, kind);
  scheduleRender();
}

function tieRange() {
  const idx = noteRangeIndices.value.filter((i) => doc.value.tokens[i].kind === "note");
  if (idx.length < 2) return;
  let next = doc.value;
  for (let k = 0; k < idx.length - 1; k += 1) next = toggleTie(next, idx[k], true);
  const keep = selected.value;
  const end = selectedNoteEnd.value;
  commit(next, keep);
  selectedNoteEnd.value = end;
  scheduleRender();
}

function tieToggle() {
  if (!requireNote()) return;
  commit(toggleTie(doc.value, selected.value));
}

/** Slur from the selected note to the next sounding event (or remove it). */
function slurToggle() {
  if (!selectedToken.value) return;
  const idx = selected.value;
  const existing = findSlurs(doc.value.tokens).find((sl) => sl.start === idx);
  if (existing) {
    commit(removeSlur(doc.value, existing.start, existing.end));
    return;
  }
  const next = nextSoundingIndex(doc.value.tokens, idx);
  if (next === -1) return;
  commit(placeSlur(doc.value, idx, next));
}

function slurOverRange() {
  const idx = noteRangeIndices.value;
  if (idx.length < 2) return;
  const first = idx[0];
  const last = idx[idx.length - 1];
  const startUid = doc.value.tokens[first].uid;
  const endUid = doc.value.tokens[last].uid;
  commit(placeSlur(doc.value, first, last), null);
  selectSlur(startUid, endUid);
  scheduleRender();
}

const tieRangeAllowed = computed(() => {
  const idx = noteRangeIndices.value;
  if (idx.length < 2 || !doc.value) return false;
  return idx.slice(0, -1).every((i) => tieAllowed(doc.value.tokens, i));
});

function hairpinToggleType() {
  const hp = selectedHairpinIndices.value;
  if (!hp) return;
  const kind = hp.kind === "cresc" ? "decresc" : "cresc";
  const sel = { ...selectedHairpin.value, kind };
  commit(setHairpin(doc.value, hp.start, kind), null);
  selectedHairpin.value = sel;
  scheduleRender();
}

/** Move one end of the selected hairpin to the event token `targetIdx`. */
function moveHairpinEnd(side, targetIdx) {
  const hp = selectedHairpinIndices.value;
  if (!hp || targetIdx === null || targetIdx === undefined) return;
  let start = hp.start;
  let end = hp.end ?? hp.start;
  if (side === "start") start = targetIdx;
  else end = targetIdx;
  if (start === end) return;
  if (start > end) [start, end] = [end, start];
  if (start === hp.start && end === hp.end) return;
  const startUid = doc.value.tokens[start].uid;
  const endUid = doc.value.tokens[end].uid;
  let next = removeHairpin(doc.value, hp.start, hp.end);
  next = placeHairpin(next, start, end, hp.kind);
  commit(next, null);
  selectHairpin(startUid, endUid, hp.kind);
  scheduleRender();
}

function articulationToggle(name) {
  if (!requireNote()) return;
  commit(toggleArticulation(doc.value, selected.value, name));
}

function dynamicSet(name) {
  if (!selectedToken.value) return;
  commit(setDynamic(doc.value, selected.value, name));
}

function hairpinSet(kind) {
  if (!selectedToken.value) return;
  commit(setHairpin(doc.value, selected.value, kind));
}

const selectedDecorations = computed(() =>
  selectedToken.value ? eventDecorations(selectedToken.value) : null,
);

const canInsertBarline = computed(() => {
  const t = selectedToken.value;
  if (!t) return false;
  const m = measureOfToken(selected.value);
  if (!m || m.percent !== null) return false;
  const pos = m.events.indexOf(selected.value);
  return pos >= 0 && pos < m.events.length - 1;
});

const canRemoveBarline = computed(() => {
  const m = selectedBarlineMeasure.value || currentMeasure();
  return !!m && m.endToken !== null && m.endToken !== undefined;
});

// ── Context menu ─────────────────────────────────────────────────────────

const menuItems = computed(() => {
  const items = [];
  const sl = selectedSlurIndices.value;
  if (sl) {
    items.push({ type: "header", label: "Bindebogen" });
    items.push({
      type: "item",
      label: "Bindebogen entfernen",
      danger: true,
      action: deleteSelection,
    });
    return items;
  }
  const hp = selectedHairpinIndices.value;
  if (hp) {
    items.push({ type: "header", label: hp.kind === "cresc" ? "Crescendo" : "Decrescendo" });
    items.push({
      type: "item",
      label: hp.kind === "cresc" ? "In Decrescendo ändern" : "In Crescendo ändern",
      action: hairpinToggleType,
    });
    items.push({ type: "sep" });
    items.push({ type: "item", label: "Gabel entfernen", danger: true, action: deleteSelection });
    return items;
  }
  if (isNoteRange.value) {
    items.push({ type: "header", label: `${noteRangeIndices.value.length} Noten` });
    items.push({
      type: "item",
      label: "Crescendo über die Auswahl",
      action: () => hairpinOverRange("cresc"),
    });
    items.push({
      type: "item",
      label: "Decrescendo über die Auswahl",
      action: () => hairpinOverRange("decresc"),
    });
    items.push({
      type: "item",
      label: tieRangeAllowed.value
        ? "Mit Haltebögen verbinden"
        : "Haltebögen nur bei gleicher Tonhöhe",
      disabled: !tieRangeAllowed.value,
      action: tieRange,
    });
    items.push({ type: "item", label: "Bindebogen über die Auswahl", action: slurOverRange });
    items.push({ type: "sep" });
    items.push({ type: "item", label: "Noten löschen", danger: true, action: deleteSelection });
    return items;
  }
  const t = selectedToken.value;
  if (t) {
    const deco = selectedDecorations.value;
    if (t.kind === "note") {
      items.push({ type: "header", label: "Artikulation" });
      for (const [name, def] of Object.entries(ARTICULATIONS)) {
        items.push({
          type: "check",
          label: def.label,
          checked: deco.articulations.has(name),
          action: () => articulationToggle(name),
        });
      }
    }
    if (t.kind !== "mmrest") {
      items.push({ type: "header", label: "Dynamik" });
      for (const dyn of DYNAMICS) {
        items.push({
          type: "radio",
          label: dyn,
          checked: deco.dynamic === dyn,
          action: () => dynamicSet(deco.dynamic === dyn ? null : dyn),
        });
      }
      items.push({ type: "header", label: "Gabel" });
      for (const [kind, label] of [
        ["cresc", "Crescendo beginnen"],
        ["decresc", "Decrescendo beginnen"],
        ["end", "Gabel beenden"],
      ]) {
        items.push({
          type: "radio",
          label,
          checked: deco.hairpin === kind,
          action: () => hairpinSet(deco.hairpin === kind ? null : kind),
        });
      }
    }
    items.push({ type: "sep" });
    const nm = measureOfToken(selected.value);
    if (nm) {
      items.push({
        type: "item",
        label: `${measureLabel(nm)} auswählen`,
        action: () => {
          selectMeasure(nm.index);
          scheduleRender();
        },
      });
    }
    if (t.kind === "note") {
      const tieOk = tieAllowed(doc.value.tokens, selected.value);
      items.push({
        type: "check",
        label:
          tieOk || deco.tie
            ? "Haltebogen zur nächsten Note"
            : "Haltebogen nur bei gleicher Tonhöhe",
        checked: deco.tie,
        disabled: !tieOk && !deco.tie,
        action: tieToggle,
      });
      items.push({
        type: "check",
        label: "Bindebogen zur nächsten Note",
        checked: deco.slurStart,
        action: slurToggle,
      });
    }
    if (t.kind !== "spacer" && t.kind !== "mmrest") {
      items.push({ type: "item", label: "Note ↔ Pause", action: restToggle });
    }
    items.push({
      type: "item",
      label: "Taktstrich danach einfügen",
      disabled: !canInsertBarline.value,
      action: barlineInsert,
    });
    items.push({ type: "item", label: "Löschen", danger: true, action: remove });
    return items;
  }
  const bm = selectedBarlineMeasure.value;
  if (bm) {
    items.push({ type: "header", label: "Taktstrich" });
    for (const [type, def] of Object.entries(BARLINE_TYPES)) {
      items.push({
        type: "radio",
        label: def.label,
        checked: selectedBarlineType.value === type,
        action: () => barlineSetType(type),
      });
    }
    items.push({ type: "sep" });
    items.push({
      type: "item",
      label: "Taktstrich entfernen",
      danger: true,
      action: deleteSelection,
    });
    return items;
  }
  const m = currentMeasure();
  if (m && isRange.value) {
    items.push({ type: "header", label: rangeLabel() });
    items.push({
      type: "header",
      label: `Tonart für ${rangeLabel()}`,
    });
    for (const [key, label] of MAJOR_KEYS) {
      items.push({
        type: "radio",
        label,
        checked: m.keyName === key && m.mode === "major",
        action: () => keySet(key),
      });
    }
    items.push({ type: "sep" });
    items.push({ type: "item", label: "Takte löschen", danger: true, action: deleteSelection });
    return items;
  }
  if (m) {
    items.push({ type: "header", label: measureLabel(m) });
    items.push({
      type: "item",
      label: "Leeren Takt davor einfügen",
      action: () => measureInsert("before"),
    });
    items.push({
      type: "item",
      label: "Leeren Takt danach einfügen",
      action: () => measureInsert("after"),
    });
    items.push({ type: "header", label: "Taktwiederholung" });
    items.push({
      type: "item",
      label:
        m.percent === null ? "Takt wiederholen (2×)" : `Eine Wiederholung mehr (${m.percent + 1}×)`,
      disabled: !m.events.length,
      action: () => repeatCountChange(1),
    });
    if (m.percent !== null) {
      items.push({
        type: "item",
        label:
          m.percent > 2 ? `Eine Wiederholung weniger (${m.percent - 1}×)` : "Wiederholung auflösen",
        action: () => repeatCountChange(-1),
      });
    }
    items.push({
      type: "header",
      label: isRange.value ? `Tonart für ${rangeLabel()}` : `Tonart für ${measureLabel(m)}`,
    });
    for (const [key, label] of MAJOR_KEYS) {
      items.push({
        type: "radio",
        label,
        checked: m.keyName === key && m.mode === "major",
        action: () => keySet(key),
      });
    }
    if (!isRange.value) {
      items.push({ type: "item", label: "Auswahl bis zum Ende erweitern", action: extendToEnd });
    }
    items.push({ type: "sep" });
    items.push({ type: "item", label: "Takt löschen", danger: true, action: measureDelete });
  }
  return items;
});

function openMenu(x, y) {
  if (!hasSelection.value) return;
  const width = 240;
  const height = Math.min(window.innerHeight - 16, 40 * Math.min(menuItems.value.length, 12) + 16);
  menu.value = {
    x: Math.max(8, Math.min(x, window.innerWidth - width - 8)),
    y: Math.max(8, Math.min(y, window.innerHeight - height - 8)),
  };
  document.addEventListener("pointerdown", onDocumentPointerDown, true);
}

function closeMenu() {
  menu.value = null;
  document.removeEventListener("pointerdown", onDocumentPointerDown, true);
}

function onDocumentPointerDown(ev) {
  if (ev.target.closest && ev.target.closest(".context-menu")) return;
  closeMenu();
}

function runMenuItem(item) {
  if (item.disabled) return;
  closeMenu();
  item.action();
  // keep keyboard navigation alive: focus returns to the editor
  nextTick(() => container.value?.focus());
}

function openMenuFromButton() {
  if (menu.value) {
    closeMenu();
    return;
  }
  const r = menuButton.value?.getBoundingClientRect();
  if (r) openMenu(r.left, r.bottom + 4);
}

function onContextMenu(ev) {
  const hit = hitTarget(ev.target);
  if (!hit) return;
  ev.preventDefault();
  applyHit(hit);
  scheduleRender();
  openMenu(ev.clientX, ev.clientY);
}

function cellSelectedForNumber(index) {
  const r = selectedRange.value;
  return !!r && index >= r[0] && index <= r[1];
}

/** Resolve an SVG element to a selectable thing: note, barline, measure number, empty measure. */
function hitTarget(el) {
  if (!el || !el.closest) return null;
  const target = el.closest(
    "g.vf-stavenote, [id^='vf-empty-'], [id^='vf-bar-'], [id^='vf-mnum-'], [id^='vf-hp-'], [id^='vf-slur-']",
  );
  if (!target) return null;
  if (target.id.startsWith("vf-slur-")) {
    return {
      kind: "slur",
      startUid: Number(target.dataset.start),
      endUid: target.dataset.end ? Number(target.dataset.end) : null,
    };
  }
  if (target.id.startsWith("vf-hp-")) {
    return {
      kind: "hairpin",
      startUid: Number(target.dataset.start),
      endUid: target.dataset.end ? Number(target.dataset.end) : null,
      hairpinKind: target.dataset.kind,
      x1: Number(target.dataset.x1),
      x2: Number(target.dataset.x2),
    };
  }
  if (target.id.startsWith("vf-empty-") || target.id.startsWith("vf-mnum-")) {
    const cell = target.dataset.cell !== undefined ? Number(target.dataset.cell) : null;
    return { kind: "measure", index: Number(target.dataset.measure), cell };
  }
  if (target.id.startsWith("vf-bar-"))
    return { kind: "barline", index: Number(target.dataset.measure) };
  const id = target.id.slice(3);
  return currentNoteMap.has(id) ? { kind: "note", tokenIndex: currentNoteMap.get(id) } : null;
}

function applyHit(hit, extend = false) {
  if (hit.kind === "note" && extend) extendNoteSelection(hit.tokenIndex);
  else if (hit.kind === "note") selectNote(hit.tokenIndex);
  else if (hit.kind === "hairpin") selectHairpin(hit.startUid, hit.endUid, hit.hairpinKind);
  else if (hit.kind === "slur") selectSlur(hit.startUid, hit.endUid);
  else if (hit.kind === "barline") selectBarline(hit.index);
  else if (extend) extendMeasureSelection(hit.index);
  else selectMeasure(hit.index, hit.cell ?? null);
  container.value?.focus();
}

let currentNoteMap = new Map();

function defaultPitchForSelection() {
  const t = selectedToken.value;
  if (t && t.kind === "note" && t.pitches.length) return { ...t.pitches[0] };
  const m = currentMeasure();
  const flats = m ? keyFlats(m.keyName, m.mode) : 0;
  // middle of the staff for the clef in use
  const letter = m && m.clef === "bass" ? "d" : "b";
  const octave = m && m.clef === "bass" ? 3 : 4;
  return { letter, alter: keyAlteration(letter, flats), octave };
}

function insert(kind) {
  if (!doc.value) return;
  const m = currentMeasure();
  if (!m) return;
  const t = selectedToken.value;
  const duration =
    t && t.duration
      ? { base: t.duration.base, dots: t.duration.dots, mult: null }
      : { base: 4, dots: 0, mult: null };
  const event = {
    kind,
    pitches: kind === "note" ? [defaultPitchForSelection()] : [],
    duration,
  };
  const after = t ? selected.value : null;
  const res = insertEvent(doc.value, m, after, event);
  commit(res.doc, res.tokenIndex);
}

function measureOfToken(idx) {
  return measures.value.find((m) => idx >= m.tokenStart && idx < m.tokenEnd) || null;
}

function currentMeasure() {
  if (selected.value !== null) return measureOfToken(selected.value);
  if (selectedMeasure.value !== null) return measures.value[selectedMeasure.value] || null;
  return null;
}

function extendNoteRange(delta) {
  const order = measures.value
    .flatMap((m) => m.events)
    .filter((i) => doc.value.tokens[i].kind !== "spacer");
  const cur = selectedNoteEnd.value ?? selected.value;
  const pos = order.indexOf(cur);
  if (pos === -1) return;
  const next = Math.min(order.length - 1, Math.max(0, pos + delta));
  extendNoteSelection(order[next]);
  scheduleRender();
}

function moveSelection(delta) {
  const order = measures.value.flatMap((m) => m.events);
  if (!order.length) return;
  if (selected.value === null) {
    // Start inside the selected measure when there is one, else at the score's edge
    const m = currentMeasure();
    if (m && m.events.length) {
      selectNote(delta > 0 ? m.events[0] : m.events[m.events.length - 1]);
    } else {
      selectNote(delta > 0 ? order[0] : order[order.length - 1]);
    }
  } else {
    const pos = order.indexOf(selected.value);
    const next = Math.min(order.length - 1, Math.max(0, pos + delta));
    selectNote(order[next]);
  }
  scheduleRender();
}

function onKeydown(e) {
  if (e.target && /^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName)) return;
  const mod = e.ctrlKey || e.metaKey;
  if (mod && e.key.toLowerCase() === "z") {
    e.preventDefault();
    if (e.shiftKey) redo();
    else undo();
    return;
  }
  if (mod && e.key.toLowerCase() === "y") {
    e.preventDefault();
    redo();
    return;
  }
  if (mod) return;
  if (e.key === "ContextMenu" || (e.shiftKey && e.key === "F10")) {
    e.preventDefault();
    openMenuFromButton();
    return;
  }
  if (menu.value && e.key === "Escape") {
    closeMenu();
    nextTick(() => container.value?.focus());
    return;
  }
  switch (e.key) {
    case "ArrowUp":
      e.preventDefault();
      e.shiftKey ? stepAccidental(1) : stepPitch(1);
      break;
    case "ArrowDown":
      e.preventDefault();
      e.shiftKey ? stepAccidental(-1) : stepPitch(-1);
      break;
    case "ArrowLeft":
      e.preventDefault();
      if (e.shiftKey && selectedMeasure.value !== null && selected.value === null) {
        extendMeasureSelection(
          Math.max(0, (selectedMeasureEnd.value ?? selectedMeasure.value) - 1),
        );
        scheduleRender();
      } else if (e.shiftKey && selected.value !== null) {
        extendNoteRange(-1);
      } else moveSelection(-1);
      break;
    case "ArrowRight":
      e.preventDefault();
      if (e.shiftKey && selectedMeasure.value !== null && selected.value === null) {
        extendMeasureSelection(
          Math.min(
            measures.value.length - 1,
            (selectedMeasureEnd.value ?? selectedMeasure.value) + 1,
          ),
        );
        scheduleRender();
      } else if (e.shiftKey && selected.value !== null) {
        extendNoteRange(1);
      } else moveSelection(1);
      break;
    case "1":
    case "2":
    case "4":
    case "8":
      setDuration(Number(e.key));
      break;
    case "6":
      setDuration(16);
      break;
    case ".":
      dot();
      break;
    case "Delete":
    case "Backspace":
      e.preventDefault();
      deleteSelection();
      break;
    case "n":
      insert("note");
      break;
    case "r":
      insert("rest");
      break;
    case "t":
      restToggle();
      break;
    case "b":
    case "|":
      barlineInsert();
      break;
    case "B":
      barlineRemove();
      break;
    case "Escape":
      clearSelection();
      scheduleRender();
      break;
    default:
      break;
  }
}

// ── Rendering ────────────────────────────────────────────────────────────

const CLEF_REST_KEY = { treble: "b/4", bass: "d/3", alto: "c/4", tenor: "a/3" };
const ACC_STR = { "-2": "bb", "-1": "b", 0: "", 1: "#", 2: "##" };
const KEY_LETTER = { c: "C", d: "D", e: "E", f: "F", g: "G", a: "A", b: "B" };
const ARTICULATION_CODES = {
  "->": "a>",
  "-.": "a.",
  "--": "a-",
  "-^": "a^",
  "\\fermata": "a@a",
  "-\\fermata": "a@a",
};
const DYNAMIC_RE = /\\(ppp|pp|p|mp|mf|f|ff|fff|fp|sf|sff|sp|spp|sfz|rfz|fz)(?![a-zA-Z])/g;

const ROW_HEIGHT = 150;
const TOP_PAD = 30;
const SIDE_PAD = 10;

let renderTimer = null;
function scheduleRender() {
  if (renderTimer) cancelAnimationFrame(renderTimer);
  renderTimer = requestAnimationFrame(() => {
    renderTimer = null;
    render();
  });
}

function lilyKeyToVex(keyName, mode) {
  const m = /^([a-g])(es|is|s)?$/.exec(keyName);
  if (!m) return "C";
  let k = KEY_LETTER[m[1]];
  if (m[2] === "es" || m[2] === "s") k += "b";
  if (m[2] === "is") k += "#";
  return mode === "minor" ? `${k}m` : k;
}

function pitchToVexKey(p) {
  return `${p.letter}${ACC_STR[p.alter] || ""}/${p.octave}`;
}

function vexDuration(t) {
  const d = t.duration || { base: 4, dots: 0 };
  const base = t.duration ? String(d.base) : "4";
  return t.kind === "note" ? base : `${base}r`;
}

const PERCENT_CELL_WIDTH = 64;
const PERCENT_GLYPH = ""; // SMuFL repeat1Bar

/** Expand measures into drawable cells: music cell + N-1 percent cells. */
function buildCells(ms) {
  const cells = [];
  for (const m of ms) {
    cells.push({ m, kind: "music", number: m.number });
    for (let k = 1; k < m.span; k += 1) {
      cells.push({ m, kind: "percent", number: m.number + k });
    }
  }
  return cells;
}

function cellWidth(cell, isRowStart, prevCell) {
  const m = cell.m;
  let w = cell.kind === "percent" ? PERCENT_CELL_WIDTH : 34 + m.events.length * 30;
  if (isRowStart || (cell.kind === "music" && m.showClef)) w += 32;
  if (isRowStart || (cell.kind === "music" && m.showKey)) {
    w += 12 + 8 * Math.abs(keyFlats(m.keyName, m.mode));
  }
  if (cell.kind === "music" && (m.showTime || !prevCell)) w += 28;
  if (cell.kind === "music" && m.startBarline === "repeat-begin") w += 12;
  return Math.max(w, cell.kind === "percent" ? PERCENT_CELL_WIDTH : 70);
}

const MIN_LILYPOND_SCALE = 0.55;

/**
 * Pack cells into rows. Returns { rows, width } where width is the content
 * width (may exceed availableWidth in "lilypond" mode, the host then scrolls
 * horizontally).
 */
function layoutRows(cells, availableWidth, mode) {
  const rows = [];
  let row = [];
  let rowWidth = 0;
  for (let i = 0; i < cells.length; i += 1) {
    const cell = cells[i];
    const prev = i > 0 ? cells[i - 1] : null;
    const w = cellWidth(cell, row.length === 0, prev);
    const breakBefore = mode === "lilypond" && cell.kind === "music" && cell.m.breakBefore;
    const overflow = mode === "auto" && rowWidth + w > availableWidth;
    if (row.length && (breakBefore || overflow)) {
      rows.push(row);
      row = [];
      rowWidth = 0;
    }
    const cw = row.length === 0 ? cellWidth(cell, true, prev) : w;
    row.push({ cell, w: cw });
    rowWidth += cw;
  }
  if (row.length) rows.push(row);

  let contentWidth = availableWidth;
  rows.forEach((r, idx) => {
    const natural = r.reduce((sum, x) => sum + x.w, 0);
    let scale;
    if (mode === "lilypond") {
      scale = Math.max(MIN_LILYPOND_SCALE, availableWidth / natural);
      if (natural * scale > contentWidth) contentWidth = Math.ceil(natural * scale);
    } else {
      scale =
        idx === rows.length - 1 ? Math.min(1, availableWidth / natural) : availableWidth / natural;
    }
    r.forEach((x) => {
      x.w = Math.floor(x.w * scale);
    });
  });
  return { rows, width: contentWidth };
}

function cssVar(name, fallback) {
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return v || fallback;
}

const END_BAR = {
  single: Barline.type.SINGLE,
  double: Barline.type.DOUBLE,
  end: Barline.type.END,
  "repeat-begin": Barline.type.REPEAT_BEGIN,
  "repeat-end": Barline.type.REPEAT_END,
  "repeat-both": Barline.type.REPEAT_BOTH,
  none: Barline.type.NONE,
};

function render() {
  const el = host.value;
  if (!el) return;
  el.innerHTML = "";
  renderError.value = null;
  if (!doc.value || !fontsReady.value) return;

  const tokens = doc.value.tokens;
  const ms = measures.value;
  measureBoxes = [];
  notePositions = [];
  tooltip.value = null;
  const availableWidth = Math.max(320, width.value - 2 * SIDE_PAD);
  const cells = buildCells(ms);
  const { rows, width: contentWidth } = layoutRows(cells, availableWidth, layoutMode.value);

  // Optional scan snippets above each row: their height follows the crop height
  const snippetsOn =
    showSnippets.value &&
    canShowSnippets.value &&
    imageSize.value &&
    layoutMode.value === "lilypond";
  const snippetScale = imageSize.value ? contentWidth / imageSize.value.w : 0;
  const snippets = rows.map((_, rowIdx) => {
    if (!snippetsOn) return null;
    const crop = snippetCrop(rowIdx);
    return crop ? { ...crop, px: Math.ceil(crop.height * snippetScale) } : null;
  });
  // Gap between a snippet and its row: room for volta brackets and the number row
  const SNIPPET_GAP = 18;
  const rowTops = [];
  let cursorY = TOP_PAD;
  snippets.forEach((sn) => {
    rowTops.push(cursorY + (sn ? sn.px + SNIPPET_GAP : 0));
    cursorY += ROW_HEIGHT + (sn ? sn.px + SNIPPET_GAP + 10 : 0);
  });
  rowTopsCache = rowTops;
  const totalHeight = cursorY + 20;

  const colorInk = cssVar("--color-text", "#1c2733");
  const colorErr = cssVar("--color-danger", "#b3261e");
  const colorSel = cssVar("--color-primary", "#2f5d9e");
  const colorCopy = cssVar("--color-muted", "#7a8794");
  const colorNumber = cssVar("--color-muted", "#7a8794");

  let renderer;
  try {
    renderer = new Renderer(el, Renderer.Backends.SVG);
    renderer.resize(contentWidth + 2 * SIDE_PAD, totalHeight);
    svgLogicalWidth = contentWidth + 2 * SIDE_PAD;
  } catch (e) {
    renderError.value = e.message;
    return;
  }
  const ctx = renderer.getContext();
  // VexFlow's volta bracket can produce a negative width on narrow measures,
  // which SVG rejects with a console error. Normalise before it reaches the DOM.
  const origFillRect = ctx.fillRect.bind(ctx);
  ctx.fillRect = (rx, ry, rw, rh) => origFillRect(rw < 0 ? rx + rw : rx, ry, Math.abs(rw), rh);
  ctx.setFillStyle(colorInk);
  ctx.setStrokeStyle(colorInk);

  const noteMap = new Map(); // svg id → token index
  // Event sequence in score order for hairpins: { tok, note|null, row }
  const sequence = [];
  rows.forEach((row, rowIdx) => {
    const y = rowTops[rowIdx];
    let x = SIDE_PAD;
    row.forEach((item, cellIdx) => {
      const { cell } = item;
      const m = cell.m;
      const isRowStart = cellIdx === 0;
      const isMusic = cell.kind === "music";
      const isLastCellOfMeasure = isMusic ? m.span === 1 : cell.number === m.number + m.span - 1;

      const stave = new Stave(x, y, item.w, { spaceAboveStaffLn: 3 });
      measureBoxes.push({ x, y, w: item.w, h: ROW_HEIGHT, m, cell });
      stave.setStyle({ strokeStyle: colorInk, fillStyle: colorInk });
      if (isRowStart || (isMusic && m.showClef)) stave.addClef(m.clef);
      if (isRowStart || (isMusic && m.showKey)) {
        stave.addKeySignature(lilyKeyToVex(m.keyName, m.mode));
      }
      if (isMusic && (m.showTime || (rowIdx === 0 && isRowStart))) {
        stave.addTimeSignature(`${m.time.beats}/${m.time.beatType}`);
      }

      if (isMusic && m.startBarline === "repeat-begin") {
        stave.setBegBarType(Barline.type.REPEAT_BEGIN);
      }
      const endType = isLastCellOfMeasure ? END_BAR[m.endBarline] : Barline.type.SINGLE;
      stave.setEndBarType(endType ?? Barline.type.SINGLE);

      if (isMusic && m.volta) {
        const vt = {
          begin: Volta.type.BEGIN,
          mid: Volta.type.MID,
          end: Volta.type.END,
          "begin-end": Volta.type.BEGIN_END,
        };
        const showNumber = m.volta.position === "begin" || m.volta.position === "begin-end";
        // +25 pulls the bracket down, right above the number row
        stave.setVoltaType(
          vt[m.volta.position] || Volta.type.BEGIN,
          showNumber ? `${m.volta.count}.` : "",
          25,
        );
      }
      if (isMusic && m.section) stave.setSection(m.section, 0, 0, 12, false);
      stave.setContext(ctx).draw();

      // Printed measure number, small and muted, at the top left of the measure.
      // Clicking it selects the whole measure.
      const numGroup = ctx.openGroup("measure-number", `mnum-${m.index}-${cell.number}`);
      ctx.rect(x, y + 2, 28, 26, { fill: "none", stroke: "none", "pointer-events": "all" });
      ctx.save();
      ctx.setFont("Academico", 9, "normal", "normal");
      ctx.setFillStyle(cellSelectedForNumber(m.index) ? colorSel : colorNumber);
      ctx.fillText(String(cell.number), x + 3, stave.getYForTopText(0) + 2);
      ctx.restore();
      ctx.closeGroup();
      if (numGroup) {
        numGroup.style.cursor = "pointer";
        numGroup.dataset.measure = String(m.index);
        numGroup.dataset.cell = String(cell.number);
      }

      // Whole-measure selection outline (for percent repeats only the clicked cell)
      const r = selectedRange.value;
      const inRange = !!r && r[0] !== r[1] && m.index >= r[0] && m.index <= r[1];
      const cellSelected =
        inRange ||
        (selectedMeasure.value === m.index &&
          (selectedCell.value === null ? isMusic : selectedCell.value === cell.number));
      if (cellSelected) {
        ctx.rect(x + 1, y + 10, item.w - 2, 84, {
          fill: colorSel,
          "fill-opacity": 0.06,
          stroke: colorSel,
          "stroke-opacity": 0.7,
          "stroke-dasharray": "4 3",
          rx: 4,
          "pointer-events": "none",
        });
      }

      // End barline hit area (last cell of the measure only)
      if (isLastCellOfMeasure && m.endToken !== null && m.endToken !== undefined) {
        const isBarSel = selectedBarline.value === m.index;
        const barGroup = ctx.openGroup("barline-hit", `bar-${m.index}`);
        ctx.rect(
          x + item.w - 8,
          stave.getYForLine(0) - 8,
          16,
          stave.getYForLine(4) - stave.getYForLine(0) + 16,
          isBarSel
            ? {
                fill: colorSel,
                "fill-opacity": 0.25,
                stroke: colorSel,
                rx: 3,
                "pointer-events": "auto",
              }
            : { fill: "none", stroke: "none", "pointer-events": "all" },
        );
        ctx.closeGroup();
        if (barGroup) {
          barGroup.style.cursor = "pointer";
          barGroup.dataset.measure = String(m.index);
        }
      }

      if (!isMusic) {
        // Percent repeat: the "%"-like repeat sign centred on the middle line
        ctx.save();
        ctx.setFont("Bravura", 30, "normal", "normal");
        ctx.setFillStyle(m.copy ? colorCopy : colorInk);
        const glyphWidth = ctx.measureText(PERCENT_GLYPH).width || 20;
        const cx = stave.getNoteStartX() + (stave.getNoteEndX() - stave.getNoteStartX()) / 2;
        ctx.fillText(PERCENT_GLYPH, cx - glyphWidth / 2, stave.getYForLine(2));
        ctx.restore();
        x += item.w;
        return;
      }

      // Notes
      const notes = [];
      const tokenForNote = [];
      let pendingDynamics = [];
      for (const ti of m.events) {
        const t = tokens[ti];
        if (t.kind === "spacer") {
          pendingDynamics.push(...extractDynamics(t.suffix));
          sequence.push({ tok: t, ti, note: null, row: rowIdx });
          continue;
        }
        const keys =
          t.kind === "note" ? t.pitches.map(pitchToVexKey) : [CLEF_REST_KEY[m.clef] || "b/4"];
        const note = new StaveNote({
          keys,
          duration: vexDuration(t),
          clef: m.clef,
          autoStem: true,
        });
        if (t.duration && t.duration.dots) {
          for (let d = 0; d < t.duration.dots; d += 1) Dot.buildAndAttach([note], { all: true });
        }
        for (const [artic, code] of Object.entries(ARTICULATION_CODES)) {
          if (t.suffix && t.suffix.includes(artic)) note.addModifier(new Articulation(code));
        }
        const dyn = [...pendingDynamics, ...extractDynamics(t.suffix)];
        pendingDynamics = [];
        if (dyn.length) {
          const ann = new Annotation(dyn.join(" "));
          ann.setFont("Academico", 13, "normal", "italic");
          ann.setVerticalJustification(Annotation.VerticalJustify.BOTTOM);
          note.addModifier(ann);
        }
        if (t.kind === "mmrest" && t.duration && t.duration.mult) {
          const ann = new Annotation(`${fracToString(t.duration.mult)} Takte`);
          ann.setFont("Academico", 11, "normal", "normal");
          ann.setVerticalJustification(Annotation.VerticalJustify.TOP);
          note.addModifier(ann);
        }
        const isSel =
          ti === selected.value || (isNoteRange.value && noteRangeIndices.value.includes(ti));
        const color = isSel ? colorSel : m.mismatch ? colorErr : m.copy ? colorCopy : colorInk;
        note.setStyle({ fillStyle: color, strokeStyle: color });
        if (typeof note.setStemStyle === "function") note.setStemStyle({ strokeStyle: color });
        notes.push(note);
        tokenForNote.push(ti);
        sequence.push({ tok: t, ti, note, row: rowIdx });
      }

      if (notes.length) {
        const voice = new Voice({ numBeats: m.time.beats, beatValue: m.time.beatType }).setMode(
          Voice.Mode.SOFT,
        );
        voice.addTickables(notes);
        try {
          Accidental.applyAccidentals([voice], lilyKeyToVex(m.keyName, m.mode));
        } catch {
          // ignore accidental errors, notes still render
        }
        const beams = Beam.generateBeams(notes.filter((n) => !n.isRest()));
        try {
          new Formatter().joinVoices([voice]).formatToStave([voice], stave, { alignRests: true });
          voice.draw(ctx, stave);
          beams.forEach((b) => b.setContext(ctx).draw());
          notes.forEach((n, k) =>
            notePositions.push({
              ti: tokenForNote[k],
              uid: tokens[tokenForNote[k]].uid,
              x: n.getAbsoluteX(),
              row: rowIdx,
            }),
          );
          // Selection highlight: soft rounded box behind each selected note
          const selSet = isNoteRange.value
            ? new Set(noteRangeIndices.value)
            : new Set([selected.value]);
          for (let k = 0; k < notes.length; k += 1) {
            if (!selSet.has(tokenForNote[k])) continue;
            const bb = notes[k].getBoundingBox();
            const pad = 6;
            ctx.rect(bb.getX() - pad, y + 12, bb.getW() + 2 * pad, 84, {
              fill: colorSel,
              "fill-opacity": 0.12,
              stroke: colorSel,
              "stroke-opacity": 0.5,
              rx: 4,
              "pointer-events": "none",
            });
          }
        } catch (e) {
          renderError.value = `${measureLabel(m)}: ${e.message}`;
        }
        notes.forEach((n, i) => noteMap.set(n.getAttribute("id"), tokenForNote[i]));
      } else {
        // Empty measure: make it selectable for inserts
        const g = ctx.openGroup("empty-measure", `empty-${m.index}`);
        ctx.rect(x + 2, y + 20, Math.max(1, item.w - 4), 50, {
          fill: "none",
          stroke: "none",
          "pointer-events": "all",
        });
        ctx.closeGroup();
        if (g) {
          g.style.cursor = "pointer";
          g.dataset.measure = String(m.index);
        }
      }
      x += item.w;
    });
  });

  drawHairpins(ctx, sequence, colorInk, colorSel);
  drawTies(ctx, sequence, colorErr);
  drawSlurs(ctx, sequence, colorInk, colorSel);

  const svg = el.querySelector("svg");
  if (svg && snippetsOn) {
    // Scan snippets as nested <svg> elements whose viewBox crops the page image
    const NS = "http://www.w3.org/2000/svg";
    const XLINK = "http://www.w3.org/1999/xlink";
    snippets.forEach((sn, rowIdx) => {
      if (!sn) return;
      const nested = document.createElementNS(NS, "svg");
      nested.setAttribute("x", String(SIDE_PAD));
      nested.setAttribute("y", String(rowTops[rowIdx] - sn.px - SNIPPET_GAP));
      nested.setAttribute("width", String(contentWidth));
      nested.setAttribute("height", String(sn.px));
      nested.setAttribute("viewBox", `0 ${sn.top} ${imageSize.value.w} ${sn.height}`);
      nested.setAttribute("preserveAspectRatio", "none");
      nested.setAttribute("class", "scan-snippet");
      const image = document.createElementNS(NS, "image");
      image.setAttribute("href", props.staffImageUrl);
      image.setAttributeNS(XLINK, "xlink:href", props.staffImageUrl);
      image.setAttribute("width", String(imageSize.value.w));
      image.setAttribute("height", String(imageSize.value.h));
      nested.appendChild(image);
      svg.insertBefore(nested, svg.firstChild);
    });
  }
  if (svg) {
    if (contentWidth > availableWidth) {
      svg.style.maxWidth = "none";
      svg.style.height = "auto";
    } else {
      svg.style.maxWidth = "100%";
      svg.style.height = "auto";
    }
    currentNoteMap = noteMap;
    svg.addEventListener("pointerdown", (ev) => {
      if (ev.button !== 0) return;
      const hit = hitTarget(ev.target);
      if (!hit) return;
      applyHit(hit, ev.shiftKey);
      if (hit.kind === "hairpin") startHairpinDrag(ev, hit);
      scheduleRender();
    });
    for (const id of noteMap.keys()) {
      const g = svg.querySelector(`#vf-${CSS.escape(id)}`);
      if (g) g.style.cursor = "pointer";
    }
  }
}

/**
 * Crescendo / decrescendo hairpins. A hairpin opens on an event carrying
 * \< or \> and closes on the next event with \! or a dynamic. Spacers
 * (<>\!) close on the previous drawn note with a right shift. Spans over a
 * row break are drawn in two pieces: to the row end and from the row start.
 */
function drawHairpins(ctx, sequence, colorInk, colorSel) {
  const drawn = sequence.filter((s) => s.note);
  let open = null; // { type, kind, startNote, startRow, startTi, startUid }
  const sel = selectedHairpinIndices.value;

  const draw = (hp, first, last, leftShift, rightShift, row) => {
    if (!first || !last) return;
    const isSel = !!sel && sel.start === hp.startTi;
    try {
      const pin = new StaveHairpin({ firstNote: first, lastNote: last }, hp.type);
      pin.setPosition(Modifier.Position.BELOW);
      pin.setRenderOptions({
        height: 9,
        yShift: 8,
        leftShiftPx: leftShift,
        rightShiftPx: rightShift,
      });
      ctx.save();
      ctx.setStrokeStyle(isSel ? colorSel : colorInk);
      ctx.setLineWidth(isSel ? 2 : 1);
      pin.setContext(ctx).draw();
      ctx.restore();
      // hit area over the whole hairpin
      const x1 = first.getModifierStartXY(Modifier.Position.BELOW, 0).x + leftShift;
      const x2 = last.getModifierStartXY(Modifier.Position.BELOW, 0).x + rightShift;
      const stave = first.checkStave();
      const yTop = stave.getY() + stave.getHeight() + 8 + 20 - 6;
      const g = ctx.openGroup("hairpin-hit", `hp-${hp.startTi}-${row}`);
      ctx.rect(Math.min(x1, x2) - 6, yTop, Math.abs(x2 - x1) + 12, 9 + 12, {
        fill: isSel ? colorSel : "none",
        "fill-opacity": isSel ? 0.12 : 0,
        stroke: "none",
        "pointer-events": "all",
      });
      ctx.closeGroup();
      if (g) {
        g.style.cursor = "ew-resize";
        g.dataset.start = String(hp.startUid);
        g.dataset.end = hp.endUid !== null && hp.endUid !== undefined ? String(hp.endUid) : "";
        g.dataset.kind = hp.kind;
        g.dataset.x1 = String(Math.min(x1, x2));
        g.dataset.x2 = String(Math.max(x1, x2));
      }
    } catch {
      // a hairpin that cannot be drawn is not worth breaking the score
    }
  };

  const close = (endNote, endRow, rightShift, endTi) => {
    if (!open) return;
    const endItem = endTi !== null ? sequence.find((s) => s.ti === endTi) : null;
    const hp = { ...open, endUid: endItem ? endItem.tok.uid : null };
    if (endRow === open.startRow) {
      draw(hp, open.startNote, endNote, 0, rightShift, endRow);
    } else {
      const rowNotes = drawn.filter((d) => d.row === open.startRow);
      const lastInRow = rowNotes[rowNotes.length - 1]?.note;
      const endRowNotes = drawn.filter((d) => d.row === endRow);
      const firstInEndRow = endRowNotes[0]?.note;
      draw(hp, open.startNote, lastInRow, 0, 18, open.startRow);
      draw(hp, firstInEndRow, endNote, -6, rightShift, endRow);
    }
    open = null;
  };

  let lastNote = null;
  let lastRow = 0;
  let pendingStart = null;
  for (const item of sequence) {
    const suffix = item.tok.suffix || "";
    const starts = suffix.includes("\\<") ? 1 : suffix.includes("\\>") ? 2 : 0;
    const ends = suffix.includes("\\!") || DYNAMIC_RE.test(suffix);
    DYNAMIC_RE.lastIndex = 0;
    if (item.note) {
      if (open && (ends || starts) && item.note !== open.startNote) {
        close(item.note, item.row, 0, item.ti);
      }
      if (pendingStart) {
        open = { ...pendingStart, startNote: item.note, startRow: item.row };
        pendingStart = null;
      }
      if (starts) {
        open = {
          type: starts,
          kind: starts === 1 ? "cresc" : "decresc",
          startNote: item.note,
          startRow: item.row,
          startTi: item.ti,
          startUid: item.tok.uid,
        };
      }
      lastNote = item.note;
      lastRow = item.row;
    } else {
      // spacer <>\\< / <>\\!
      if (open && ends) close(lastNote, lastRow, 22, item.ti);
      if (starts) {
        pendingStart = {
          type: starts,
          kind: starts === 1 ? "cresc" : "decresc",
          startTi: item.ti,
          startUid: item.tok.uid,
        };
      }
    }
  }
  if (open && lastNote && lastNote !== open.startNote) close(lastNote, lastRow, 22, null);
}

/** Ties (~): connect a note to the next drawn note, split at row breaks. */
function drawTies(ctx, sequence, colorErr) {
  const drawn = sequence.filter((s) => s.note && s.tok.kind !== "spacer");
  for (let i = 0; i < drawn.length; i += 1) {
    const cur = drawn[i];
    if (cur.tok.kind !== "note" || !(cur.tok.suffix || "").includes("~")) continue;
    const next = drawn[i + 1];
    // LilyPond only ties equal pitches: show an impossible tie in red
    const valid = doc.value ? tieAllowed(doc.value.tokens, cur.ti) : true;
    const style = valid ? undefined : { strokeStyle: colorErr, fillStyle: colorErr };
    const opts = { firstIndices: [0], lastIndices: [0] };
    try {
      if (next && next.row === cur.row && next.tok.kind === "note") {
        const tie = new StaveTie({ firstNote: cur.note, lastNote: next.note, ...opts });
        if (style) tie.setStyle(style);
        tie.setContext(ctx).draw();
      } else {
        const tie = new StaveTie({ firstNote: cur.note, ...opts });
        if (style) tie.setStyle(style);
        tie.setContext(ctx).draw();
        if (next && next.tok.kind === "note" && valid) {
          new StaveTie({ lastNote: next.note, ...opts }).setContext(ctx).draw();
        }
      }
    } catch {
      // ignore ties that cannot be drawn
    }
  }
}

/** Slurs ( … ): a curve from the start note to the end note, selectable. */
function drawSlurs(ctx, sequence, colorInk, colorSel) {
  if (!doc.value) return;
  const byTi = new Map(sequence.filter((s) => s.note).map((s) => [s.ti, s]));
  const sel = selectedSlurIndices.value;
  for (const sl of findSlurs(doc.value.tokens)) {
    const a = byTi.get(sl.start);
    const b = sl.end !== null ? byTi.get(sl.end) : null;
    if (!a) continue;
    const isSel = !!sel && sel.start === sl.start;
    const color = isSel ? colorSel : colorInk;
    const pieces = [];
    if (b && b.row === a.row) pieces.push([a.note, b.note]);
    else {
      pieces.push([a.note, undefined]);
      if (b) pieces.push([undefined, b.note]);
    }
    for (const [first, last] of pieces) {
      try {
        const curve = new Curve(first, last, { thickness: isSel ? 3 : 2 });
        curve.setStyle({ strokeStyle: color, fillStyle: color });
        curve.setContext(ctx).draw();
        // hit area between the two anchors, above the notes
        const anchor = first || last;
        const stave = anchor.checkStave();
        const x1 = first ? first.getAbsoluteX() : stave.getNoteStartX();
        const x2 = last ? last.getAbsoluteX() : stave.getNoteEndX();
        const yTop = stave.getYForTopText(1) - 4;
        const g = ctx.openGroup("slur-hit", `slur-${sl.start}-${a.row}`);
        ctx.rect(Math.min(x1, x2), yTop, Math.abs(x2 - x1) + 10, 22, {
          fill: isSel ? colorSel : "none",
          "fill-opacity": isSel ? 0.12 : 0,
          stroke: "none",
          "pointer-events": "all",
        });
        ctx.closeGroup();
        if (g) {
          g.style.cursor = "pointer";
          g.dataset.start = String(doc.value.tokens[sl.start].uid);
          g.dataset.end = sl.end !== null ? String(doc.value.tokens[sl.end].uid) : "";
        }
      } catch {
        // ignore slurs that cannot be drawn
      }
    }
  }
}

// ── Hairpin drag ─────────────────────────────────────────────────────────

function svgPoint(ev) {
  const svg = host.value?.querySelector("svg");
  if (!svg || !svgLogicalWidth) return null;
  const rect = svg.getBoundingClientRect();
  if (!rect.width) return null;
  const scale = svgLogicalWidth / rect.width;
  return { x: (ev.clientX - rect.left) * scale, y: (ev.clientY - rect.top) * scale };
}

function startHairpinDrag(ev, hit) {
  const pt = svgPoint(ev);
  if (!pt) return;
  const side = Math.abs(pt.x - hit.x1) <= Math.abs(pt.x - hit.x2) ? "start" : "end";
  hairpinDrag = { side, moved: false };
  window.addEventListener("pointermove", onHairpinDragMove);
  window.addEventListener("pointerup", onHairpinDragEnd, { once: true });
}

function onHairpinDragMove() {
  if (hairpinDrag) hairpinDrag.moved = true;
}

function onHairpinDragEnd(ev) {
  window.removeEventListener("pointermove", onHairpinDragMove);
  const drag = hairpinDrag;
  hairpinDrag = null;
  if (!drag || !drag.moved) return;
  const pt = svgPoint(ev);
  if (!pt) return;
  // nearest drawn note in the row under the pointer (fallback: nearest anywhere)
  const box = measureBoxes.find((b) => pt.y >= b.y && pt.y < b.y + b.h);
  const rowIdx = box ? rowTopsCache.indexOf(box.y) : -1;
  const inRow = notePositions.filter((n) => n.row === rowIdx);
  const pool = inRow.length ? inRow : notePositions;
  let best = null;
  for (const n of pool) {
    const d = Math.abs(n.x - pt.x);
    if (!best || d < best.d) best = { ...n, d };
  }
  if (best) moveHairpinEnd(drag.side, best.ti);
}

/** Toolbar clicks must not steal the keyboard from the editor. */
function refocusEditor() {
  nextTick(() => container.value?.focus());
}

function extractDynamics(suffix) {
  if (!suffix) return [];
  const out = [];
  for (const m of suffix.matchAll(DYNAMIC_RE)) out.push(m[1]);
  return out;
}

// ── Hover hints ──────────────────────────────────────────────────────────

function measureAtPointer(ev) {
  const svg = host.value?.querySelector("svg");
  if (!svg || !svgLogicalWidth) return null;
  const rect = svg.getBoundingClientRect();
  if (!rect.width) return null;
  const scale = svgLogicalWidth / rect.width;
  const px = (ev.clientX - rect.left) * scale;
  const py = (ev.clientY - rect.top) * scale;
  return (
    measureBoxes.find((b) => px >= b.x && px < b.x + b.w && py >= b.y && py < b.y + b.h) || null
  );
}

function onPointerMove(ev) {
  if (ev.pointerType === "touch") return;
  const box = measureAtPointer(ev);
  let lines = [];
  let title = "";
  if (box && box.cell && box.cell.kind === "percent") {
    title = `Takt ${box.cell.number}`;
    lines = [`Wiederholung von Takt ${box.m.number}`];
  } else if (box) {
    title = measureLabel(box.m);
    lines = measureHints(box.m);
  }
  if (!box || !lines.length) {
    tooltip.value = null;
    return;
  }
  tooltip.value = { x: ev.clientX + 12, y: ev.clientY + 16, title, lines };
}

function onPointerLeave() {
  tooltip.value = null;
}

// ── Lifecycle ────────────────────────────────────────────────────────────

let resizeObserver = null;

onMounted(async () => {
  loadCode(props.code);
  if (container.value) {
    width.value = container.value.clientWidth || 900;
    resizeObserver = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect?.width;
      if (w && Math.abs(w - width.value) > 4) {
        width.value = w;
        scheduleRender();
      }
    });
    resizeObserver.observe(container.value);
  }
  try {
    if (document.fonts && document.fonts.load) {
      await Promise.allSettled([
        document.fonts.load("30px Bravura"),
        document.fonts.load("13px Academico"),
      ]);
    }
  } catch {
    // fall through, render anyway
  }
  fontsReady.value = true;
  await nextTick();
  scheduleRender();
});

onBeforeUnmount(() => {
  closeMenu();
  if (resizeObserver) resizeObserver.disconnect();
  if (renderTimer) cancelAnimationFrame(renderTimer);
});
</script>

<template>
  <div ref="container" class="ly-editor" tabindex="0" @keydown="onKeydown">
    <div class="toolbar" role="toolbar" aria-label="Notenbearbeitung" @click="refocusEditor">
      <div class="tool-group">
        <button
          type="button"
          class="tool"
          :disabled="!selectedToken || selectedToken.kind !== 'note'"
          title="Ton höher (↑)"
          @click="stepPitch(1)"
        >
          ↑
        </button>
        <button
          type="button"
          class="tool"
          :disabled="!selectedToken || selectedToken.kind !== 'note'"
          title="Ton tiefer (↓)"
          @click="stepPitch(-1)"
        >
          ↓
        </button>
        <button
          type="button"
          class="tool"
          :disabled="!selectedToken || selectedToken.kind !== 'note'"
          title="Erhöhen ♯ (Shift+↑)"
          @click="stepAccidental(1)"
        >
          ♯
        </button>
        <button
          type="button"
          class="tool"
          :disabled="!selectedToken || selectedToken.kind !== 'note'"
          title="Erniedrigen ♭ (Shift+↓)"
          @click="stepAccidental(-1)"
        >
          ♭
        </button>
      </div>
      <div class="tool-group">
        <button
          v-for="d in [1, 2, 4, 8, 16]"
          :key="d"
          type="button"
          class="tool"
          :class="{ active: selectedToken?.duration?.base === d }"
          :disabled="!selectedToken || selectedToken.kind === 'spacer'"
          :title="`${durationLabel({ base: d, dots: 0 })} (${d === 16 ? 6 : d})`"
          @click="setDuration(d)"
        >
          1/{{ d }}
        </button>
        <button
          type="button"
          class="tool"
          :class="{ active: selectedToken?.duration?.dots > 0 }"
          :disabled="!selectedToken"
          title="Punktierung (.)"
          @click="dot"
        >
          •
        </button>
      </div>
      <div class="tool-group">
        <button
          type="button"
          class="tool"
          :disabled="!currentMeasure()"
          title="Note einfügen (n)"
          @click="insert('note')"
        >
          + Note
        </button>
        <button
          type="button"
          class="tool"
          :disabled="!currentMeasure()"
          title="Pause einfügen (r)"
          @click="insert('rest')"
        >
          + Pause
        </button>
        <button
          type="button"
          class="tool"
          :disabled="
            !selectedToken || selectedToken.kind === 'spacer' || selectedToken.kind === 'mmrest'
          "
          title="Note ↔ Pause (t)"
          @click="restToggle"
        >
          Note ↔ Pause
        </button>
        <button
          type="button"
          class="tool danger"
          :disabled="!selectedToken"
          title="Löschen (Entf)"
          @click="remove"
        >
          Löschen
        </button>
      </div>
      <div class="tool-group">
        <button
          type="button"
          class="tool"
          :disabled="!canInsertBarline"
          title="Taktstrich nach der Note einfügen (b)"
          @click="barlineInsert"
        >
          Taktstrich +
        </button>
        <button
          type="button"
          class="tool"
          :disabled="!canRemoveBarline"
          title="Taktstrich am Taktende entfernen, Takte zusammenlegen (Shift+B)"
          @click="barlineRemove"
        >
          Taktstrich −
        </button>
      </div>
      <div class="tool-group layout-toggle" role="group" aria-label="Zeilenanordnung">
        <button
          type="button"
          class="tool"
          :class="{ active: layoutMode === 'auto' }"
          :aria-pressed="layoutMode === 'auto'"
          title="Takte nach verfügbarer Breite umbrechen"
          @click="setLayoutMode('auto')"
        >
          Automatisch
        </button>
        <button
          type="button"
          class="tool"
          :class="{ active: layoutMode === 'lilypond' }"
          :aria-pressed="layoutMode === 'lilypond'"
          title="Zeilen wie im LilyPond-Satz (Umbrüche aus dem Code)"
          @click="setLayoutMode('lilypond')"
        >
          Wie LilyPond
        </button>
        <button
          type="button"
          class="tool"
          :class="{ active: showSnippets && canShowSnippets }"
          :aria-pressed="showSnippets && canShowSnippets"
          :disabled="!canShowSnippets"
          title="Über jeder Zeile den Ausschnitt der Original-Zeile aus dem Scan zeigen (schaltet auf „Wie LilyPond“)"
          @click="toggleSnippets"
        >
          Original-Zeilen
        </button>
      </div>
      <div class="tool-group">
        <button
          ref="menuButton"
          type="button"
          class="tool"
          :disabled="!hasSelection"
          :aria-expanded="!!menu"
          aria-haspopup="menu"
          title="Aktionen für die Auswahl (Kontextmenü, auch Rechtsklick)"
          @click="openMenuFromButton"
        >
          Aktionen ▾
        </button>
      </div>
      <div class="tool-group">
        <button
          type="button"
          class="tool"
          :disabled="!history.length"
          title="Rückgängig (Strg+Z)"
          @click="undo"
        >
          ↶
        </button>
        <button
          type="button"
          class="tool"
          :disabled="!future.length"
          title="Wiederholen (Strg+Y)"
          @click="redo"
        >
          ↷
        </button>
        <button
          type="button"
          class="tool"
          :disabled="!isDirty"
          title="Ungespeicherte Änderungen verwerfen (zurück zur zuletzt gespeicherten Fassung)"
          @click="resetToOriginal"
        >
          Änderungen verwerfen
        </button>
      </div>
    </div>

    <div class="status">
      <span v-if="selectedInfo" class="status-sel">
        {{ selectedInfo }}
        <span v-if="selectedMeasureInfo" class="status-measure">· {{ selectedMeasureInfo }}</span>
      </span>
      <span v-else-if="selectedMeasureInfo" class="status-sel"
        >{{ selectedMeasureInfo
        }}<template v-if="!isRange">
          · {{ currentMeasure()?.events.length ? "ganzer Takt ausgewählt" : "leer" }}</template
        ></span
      >
      <span v-else class="status-hint"
        >Note, Taktstrich oder Taktnummer anklicken · Rechtsklick für Aktionen · Pfeiltasten, 1 2 4
        8 6, Punkt, n, r, t, b, Entf</span
      >
      <span class="status-measures">
        {{ measureSummary.total }} Takte
        <template v-if="measureSummary.bad">
          · <span class="status-bad">{{ measureSummary.bad }} mit falscher Taktfüllung</span>
        </template>
      </span>
    </div>

    <p v-if="parseError" class="editor-error">{{ parseError }}</p>
    <p v-else-if="renderError" class="editor-error">Darstellungsfehler: {{ renderError }}</p>
    <div v-if="!fontsReady && !parseError" class="editor-loading">Notenschrift wird geladen…</div>
    <div
      ref="host"
      class="score-host"
      :hidden="!!parseError"
      @pointermove="onPointerMove"
      @pointerleave="onPointerLeave"
      @contextmenu="onContextMenu"
    ></div>
    <div
      v-if="menu"
      class="context-menu"
      role="menu"
      :style="{ left: `${menu.x}px`, top: `${menu.y}px` }"
    >
      <template v-for="(item, i) in menuItems" :key="i">
        <div v-if="item.type === 'header'" class="menu-header">{{ item.label }}</div>
        <div v-else-if="item.type === 'sep'" class="menu-sep" role="separator"></div>
        <button
          v-else
          type="button"
          class="menu-item"
          :class="{ danger: item.danger, checked: item.checked }"
          :role="
            item.type === 'item'
              ? 'menuitem'
              : item.type === 'check'
                ? 'menuitemcheckbox'
                : 'menuitemradio'
          "
          :aria-checked="item.type === 'item' ? undefined : !!item.checked"
          :disabled="item.disabled"
          @click="runMenuItem(item)"
        >
          <span class="menu-mark">{{ item.checked ? "✓" : "" }}</span>
          {{ item.label }}
        </button>
      </template>
    </div>
    <div
      v-if="tooltip"
      class="measure-tooltip"
      role="tooltip"
      :style="{ left: `${tooltip.x}px`, top: `${tooltip.y}px` }"
    >
      <strong>{{ tooltip.title }}</strong>
      <div v-for="(line, i) in tooltip.lines" :key="i">{{ line }}</div>
    </div>
  </div>
</template>

<style scoped>
.ly-editor {
  outline: none;
  border-radius: var(--radius);
}

.ly-editor:focus-visible {
  box-shadow: 0 0 0 2px var(--color-primary-light);
}

.toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem 1rem;
  padding: 0.5rem 0;
  border-bottom: 1px solid var(--color-border);
}

.tool-group {
  display: flex;
  gap: 0.25rem;
}

.layout-toggle {
  margin-left: auto;
}

.tool {
  min-width: 44px;
  min-height: 40px;
  padding: 0 0.6rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  background: var(--color-bg-soft);
  color: var(--color-text);
  font-size: 0.85rem;
  font-variant-numeric: tabular-nums;
  cursor: pointer;
}

.tool:hover:not(:disabled) {
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.tool.active,
.tool.active:hover:not(:disabled) {
  background: var(--color-primary);
  border-color: var(--color-primary);
  color: var(--color-on-primary);
}

.tool.danger:hover:not(:disabled) {
  border-color: var(--color-danger);
  color: var(--color-danger);
}

.tool:disabled {
  opacity: 0.45;
  cursor: default;
}

.status {
  display: flex;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 0.5rem;
  padding: 0.4rem 0;
  font-size: 0.8rem;
  color: var(--color-muted);
}

.status-sel {
  color: var(--color-text);
  font-weight: 600;
}

.status-bad {
  color: var(--color-danger);
}

.status-measure {
  font-weight: 400;
  color: var(--color-muted);
}

.measure-tooltip {
  position: fixed;
  z-index: 1000;
  max-width: 260px;
  padding: 0.4rem 0.6rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  background: var(--color-bg);
  color: var(--color-text);
  box-shadow: var(--shadow-float);
  font-size: 0.8rem;
  line-height: 1.4;
  pointer-events: none;
}

.context-menu {
  position: fixed;
  z-index: 1001;
  min-width: 220px;
  max-height: calc(100vh - 16px);
  overflow-y: auto;
  padding: 0.3rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  background: var(--color-bg);
  box-shadow: var(--shadow-float);
}

.menu-header {
  padding: 0.5rem 0.6rem 0.2rem;
  font-size: 0.7rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--color-muted);
}

.menu-sep {
  height: 1px;
  margin: 0.3rem 0;
  background: var(--color-border);
}

.menu-item {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  width: 100%;
  min-height: 40px;
  padding: 0 0.6rem;
  border: none;
  border-radius: calc(var(--radius) - 2px);
  background: none;
  color: var(--color-text);
  font-size: 0.875rem;
  text-align: left;
  cursor: pointer;
}

.menu-item:hover:not(:disabled),
.menu-item:focus-visible {
  background: var(--color-bg-soft);
  outline: none;
}

.menu-item.checked {
  color: var(--color-primary);
  font-weight: 600;
}

.menu-item.danger {
  color: var(--color-danger);
}

.menu-item:disabled {
  opacity: 0.45;
  cursor: default;
}

.menu-mark {
  display: inline-block;
  width: 1em;
  font-size: 0.8rem;
}

.measure-tooltip strong {
  display: block;
  margin-bottom: 0.15rem;
}

.status-measures {
  font-variant-numeric: tabular-nums;
}

.editor-error {
  color: var(--color-danger);
  font-size: 0.85rem;
}

.editor-loading {
  padding: 2rem;
  text-align: center;
  color: var(--color-muted);
}

.score-host {
  overflow-x: auto;
  /* The modal sets --score-max-height in fullscreen so the score fills the screen */
  max-height: var(--score-max-height, 60vh);
  overflow-y: auto;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  background: var(--color-bg);
}

.score-host :deep(svg) {
  display: block;
}
</style>
