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
  insertBarline,
  removeBarline,
  deleteBarline,
  setBarlineType,
  barlineTypeOf,
  deleteMeasure,
  insertEmptyMeasure,
  toggleArticulation,
  setDynamic,
  setHairpin,
  eventDecorations,
  setKeySignature,
  setKeyForRange,
  toggleTie,
  tieAllowed,
  placeSlur,
  removeSlur,
  findSlurs,
  setHairpin,
  removeHairpin,
  placeHairpin,
  findHairpins,
  setPercentCount,
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
    // \bar ".|:" at the end of measure 4 is shown as repeat start of measure 5
    expect(ms[3].endBarline).toBe("single");
    expect(ms[4].startBarline).toBe("repeat-begin");
    expect(ms[4].percent).toBe(2);
    expect(ms[6].breakBefore).toBe(true);
    expect(ms[7].section).toBe("Trio");
    expect(ms[7].breakBefore).toBe(true); // \pseudoIndent starts a new system
    expect(ms[7].keyName).toBe("es");
    expect(ms[8].startBarline).toBe("repeat-begin");
    expect(ms[9].startBarline).toBeNull(); // only the first measure of the repeat
    expect(ms[10].volta).toEqual({ count: 1, position: "begin-end" });
    expect(ms[10].endBarline).toBe("repeat-end");
    expect(ms[11].volta).toEqual({ count: 2, position: "begin-end" });
    expect(ms[11].endBarline).toBe("repeat-end");
    expect(ms[12].mismatch).toBe(false); // R1*4 is exempt
    // Printed numbering: the percent repeat (measure 5) counts twice
    expect(ms.map((m) => m.number).slice(0, 7)).toEqual([1, 2, 3, 4, 5, 7, 8]);
    expect(ms[4].span).toBe(2);
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

  it("inserts a barline after an event", () => {
    const idx = ms[2].events[1]; // f4 r4 | f,2
    const d2 = normalizeDocument(insertBarline(doc, ms, idx));
    const code = serializeDocument(d2);
    expect(code).toContain(
      "\\set Timing.measureLength = #(ly:make-moment 1/2) \\markErr f4 r4 \\unmarkErr |",
    );
    expect(code).toContain("\\markErr f,2-> \\unmarkErr |");
    // Not after the last event of a measure, not inside percent repeats
    expect(insertBarline(doc, ms, ms[2].events[2])).toBe(doc);
    expect(insertBarline(doc, ms, ms[4].events[0])).toBe(doc);
  });

  it("removes a barline and merges measures", () => {
    const d2 = normalizeDocument(removeBarline(doc, ms[1]));
    const code = serializeDocument(d2);
    expect(code).toContain(
      "\\set Timing.measureLength = #(ly:make-moment 2/1) \\markErr f2-> a2-> f4 r4 f,2-> \\unmarkErr |",
    );
    // A special barline is reduced to a plain one first
    const d3 = removeBarline(doc, ms[3]);
    expect(serializeDocument(d3)).toContain("bes,4 bes,4 bes,4 r4 |");
    expect(serializeDocument(d3)).not.toContain('\\bar ".|:"');
  });

  it("toggles articulations and sets dynamics and hairpins", () => {
    const idx = ms[0].events[0]; // bes,2->\f
    expect(eventDecorations(doc.tokens[idx])).toEqual({
      articulations: new Set(["accent"]),
      dynamic: "f",
      hairpin: null,
      tie: false,
      slurStart: false,
      slurEnd: false,
    });
    let d = toggleArticulation(doc, idx, "accent");
    expect(serializeDocument(d)).toContain("bes,2\\f d4->");
    d = toggleArticulation(d, idx, "staccato");
    expect(serializeDocument(d)).toContain("bes,2\\f-. d4->");
    d = setDynamic(d, idx, "mp");
    expect(serializeDocument(d)).toContain("bes,2-.\\mp d4->");
    d = setDynamic(d, idx, null);
    expect(serializeDocument(d)).toContain("bes,2-. d4->");
    d = setHairpin(d, idx, "cresc");
    expect(serializeDocument(d)).toContain("bes,2-.\\< d4->");
    d = setHairpin(d, idx, "end");
    expect(serializeDocument(d)).toContain("bes,2-.\\! d4->");
    // articulations are not added to rests
    const rest = ms[2].events[1];
    expect(toggleArticulation(doc, rest, "accent").tokens[rest].suffix).toBe("");
  });

  it("changes barline types and deletes barlines", () => {
    expect(barlineTypeOf(doc.tokens, ms[1])).toBe("single");
    expect(barlineTypeOf(doc.tokens, ms[3])).toBe("repeat-begin");
    let d = setBarlineType(doc, ms[1], "double");
    expect(serializeDocument(d)).toContain('f2-> a2-> \\bar "||"');
    d = setBarlineType(d, ms[3], "single");
    expect(serializeDocument(d)).toContain("bes,4 bes,4 bes,4 r4 |");
    d = deleteBarline(doc, ms[3]);
    expect(serializeDocument(d)).toContain("bes,4 bes,4 bes,4 r4 \\repeat percent 2");
  });

  it("deletes and inserts whole measures", () => {
    let d = normalizeDocument(deleteMeasure(doc, ms[2]));
    expect(serializeDocument(d)).not.toContain("f4 r4 f,2->");
    expect(buildMeasures(d.tokens)).toHaveLength(ms.length - 1);
    // percent repeat measure: the wrapper goes too
    d = deleteMeasure(doc, ms[4]);
    expect(serializeDocument(d)).not.toContain("\\repeat percent");
    expect(serializeDocument(d)).toContain('\\bar ".|:"\n    \\set Timing.measureLength = #(ly:make-moment 3/4)');
    // insert an empty 2/2 measure after measure 2 and before measure 1
    d = normalizeDocument(insertEmptyMeasure(doc, ms[1], "after"));
    expect(serializeDocument(d)).toContain("f2-> a2-> |\n    r1 |\n    f4 r4 f,2-> |");
    expect(buildMeasures(d.tokens)).toHaveLength(ms.length + 1);
    d = normalizeDocument(insertEmptyMeasure(doc, ms[0], "before"));
    expect(serializeDocument(d)).toContain(
      "\\time 2/2\n    r1 |\n    \\set Timing.measureLength = #(ly:make-moment 3/4) \\markErr bes,2->\\f d4-> \\unmarkErr |",
    );
  });

  it("sets and removes key signatures", () => {
    let d = setKeySignature(doc, ms[1], "es");
    expect(serializeDocument(d)).toContain(
      "\n    \\key es \\major \\set Timing.measureLength = #(ly:make-moment 1/1) f2-> a2-> |",
    );
    expect(buildMeasures(d.tokens)[1].keyName).toBe("es");
    // existing key is replaced, and can be removed
    d = setKeySignature(doc, ms[7], "f");
    expect(serializeDocument(d)).toContain('8 \\key f \\major es4\\f');
    d = setKeySignature(doc, ms[7], null);
    expect(serializeDocument(d)).not.toContain("\\key es \\major");
    // percent measure: key goes before the repeat
    d = setKeySignature(doc, ms[4], "g");
    expect(serializeDocument(d)).toContain("\\key g \\major \\repeat percent 2 { c4 r4 f4 r4 } |");
  });

  it("sets a key for a range and restores the old key afterwards", () => {
    // measures 1–3 → g major; measure 4 keeps b-flat major (restored), the Trio's
    // own key change at measure 8 stays untouched
    const d = setKeyForRange(doc, ms, 1, 3, "g");
    const code = serializeDocument(d);
    expect(code).toContain("\\key g \\major \\set Timing.measureLength = #(ly:make-moment 1/1) f2-> a2-> |");
    expect(code).toContain("\\key bes \\major \\repeat percent 2 { c4 r4 f4 r4 } |");
    expect(code).toContain('8 \\key es \\major es4');
    const after = buildMeasures(d.tokens);
    expect(after.slice(1, 4).map((m) => m.keyName)).toEqual(["g", "g", "g"]);
    expect(after[4].keyName).toBe("bes");
    // a range that swallows an existing change removes it
    const d2 = setKeyForRange(doc, ms, 6, 9, "f");
    expect(serializeDocument(d2)).not.toContain("8 \\key es \\major"); // Trio change swallowed
    const ms2 = buildMeasures(d2.tokens);
    expect(ms2.slice(6, 10).map((m) => m.keyName)).toEqual(["f", "f", "f", "f"]);
    expect(ms2[10].showKey).toBe(true); // restored after the range
    expect(ms2[10].keyName).toBe("es");
  });

  it("wraps, changes and unwraps percent repeats", () => {
    let d = setPercentCount(doc, ms[1], 2);
    expect(serializeDocument(d)).toContain("\\repeat percent 2 { f2-> a2-> } |");
    expect(buildMeasures(d.tokens)[1].percent).toBe(2);
    d = setPercentCount(d, buildMeasures(d.tokens)[1], 3);
    expect(serializeDocument(d)).toContain("\\repeat percent 3 { f2-> a2-> } |");
    d = setPercentCount(d, buildMeasures(d.tokens)[1], 1);
    expect(serializeDocument(d)).toContain("#(ly:make-moment 1/1) f2-> a2-> |");
    expect(serializeDocument(d)).not.toContain("percent 3");
    expect(buildMeasures(d.tokens)[1].percent).toBeNull();
  });

  it("drops percent repeats that lost all their events", () => {
    const idx = ms[4].events; // c4 r4 f4 r4 inside \repeat percent 2 { }
    let d = doc;
    for (const i of [...idx].reverse()) d = deleteEvent(d, i);
    const code = serializeDocument(normalizeDocument(d));
    expect(code).not.toContain("\\repeat percent");
    // the measure stays as an empty measure, the invalid wrapper is gone
    const after = buildMeasures(normalizeDocument(d).tokens);
    expect(after).toHaveLength(ms.length);
    expect(after[4].events).toHaveLength(0);
    expect(after[4].percent).toBeNull();
  });

  it("normalizes percent repeats, multi-measure rests and leftovers", () => {
    const src = String.raw`\score { \new Staff {
    \time 2/2 c1 |
    \set Timing.measureLength = #(ly:make-moment 5/4) \repeat percent 4 { \markErr c4 d4 e4 f4 \unmarkErr } |
    \set Timing.measureLength = #(ly:make-moment 1/8) \markErr \unmarkErr
    \set Timing.measureLength = #(ly:make-moment 1/1) \repeat percent 2 { g4 r4 a4 r4 } |
    R1*3 |
    \repeat percent 2 { c2 } |
    c1 |
  } }`;
    const d = normalizeDocument(parseLilypond(src));
    const code = serializeDocument(d);
    // stale 5/4 and the error marking are gone: the body is a full 2/2 measure
    expect(code).toContain("\n    \\repeat percent 4 { c4 d4 e4 f4 } |");
    // the leftover of a deleted measure disappears, the following measure needs no set
    expect(code).toContain("\n    \\repeat percent 2 { g4 r4 a4 r4 } |");
    expect(code).not.toContain("1/8");
    // multi-measure rest: explicit length, no error marking
    expect(code).toContain("\\set Timing.measureLength = #(ly:make-moment 3/1) R1*3 |");
    // short percent body: length before the wrapper, marking inside it
    expect(code).toContain(
      "\\set Timing.measureLength = #(ly:make-moment 1/2) \\repeat percent 2 { \\markErr c2 \\unmarkErr } |",
    );
    expect(code).toContain("\\set Timing.measureLength = #(ly:make-moment 1/1) c1 |\n  } }");
  });

  it("handles ties and hairpin spans", () => {
    const toks = tokenize("c4~ c4 d4\\< e4 f4\\! g4\\> a4\\f");
    expect(toks[0].suffix).toBe("~");
    expect(eventDecorations(toks[0]).tie).toBe(true);
    expect(findHairpins(toks)).toEqual([
      { start: 2, end: 4, kind: "cresc" },
      { start: 5, end: 6, kind: "decresc" },
    ]);
    // range operations on the sample
    const a = ms[2].events[0]; // f4
    const b = ms[3].events[1]; // bes,4 (second)
    let d = placeHairpin(doc, a, b, "cresc");
    expect(serializeDocument(d)).toContain("f4\\< r4 f,2-> |\n    bes,4 bes,4\\! bes,4 r4");
    d = removeHairpin(d, a, b);
    expect(serializeDocument(d)).toContain("f4 r4 f,2-> |\n    bes,4 bes,4 bes,4 r4");
    // end on a note with a dynamic gets no \\!
    d = placeHairpin(doc, ms[6].events[0], ms[7].events[0], "decresc"); // ... es4\\f
    expect(serializeDocument(d)).toContain("r4\\f\\> bes,4-> bes,2-> |");
    expect(serializeDocument(d)).toContain("es4\\f r4 es4 r4 |");
    // ties
    d = toggleTie(doc, ms[1].events[0]);
    expect(serializeDocument(d)).toContain("f2->~ a2-> |");
    d = toggleTie(d, ms[1].events[0]);
    expect(serializeDocument(d)).toContain("f2-> a2-> |");
  });

  it("removes spacers that lost their marks", () => {
    const start = ms[5].events[1]; // bes,4 after <>\\>
    const end = ms[5].events[4]; // <>\\!
    const d = normalizeDocument(removeHairpin(setHairpin(doc, ms[5].events[0], null), start, end));
    expect(serializeDocument(d)).toContain("\\markErr bes,4 r4 f4 \\unmarkErr |");
    expect(serializeDocument(d)).not.toContain("<>");
  });

  it("knows when a tie is valid and handles slurs", () => {
    const toks = tokenize("f2~ f4 g4( a4 b4) c4");
    expect(tieAllowed(toks, 0)).toBe(true); // f2 → f4
    expect(tieAllowed(toks, 1)).toBe(false); // f4 → g4
    expect(findSlurs(toks)).toEqual([{ start: 2, end: 4 }]);
    // sample: bes,4 bes,4 in measure 4 can be tied, f4 → r4 cannot
    expect(tieAllowed(doc.tokens, ms[3].events[0])).toBe(true);
    expect(tieAllowed(doc.tokens, ms[2].events[0])).toBe(false);
    let d = placeSlur(doc, ms[2].events[0], ms[2].events[2]);
    expect(serializeDocument(d)).toContain("f4( r4 f,2->) |");
    d = removeSlur(d, ms[2].events[0], ms[2].events[2]);
    expect(serializeDocument(d)).toContain("f4 r4 f,2-> |");
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
