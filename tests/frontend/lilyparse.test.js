import { describe, it, expect } from "vitest";
import { readFileSync } from "fs";
import { resolve } from "path";
import {
  parseLilypond,
  serializeDocument,
  buildMeasures,
  tokenize,
  serializeTokens,
  transposeEvent,
  setEventDuration,
  deleteEvent,
  insertEvent,
  toggleRest,
  normalizeDocument,
  parsePitch,
  pitchToLily,
  durationLength,
  frac,
  fracEq,
} from "../../src/frontend/src/lib/lilyparse.js";

const SAMPLE = String.raw`\version "2.24.0"
\header {
  title = "Test"
  subtitle = "Tuba 1"
}
markErr = { \override NoteHead.color = #red }
\score {
  \new Staff {
    \set Staff.instrumentName = ""
    \compressEmptyMeasures
    \clef bass \key bes \major \time 2/2 \set Timing.measureLength = #(ly:make-moment 3/4) \markErr bes,2->\f d4-> \unmarkErr |
    \set Timing.measureLength = #(ly:make-moment 1/1) f2-> a2-> |
    f4 r4 f,2-> |
    bes,4 bes,4 bes,4 r4 \bar ".|:"
    \repeat percent 2 { c4 r4 f4 r4 } |
    \set Timing.measureLength = #(ly:make-moment 3/4) \markErr <>\> bes,4 r4 f4 <>\! \unmarkErr |
    \break \set Timing.measureLength = #(ly:make-moment 1/1) r4\f bes,4-> bes,2-> |
    \pseudoIndent \markuplist { \fontsize #5 \bold "Trio" } 8 \key es \major es4\f r4 es4 r4 |
    \repeat volta 2 {
      f4\f\< r4\! bes,4 r4 |
      c4 r4 f2 |
    }
    \alternative {
      \volta 1 { bes,4\> as,4 g,4 f,4 | }
      \volta 2 { bes,4 r4 d4 r4 \bar ":|." }
    }
    R1*4 |
    <bes, d f>2 r2 _\markup { \italic "solo" } \bar "|."
  }
  \layout { }
}
`;

describe("tokenizer", () => {
  it("round-trips arbitrary staff bodies", () => {
    const body = SAMPLE.slice(SAMPLE.indexOf("\\new Staff {") + 12, SAMPLE.lastIndexOf("\\layout") - 4);
    expect(serializeTokens(tokenize(body))).toBe(body);
  });

  it("parses events with suffixes", () => {
    const toks = tokenize("bes,2->\\f d4-> r4 <>\\! R1*4 <bes, d f>2. c'8_\\markup { \\italic \"x\" }");
    const events = toks.filter((t) => t.type === "event");
    expect(events.map((e) => e.kind)).toEqual(["note", "note", "rest", "spacer", "mmrest", "note", "note"]);
    expect(events[0].pitches[0]).toEqual({ letter: "b", alter: -1, octave: 2 });
    expect(events[0].suffix).toBe("->\\f");
    expect(events[4].duration).toEqual({ base: 1, dots: 0, mult: { n: 4, d: 1 } });
    expect(events[5].pitches).toHaveLength(3);
    expect(events[5].duration.dots).toBe(1);
    expect(events[6].suffix).toContain("\\markup");
  });

  it("does not mistake words for pitches", () => {
    const toks = tokenize("\\clef bass \\key es \\major \\set Staff.instrumentName = \"\"");
    expect(toks.map((t) => t.type)).toEqual(["clef", "key", "set"]);
    expect(toks[0].clef).toBe("bass");
    expect(toks[1].keyName).toBe("es");
  });
});

describe("document", () => {
  it("round-trips a whole file", () => {
    const doc = parseLilypond(SAMPLE);
    expect(doc.ok).toBe(true);
    expect(doc.header.title).toBe("Test");
    expect(serializeDocument(doc)).toBe(SAMPLE);
  });

  it("round-trips real generated files", () => {
    for (const rel of ["data/scans/5/5/5/generated.ly", "data/scans/12/12/12/generated.ly"]) {
      let code;
      try {
        code = readFileSync(resolve(__dirname, "../..", rel), "utf-8");
      } catch {
        continue; // file not present in this checkout
      }
      const doc = parseLilypond(code);
      expect(doc.ok).toBe(true);
      expect(serializeDocument(doc)).toBe(code);
      const measures = buildMeasures(doc.tokens);
      expect(measures.length).toBeGreaterThan(10);
    }
  });

  it("builds measures with state and repeats", () => {
    const doc = parseLilypond(SAMPLE);
    const ms = buildMeasures(doc.tokens);
    expect(ms[0].clef).toBe("bass");
    expect(ms[0].keyName).toBe("bes");
    expect(ms[0].time).toEqual({ beats: 2, beatType: 2 });
    expect(ms[0].events).toHaveLength(2);
    expect(ms[0].err).toBe(true);
    expect(ms[0].mismatch).toBe(true);
    expect(ms[1].mismatch).toBe(false);
    expect(ms[3].endBarline).toBe("repeat-begin");
    expect(ms[4].percent).toBe(2);
    expect(ms[6].breakBefore).toBe(true);
    expect(ms[7].section).toBe("Trio");
    expect(ms[7].keyName).toBe("es");
    expect(ms[8].startBarline).toBe("repeat-begin");
    expect(ms[10].volta).toEqual({ count: 1, position: "begin-end" });
    expect(ms[10].endBarline).toBe("repeat-end");
    expect(ms[11].volta).toEqual({ count: 2, position: "begin-end" });
    expect(ms[11].endBarline).toBe("repeat-end");
    expect(ms[12].mismatch).toBe(false); // R1*4 is exempt
  });
});

describe("editing", () => {
  const doc = parseLilypond(SAMPLE);
  const ms = buildMeasures(doc.tokens);

  it("transposes with key-aware accidentals", () => {
    const idx = ms[1].events[0]; // f2
    const d2 = transposeEvent(doc, ms, idx, -1); // f → es in B-flat major
    expect(pitchToLily(d2.tokens[idx].pitches[0])).toBe("es");
    const d3 = transposeEvent(doc, ms, idx, 1); // f → g
    expect(pitchToLily(d3.tokens[idx].pitches[0])).toBe("g");
    expect(serializeDocument(d3)).toContain("g2-> a2-> |");
  });

  it("changes durations and normalizes measure bookkeeping", () => {
    const idx = ms[2].events[0]; // f4 r4 f,2 → f2 r4 f,2 (5/4)
    const d2 = normalizeDocument(setEventDuration(doc, idx, 2));
    const code = serializeDocument(d2);
    expect(code).toContain(
      "\\set Timing.measureLength = #(ly:make-moment 5/4) \\markErr f2 r4 f,2-> \\unmarkErr |",
    );
    // Following measure must restore the full length again
    expect(code).toContain("\\set Timing.measureLength = #(ly:make-moment 1/1) bes,4 bes,4 bes,4 r4 \\bar \".|:\"");
  });

  it("fixing a measure removes the error marking", () => {
    // measure 0: bes,2 d4 (3/4 of 2/2) → make d a half note
    const idx = ms[0].events[1];
    const d2 = normalizeDocument(setEventDuration(doc, idx, 2));
    const code = serializeDocument(d2);
    expect(code).toContain("\\time 2/2 bes,2->\\f d2-> |");
    // the 3/4 measure further down legitimately keeps its explicit length
    expect(code.match(/ly:make-moment 3\/4/g)).toHaveLength(1);
    // measure 1 no longer needs an explicit length
    expect(code).toContain("\\time 2/2 bes,2->\\f d2-> |\n    f2-> a2-> |");
  });

  it("deletes and inserts events", () => {
    const idx = ms[2].events[1]; // r4
    const d2 = deleteEvent(doc, idx);
    expect(serializeDocument(d2)).toContain("f4 f,2-> |");
    const { doc: d3, tokenIndex } = insertEvent(doc, ms[2], idx, {
      kind: "note",
      pitches: [parsePitch("g")],
      duration: { base: 8, dots: 0, mult: null },
    });
    expect(d3.tokens[tokenIndex].kind).toBe("note");
    expect(serializeDocument(d3)).toContain("f4 r4 g8 f,2-> |");
  });

  it("toggles note and rest", () => {
    const idx = ms[1].events[0];
    const d2 = toggleRest(doc, idx);
    expect(serializeDocument(d2)).toContain("r2 a2-> |");
    const d3 = toggleRest(d2, idx, parsePitch("c'"));
    expect(serializeDocument(d3)).toContain("c'2 a2-> |");
  });

  it("computes durations", () => {
    expect(fracEq(durationLength({ base: 2, dots: 1, mult: null }), frac(3, 4))).toBe(true);
    expect(fracEq(durationLength({ base: 1, dots: 0, mult: frac(4, 1) }), frac(4, 1))).toBe(true);
  });
});
