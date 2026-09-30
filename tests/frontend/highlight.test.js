import { describe, it, expect } from "vitest";
import {
  highlightParts,
  displayNrParts,
  snippetParts,
  searchHint,
} from "../../src/frontend/src/lib/highlight.js";

const marked = (parts) => parts.filter((p) => p.match).map((p) => p.text);
const joined = (parts) => parts.map((p) => p.text).join("");

describe("highlightParts", () => {
  it("marks every hit case-insensitively and keeps the text", () => {
    const parts = highlightParts("Markus und markus", "MARKUS");
    expect(marked(parts)).toEqual(["Markus", "markus"]);
    expect(joined(parts)).toBe("Markus und markus");
  });

  it("marks every search word and treats words literally", () => {
    expect(marked(highlightParts("Anna Maier", "maier anna"))).toEqual(["Anna", "Maier"]);
    expect(marked(highlightParts("a.b axb", "a.b"))).toEqual(["a.b"]);
    expect(marked(highlightParts("Tuba", ""))).toEqual([]);
  });
});

describe("displayNrParts", () => {
  it("marks the whole number when typed as 'tu 2'", () => {
    expect(marked(displayNrParts("TU-002", "tu 2"))).toEqual(["TU-002"]);
    expect(marked(displayNrParts("TU-002", "TU2"))).toEqual(["TU-002"]);
    expect(marked(displayNrParts("TU-012", "tu 2"))).toEqual([]);
    expect(marked(displayNrParts("TU-0002", "tu 2"))).toEqual(["TU-0002"]);
    expect(marked(displayNrParts("TU-0002", "TU-002"))).toEqual(["TU-0002"]);
  });
});

describe("snippetParts", () => {
  it("cuts an excerpt around the first hit on one line", () => {
    const text = `${"Vorher ".repeat(20)}\n'Lackinger Markus' als Spieler${" danach".repeat(20)}`;
    const parts = snippetParts(text, "markus");
    expect(marked(parts)).toEqual(["Markus"]);
    const excerpt = joined(parts);
    expect(excerpt.startsWith("…")).toBe(true);
    expect(excerpt.endsWith("…")).toBe(true);
    expect(excerpt).not.toContain("\n");
    expect(excerpt.length).toBeLessThan(70);
  });

  it("is null without a hit", () => {
    expect(snippetParts("nichts", "markus")).toBeNull();
    expect(snippetParts(null, "markus")).toBeNull();
  });
});

describe("searchHint", () => {
  const row = {
    display_nr: "TR-006",
    label: "Trompete YTR-935",
    manufacturer: "Yamaha",
    borrower: "Luisa Auinger",
    notes: "Belegliste nennt 'Lackinger Markus' als Spieler",
  };

  it("names a hidden field the row was found in", () => {
    const hint = searchHint(row, "markus", ["display_nr", "manufacturer", "borrower"]);
    expect(hint.label).toBe("Notizen");
    expect(marked(hint.parts)).toEqual(["Markus"]);
    expect(searchHint(row, "ytr", ["display_nr", "manufacturer"]).label).toBe("Bezeichnung");
  });

  it("is null when a visible field or the number shows the hit", () => {
    expect(searchHint(row, "yamaha", ["manufacturer"])).toBeNull();
    expect(searchHint(row, "tr 6", ["display_nr"])).toBeNull();
    expect(searchHint(row, "", ["label"])).toBeNull();
  });
});

describe("tolerant matching (like the backend's fold())", () => {
  it("folds case, umlauts, ue-spellings and ß", async () => {
    const { fold, searchWords } = await import("../../src/frontend/src/lib/highlight.js");
    expect(fold("MÜLLER")).toBe("muller");
    expect(fold("Mueller")).toBe("muller");
    expect(fold("Straße")).toBe("strasse");
    expect(fold("Crème")).toBe("creme");
    expect(searchWords("  Trompete YAMAHA trompete ")).toEqual(["trompete", "yamaha"]);
  });

  it("marks the original characters, also when spellings differ in length", () => {
    expect(marked(highlightParts("Jürgen Müller", "mueller"))).toEqual(["Müller"]);
    expect(marked(highlightParts("Josef Mueller", "müller"))).toEqual(["Mueller"]);
    expect(marked(highlightParts("FLÜGELHORN", "flügel"))).toEqual(["FLÜGEL"]);
    expect(marked(highlightParts("Große Trommel", "grosse"))).toEqual(["Große"]);
    expect(joined(highlightParts("Jürgen Müller", "mueller"))).toBe("Jürgen Müller");
  });

  it("merges overlapping hits of several words", () => {
    expect(marked(highlightParts("Trompetenkoffer", "trompete kofFer"))).toEqual(["Trompetenkoffer".slice(0, 8), "koffer"]);
    expect(marked(highlightParts("abc", "ab bc"))).toEqual(["abc"]);
  });

  it("hints at the hidden field of a word no visible field shows", () => {
    const row = { display_nr: "TR-0006", label: "Trompete", manufacturer: "Yamaha", notes: "Spieler Lackinger Markus" };
    const hint = searchHint(row, "yamaha markus", ["display_nr", "manufacturer"]);
    expect(hint.label).toBe("Notizen");
    expect(marked(hint.parts)).toEqual(["Markus"]);
    expect(searchHint(row, "yamaha", ["manufacturer"])).toBeNull();
  });
});
