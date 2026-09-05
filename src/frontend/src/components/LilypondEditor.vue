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
  StaveText,
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
});
const emit = defineEmits(["update:code"]);

// ── State ────────────────────────────────────────────────────────────────

const host = ref(null);
const container = ref(null);
const doc = ref(null);
const measures = ref([]);
const parseError = ref(null);
const selected = ref(null); // token index
const selectedMeasure = ref(null); // measure index (for empty-measure inserts)
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
  if (m.percent !== null) lines.push(`Wiederholung ${m.percent}×`);
  if (m.copy) lines.push("Aus Vorlage übernommen");
  if (m.volta) lines.push(`Volta ${m.volta.count}`);
  return lines;
}

const selectedMeasureInfo = computed(() => {
  const m = currentMeasure();
  if (!m) return null;
  const hints = measureHints(m);
  return `${measureLabel(m)}${hints.length ? " · " + hints.join(" · ") : ""}`;
});

const measureSummary = computed(() => {
  const total = measures.value.length;
  const bad = measures.value.filter((m) => m.mismatch).length;
  return { total, bad };
});

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
    selected.value = null;
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
  emit("update:code", serializeDocument(normalized));
  scheduleRender();
}

function undo() {
  if (!history.value.length) return;
  future.value.push(serializeDocument(doc.value));
  const code = history.value.pop();
  loadCode(code);
  selected.value = null;
  emit("update:code", code);
  scheduleRender();
}

function redo() {
  if (!future.value.length) return;
  history.value.push(serializeDocument(doc.value));
  const code = future.value.pop();
  loadCode(code);
  selected.value = null;
  emit("update:code", code);
  scheduleRender();
}

function resetToOriginal() {
  if (!props.originalCode) return;
  history.value = [];
  future.value = [];
  loadCode(props.originalCode);
  selected.value = null;
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

function remove() {
  if (!selectedToken.value) return;
  const m = measureOfToken(selected.value);
  const next = deleteEvent(doc.value, selected.value);
  selectedMeasure.value = m ? m.index : null;
  commit(next, null);
}

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

function moveSelection(delta) {
  const order = measures.value.flatMap((m) => m.events);
  if (!order.length) return;
  if (selected.value === null) {
    selected.value = delta > 0 ? order[0] : order[order.length - 1];
  } else {
    const pos = order.indexOf(selected.value);
    const next = Math.min(order.length - 1, Math.max(0, pos + delta));
    selected.value = order[next];
  }
  selectedMeasure.value = null;
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
      moveSelection(-1);
      break;
    case "ArrowRight":
      e.preventDefault();
      moveSelection(1);
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
      remove();
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
    case "Escape":
      selected.value = null;
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

function measureWidth(m, tokens, isRowStart, prev) {
  let w = 34 + m.events.length * 30;
  if (isRowStart || m.showClef) w += 32;
  if (isRowStart || m.showKey) w += 12 + 8 * Math.abs(keyFlats(m.keyName, m.mode));
  if (m.showTime || !prev) w += 28;
  if (m.startBarline === "repeat-begin") w += 12;
  if (m.percent !== null) w += 24;
  return Math.max(w, 70);
}

const MIN_LILYPOND_SCALE = 0.55;

/**
 * Pack measures into rows. Returns { rows, width } where width is the
 * content width (may exceed availableWidth in "lilypond" mode, the host
 * then scrolls horizontally).
 */
function layoutRows(ms, tokens, availableWidth, mode) {
  const rows = [];
  let row = [];
  let rowWidth = 0;
  for (let i = 0; i < ms.length; i += 1) {
    const m = ms[i];
    const prev = i > 0 ? ms[i - 1] : null;
    const w = measureWidth(m, tokens, row.length === 0, prev);
    const overflow = mode === "auto" && rowWidth + w > availableWidth;
    if (row.length && (m.breakBefore || overflow)) {
      rows.push(row);
      row = [];
      rowWidth = 0;
    }
    const cellW = row.length === 0 ? measureWidth(m, tokens, true, prev) : w;
    row.push({ m, w: cellW });
    rowWidth += cellW;
  }
  if (row.length) rows.push(row);

  let contentWidth = availableWidth;
  rows.forEach((r, idx) => {
    const natural = r.reduce((sum, x) => sum + x.w, 0);
    let scale;
    if (mode === "lilypond") {
      // Fill the row like LilyPond does, but never squeeze below a legible size.
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

function render() {
  const el = host.value;
  if (!el) return;
  el.innerHTML = "";
  renderError.value = null;
  if (!doc.value || !fontsReady.value) return;

  const tokens = doc.value.tokens;
  const ms = measures.value;
  measureBoxes = [];
  tooltip.value = null;
  const availableWidth = Math.max(320, width.value - 2 * SIDE_PAD);
  const { rows, width: contentWidth } = layoutRows(ms, tokens, availableWidth, layoutMode.value);
  const totalHeight = TOP_PAD + rows.length * ROW_HEIGHT + 20;

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
  let y = TOP_PAD;

  rows.forEach((row, rowIdx) => {
    let x = SIDE_PAD;
    row.forEach((cell, cellIdx) => {
      const m = cell.m;
      const stave = new Stave(x, y, cell.w, { spaceAboveStaffLn: 3 });
      measureBoxes.push({ x, y, w: cell.w, h: ROW_HEIGHT, m });
      stave.setStyle({ strokeStyle: colorInk, fillStyle: colorInk });
      const isRowStart = cellIdx === 0;
      if (isRowStart || m.showClef) stave.addClef(m.clef);
      if (isRowStart || m.showKey) stave.addKeySignature(lilyKeyToVex(m.keyName, m.mode));
      if (m.showTime || (rowIdx === 0 && isRowStart))
        stave.addTimeSignature(`${m.time.beats}/${m.time.beatType}`);

      if (m.startBarline === "repeat-begin") stave.setBegBarType(Barline.type.REPEAT_BEGIN);
      const endMap = {
        single: Barline.type.SINGLE,
        double: Barline.type.DOUBLE,
        end: Barline.type.END,
        "repeat-begin": Barline.type.REPEAT_BEGIN,
        "repeat-end": Barline.type.REPEAT_END,
        "repeat-both": Barline.type.REPEAT_BOTH,
        none: Barline.type.NONE,
      };
      stave.setEndBarType(endMap[m.endBarline] ?? Barline.type.SINGLE);

      if (m.volta) {
        const vt = {
          begin: Volta.type.BEGIN,
          mid: Volta.type.MID,
          end: Volta.type.END,
          "begin-end": Volta.type.BEGIN_END,
        };
        stave.setVoltaType(
          vt[m.volta.position] || Volta.type.BEGIN,
          m.volta.position === "begin" || m.volta.position === "begin-end"
            ? `${m.volta.count}.`
            : "",
          -5,
        );
      }
      if (m.section) stave.setSection(m.section, 0, 0, 12, false);
      if (m.percent !== null) {
        const label = new StaveText(`${m.percent}×`, Modifier.Position.ABOVE, {
          shiftX: -8,
          shiftY: 14,
          justification: 3,
        });
        label.setFont("Academico", 11, "normal", "normal");
        stave.addModifier(label);
      }
      stave.setContext(ctx).draw();

      // Printed measure number, small and muted, at the top left of the measure
      ctx.save();
      ctx.setFont("Academico", 9, "normal", "normal");
      ctx.setFillStyle(colorNumber);
      ctx.fillText(String(m.number), x + 3, stave.getYForTopText(0) + 2);
      ctx.restore();

      // Notes
      const notes = [];
      const tokenForNote = [];
      let pendingDynamics = [];
      for (const ti of m.events) {
        const t = tokens[ti];
        if (t.kind === "spacer") {
          pendingDynamics.push(...extractDynamics(t.suffix));
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
        const isSel = ti === selected.value;
        const color = isSel ? colorSel : m.mismatch ? colorErr : m.copy ? colorCopy : colorInk;
        note.setStyle({ fillStyle: color, strokeStyle: color });
        if (typeof note.setStemStyle === "function") note.setStemStyle({ strokeStyle: color });
        notes.push(note);
        tokenForNote.push(ti);
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
          // Selection highlight: soft rounded box behind the whole note column
          const selIdx = tokenForNote.indexOf(selected.value);
          if (selIdx >= 0) {
            const bb = notes[selIdx].getBoundingBox();
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
        ctx.rect(x + 2, y + 20, cell.w - 4, 50, { fill: "transparent", stroke: "none" });
        ctx.closeGroup();
        if (g) {
          g.style.cursor = "pointer";
          g.dataset.measure = String(m.index);
        }
      }
      // Highlight background of the selected empty measure
      if (selectedMeasure.value === m.index && selected.value === null) {
        ctx.save();
        ctx.setFillStyle(colorSel);
        ctx.globalAlpha = 0.08;
        ctx.fillRect(x, y + 10, cell.w, 70);
        ctx.restore();
      }
      x += cell.w;
    });
    y += ROW_HEIGHT;
  });

  // Attach click handlers
  const svg = el.querySelector("svg");
  if (svg) {
    if (contentWidth > availableWidth) {
      svg.style.maxWidth = "none";
      svg.style.height = "auto";
    } else {
      svg.style.maxWidth = "100%";
      svg.style.height = "auto";
    }
    svg.addEventListener("pointerdown", (ev) => {
      const target = ev.target.closest("g.vf-stavenote, [id^='empty-']");
      if (!target) return;
      if (target.id.startsWith("empty-")) {
        selected.value = null;
        selectedMeasure.value = Number(target.dataset.measure);
        scheduleRender();
        return;
      }
      const id = target.id.slice(3);
      if (noteMap.has(id)) {
        selected.value = noteMap.get(id);
        selectedMeasure.value = null;
        container.value?.focus();
        scheduleRender();
      }
    });
    for (const id of noteMap.keys()) {
      const g = svg.querySelector(`#vf-${CSS.escape(id)}`);
      if (g) g.style.cursor = "pointer";
    }
  }
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
  const lines = box ? measureHints(box.m) : [];
  if (!box || !lines.length) {
    tooltip.value = null;
    return;
  }
  tooltip.value = {
    x: ev.clientX + 12,
    y: ev.clientY + 16,
    title: measureLabel(box.m),
    lines,
  };
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
  if (resizeObserver) resizeObserver.disconnect();
  if (renderTimer) cancelAnimationFrame(renderTimer);
});
</script>

<template>
  <div ref="container" class="ly-editor" tabindex="0" @keydown="onKeydown">
    <div class="toolbar" role="toolbar" aria-label="Notenbearbeitung">
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
          title="Alle Änderungen verwerfen"
          @click="resetToOriginal"
        >
          Zurücksetzen
        </button>
      </div>
    </div>

    <div class="status">
      <span v-if="selectedInfo" class="status-sel">
        {{ selectedInfo }}
        <span v-if="selectedMeasureInfo" class="status-measure">· {{ selectedMeasureInfo }}</span>
      </span>
      <span v-else-if="selectedMeasureInfo" class="status-sel"
        >{{ selectedMeasureInfo }} (leer)</span
      >
      <span v-else class="status-hint"
        >Note anklicken, dann Pfeiltasten, Ziffern 1 2 4 8 6, Punkt, n, r, t, Entf</span
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
    ></div>
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
