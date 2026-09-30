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

  it("treats the term literally and as a whole", () => {
    expect(marked(highlightParts("Anna Maier", "anna maier"))).toEqual(["Anna Maier"]);
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
