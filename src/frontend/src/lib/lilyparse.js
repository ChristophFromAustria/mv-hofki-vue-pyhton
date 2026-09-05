/**
 * Parser, model and serializer for the LilyPond dialect emitted by the
 * backend generator (lilypond_generator.py).
 *
 * The goal is not a general LilyPond parser. The staff body produced by
 * the generator uses a small, predictable vocabulary: absolute Dutch pitch
 * names, plain durations, rests, a handful of commands (\clef, \key, \time,
 * \bar, \set Timing.measureLength, \repeat, \alternative, \volta, \break,
 * \markErr …). Everything the tokenizer does not understand is kept as an
 * opaque token so that serialization stays faithful to the source.
 *
 * The model is a flat token list. Measures are views onto that list
 * (token index ranges), so editing a note means editing one token and
 * re-serializing the whole list.
 */

// ── Fractions (integer maths for durations) ──────────────────────────────

function gcd(a, b) {
  a = Math.abs(a);
  b = Math.abs(b);
  while (b) [a, b] = [b, a % b];
  return a || 1;
}

export function frac(n, d = 1) {
  if (d < 0) {
    n = -n;
    d = -d;
  }
  const g = gcd(n, d);
  return { n: n / g, d: d / g };
}

export function fracAdd(a, b) {
  return frac(a.n * b.d + b.n * a.d, a.d * b.d);
}

export function fracMul(a, b) {
  return frac(a.n * b.n, a.d * b.d);
}

export function fracEq(a, b) {
  return a.n * b.d === b.n * a.d;
}

export function fracCmp(a, b) {
  return a.n * b.d - b.n * a.d;
}

export function fracToString(f) {
  return f.d === 1 ? `${f.n}` : `${f.n}/${f.d}`;
}

// ── Pitch helpers ────────────────────────────────────────────────────────

export const LETTERS = ["c", "d", "e", "f", "g", "a", "b"];

const FLAT_ORDER = ["b", "e", "a", "d", "g", "c", "f"];
const SHARP_ORDER = ["f", "c", "g", "d", "a", "e", "b"];

/** LilyPond major key name → number of flats (negative = sharps). */
const MAJOR_FLATS = {
  c: 0,
  f: 1,
  bes: 2,
  es: 3,
  as: 4,
  des: 5,
  ges: 6,
  ces: 7,
  g: -1,
  d: -2,
  a: -3,
  e: -4,
  b: -5,
  fis: -6,
  cis: -7,
};
const MINOR_FLATS = {
  a: 0,
  d: 1,
  g: 2,
  c: 3,
  f: 4,
  bes: 5,
  es: 6,
  as: 7,
  e: -1,
  b: -2,
  fis: -3,
  cis: -4,
  gis: -5,
  dis: -6,
  ais: -7,
};

export function keyFlats(keyName, mode = "major") {
  const table = mode === "minor" ? MINOR_FLATS : MAJOR_FLATS;
  return table[keyName] ?? 0;
}

/** Alteration (−1/0/+1) a letter gets from the key signature. */
export function keyAlteration(letter, flats) {
  if (flats > 0) return FLAT_ORDER.slice(0, Math.min(flats, 7)).includes(letter) ? -1 : 0;
  if (flats < 0) return SHARP_ORDER.slice(0, Math.min(-flats, 7)).includes(letter) ? 1 : 0;
  return 0;
}

const ACC_FROM_SUFFIX = { "": 0, es: -1, s: -1, eses: -2, is: 1, isis: 2 };
const SUFFIX_FROM_ACC = { 0: "", "-1": "es", "-2": "eses", 1: "is", 2: "isis" };

const PITCH_RE = /^([a-g])(eses|isis|es|is|s)?([',]*)$/;

/** "bes," → { letter: "b", alter: -1, octave: 2 } (octave 4 = middle C). */
export function parsePitch(text) {
  const m = PITCH_RE.exec(text);
  if (!m) return null;
  const letter = m[1];
  let suffix = m[2] || "";
  // "as"/"es" are written without the leading e: letter a/e + "s"
  if (suffix === "s" && !(letter === "a" || letter === "e")) return null;
  const alter = ACC_FROM_SUFFIX[suffix] ?? 0;
  const marks = m[3] || "";
  const ups = (marks.match(/'/g) || []).length;
  const downs = (marks.match(/,/g) || []).length;
  return { letter, alter, octave: 3 + ups - downs };
}

export function pitchToLily({ letter, alter, octave }) {
  let name;
  if (alter === -1 && (letter === "a" || letter === "e")) name = letter + "s";
  else if (alter === -2 && (letter === "a" || letter === "e")) name = letter + "ses";
  else name = letter + (SUFFIX_FROM_ACC[alter] ?? "");
  const rel = octave - 3;
  const marks = rel > 0 ? "'".repeat(rel) : ",".repeat(-rel);
  return name + marks;
}

/** Diatonic index (letter + octave) for stepping up/down. */
export function pitchIndex(p) {
  return p.octave * 7 + LETTERS.indexOf(p.letter);
}

export function pitchFromIndex(index, alter = 0) {
  const octave = Math.floor(index / 7);
  const letter = LETTERS[((index % 7) + 7) % 7];
  return { letter, alter, octave };
}

// ── Durations ────────────────────────────────────────────────────────────

const DURATION_RE = /^(1|2|4|8|16|32|64|128)(\.*)(?:\*(\d+)(?:\/(\d+))?)?$/;

export function parseDuration(text) {
  const m = DURATION_RE.exec(text);
  if (!m) return null;
  const base = Number(m[1]);
  const dots = m[2].length;
  const mult = m[3] ? frac(Number(m[3]), m[4] ? Number(m[4]) : 1) : null;
  return { base, dots, mult };
}

export function durationToLily({ base, dots, mult }) {
  let s = `${base}${".".repeat(dots)}`;
  if (mult) s += `*${fracToString(mult)}`;
  return s;
}

export function durationLength({ base, dots, mult }) {
  // 1/base * (2 - 1/2^dots)
  let len = frac(2 ** (dots + 1) - 1, base * 2 ** dots);
  if (mult) len = fracMul(len, mult);
  return len;
}

/** Decompose a length into duration tokens (3/4 → ["2."]), longest first. */
export function durationTokensFor(length) {
  const out = [];
  let rest = length;
  const candidates = [];
  for (const base of [1, 2, 4, 8, 16, 32]) {
    for (const dots of [2, 1, 0]) candidates.push({ base, dots, mult: null });
  }
  candidates.sort((a, b) => fracCmp(durationLength(b), durationLength(a)));
  let guard = 0;
  while (rest.n > 0 && guard++ < 16) {
    const c = candidates.find((cand) => fracCmp(durationLength(cand), rest) <= 0);
    if (!c) break;
    out.push(c);
    rest = fracAdd(rest, frac(-durationLength(c).n, durationLength(c).d));
  }
  return out;
}

// ── Tokenizer ────────────────────────────────────────────────────────────

let uidCounter = 0;
/** Stable identity for a token that survives cloning and re-indexing. */
export function nextUid() {
  uidCounter += 1;
  return uidCounter;
}

const PITCH_SRC = "[a-g](?:eses|isis|es|is|s)?[',]*";
const DUR_SRC = "(?:1|2|4|8|16|32|64|128)\\.*(?:\\*\\d+(?:/\\d+)?)?";
// Post-fix material on an event: articulations, dynamics, hairpins,
// fingering-like "-x", and _\markup { … } / ^\markup { … } blocks.
const SUFFIX_PIECE_RE = /^(?:-[>.^_+-]|-\\[a-zA-Z]+|\\[<>!]|\\[a-zA-Z]+(?![a-zA-Z]))/;

const EVENT_RE = new RegExp(
  `^(?:(<>)|(<(?:\\s*${PITCH_SRC})+\\s*>)|(${PITCH_SRC})|(r|R|s))(${DUR_SRC})?`,
);

function readBalanced(src, start) {
  // src[start] must be "{"; returns index after matching "}"
  let depth = 0;
  let i = start;
  let inString = false;
  while (i < src.length) {
    const ch = src[i];
    if (inString) {
      if (ch === "\\") i += 1;
      else if (ch === '"') inString = false;
    } else if (ch === '"') inString = true;
    else if (ch === "{") depth += 1;
    else if (ch === "}") {
      depth -= 1;
      if (depth === 0) return i + 1;
    }
    i += 1;
  }
  return src.length;
}

function readString(src, start) {
  // src[start] === '"'
  let i = start + 1;
  while (i < src.length) {
    if (src[i] === "\\") i += 2;
    else if (src[i] === '"') return i + 1;
    else i += 1;
  }
  return src.length;
}

function readSuffix(src, start) {
  let i = start;
  for (;;) {
    const rest = src.slice(i);
    const m = SUFFIX_PIECE_RE.exec(rest);
    if (m) {
      i += m[0].length;
      continue;
    }
    const mk = /^[_^-]?\\markup\s*\{/.exec(rest);
    if (mk) {
      const braceAt = i + mk[0].length - 1;
      i = readBalanced(src, braceAt);
      continue;
    }
    break;
  }
  return i;
}

function makeEventToken(raw) {
  const m = EVENT_RE.exec(raw);
  if (!m) return null;
  const durText = m[5] || "";
  const suffix = raw.slice(m[0].length);
  const tok = { type: "event", raw, ws: "", suffix };
  if (m[1]) {
    tok.kind = "spacer";
    tok.pitches = [];
    tok.duration = null;
  } else if (m[2]) {
    tok.kind = "note";
    tok.pitches = m[2].slice(1, -1).trim().split(/\s+/).map(parsePitch).filter(Boolean);
    tok.duration = parseDuration(durText);
  } else if (m[3]) {
    tok.kind = "note";
    tok.pitches = [parsePitch(m[3])];
    tok.duration = parseDuration(durText);
  } else {
    tok.kind = m[4] === "R" ? "mmrest" : m[4] === "s" ? "skip" : "rest";
    tok.pitches = [];
    tok.duration = parseDuration(durText);
  }
  return tok;
}

/** Rebuild the raw text of an event token from its parsed fields. */
export function eventToLily(tok) {
  let body;
  if (tok.kind === "spacer") body = "<>";
  else if (tok.kind === "rest") body = "r";
  else if (tok.kind === "mmrest") body = "R";
  else if (tok.kind === "skip") body = "s";
  else if (tok.pitches.length === 1) body = pitchToLily(tok.pitches[0]);
  else body = `<${tok.pitches.map(pitchToLily).join(" ")}>`;
  if (tok.duration) body += durationToLily(tok.duration);
  return body + (tok.suffix || "");
}

const WORD_ARG_COMMANDS = new Set(["\\clef"]);

/**
 * Tokenize a staff body. Each token carries the whitespace that preceded it
 * (`ws`) so that `serializeTokens` reproduces the input exactly.
 */
export function tokenize(src) {
  const tokens = [];
  let i = 0;
  const n = src.length;

  const push = (type, raw, ws, extra = {}) => {
    tokens.push({ type, raw, ws, uid: nextUid(), ...extra });
  };

  while (i < n) {
    const wsStart = i;
    while (i < n && /\s/.test(src[i])) i += 1;
    const ws = src.slice(wsStart, i);
    if (i >= n) {
      if (ws) push("ws", "", ws);
      break;
    }
    const ch = src[i];
    const rest = src.slice(i);

    if (ch === "%") {
      const end = src.indexOf("\n", i);
      const stop = end === -1 ? n : end;
      push("comment", src.slice(i, stop), ws);
      i = stop;
      continue;
    }
    if (ch === "{" || ch === "}") {
      push(ch === "{" ? "open" : "close", ch, ws);
      i += 1;
      continue;
    }
    if (ch === "|") {
      push("bar", "|", ws);
      i += 1;
      continue;
    }
    if (ch === '"') {
      const end = readString(src, i);
      push("string", src.slice(i, end), ws);
      i = end;
      continue;
    }
    if (ch === "#") {
      if (rest.startsWith("#(")) {
        // scheme expression: balance parentheses
        let depth = 0;
        let j = i + 1;
        while (j < n) {
          if (src[j] === "(") depth += 1;
          else if (src[j] === ")") {
            depth -= 1;
            if (depth === 0) {
              j += 1;
              break;
            }
          }
          j += 1;
        }
        push("scheme", src.slice(i, j), ws);
        i = j;
        continue;
      }
      const m = /^#[#\w.-]*/.exec(rest);
      push("scheme", m[0], ws);
      i += m[0].length;
      continue;
    }
    if (ch === "\\") {
      const m = /^\\[a-zA-Z]+/.exec(rest);
      if (!m) {
        push("other", ch, ws);
        i += 1;
        continue;
      }
      const cmd = m[0];
      let j = i + cmd.length;
      if (cmd === "\\bar") {
        const s = /^\s*"(?:[^"\\]|\\.)*"/.exec(src.slice(j));
        if (s) {
          const raw = src.slice(i, j + s[0].length);
          push("barline", raw, ws, { barType: s[0].trim().slice(1, -1) });
          i = j + s[0].length;
          continue;
        }
      } else if (WORD_ARG_COMMANDS.has(cmd)) {
        const w = /^\s+([a-zA-Z"][\w"^_]*)/.exec(src.slice(j));
        if (w) {
          push("clef", src.slice(i, j + w[0].length), ws, { clef: w[1].replace(/"/g, "") });
          i = j + w[0].length;
          continue;
        }
      } else if (cmd === "\\key") {
        const k = /^\s+([a-g](?:eses|isis|es|is|s)?)\s*(\\major|\\minor)/.exec(src.slice(j));
        if (k) {
          push("key", src.slice(i, j + k[0].length), ws, {
            keyName: k[1],
            mode: k[2] === "\\minor" ? "minor" : "major",
          });
          i = j + k[0].length;
          continue;
        }
      } else if (cmd === "\\time") {
        const t = /^\s+(\d+)\/(\d+)/.exec(src.slice(j));
        if (t) {
          push("time", src.slice(i, j + t[0].length), ws, {
            beats: Number(t[1]),
            beatType: Number(t[2]),
          });
          i = j + t[0].length;
          continue;
        }
      } else if (cmd === "\\set" || cmd === "\\unset") {
        const s = /^\s+([\w.]+)(\s*=\s*)?/.exec(src.slice(j));
        if (s) {
          j += s[0].length;
          let valueRaw = "";
          if (s[2]) {
            const r2 = src.slice(j);
            let vm;
            if (r2.startsWith("#(")) {
              let depth = 0;
              let k = 1;
              while (k < r2.length) {
                if (r2[k] === "(") depth += 1;
                else if (r2[k] === ")") {
                  depth -= 1;
                  if (depth === 0) {
                    k += 1;
                    break;
                  }
                }
                k += 1;
              }
              valueRaw = r2.slice(0, k);
            } else if ((vm = /^(?:##[tf]|"(?:[^"\\]|\\.)*"|-?\d+(?:\.\d+)?|#[\w.-]+)/.exec(r2))) {
              valueRaw = vm[0];
            }
            j += valueRaw.length;
          }
          const extra = { property: s[1], valueRaw };
          const mom = /ly:make-moment\s+(\d+)(?:\/(\d+))?/.exec(valueRaw);
          if (s[1] === "Timing.measureLength" && mom) {
            extra.measureLength = frac(Number(mom[1]), mom[2] ? Number(mom[2]) : 1);
          }
          push("set", src.slice(i, j), ws, extra);
          i = j;
          continue;
        }
      } else if (cmd === "\\repeat") {
        const r = /^\s+(percent|volta|unfold)\s+(\d+)/.exec(src.slice(j));
        if (r) {
          push("repeat", src.slice(i, j + r[0].length), ws, {
            repeatKind: r[1],
            count: Number(r[2]),
          });
          i = j + r[0].length;
          continue;
        }
      } else if (cmd === "\\volta") {
        const v = /^\s+(\d+)/.exec(src.slice(j));
        if (v) {
          push("volta", src.slice(i, j + v[0].length), ws, { count: Number(v[1]) });
          i = j + v[0].length;
          continue;
        }
      } else if (cmd === "\\pseudoIndent" || cmd === "\\pseudoIndents") {
        // \pseudoIndent \markuplist { ... } N [M]
        const mk = /^\s*\\markuplist\s*\{/.exec(src.slice(j));
        let k = j;
        if (mk) k = readBalanced(src, j + mk[0].length - 1);
        const nums = /^(?:\s+-?\d+(?:\.\d+)?){1,2}/.exec(src.slice(k));
        if (nums) k += nums[0].length;
        const raw = src.slice(i, k);
        const label = /"((?:[^"\\]|\\.)*)"/.exec(raw);
        push("section", raw, ws, { label: label ? label[1] : "" });
        i = k;
        continue;
      } else if (cmd === "\\mark") {
        const mk = /^\s*\\markup\s*\{/.exec(src.slice(j));
        if (mk) {
          const k = readBalanced(src, j + mk[0].length - 1);
          const raw = src.slice(i, k);
          const label = /"((?:[^"\\]|\\.)*)"/.exec(raw);
          push("section", raw, ws, { label: label ? label[1] : "" });
          i = k;
          continue;
        }
      } else if (cmd === "\\tempo") {
        const t = /^\s+(?:"(?:[^"\\]|\\.)*"\s*)?(?:\d+\.*\s*=\s*\d+)?/.exec(src.slice(j));
        if (t) {
          push("command", src.slice(i, j + t[0].length), ws, { command: cmd });
          i = j + t[0].length;
          continue;
        }
      }
      push("command", cmd, ws, { command: cmd });
      i = j;
      continue;
    }
    if (ch === "<" || /[a-gRrs]/.test(ch)) {
      const m = EVENT_RE.exec(rest);
      // A bare letter followed by more letters is a word, not a pitch.
      const wordish = m && !m[1] && !m[2] && /^[a-zA-Z]/.test(rest.slice(m[0].length));
      if (m && !wordish) {
        const end = readSuffix(src, i + m[0].length);
        const tok = makeEventToken(src.slice(i, end));
        if (tok) {
          tok.ws = ws;
          tok.uid = nextUid();
          tokens.push(tok);
          i = end;
          continue;
        }
      }
    }
    const m = /^[^\s{}|"\\%]+/.exec(rest);
    const raw = m ? m[0] : ch;
    push("other", raw, ws);
    i += raw.length;
  }
  return tokens;
}

export function serializeTokens(tokens) {
  let out = "";
  for (const t of tokens) {
    out += t.ws + (t.type === "event" ? eventToLily(t) : t.raw);
  }
  return out;
}

// ── Document ─────────────────────────────────────────────────────────────

function findStaffBody(code) {
  const m = /\\new\s+Staff\s*(?:=\s*"[^"]*"\s*)?(?:\\with\s*\{[^}]*\}\s*)?\{/.exec(code);
  if (!m) return null;
  const open = m.index + m[0].length - 1;
  const end = readBalanced(code, open);
  return { start: open + 1, end: end - 1 };
}

function parseHeader(code) {
  const header = {};
  const m = /\\header\s*\{/.exec(code);
  if (!m) return header;
  const end = readBalanced(code, m.index + m[0].length - 1);
  const body = code.slice(m.index + m[0].length, end - 1);
  for (const line of body.matchAll(/(\w+)\s*=\s*"((?:[^"\\]|\\.)*)"/g)) {
    header[line[1]] = line[2].replace(/\\(.)/g, "$1");
  }
  return header;
}

/**
 * Parse a full LilyPond file into a document: header fields, the staff
 * body token list and the code around it.
 */
export function parseLilypond(code) {
  const body = findStaffBody(code);
  if (!body) {
    return { ok: false, error: "Kein \\new Staff { … } Block gefunden.", tokens: [], header: {} };
  }
  const tokens = tokenize(code.slice(body.start, body.end));
  return {
    ok: true,
    header: parseHeader(code),
    prefix: code.slice(0, body.start),
    suffix: code.slice(body.end),
    tokens,
  };
}

export function serializeDocument(doc) {
  return doc.prefix + serializeTokens(doc.tokens) + doc.suffix;
}

// ── Measures ─────────────────────────────────────────────────────────────

const BAR_TYPE_MAP = {
  "|": "single",
  "||": "double",
  "|.": "end",
  ".|:": "repeat-begin",
  ":|.": "repeat-end",
  ":|.|:": "repeat-both",
  ".|": "thick",
  "": "none",
};

/**
 * Build measure views from the token list. Each measure references token
 * indices and carries the notation state (clef, key, time) at its start.
 */
export function buildMeasures(tokens) {
  const measures = [];
  let clef = "treble";
  let keyName = "c";
  let mode = "major";
  let time = { beats: 4, beatType: 4 };
  let timeLen = frac(1, 1);
  let effectiveLen = timeLen;
  let inErr = false;
  let inCopy = false;
  let pendingRepeatBegin = false;
  let pendingBreak = false;
  let pendingSection = null;
  let pendingVolta = null;
  let voltaOpen = null; // { count, measures: [] }
  let afterRepeatClose = false;
  let percentPending = null;
  // brace stack entries: kind
  const stack = [];

  let cur = null;
  const startMeasure = (tokenStart) => {
    cur = {
      index: measures.length,
      tokenStart,
      tokenEnd: tokenStart,
      events: [],
      clef,
      keyName,
      mode,
      time: { ...time },
      timeLen,
      expectedLen: effectiveLen,
      explicitLength: null,
      startBarline: pendingRepeatBegin ? "repeat-begin" : null,
      endBarline: "single",
      endToken: null,
      breakBefore: pendingBreak,
      section: pendingSection,
      percent: null,
      volta: pendingVolta,
      showClef: false,
      showKey: false,
      showTime: false,
      err: false,
      copy: inCopy,
    };
    pendingRepeatBegin = false;
    pendingBreak = false;
    pendingSection = null;
    pendingVolta = voltaOpen ? { count: voltaOpen.count, position: "mid" } : null;
  };

  const finishMeasure = (endIdx, endBarline, endToken) => {
    if (!cur) return;
    cur.tokenEnd = endIdx + 1;
    cur.endBarline = endBarline;
    cur.endToken = endToken;
    if (afterRepeatClose && !voltaOpen) {
      afterRepeatClose = false;
    }
    if (voltaOpen) voltaOpen.measures.push(cur);
    measures.push(cur);
    cur = null;
  };

  for (let i = 0; i < tokens.length; i += 1) {
    const t = tokens[i];
    if (!cur) startMeasure(i);
    cur.tokenEnd = i + 1;

    switch (t.type) {
      case "clef":
        clef = t.clef;
        cur.clef = clef;
        cur.showClef = true;
        break;
      case "key":
        keyName = t.keyName;
        mode = t.mode;
        cur.keyName = keyName;
        cur.mode = mode;
        cur.showKey = true;
        break;
      case "time":
        time = { beats: t.beats, beatType: t.beatType };
        timeLen = frac(t.beats, t.beatType);
        effectiveLen = timeLen;
        cur.time = { ...time };
        cur.timeLen = timeLen;
        cur.expectedLen = effectiveLen;
        cur.showTime = true;
        break;
      case "set":
        if (t.measureLength) {
          effectiveLen = t.measureLength;
          cur.expectedLen = effectiveLen;
          cur.explicitLength = i;
        }
        break;
      case "command":
        if (t.command === "\\markErr") inErr = true;
        else if (t.command === "\\unmarkErr") inErr = false;
        else if (t.command === "\\markCopy") {
          inCopy = true;
          cur.copy = true;
        } else if (t.command === "\\unmarkCopy") inCopy = false;
        else if (t.command === "\\break") {
          if (cur.events.length === 0) cur.breakBefore = true;
          else pendingBreak = true;
        } else if (t.command === "\\alternative") {
          stack.push({ kind: "alternative-pending" });
        }
        break;
      case "section":
        cur.section = t.label;
        break;
      case "repeat":
        if (t.repeatKind === "percent") percentPending = t.count;
        else if (t.repeatKind === "volta") {
          pendingRepeatBegin = true;
          cur.startBarline = "repeat-begin";
          stack.push({ kind: "repeat-volta-pending", count: t.count });
        }
        break;
      case "volta":
        if (stack.length && stack[stack.length - 1].kind === "alternative") {
          stack.push({ kind: "volta-pending", count: t.count });
        }
        break;
      case "open": {
        const top = stack[stack.length - 1];
        if (percentPending !== null) {
          cur.percent = percentPending;
          percentPending = null;
          stack.push({ kind: "percent" });
        } else if (top && top.kind === "repeat-volta-pending") {
          stack.pop();
          stack.push({ kind: "repeat-volta", count: top.count });
        } else if (top && top.kind === "alternative-pending") {
          stack.pop();
          stack.push({ kind: "alternative" });
        } else if (top && top.kind === "volta-pending") {
          stack.pop();
          stack.push({ kind: "volta", count: top.count });
          voltaOpen = { count: top.count, measures: [] };
          cur.volta = { count: top.count, position: "begin" };
        } else {
          stack.push({ kind: "block" });
        }
        break;
      }
      case "close": {
        const top = stack.pop();
        if (top && top.kind === "repeat-volta") {
          // Repeat end bar goes on the last measure of the body unless an
          // \alternative follows (then on the first alternative's end).
          const next = tokens.slice(i + 1).find((x) => x.type !== "ws" && x.type !== "comment");
          const last = measures[measures.length - 1];
          if (!(next && next.type === "command" && next.command === "\\alternative") && last) {
            if (last.endBarline === "single") last.endBarline = "repeat-end";
          } else {
            afterRepeatClose = true;
          }
        } else if (top && top.kind === "volta") {
          if (voltaOpen) {
            const ms = voltaOpen.measures;
            if (cur && cur.events.length && !ms.includes(cur)) ms.push(cur);
            if (ms.length) {
              const lastM = ms[ms.length - 1];
              lastM.volta = {
                count: voltaOpen.count,
                position: ms.length === 1 ? "begin-end" : "end",
              };
              if (afterRepeatClose && voltaOpen.count === 1 && lastM.endBarline === "single") {
                lastM.endBarline = "repeat-end";
              }
            }
          }
          voltaOpen = null;
          pendingVolta = null;
        } else if (top && top.kind === "alternative") {
          afterRepeatClose = false;
        }
        break;
      }
      case "event":
        if (t.kind === "skip") break;
        cur.events.push(i);
        if (inErr) cur.err = true;
        break;
      case "bar":
        finishMeasure(i, "single", i);
        break;
      case "barline":
        finishMeasure(i, BAR_TYPE_MAP[t.barType] || "single", i);
        break;
      default:
        break;
    }
  }
  if (cur) {
    if (cur.events.length) {
      finishMeasure(tokens.length - 1, "none", null);
    } else if (measures.length) {
      // trailing structural tokens belong to the last measure
      measures[measures.length - 1].tokenEnd = tokens.length;
    }
  }

  // Derived values
  for (const m of measures) {
    m.actualLen = measureActualLength(tokens, m);
    m.mismatch =
      m.percent === null && !isMmrestMeasure(tokens, m) && !fracEq(m.actualLen, m.timeLen);
  }
  return measures;
}

function isMmrestMeasure(tokens, m) {
  return m.events.some((i) => tokens[i].kind === "mmrest");
}

export function measureActualLength(tokens, m) {
  let total = frac(0, 1);
  for (const i of m.events) {
    const t = tokens[i];
    if (!t.duration || t.kind === "spacer") continue;
    total = fracAdd(total, durationLength(t.duration));
  }
  return total;
}

// ── Editing ──────────────────────────────────────────────────────────────

function cloneTokens(tokens) {
  return tokens.map((t) => ({
    ...t,
    pitches: t.pitches ? t.pitches.map((p) => ({ ...p })) : t.pitches,
    duration: t.duration
      ? { ...t.duration, mult: t.duration.mult ? { ...t.duration.mult } : null }
      : t.duration,
  }));
}

/** Key/mode in effect for a token index (for accidental defaults). */
export function keyAtToken(measures, tokenIndex) {
  const m = measures.find((mm) => tokenIndex >= mm.tokenStart && tokenIndex < mm.tokenEnd);
  return m ? keyFlats(m.keyName, m.mode) : 0;
}

/** Move every pitch of the event by `steps` diatonic steps (accidental follows the key). */
export function transposeEvent(doc, measures, tokenIndex, steps) {
  const tokens = cloneTokens(doc.tokens);
  const t = tokens[tokenIndex];
  if (!t || t.type !== "event" || t.kind !== "note") return doc;
  const flats = keyAtToken(measures, tokenIndex);
  t.pitches = t.pitches.map((p) => {
    const np = pitchFromIndex(pitchIndex(p) + steps);
    np.alter = keyAlteration(np.letter, flats);
    return np;
  });
  return { ...doc, tokens };
}

/** Alter the accidental of every pitch (delta ±1, clamped to ±2). */
export function alterEvent(doc, tokenIndex, delta) {
  const tokens = cloneTokens(doc.tokens);
  const t = tokens[tokenIndex];
  if (!t || t.type !== "event" || t.kind !== "note") return doc;
  t.pitches = t.pitches.map((p) => ({ ...p, alter: Math.max(-2, Math.min(2, p.alter + delta)) }));
  return { ...doc, tokens };
}

export function setEventDuration(doc, tokenIndex, base, dots = null) {
  const tokens = cloneTokens(doc.tokens);
  const t = tokens[tokenIndex];
  if (!t || t.type !== "event" || t.kind === "spacer") return doc;
  const prev = t.duration || { base: 4, dots: 0, mult: null };
  t.duration = {
    base,
    dots: dots === null ? prev.dots : dots,
    mult: t.kind === "mmrest" ? prev.mult : null,
  };
  return { ...doc, tokens };
}

export function toggleDot(doc, tokenIndex) {
  const tokens = cloneTokens(doc.tokens);
  const t = tokens[tokenIndex];
  if (!t || t.type !== "event" || !t.duration) return doc;
  t.duration = { ...t.duration, dots: t.duration.dots ? 0 : 1 };
  return { ...doc, tokens };
}

/** Note ↔ rest. A rest turned into a note gets the given pitch. */
export function toggleRest(doc, tokenIndex, pitch = { letter: "c", alter: 0, octave: 4 }) {
  const tokens = cloneTokens(doc.tokens);
  const t = tokens[tokenIndex];
  if (!t || t.type !== "event" || t.kind === "spacer" || t.kind === "mmrest") return doc;
  if (t.kind === "note") {
    t.kind = "rest";
    t.pitches = [];
    // articulations make no sense on rests; keep dynamics/hairpins
    t.suffix = (t.suffix || "").replace(/-[>.^_+-]|-\\[a-zA-Z]+/g, "");
  } else {
    t.kind = "note";
    t.pitches = [{ ...pitch }];
  }
  return { ...doc, tokens };
}

export function deleteEvent(doc, tokenIndex) {
  const tokens = cloneTokens(doc.tokens);
  const t = tokens[tokenIndex];
  if (!t || t.type !== "event") return doc;
  tokens.splice(tokenIndex, 1);
  // keep a single space between neighbours
  if (tokens[tokenIndex] && tokens[tokenIndex].ws === "") tokens[tokenIndex].ws = " ";
  return { ...doc, tokens };
}

/**
 * Insert a new event after `afterTokenIndex`, or at the start of the
 * measure `measure` when afterTokenIndex is null.
 * Returns { doc, tokenIndex } of the inserted token.
 */
export function insertEvent(doc, measure, afterTokenIndex, event) {
  const tokens = cloneTokens(doc.tokens);
  const tok = {
    type: "event",
    uid: nextUid(),
    ws: " ",
    raw: "",
    kind: event.kind,
    pitches: (event.pitches || []).map((p) => ({ ...p })),
    duration: event.duration ? { ...event.duration } : { base: 4, dots: 0, mult: null },
    suffix: "",
  };
  let at;
  if (afterTokenIndex !== null && afterTokenIndex !== undefined) {
    at = afterTokenIndex + 1;
  } else if (measure.events.length) {
    at = measure.events[0];
  } else if (measure.endToken !== null) {
    at = measure.endToken;
  } else {
    at = measure.tokenEnd;
  }
  tokens.splice(at, 0, tok);
  return { doc: { ...doc, tokens }, tokenIndex: at };
}

// ── Normalization (measureLength / markErr bookkeeping) ──────────────────

const MOMENT = (f) => `\\set Timing.measureLength = #(ly:make-moment ${f.n}/${f.d})`;

/**
 * Re-derive `\set Timing.measureLength` and `\markErr … \unmarkErr` for
 * every plain measure, mirroring the generator's rules: a measure whose
 * content differs from the effective length gets an explicit length and,
 * when it differs from the time signature, the red error marking.
 * Percent repeats and multi-measure rests are left untouched.
 */
export function normalizeDocument(doc) {
  const tokens = cloneTokens(doc.tokens);
  const measures = buildMeasures(tokens);
  let effective = null;
  let timeLen = null;

  const plan = [];
  for (const m of measures) {
    if (timeLen === null || !fracEq(timeLen, m.timeLen)) {
      timeLen = m.timeLen;
      effective = timeLen;
    }
    const isPlain = m.percent === null && !isMmrestMeasure(tokens, m) && m.events.length > 0;
    const spacerOnly = m.events.every((i) => tokens[i].kind === "spacer");
    if (!isPlain || spacerOnly) {
      if (m.explicitLength !== null) effective = tokens[m.explicitLength].measureLength;
      continue;
    }
    const needed = m.actualLen;
    plan.push({
      m,
      needsSet: !fracEq(needed, effective),
      needed,
      needsErr: !fracEq(needed, m.timeLen),
    });
    effective = needed;
  }

  // Rebuild each affected measure slice back to front so earlier indices stay valid.
  for (let p = plan.length - 1; p >= 0; p -= 1) {
    const { m, needsSet, needed, needsErr } = plan[p];
    const slice = tokens.slice(m.tokenStart, m.tokenEnd);
    const isBookkeeping = (t) =>
      (t.type === "set" && t.measureLength) ||
      (t.type === "command" && (t.command === "\\markErr" || t.command === "\\unmarkErr"));
    const kept = slice.filter((t) => !isBookkeeping(t));
    const eventPos = kept
      .map((t, i) => (t.type === "event" && t.kind !== "skip" ? i : -1))
      .filter((i) => i >= 0);
    const first = eventPos[0];
    const last = eventPos[eventPos.length - 1];
    const rebuilt = [];
    kept.forEach((t, i) => {
      if (i === first) {
        if (needsSet) {
          const raw = MOMENT(needed);
          rebuilt.push({
            type: "set",
            uid: nextUid(),
            raw,
            ws: t.ws,
            property: "Timing.measureLength",
            valueRaw: raw.slice(raw.indexOf("#(")),
            measureLength: needed,
          });
          t = { ...t, ws: " " };
        }
        if (needsErr) {
          rebuilt.push({
            type: "command",
            uid: nextUid(),
            raw: "\\markErr",
            ws: t.ws,
            command: "\\markErr",
          });
          t = { ...t, ws: " " };
        }
      }
      rebuilt.push(t);
      if (i === last && needsErr) {
        rebuilt.push({
          type: "command",
          uid: nextUid(),
          raw: "\\unmarkErr",
          ws: " ",
          command: "\\unmarkErr",
        });
      }
    });
    // The first kept token inherits the leading whitespace of the original slice
    if (rebuilt.length && slice.length) rebuilt[0] = { ...rebuilt[0], ws: slice[0].ws };
    tokens.splice(m.tokenStart, m.tokenEnd - m.tokenStart, ...rebuilt);
  }
  return { ...doc, tokens };
}

// ── Convenience ──────────────────────────────────────────────────────────

/** Human-readable label for a duration (German). */
export function durationLabel(d) {
  if (!d) return "";
  const names = {
    1: "Ganze",
    2: "Halbe",
    4: "Viertel",
    8: "Achtel",
    16: "Sechzehntel",
    32: "Zweiunddreißigstel",
  };
  return (names[d.base] || `1/${d.base}`) + (d.dots ? " punktiert" : "");
}

export const GERMAN_NOTE_NAMES = { c: "C", d: "D", e: "E", f: "F", g: "G", a: "A", b: "H" };

export function pitchLabel(p) {
  const base = GERMAN_NOTE_NAMES[p.letter] || p.letter.toUpperCase();
  let name = base;
  if (p.alter === -1)
    name = p.letter === "b" ? "B" : p.letter === "e" || p.letter === "a" ? base + "s" : base + "es";
  else if (p.alter === 1) name = base + "is";
  else if (p.alter === -2) name = base + "eses";
  else if (p.alter === 2) name = base + "isis";
  return `${name}${p.octave}`;
}
