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
const SUFFIX_PIECE_RE = /^(?:~|\\?[()]|-[>.^_+-]|-\\[a-zA-Z]+|\\[<>!]|\\[a-zA-Z]+(?![a-zA-Z]))/;

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
        // \pseudoIndent starts a new system by itself (it contains \break)
        push("section", raw, ws, { label: label ? label[1] : "", lineBreak: true });
        i = k;
        continue;
      } else if (cmd === "\\mark") {
        const mk = /^\s*\\markup\s*\{/.exec(src.slice(j));
        if (mk) {
          const k = readBalanced(src, j + mk[0].length - 1);
          const raw = src.slice(i, k);
          const label = /"((?:[^"\\]|\\.)*)"/.exec(raw);
          push("section", raw, ws, { label: label ? label[1] : "", lineBreak: false });
          i = k;
          continue;
        }
      } else if (cmd === "\\tuplet" || cmd === "\\times") {
        const t = /^\s+(\d+)\/(\d+)/.exec(src.slice(j));
        if (t) {
          const num = cmd === "\\tuplet" ? Number(t[1]) : Number(t[2]);
          const den = cmd === "\\tuplet" ? Number(t[2]) : Number(t[1]);
          push("tuplet", src.slice(i, j + t[0].length), ws, { num, den });
          i = j + t[0].length;
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
  let tupletPending = null;
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
      tuplets: [], // [{ num, den, tokenIndex, events }]
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
        if (t.lineBreak) {
          if (cur.events.length === 0) cur.breakBefore = true;
          else pendingBreak = true;
        }
        break;
      case "repeat":
        if (t.repeatKind === "percent") percentPending = t.count;
        else if (t.repeatKind === "volta") {
          // The measure that is open right now is the first of the repeat.
          cur.startBarline = "repeat-begin";
          stack.push({ kind: "repeat-volta-pending", count: t.count });
        }
        break;
      case "volta":
        if (stack.length && stack[stack.length - 1].kind === "alternative") {
          stack.push({ kind: "volta-pending", count: t.count });
        }
        break;
      case "tuplet":
        tupletPending = { num: t.num, den: t.den, tokenIndex: i };
        break;
      case "open": {
        const top = stack[stack.length - 1];
        if (tupletPending !== null) {
          stack.push({ kind: "tuplet", ...tupletPending, events: [] });
          cur.tuplets.push(stack[stack.length - 1]);
          tupletPending = null;
        } else if (percentPending !== null) {
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
        if (top && top.kind === "tuplet") break;
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
      case "event": {
        if (t.kind === "skip") break;
        cur.events.push(i);
        if (inErr) cur.err = true;
        // duration scaling from enclosing \\tuplet blocks
        let factor = frac(1, 1);
        let tupletCtx = null;
        for (const ctx of stack) {
          if (ctx.kind === "tuplet") {
            factor = fracMul(factor, frac(ctx.den, ctx.num));
            tupletCtx = ctx;
          }
        }
        t.tupletFactor = factor.n === factor.d ? null : factor;
        if (tupletCtx) tupletCtx.events.push(i);
        break;
      }
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

  // A repeat start written as the *end* barline of a measure (\bar ".|:" or
  // ":|.|:") is displayed at the start of the following measure, which is
  // also where it ends up after a line break in LilyPond.
  for (let i = 0; i < measures.length; i += 1) {
    const m = measures[i];
    const next = measures[i + 1];
    if (m.endBarline === "repeat-begin") {
      m.endBarline = "single";
      if (next) next.startBarline = "repeat-begin";
    } else if (m.endBarline === "repeat-both") {
      m.endBarline = "repeat-end";
      if (next) next.startBarline = "repeat-begin";
    }
  }

  // Physical measure numbers as printed on the page: a percent repeat
  // stands for N measures, a multi-measure rest is one printed measure.
  let number = 1;
  for (const m of measures) {
    m.number = number;
    m.span = m.percent !== null ? m.percent : 1;
    number += m.span;
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
    let len = durationLength(t.duration);
    if (t.tupletFactor) len = fracMul(len, t.tupletFactor);
    total = fracAdd(total, len);
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

/**
 * Insert a plain barline right after the event at `tokenIndex`, splitting
 * its measure in two. Refused inside percent repeats and when no further
 * event follows in the measure (that would only create an empty measure).
 */
export function insertBarline(doc, measures, tokenIndex) {
  const m = measures.find((mm) => tokenIndex >= mm.tokenStart && tokenIndex < mm.tokenEnd);
  if (!m || m.percent !== null) return doc;
  const pos = m.events.indexOf(tokenIndex);
  if (pos === -1 || pos === m.events.length - 1) return doc;
  const tokens = cloneTokens(doc.tokens);
  tokens.splice(tokenIndex + 1, 0, { type: "bar", raw: "|", ws: " ", uid: nextUid() });
  return { ...doc, tokens };
}

/**
 * Remove the barline that ends `measure`, merging it with the next one.
 * A special barline (repeat, double, final) is first reduced to a plain
 * barline; a second call then removes it.
 */
export function removeBarline(doc, measure) {
  if (!measure || measure.endToken === null || measure.endToken === undefined) return doc;
  const tokens = cloneTokens(doc.tokens);
  const t = tokens[measure.endToken];
  if (!t) return doc;
  if (t.type === "barline") {
    tokens[measure.endToken] = { type: "bar", raw: "|", ws: t.ws, uid: nextUid() };
    return { ...doc, tokens };
  }
  if (t.type !== "bar") return doc;
  tokens.splice(measure.endToken, 1);
  const next = tokens[measure.endToken];
  if (next) next.ws = " ";
  return { ...doc, tokens };
}

// ── Decorations (articulations, dynamics, hairpins) ──────────────────────

export const ARTICULATIONS = {
  accent: { token: "->", label: "Akzent" },
  staccato: { token: "-.", label: "Staccato" },
  tenuto: { token: "--", label: "Tenuto" },
  marcato: { token: "-^", label: "Marcato" },
  fermata: { token: "\\fermata", label: "Fermate" },
};

export const DYNAMICS = ["pp", "p", "mp", "mf", "f", "ff", "sfz", "fp"];

const HAIRPIN_TOKENS = { cresc: "\\<", decresc: "\\>", end: "\\!" };

/** Split an event suffix into its pieces (articulations, dynamics, markup …). */
export function splitSuffix(suffix) {
  const pieces = [];
  let i = 0;
  const src = suffix || "";
  while (i < src.length) {
    const rest = src.slice(i);
    const m = SUFFIX_PIECE_RE.exec(rest);
    if (m) {
      pieces.push(m[0]);
      i += m[0].length;
      continue;
    }
    const mk = /^[_^-]?\\markup\s*\{/.exec(rest);
    if (mk) {
      const end = readBalanced(src, i + mk[0].length - 1);
      pieces.push(src.slice(i, end));
      i = end;
      continue;
    }
    // unknown character: keep it attached to the previous piece
    if (pieces.length) pieces[pieces.length - 1] += src[i];
    else pieces.push(src[i]);
    i += 1;
  }
  return pieces;
}

/** Describe the decorations of an event for menus. */
export function eventDecorations(tok) {
  const pieces = splitSuffix(tok.suffix);
  const articulations = new Set();
  for (const [name, def] of Object.entries(ARTICULATIONS)) {
    if (pieces.includes(def.token)) articulations.add(name);
  }
  const dynamic = pieces.map((p) => p.slice(1)).find((p) => DYNAMICS.includes(p)) || null;
  let hairpin = null;
  if (pieces.includes("\\<")) hairpin = "cresc";
  else if (pieces.includes("\\>")) hairpin = "decresc";
  else if (pieces.includes("\\!")) hairpin = "end";
  const tie = pieces.includes("~");
  const slurStart = pieces.includes("(");
  const slurEnd = pieces.includes(")");
  return { articulations, dynamic, hairpin, tie, slurStart, slurEnd };
}

/** The next sounding event after `tokenIndex` (rests included, spacers skipped). */
export function nextSoundingIndex(tokens, tokenIndex) {
  for (let i = tokenIndex + 1; i < tokens.length; i += 1) {
    const t = tokens[i];
    if (t.type === "event" && t.kind !== "spacer" && t.kind !== "skip") return i;
  }
  return -1;
}

/**
 * A tie (~) only works towards a following note of the same pitch; LilyPond
 * drops it otherwise ("unterminated tie").
 */
export function tieAllowed(tokens, tokenIndex) {
  const t = tokens[tokenIndex];
  if (!t || t.type !== "event" || t.kind !== "note") return false;
  const n = nextSoundingIndex(tokens, tokenIndex);
  if (n === -1) return false;
  const next = tokens[n];
  if (next.kind !== "note") return false;
  const a = t.pitches.map(pitchToLily).sort().join(" ");
  const b = next.pitches.map(pitchToLily).sort().join(" ");
  return a === b;
}

/** Slur ( … ) from `startIndex` to `endIndex` (legato bow over different pitches). */
export function placeSlur(doc, startIndex, endIndex) {
  if (startIndex === endIndex) return doc;
  const lo = Math.min(startIndex, endIndex);
  const hi = Math.max(startIndex, endIndex);
  let out = withSuffix(doc, lo, (pieces) => (pieces.includes("(") ? pieces : [...pieces, "("]));
  out = withSuffix(out, hi, (pieces) => (pieces.includes(")") ? pieces : [...pieces, ")"]));
  return out;
}

export function removeSlur(doc, startIndex, endIndex) {
  let out = withSuffix(doc, startIndex, (pieces) => pieces.filter((p) => p !== "("));
  if (endIndex !== null && endIndex !== undefined) {
    out = withSuffix(out, endIndex, (pieces) => pieces.filter((p) => p !== ")"));
  }
  return out;
}

/** Slurs as [{ start, end }] token indices; `end` null when never closed. */
export function findSlurs(tokens) {
  const out = [];
  let open = null;
  tokens.forEach((t, i) => {
    if (t.type !== "event") return;
    const pieces = splitSuffix(t.suffix);
    if (open !== null && pieces.includes(")")) {
      out.push({ start: open, end: i });
      open = null;
    }
    if (pieces.includes("(")) open = i;
  });
  if (open !== null) out.push({ start: open, end: null });
  return out;
}

/** Add or remove the tie (~) that connects a note to the next one. */
export function toggleTie(doc, tokenIndex, force = null) {
  return withSuffix(doc, tokenIndex, (pieces, t) => {
    if (t.kind !== "note") return pieces;
    const has = pieces.includes("~");
    const want = force === null ? !has : force;
    if (want === has) return pieces;
    return want ? [...pieces, "~"] : pieces.filter((p) => p !== "~");
  });
}

/** Start marks of a hairpin (\\< / \\>) and its end mark (\\!) as one operation. */
export function removeHairpin(doc, startIndex, endIndex) {
  let out = setHairpin(doc, startIndex, null);
  if (endIndex !== null && endIndex !== undefined && endIndex !== startIndex) {
    const end = out.tokens[endIndex];
    if (end && splitSuffix(end.suffix).includes("\\!")) out = setHairpin(out, endIndex, null);
  }
  return out;
}

/**
 * Lay a hairpin from `startIndex` to `endIndex` (score order). The end gets
 * \\! unless it already carries a dynamic, which terminates the hairpin.
 */
export function placeHairpin(doc, startIndex, endIndex, kind) {
  if (startIndex === endIndex) return doc;
  const lo = Math.min(startIndex, endIndex);
  const hi = Math.max(startIndex, endIndex);
  let out = setHairpin(doc, lo, kind);
  const endTok = out.tokens[hi];
  if (endTok) {
    const hasDynamic = eventDecorations(endTok).dynamic !== null;
    out = setHairpin(out, hi, hasDynamic ? null : "end");
  }
  return out;
}

/**
 * Hairpins as [{ start, end, kind }] token indices in score order; `end` is
 * null for a hairpin that is never terminated.
 */
export function findHairpins(tokens) {
  const out = [];
  let open = null;
  tokens.forEach((t, i) => {
    if (t.type !== "event") return;
    const deco = eventDecorations(t);
    if (
      open &&
      (deco.hairpin === "end" ||
        deco.dynamic !== null ||
        deco.hairpin === "cresc" ||
        deco.hairpin === "decresc")
    ) {
      if (i !== open.start) {
        out.push({ ...open, end: i });
        open = null;
      }
    }
    if (deco.hairpin === "cresc" || deco.hairpin === "decresc")
      open = { start: i, kind: deco.hairpin };
  });
  if (open) out.push({ ...open, end: null });
  return out;
}

function withSuffix(doc, tokenIndex, fn) {
  const tokens = cloneTokens(doc.tokens);
  const t = tokens[tokenIndex];
  if (!t || t.type !== "event") return doc;
  t.suffix = fn(splitSuffix(t.suffix), t).join("");
  return { ...doc, tokens };
}

export function toggleArticulation(doc, tokenIndex, name) {
  const def = ARTICULATIONS[name];
  if (!def) return doc;
  return withSuffix(doc, tokenIndex, (pieces, t) => {
    if (t.kind !== "note") return pieces;
    return pieces.includes(def.token)
      ? pieces.filter((p) => p !== def.token)
      : [...pieces, def.token];
  });
}

/** Set the dynamic mark (\\p, \\f …) of an event; null removes it. */
export function setDynamic(doc, tokenIndex, name) {
  return withSuffix(doc, tokenIndex, (pieces) => {
    const kept = pieces.filter((p) => !DYNAMICS.includes(p.slice(1)) || !p.startsWith("\\"));
    return name ? [...kept, `\\${name}`] : kept;
  });
}

/** Set the hairpin mark of an event: "cresc", "decresc", "end" or null. */
export function setHairpin(doc, tokenIndex, kind) {
  return withSuffix(doc, tokenIndex, (pieces) => {
    const kept = pieces.filter((p) => !Object.values(HAIRPIN_TOKENS).includes(p));
    return kind && HAIRPIN_TOKENS[kind] ? [...kept, HAIRPIN_TOKENS[kind]] : kept;
  });
}

// ── Barline and measure operations ───────────────────────────────────────

export const BARLINE_TYPES = {
  single: { lily: null, label: "Einfach" },
  double: { lily: "||", label: "Doppelt" },
  end: { lily: "|.", label: "Schluss" },
  "repeat-begin": { lily: ".|:", label: "Wiederholung Anfang" },
  "repeat-end": { lily: ":|.", label: "Wiederholung Ende" },
  "repeat-both": { lily: ":|.|:", label: "Wiederholung beidseitig" },
};

/** The barline type actually written at the end of a measure. */
export function barlineTypeOf(tokens, measure) {
  if (!measure || measure.endToken === null || measure.endToken === undefined) return null;
  const t = tokens[measure.endToken];
  if (!t) return null;
  if (t.type === "bar") return "single";
  if (t.type === "barline") return BAR_TYPE_MAP[t.barType] || "single";
  return null;
}

export function setBarlineType(doc, measure, type) {
  const def = BARLINE_TYPES[type];
  if (!def || !measure || measure.endToken === null || measure.endToken === undefined) return doc;
  const tokens = cloneTokens(doc.tokens);
  const old = tokens[measure.endToken];
  if (!old || (old.type !== "bar" && old.type !== "barline")) return doc;
  tokens[measure.endToken] = def.lily
    ? { type: "barline", raw: `\\bar "${def.lily}"`, ws: old.ws, uid: nextUid(), barType: def.lily }
    : { type: "bar", raw: "|", ws: old.ws, uid: nextUid() };
  return { ...doc, tokens };
}

/** Remove the barline ending `measure` outright (merging with the next measure). */
export function deleteBarline(doc, measure) {
  if (!measure || measure.endToken === null || measure.endToken === undefined) return doc;
  const tokens = cloneTokens(doc.tokens);
  const t = tokens[measure.endToken];
  if (!t || (t.type !== "bar" && t.type !== "barline")) return doc;
  tokens.splice(measure.endToken, 1);
  const next = tokens[measure.endToken];
  if (next) next.ws = " ";
  return { ...doc, tokens };
}

/**
 * Delete a whole measure: its events, its end barline and, for percent
 * repeats, the \\repeat wrapper. Structural tokens (clef, key, repeats
 * braces, breaks) are kept and carry over to the next measure.
 */
export function deleteMeasure(doc, measure) {
  if (!measure) return doc;
  const tokens = cloneTokens(doc.tokens);
  const remove = new Set(measure.events);
  if (measure.endToken !== null && measure.endToken !== undefined) remove.add(measure.endToken);
  if (measure.percent !== null) {
    const rep = tokens.findIndex(
      (t, i) =>
        i >= measure.tokenStart &&
        i < measure.tokenEnd &&
        t.type === "repeat" &&
        t.repeatKind === "percent",
    );
    if (rep >= 0) {
      let depth = 0;
      for (let i = rep + 1; i < measure.tokenEnd; i += 1) {
        remove.add(i);
        if (tokens[i].type === "open") depth += 1;
        if (tokens[i].type === "close") {
          depth -= 1;
          if (depth === 0) break;
        }
      }
      remove.add(rep);
    }
  }
  const kept = tokens.filter((_, i) => !remove.has(i));
  return { ...doc, tokens: kept };
}

/** Insert an empty measure (full-measure rests + barline) before or after `measure`. */
export function insertEmptyMeasure(doc, measure, where) {
  if (!measure) return doc;
  const tokens = cloneTokens(doc.tokens);
  const rests = durationTokensFor(measure.timeLen).map((d, i) => ({
    type: "event",
    uid: nextUid(),
    ws: i === 0 ? "\n    " : " ",
    raw: "",
    kind: "rest",
    pitches: [],
    duration: { ...d },
    suffix: "",
  }));
  const bar = { type: "bar", raw: "|", ws: " ", uid: nextUid() };
  let at;
  let inserted;
  if (where === "after") {
    if (measure.endToken !== null && measure.endToken !== undefined) {
      at = measure.endToken + 1;
      inserted = [...rests, bar];
    } else {
      at = measure.tokenEnd;
      inserted = [{ ...bar, ws: " " }, ...rests];
    }
  } else {
    const percentIdx = tokens.findIndex(
      (t, i) =>
        i >= measure.tokenStart &&
        i < measure.tokenEnd &&
        t.type === "repeat" &&
        t.repeatKind === "percent",
    );
    if (percentIdx >= 0) at = percentIdx;
    else if (measure.events.length) at = measure.events[0];
    else if (measure.endToken !== null && measure.endToken !== undefined) at = measure.endToken;
    else at = measure.tokenEnd;
    inserted = [...rests, bar];
    // the displaced token continues on a new line
    if (tokens[at]) tokens[at].ws = "\n    ";
  }
  tokens.splice(at, 0, ...inserted);
  return { ...doc, tokens };
}

// ── Key signatures and percent repeats ───────────────────────────────────

/** Major keys offered in the editor, in LilyPond spelling with German labels. */
export const MAJOR_KEYS = [
  ["c", "C-Dur"],
  ["f", "F-Dur"],
  ["bes", "B-Dur"],
  ["es", "Es-Dur"],
  ["as", "As-Dur"],
  ["des", "Des-Dur"],
  ["ges", "Ges-Dur"],
  ["g", "G-Dur"],
  ["d", "D-Dur"],
  ["a", "A-Dur"],
  ["e", "E-Dur"],
  ["b", "H-Dur"],
];

function percentRepeatIndex(tokens, measure) {
  for (let i = measure.tokenStart; i < measure.tokenEnd; i += 1) {
    const t = tokens[i];
    if (t.type === "repeat" && t.repeatKind === "percent") return i;
  }
  return -1;
}

/** Index of the "}" closing the brace opened right after `repIdx`. */
function percentCloseIndex(tokens, repIdx) {
  let depth = 0;
  for (let i = repIdx + 1; i < tokens.length; i += 1) {
    if (tokens[i].type === "open") depth += 1;
    else if (tokens[i].type === "close") {
      depth -= 1;
      if (depth === 0) return i;
    }
  }
  return -1;
}

/**
 * Set (or remove with keyName = null) the key signature at the start of a
 * measure. An existing \key in the measure is replaced.
 */
export function setKeySignature(doc, measure, keyName, mode = "major") {
  if (!measure) return doc;
  const tokens = cloneTokens(doc.tokens);
  let existing = -1;
  for (let i = measure.tokenStart; i < measure.tokenEnd; i += 1) {
    if (tokens[i].type === "key") existing = i;
  }
  if (!keyName) {
    if (existing === -1) return doc;
    const ws = tokens[existing].ws;
    tokens.splice(existing, 1);
    if (tokens[existing] && /\n/.test(ws)) tokens[existing].ws = ws;
    return { ...doc, tokens };
  }
  const tok = {
    type: "key",
    uid: nextUid(),
    raw: `\\key ${keyName} \\${mode}`,
    ws: " ",
    keyName,
    mode,
  };
  if (existing >= 0) {
    tokens[existing] = { ...tok, ws: tokens[existing].ws };
    return { ...doc, tokens };
  }
  // Place the key before the measure's bookkeeping (\\set measureLength, \\markErr),
  // the percent-repeat wrapper or the first event, whichever comes first.
  let at = -1;
  for (let i = measure.tokenStart; i < measure.tokenEnd; i += 1) {
    const t = tokens[i];
    const bookkeeping =
      (t.type === "set" && t.measureLength) ||
      (t.type === "command" && t.command === "\\markErr") ||
      (t.type === "repeat" && t.repeatKind === "percent") ||
      (t.type === "event" && t.kind !== "skip");
    if (bookkeeping) {
      at = i;
      break;
    }
  }
  if (at === -1) {
    at =
      measure.endToken !== null && measure.endToken !== undefined
        ? measure.endToken
        : measure.tokenEnd;
  }
  tok.ws = tokens[at] ? tokens[at].ws : " ";
  if (tokens[at]) tokens[at] = { ...tokens[at], ws: " " };
  tokens.splice(at, 0, tok);
  return { ...doc, tokens };
}

/**
 * Set the key for measures fromIdx..toIdx (inclusive): the key is written at
 * the first measure, key changes inside the range are removed, and the
 * measure after the range gets its previous key back when it differs.
 */
export function setKeyForRange(doc, measures, fromIdx, toIdx, keyName, mode = "major") {
  const lo = Math.min(fromIdx, toIdx);
  const hi = Math.max(fromIdx, toIdx);
  if (!measures[lo] || !measures[hi]) return doc;
  let out = doc;
  // Work back to front so earlier token indices stay valid.
  const after = measures[hi + 1];
  if (after && !after.showKey && (after.keyName !== keyName || after.mode !== mode)) {
    out = setKeySignature(out, after, after.keyName, after.mode);
  }
  for (let i = hi; i > lo; i -= 1) {
    if (measures[i].showKey) out = setKeySignature(out, measures[i], null);
  }
  return setKeySignature(out, measures[lo], keyName, mode);
}

/**
 * Set how often a measure is played: 1 removes a percent-repeat wrapper,
 * 2+ wraps the measure in \repeat percent N { … } or changes N.
 */
export function setPercentCount(doc, measure, count) {
  if (!measure) return doc;
  const tokens = cloneTokens(doc.tokens);
  const rep = percentRepeatIndex(tokens, measure);
  if (count <= 1) {
    if (rep === -1) return doc;
    const close = percentCloseIndex(tokens, rep);
    const open = tokens.findIndex((t, i) => i > rep && t.type === "open");
    const remove = [rep, open, close].filter((i) => i >= 0).sort((a, b) => b - a);
    for (const i of remove) {
      const ws = tokens[i].ws;
      tokens.splice(i, 1);
      if (tokens[i] && /\n/.test(ws) && !/\n/.test(tokens[i].ws)) tokens[i].ws = ws;
    }
    return { ...doc, tokens };
  }
  if (rep >= 0) {
    tokens[rep] = { ...tokens[rep], raw: `\\repeat percent ${count}`, count };
    return { ...doc, tokens };
  }
  if (!measure.events.length) return doc;
  const first = measure.events[0];
  const last = measure.events[measure.events.length - 1];
  tokens.splice(last + 1, 0, { type: "close", raw: "}", ws: " ", uid: nextUid() });
  tokens.splice(
    first,
    0,
    {
      type: "repeat",
      raw: `\\repeat percent ${count}`,
      ws: tokens[first].ws,
      uid: nextUid(),
      repeatKind: "percent",
      count,
    },
    { type: "open", raw: "{", ws: " ", uid: nextUid() },
  );
  tokens[first + 2] = { ...tokens[first + 2], ws: " " };
  return { ...doc, tokens };
}

/**
 * Drop percent repeats whose body has no events left (LilyPond aborts on
 * them). Only bookkeeping tokens may remain inside such a body.
 */
function dropEmptyPercentRepeats(tokens) {
  for (let rep = tokens.length - 1; rep >= 0; rep -= 1) {
    const t = tokens[rep];
    if (t.type !== "repeat" || t.repeatKind !== "percent") continue;
    const open = tokens.findIndex((x, i) => i > rep && x.type === "open");
    const close = percentCloseIndex(tokens, rep);
    if (open === -1 || close === -1) continue;
    const inner = tokens.slice(open + 1, close);
    if (inner.some((x) => x.type === "event")) continue;
    const disposable = (x) =>
      (x.type === "command" && (x.command === "\\markErr" || x.command === "\\unmarkErr")) ||
      (x.type === "set" && x.measureLength);
    const remove = [
      close,
      ...inner.map((_, k) => open + 1 + k).filter((i) => disposable(tokens[i])),
      open,
      rep,
    ];
    remove.sort((a, b) => b - a);
    for (const i of remove) tokens.splice(i, 1);
  }
  return tokens;
}

// ── Tuplets and multi-measure rests ──────────────────────────────────────

export const TUPLET_PRESETS = [
  { num: 3, den: 2, label: "Triole (3:2)" },
  { num: 5, den: 4, label: "Quintole (5:4)" },
  { num: 6, den: 4, label: "Sextole (6:4)" },
  { num: 7, den: 4, label: "Septole (7:4)" },
];

/** Wrap consecutive event tokens (same measure) in \\tuplet num/den { … }. */
export function wrapTuplet(doc, indices, num, den) {
  if (!indices.length) return doc;
  const tokens = cloneTokens(doc.tokens);
  const first = Math.min(...indices);
  const last = Math.max(...indices);
  for (let i = first; i <= last; i += 1) {
    const t = tokens[i];
    if (t.type === "bar" || t.type === "barline" || t.type === "open" || t.type === "close")
      return doc;
    if (t.type === "tuplet") return doc;
  }
  tokens.splice(last + 1, 0, { type: "close", raw: "}", ws: " ", uid: nextUid() });
  tokens.splice(
    first,
    0,
    {
      type: "tuplet",
      raw: `\\tuplet ${num}/${den}`,
      ws: tokens[first].ws,
      uid: nextUid(),
      num,
      den,
    },
    { type: "open", raw: "{", ws: " ", uid: nextUid() },
  );
  tokens[first + 2] = { ...tokens[first + 2], ws: " " };
  return { ...doc, tokens };
}

/** Remove the \\tuplet wrapper whose command token is at `tupletIndex`. */
export function unwrapTuplet(doc, tupletIndex) {
  const tokens = cloneTokens(doc.tokens);
  const rep = tokens[tupletIndex];
  if (!rep || rep.type !== "tuplet") return doc;
  const open = tokens.findIndex((t, i) => i > tupletIndex && t.type === "open");
  const close = percentCloseIndex(tokens, tupletIndex);
  if (open === -1 || close === -1) return doc;
  for (const i of [close, open, tupletIndex]) {
    const ws = tokens[i].ws;
    tokens.splice(i, 1);
    if (tokens[i] && /\n/.test(ws) && !/\n/.test(tokens[i].ws)) tokens[i].ws = ws;
  }
  return { ...doc, tokens };
}

/** Number of measures of a multi-measure rest token (R1*N). */
export function mmrestCount(tok) {
  if (!tok || tok.kind !== "mmrest" || !tok.duration) return 1;
  return tok.duration.mult ? Math.max(1, Math.round(tok.duration.mult.n / tok.duration.mult.d)) : 1;
}

export function setMmrestCount(doc, tokenIndex, count) {
  const tokens = cloneTokens(doc.tokens);
  const t = tokens[tokenIndex];
  if (!t || t.kind !== "mmrest" || !t.duration) return doc;
  const n = Math.max(1, Math.round(count));
  t.duration = { ...t.duration, mult: n === 1 ? null : frac(n, 1) };
  return { ...doc, tokens };
}

/**
 * Compact multi-measure rest for marches: inserted after `measure` as
 * \\compressMMRests { \\once \\override MultiMeasureRestNumber.direction = #DOWN R1*N } |
 * (the rest length follows the time signature).
 */
export function insertCompactRest(doc, measure, count) {
  if (!measure) return doc;
  const tokens = cloneTokens(doc.tokens);
  const durs = durationTokensFor(measure.timeLen);
  const restDur = durs.length === 1 ? durationToLily(durs[0]) : "1";
  const n = Math.max(1, Math.round(count));
  const snippet = `\\compressMMRests { \\once \\override MultiMeasureRestNumber.direction = #DOWN R${restDur}*${n} } |`;
  const inserted = tokenize(snippet);
  inserted[0].ws = "\n    ";
  let at;
  if (measure.endToken !== null && measure.endToken !== undefined) at = measure.endToken + 1;
  else {
    at = measure.tokenEnd;
    inserted.unshift({ type: "bar", raw: "|", ws: " ", uid: nextUid() });
    inserted[1].ws = "\n    ";
  }
  tokens.splice(at, 0, ...inserted);
  return { ...doc, tokens };
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
/** Spacers (<>) exist only to carry marks; one without marks is noise. */
function dropBareSpacers(tokens) {
  for (let i = tokens.length - 1; i >= 0; i -= 1) {
    const t = tokens[i];
    if (t.type === "event" && t.kind === "spacer" && !(t.suffix || "").trim()) {
      const ws = t.ws;
      tokens.splice(i, 1);
      if (tokens[i] && /\n/.test(ws) && !/\n/.test(tokens[i].ws)) tokens[i].ws = ws;
    }
  }
  return tokens;
}

/** \\tuplet blocks without events are dropped (LilyPond rejects them). */
function dropEmptyTuplets(tokens) {
  for (let i = tokens.length - 1; i >= 0; i -= 1) {
    if (tokens[i].type !== "tuplet") continue;
    const open = tokens.findIndex((x, k) => k > i && x.type === "open");
    const close = percentCloseIndex(tokens, i);
    if (open === -1 || close === -1) continue;
    if (tokens.slice(open + 1, close).some((x) => x.type === "event")) continue;
    for (const k of [close, open, i]) tokens.splice(k, 1);
  }
  return tokens;
}

/**
 * An explicit \\bar ":|." right before \\repeat volta hides LilyPond's
 * automatic start repeat; write both sides so the start shows up.
 */
function fixRepeatEndBeforeVolta(tokens) {
  tokens.forEach((t, i) => {
    if (t.type !== "barline" || t.barType !== ":|.") return;
    for (let k = i + 1; k < tokens.length; k += 1) {
      const n = tokens[k];
      if (n.type === "comment" || (n.type === "command" && n.command === "\\break")) continue;
      if (n.type === "repeat" && n.repeatKind === "volta") {
        tokens[i] = { ...t, raw: '\\bar ":|.|:"', barType: ":|.|:" };
      }
      break;
    }
  });
  return tokens;
}

export function normalizeDocument(doc) {
  const tokens = fixRepeatEndBeforeVolta(
    dropEmptyTuplets(dropEmptyPercentRepeats(dropBareSpacers(cloneTokens(doc.tokens)))),
  );
  const measures = buildMeasures(tokens);
  let effective = null;
  let timeLen = null;

  const plan = [];
  for (const m of measures) {
    if (timeLen === null || !fracEq(timeLen, m.timeLen)) {
      timeLen = m.timeLen;
      effective = timeLen;
    }
    const hasMusic = m.events.some((i) => tokens[i].kind !== "spacer");
    if (!hasMusic) {
      // Nothing to measure: stale bookkeeping left behind by deletions goes away.
      plan.push({ m, strip: true });
      continue;
    }
    // Percent repeats and multi-measure rests take part too: their length may
    // have changed through editing, and a stale measureLength derails LilyPond.
    // A multi-measure rest keeps the plain measure length: with a longer
    // measureLength LilyPond treats R1*N as one measure and drops the number.
    const isMm = isMmrestMeasure(tokens, m);
    const needed = isMm ? m.timeLen : m.actualLen;
    plan.push({
      m,
      needsSet: !fracEq(needed, effective),
      needed,
      needsErr: !isMm && !fracEq(needed, m.timeLen),
    });
    effective = needed;
  }

  // Rebuild each affected measure slice back to front so earlier indices stay valid.
  for (let p = plan.length - 1; p >= 0; p -= 1) {
    const { m, needsSet, needed, needsErr, strip } = plan[p];
    const slice = tokens.slice(m.tokenStart, m.tokenEnd);
    const isBookkeeping = (t) =>
      (t.type === "set" && t.measureLength) ||
      (t.type === "command" && (t.command === "\\markErr" || t.command === "\\unmarkErr"));
    // Drop bookkeeping tokens; a removed token's line break moves to the next kept one.
    const kept = [];
    let pendingWs = null;
    for (const t of slice) {
      if (isBookkeeping(t)) {
        if (/\n/.test(t.ws) && pendingWs === null) pendingWs = t.ws;
        continue;
      }
      if (pendingWs !== null && !/\n/.test(t.ws)) {
        kept.push({ ...t, ws: pendingWs });
      } else {
        kept.push(t);
      }
      pendingWs = null;
    }
    if (strip) {
      if (kept.length && slice.length) kept[0] = { ...kept[0], ws: slice[0].ws };
      tokens.splice(m.tokenStart, m.tokenEnd - m.tokenStart, ...kept);
      continue;
    }
    const eventPos = kept
      .map((t, i) => (t.type === "event" && t.kind !== "skip" ? i : -1))
      .filter((i) => i >= 0);
    const first = eventPos[0];
    const last = eventPos[eventPos.length - 1];
    // measureLength goes in front of the percent-repeat wrapper, the error
    // marking around the events inside it
    // Where the bookkeeping goes: in front of a wrapper (percent repeat,
    // compressMMRests, tuplet) that starts the music, else at the first event.
    const isWrapper = (t) =>
      (t.type === "repeat" && t.repeatKind === "percent") ||
      (t.type === "command" && t.command === "\\compressMMRests") ||
      t.type === "tuplet";
    const wrapperPos = kept.findIndex((t, i) => isWrapper(t) && i < first);
    const setAnchor = wrapperPos >= 0 ? wrapperPos : first;
    const percentWrapper = wrapperPos >= 0 && kept[wrapperPos].type === "repeat";
    // markErr sits inside a percent repeat body, otherwise with the set
    const errStart = percentWrapper ? first : setAnchor;
    // unmarkErr after the last event, but outside a tuplet that closes right after it
    let errEnd = last;
    let depth = 0;
    kept.forEach((t, i) => {
      if (i > last) return;
      if (t.type === "tuplet") depth += 1;
      else if (t.type === "close" && depth > 0) depth -= 1;
    });
    for (let i = last + 1; i < kept.length && depth > 0; i += 1) {
      if (kept[i].type === "close") {
        depth -= 1;
        errEnd = i;
      } else break;
    }
    const rebuilt = [];
    kept.forEach((t, i) => {
      if (i === setAnchor && needsSet) {
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
      if (i === errStart && needsErr) {
        rebuilt.push({
          type: "command",
          uid: nextUid(),
          raw: "\\markErr",
          ws: t.ws,
          command: "\\markErr",
        });
        t = { ...t, ws: " " };
      }
      rebuilt.push(t);
      if (i === errEnd && needsErr) {
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
